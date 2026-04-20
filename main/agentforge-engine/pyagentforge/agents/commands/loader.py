"""
命令加载器

扫描和加载命令目录
"""

import asyncio
from pathlib import Path
from typing import Any

from pyagentforge.agents.commands.models import Command
from pyagentforge.agents.commands.parser import CommandParser, CommandParseError, DynamicCommandExecutor
from pyagentforge.config.settings import get_settings
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CommandLoader:
    """命令加载器 - 扫描目录并加载所有命令"""

    def __init__(
        self,
        commands_dir: Path | None = None,
        parser: CommandParser | None = None,
        dynamic_executor: DynamicCommandExecutor | None = None,
    ) -> None:
        """
        初始化命令加载器

        Args:
            commands_dir: 命令目录
            parser: 命令解析器
            dynamic_executor: 动态命令执行器
        """
        settings = get_settings()
        self.commands_dir = commands_dir or settings.commands_dir
        self.dynamic_executor = dynamic_executor or DynamicCommandExecutor(
            working_dir=self.commands_dir.parent if self.commands_dir else Path.cwd(),
        )
        self.parser = parser or CommandParser(dynamic_executor=self.dynamic_executor)
        self.commands: dict[str, Command] = {}
        self._load_errors: dict[str, str] = {}

    def load_all(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """
        加载所有命令

        Args:
            inject_dynamic: 是否注入动态命令

        Returns:
            命令名称到命令对象的映射
        """
        if not self.commands_dir.exists():
            logger.warning(
                "Commands directory does not exist",
                extra_data={"path": str(self.commands_dir)},
            )
            return {}

        logger.info(
            "Loading commands from directory",
            extra_data={"path": str(self.commands_dir)},
        )

        self.commands.clear()
        self._load_errors.clear()

        # 遍历命令文件
        for command_file in self.commands_dir.glob("*.md"):
            try:
                command = self.parser.parse_file(command_file, inject_dynamic=inject_dynamic)
                self.commands[command.name] = command

                # 注册别名
                for alias in command.metadata.alias:
                    if alias not in self.commands:
                        self.commands[alias] = command

                logger.debug(
                    "Loaded command",
                    extra_data={"name": command.name, "path": str(command_file)},
                )
            except CommandParseError as e:
                self._load_errors[str(command_file)] = str(e)
                logger.error(
                    "Failed to load command",
                    extra_data={"path": str(command_file), "error": str(e)},
                )

        logger.info(
            "Commands loaded",
            extra_data={
                "count": len(set(c.name for c in self.commands.values())),
                "aliases": len(self.commands) - len(set(c.name for c in self.commands.values())),
                "errors": len(self._load_errors),
            },
        )

        return self.commands

    async def load_all_async(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """
        异步加载所有命令 (支持并行解析)

        Args:
            inject_dynamic: 是否注入动态命令

        Returns:
            命令名称到命令对象的映射
        """
        if not self.commands_dir.exists():
            logger.warning(
                "Commands directory does not exist",
                extra_data={"path": str(self.commands_dir)},
            )
            return {}

        logger.info(
            "Loading commands asynchronously",
            extra_data={"path": str(self.commands_dir)},
        )

        self.commands.clear()
        self._load_errors.clear()

        # 收集所有命令文件
        command_files = list(self.commands_dir.glob("*.md"))
        if not command_files:
            return {}

        # 并行解析所有命令
        async def parse_file_safe(file_path: Path) -> Command | None:
            try:
                content = file_path.read_text(encoding="utf-8")
                return await self.parser.parse_async(content, file_path, inject_dynamic)
            except CommandParseError as e:
                self._load_errors[str(file_path)] = str(e)
                logger.error(
                    "Failed to load command",
                    extra_data={"path": str(file_path), "error": str(e)},
                )
                return None

        commands = await asyncio.gather(*[parse_file_safe(f) for f in command_files])

        # 注册命令和别名
        for command in commands:
            if command is None:
                continue

            self.commands[command.name] = command
            for alias in command.metadata.alias:
                if alias not in self.commands:
                    self.commands[alias] = command

        logger.info(
            "Commands loaded asynchronously",
            extra_data={
                "count": len(set(c.name for c in self.commands.values())),
                "errors": len(self._load_errors),
            },
        )

        return self.commands

    def get(self, name: str) -> Command | None:
        """
        获取命令

        Args:
            name: 命令名称 (可以有或没有 / 前缀)

        Returns:
            命令对象或 None
        """
        # 移除 / 前缀
        if name.startswith("/"):
            name = name[1:]
        return self.commands.get(name)

    def get_command_content(self, name: str, inject_dynamic: bool = False) -> str:
        """
        获取命令内容 (用于注入到上下文)

        Args:
            name: 命令名称
            inject_dynamic: 是否重新注入动态命令

        Returns:
            命令完整内容
        """
        command = self.get(name)
        if command is None:
            return f"Error: Command '/{name}' not found"

        body = command.body

        # 如果需要，重新注入动态命令
        if inject_dynamic:
            body = self.dynamic_executor.inject(body)

        return f'<command name="/{command.name}">\n{body}\n</command>'

    def get_descriptions(self) -> str:
        """
        获取所有命令的描述 (用于系统提示词)

        Returns:
            命令描述列表
        """
        if not self.commands:
            return "No commands available."

        # 去重 (因为别名会创建重复条目)
        unique_commands = {c.name: c for c in self.commands.values()}

        lines = ["Available commands:"]
        for command in sorted(unique_commands.values(), key=lambda c: c.name):
            lines.append(command.get_description_for_prompt())

        return "\n".join(lines)

    def get_command_names(self) -> list[str]:
        """
        获取所有命令名称 (不含别名)

        Returns:
            命令名称列表
        """
        return list({c.name for c in self.commands.values()})

    def get_aliases(self) -> dict[str, str]:
        """
        获取别名到命令名称的映射

        Returns:
            别名到命令名称的映射
        """
        result = {}
        for name, command in self.commands.items():
            if name != command.name:
                result[name] = command.name
        return result

    def match_command(self, text: str) -> Command | None:
        """
        从文本中匹配命令

        Args:
            text: 用户输入文本 (如 "/commit" 或 "commit the changes")

        Returns:
            匹配的命令或 None
        """
        text = text.strip()

        # 直接匹配 /command 格式
        if text.startswith("/"):
            return self.get(text.split()[0])

        # 尝试匹配第一个单词
        first_word = text.split()[0] if text.split() else ""
        return self.get(first_word)

    def get_load_errors(self) -> dict[str, str]:
        """获取加载错误"""
        return self._load_errors.copy()

    def reload(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """重新加载所有命令"""
        return self.load_all(inject_dynamic=inject_dynamic)

    async def reload_async(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """异步重新加载所有命令"""
        return await self.load_all_async(inject_dynamic=inject_dynamic)

    def __len__(self) -> int:
        return len({c.name for c in self.commands.values()})

    def __contains__(self, name: str) -> bool:
        return self.get(name) is not None

    def __iter__(self):
        # 迭代唯一命令
        return iter({c.name: c for c in self.commands.values()}.items())
