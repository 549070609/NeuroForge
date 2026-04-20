"""
命令解析器

解析 COMMAND.md 文件，支持动态命令注入 (!`cmd`)
"""

import asyncio
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from pyagentforge.agents.commands.models import Command, CommandMetadata
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CommandParseError(Exception):
    """命令解析错误"""
    pass


class DynamicCommandExecutor:
    """动态命令执行器 - 在提示词中执行 shell 命令"""

    # 匹配 !`cmd` 或 !`cmd args` 格式
    DYNAMIC_COMMAND_PATTERN = re.compile(r"!\`([^`]+)\`")

    def __init__(
        self,
        timeout: int = 10,
        allowed_commands: list[str] | None = None,
        blocked_commands: list[str] | None = None,
        working_dir: Path | None = None,
    ) -> None:
        """
        初始化动态命令执行器

        Args:
            timeout: 命令执行超时时间 (秒)
            allowed_commands: 允许的命令列表 (None 表示允许所有)
            blocked_commands: 禁止的命令列表
            working_dir: 工作目录
        """
        self.timeout = timeout
        self.allowed_commands = allowed_commands
        self.blocked_commands = blocked_commands or [
            "rm -rf /",
            "mkfs",
            "dd if=/dev/zero",
            ":(){:|:&};:",  # Fork bomb
        ]
        self.working_dir = working_dir or Path.cwd()

    def _is_command_allowed(self, command: str) -> tuple[bool, str]:
        """
        检查命令是否被允许

        Returns:
            (是否允许, 原因)
        """
        # 检查禁止的命令
        for blocked in self.blocked_commands:
            if blocked in command:
                return False, f"Command contains blocked pattern: {blocked}"

        # 检查允许列表
        if self.allowed_commands is not None:
            cmd_base = command.split()[0] if command.split() else ""
            if cmd_base not in self.allowed_commands:
                return False, f"Command not in allowed list: {cmd_base}"

        return True, ""

    def execute(self, command: str) -> str:
        """
        执行命令并返回输出

        Args:
            command: 要执行的命令

        Returns:
            命令输出 (stdout 或错误信息)
        """
        # 安全检查
        allowed, reason = self._is_command_allowed(command)
        if not allowed:
            logger.warning(
                "Blocked dynamic command",
                extra_data={"command": command, "reason": reason},
            )
            return f"[Blocked: {reason}]"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=self.working_dir,
            )

            if result.returncode != 0:
                # 命令失败，返回 stderr
                error_output = result.stderr.strip() or f"Exit code: {result.returncode}"
                logger.debug(
                    "Dynamic command failed",
                    extra_data={"command": command, "error": error_output},
                )
                return f"[Error: {error_output}]"

            output = result.stdout.strip()
            logger.debug(
                "Dynamic command executed",
                extra_data={"command": command, "output_length": len(output)},
            )
            return output

        except subprocess.TimeoutExpired:
            logger.warning(
                "Dynamic command timed out",
                extra_data={"command": command, "timeout": self.timeout},
            )
            return f"[Timeout after {self.timeout}s]"

        except Exception as e:
            logger.error(
                "Dynamic command error",
                extra_data={"command": command, "error": str(e)},
            )
            return f"[Error: {e}]"

    async def execute_async(self, command: str) -> str:
        """异步执行命令"""
        # 在事件循环中运行同步代码
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute, command)

    def inject(self, content: str) -> str:
        """
        在内容中注入动态命令输出

        Args:
            content: 包含 !`cmd` 格式的内容

        Returns:
            替换后的内容
        """
        def replace_command(match: re.Match) -> str:
            command = match.group(1).strip()
            return self.execute(command)

        return self.DYNAMIC_COMMAND_PATTERN.sub(replace_command, content)

    async def inject_async(self, content: str) -> str:
        """
        异步在内容中注入动态命令输出

        对于多个命令，会并行执行以提高效率
        """
        # 找到所有需要执行的命令
        matches = list(self.DYNAMIC_COMMAND_PATTERN.finditer(content))
        if not matches:
            return content

        # 并行执行所有命令
        commands = [m.group(1).strip() for m in matches]
        results = await asyncio.gather(*[self.execute_async(cmd) for cmd in commands])

        # 替换内容
        result_content = content
        for match, output in zip(matches, results):
            result_content = result_content.replace(match.group(0), output, 1)

        return result_content


class CommandParser:
    """命令解析器 - 解析 YAML frontmatter + Markdown 格式"""

    # 匹配 YAML frontmatter
    FRONTMATTER_PATTERN = re.compile(
        r"^---\s*\n(.*?)\n---\s*\n(.*)$",
        re.DOTALL,
    )

    def __init__(
        self,
        dynamic_executor: DynamicCommandExecutor | None = None,
        enable_dynamic_injection: bool = True,
    ) -> None:
        """
        初始化命令解析器

        Args:
            dynamic_executor: 动态命令执行器 (None 则使用默认配置)
            enable_dynamic_injection: 是否启用动态命令注入
        """
        self.dynamic_executor = dynamic_executor or DynamicCommandExecutor()
        self.enable_dynamic_injection = enable_dynamic_injection

    def parse(
        self,
        content: str,
        path: Path | None = None,
        inject_dynamic: bool | None = None,
    ) -> Command:
        """
        解析命令文件内容

        Args:
            content: 文件内容
            path: 文件路径
            inject_dynamic: 是否注入动态命令 (None 使用默认设置)

        Returns:
            命令对象

        Raises:
            CommandParseError: 解析错误
        """
        match = self.FRONTMATTER_PATTERN.match(content)

        if not match:
            # 没有 frontmatter，整个内容作为 body
            logger.warning(
                "No frontmatter found, using entire content as body",
                extra_data={"path": str(path) if path else "unknown"},
            )
            body = content.strip()
            metadata = CommandMetadata(
                name=path.stem if path else "unknown",
                description="No description",
            )
        else:
            frontmatter_str = match.group(1)
            body = match.group(2).strip()

            try:
                metadata_dict = yaml.safe_load(frontmatter_str)
            except yaml.YAMLError as e:
                raise CommandParseError(f"Invalid YAML frontmatter: {e}") from e

            if not isinstance(metadata_dict, dict):
                raise CommandParseError("Frontmatter must be a YAML mapping")

            # 提取必需字段
            name = metadata_dict.pop("name", path.stem if path else "unknown")
            description = metadata_dict.pop("description", "")

            # 构建 metadata
            metadata = CommandMetadata(
                name=name,
                description=description,
                **{
                    k: v
                    for k, v in metadata_dict.items()
                    if k in CommandMetadata.model_fields
                },
            )

        # 动态命令注入
        should_inject = inject_dynamic if inject_dynamic is not None else self.enable_dynamic_injection
        if should_inject:
            body = self.dynamic_executor.inject(body)

        logger.debug(
            "Parsed command",
            extra_data={"name": metadata.name, "path": str(path) if path else "unknown"},
        )

        return Command(metadata=metadata, body=body, path=path)

    def parse_file(
        self,
        file_path: Path,
        inject_dynamic: bool | None = None,
    ) -> Command:
        """
        解析命令文件

        Args:
            file_path: 文件路径
            inject_dynamic: 是否注入动态命令

        Returns:
            命令对象
        """
        if not file_path.exists():
            raise CommandParseError(f"Command file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return self.parse(content, file_path, inject_dynamic)

    async def parse_async(
        self,
        content: str,
        path: Path | None = None,
        inject_dynamic: bool | None = None,
    ) -> Command:
        """
        异步解析命令 (支持并行执行多个动态命令)

        Args:
            content: 文件内容
            path: 文件路径
            inject_dynamic: 是否注入动态命令

        Returns:
            命令对象
        """
        match = self.FRONTMATTER_PATTERN.match(content)

        if not match:
            body = content.strip()
            metadata = CommandMetadata(
                name=path.stem if path else "unknown",
                description="No description",
            )
        else:
            frontmatter_str = match.group(1)
            body = match.group(2).strip()

            try:
                metadata_dict = yaml.safe_load(frontmatter_str)
            except yaml.YAMLError as e:
                raise CommandParseError(f"Invalid YAML frontmatter: {e}") from e

            if not isinstance(metadata_dict, dict):
                raise CommandParseError("Frontmatter must be a YAML mapping")

            name = metadata_dict.pop("name", path.stem if path else "unknown")
            description = metadata_dict.pop("description", "")

            metadata = CommandMetadata(
                name=name,
                description=description,
                **{
                    k: v
                    for k, v in metadata_dict.items()
                    if k in CommandMetadata.model_fields
                },
            )

        # 异步动态命令注入
        should_inject = inject_dynamic if inject_dynamic is not None else self.enable_dynamic_injection
        if should_inject:
            body = await self.dynamic_executor.inject_async(body)

        return Command(metadata=metadata, body=body, path=path)

    def validate(self, command: Command) -> list[str]:
        """
        验证命令

        Args:
            command: 命令对象

        Returns:
            验证错误列表 (空列表表示通过)
        """
        errors: list[str] = []

        if not command.metadata.name:
            errors.append("Command name is required")

        if not command.metadata.description:
            errors.append("Command description is required")

        if not command.body:
            errors.append("Command body is empty")

        # 检查命令名称格式
        if command.metadata.name.startswith("/"):
            errors.append("Command name should not start with /")

        # 检查别名是否与名称重复
        if command.metadata.name in command.metadata.alias:
            errors.append(f"Command alias cannot be the same as name: {command.metadata.name}")

        return errors
