"""
AGENTS.md 自动加载机制

根据文件路径自动加载上下文相关的提示词
"""

import re
from pathlib import Path
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class AgentsMdLoader:
    """
    AGENTS.md 自动加载器

    根据当前操作的文件路径，自动加载对应目录层级中的 AGENTS.md 文件
    """

    def __init__(
        self,
        workspace: Path | str,
        filename: str = "AGENTS.md",
    ) -> None:
        """
        初始化加载器

        Args:
            workspace: 工作空间根目录
            filename: 提示文件名，默认为 AGENTS.md
        """
        self.workspace = Path(workspace).resolve()
        self.filename = filename
        self._cache: dict[str, str] = {}

    def load_for_path(self, file_path: Path | str) -> str:
        """
        为指定文件路径加载所有相关的 AGENTS.md

        按目录层级从根到叶子加载，后面的覆盖前面的

        Args:
            file_path: 目标文件路径

        Returns:
            合并后的提示词
        """
        file_path = Path(file_path).resolve()

        # 确保文件在工作空间内
        try:
            relative = file_path.relative_to(self.workspace)
        except ValueError:
            logger.warning(
                "File outside workspace",
                extra_data={"file": str(file_path), "workspace": str(self.workspace)},
            )
            return ""

        # 构建目录层级
        dirs_to_check = [self.workspace]

        for parent in relative.parents:
            if parent != Path("."):
                dirs_to_check.append(self.workspace / parent)

        # 如果是文件，添加文件所在目录
        if file_path.is_file():
            dirs_to_check.append(file_path.parent)

        # 加载并合并
        prompts: list[str] = []

        for dir_path in dirs_to_check:
            agents_file = dir_path / self.filename
            content = self._load_file(agents_file)
            if content:
                prompts.append(content)
                logger.debug(
                    "Loaded AGENTS.md",
                    extra_data={"path": str(agents_file)},
                )

        if not prompts:
            return ""

        # 合并提示词
        combined = "\n\n---\n\n".join(prompts)

        logger.info(
            "Loaded AGENTS.md files",
            extra_data={"count": len(prompts), "target": str(file_path)},
        )

        return combined

    def _load_file(self, file_path: Path) -> str:
        """
        加载单个文件（带缓存）

        Args:
            file_path: 文件路径

        Returns:
            文件内容或空字符串
        """
        cache_key = str(file_path)

        if cache_key in self._cache:
            return self._cache[cache_key]

        if not file_path.exists():
            self._cache[cache_key] = ""
            return ""

        try:
            content = file_path.read_text(encoding="utf-8")
            self._cache[cache_key] = content
            return content
        except Exception as e:
            logger.warning(
                "Failed to load AGENTS.md",
                extra_data={"path": str(file_path), "error": str(e)},
            )
            self._cache[cache_key] = ""
            return ""

    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()

    def get_all_agents_files(self) -> list[Path]:
        """
        获取工作空间中所有的 AGENTS.md 文件

        Returns:
            文件路径列表
        """
        files = list(self.workspace.rglob(self.filename))
        return sorted(files)


class DynamicPromptInjector:
    """
    动态提示注入器

    支持 !`command` 语法在提示词中执行命令
    """

    # 匹配 !`command` 或 !`(command)`
    INJECTION_PATTERN = re.compile(r"!\`([^`]+)\`")

    def __init__(
        self,
        workspace: Path | str,
        timeout: int = 10,
    ) -> None:
        """
        初始化注入器

        Args:
            workspace: 工作空间目录
            timeout: 命令执行超时时间（秒）
        """
        self.workspace = Path(workspace).resolve()
        self.timeout = timeout

    async def inject(self, prompt: str) -> str:
        """
        处理提示词中的动态命令注入

        Args:
            prompt: 原始提示词

        Returns:
            处理后的提示词
        """
        import asyncio

        def replace_command(match: re.Match) -> str:
            command = match.group(1)
            try:
                # 同步执行命令
                import subprocess

                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.workspace,
                )

                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    logger.warning(
                        "Command failed",
                        extra_data={"command": command, "error": result.stderr},
                    )
                    return f"[Error: {result.stderr.strip()}]"

            except subprocess.TimeoutExpired:
                return f"[Timeout after {self.timeout}s]"
            except Exception as e:
                logger.error(
                    "Command execution error",
                    extra_data={"command": command, "error": str(e)},
                )
                return f"[Error: {str(e)}]"

        # 替换所有匹配项
        result = self.INJECTION_PATTERN.sub(replace_command, prompt)
        return result

    def inject_sync(self, prompt: str) -> str:
        """
        同步版本的动态命令注入

        Args:
            prompt: 原始提示词

        Returns:
            处理后的提示词
        """
        import subprocess

        def replace_command(match: re.Match) -> str:
            command = match.group(1)
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.workspace,
                )

                if result.returncode == 0:
                    return result.stdout.strip()
                else:
                    logger.warning(
                        "Command failed",
                        extra_data={"command": command, "error": result.stderr},
                    )
                    return f"[Error: {result.stderr.strip()}]"

            except subprocess.TimeoutExpired:
                return f"[Timeout after {self.timeout}s]"
            except Exception as e:
                logger.error(
                    "Command execution error",
                    extra_data={"command": command, "error": str(e)},
                )
                return f"[Error: {str(e)}]"

        return self.INJECTION_PATTERN.sub(replace_command, prompt)


class ContextAwarePromptManager:
    """
    上下文感知提示词管理器

    整合 AGENTS.md 加载和动态命令注入
    """

    def __init__(
        self,
        workspace: Path | str,
        enable_agents_md: bool = True,
        enable_dynamic_injection: bool = True,
        injection_timeout: int = 10,
    ) -> None:
        """
        初始化管理器

        Args:
            workspace: 工作空间目录
            enable_agents_md: 是否启用 AGENTS.md 自动加载
            enable_dynamic_injection: 是否启用动态命令注入
            injection_timeout: 命令执行超时
        """
        self.workspace = Path(workspace).resolve()
        self.enable_agents_md = enable_agents_md
        self.enable_dynamic_injection = enable_dynamic_injection

        self.agents_loader = AgentsMdLoader(workspace) if enable_agents_md else None
        self.dynamic_injector = (
            DynamicPromptInjector(workspace, injection_timeout)
            if enable_dynamic_injection
            else None
        )

    def build_system_prompt(
        self,
        base_prompt: str,
        current_file: Path | str | None = None,
    ) -> str:
        """
        构建完整的系统提示词

        Args:
            base_prompt: 基础系统提示词
            current_file: 当前操作的文件路径

        Returns:
            完整的系统提示词
        """
        parts = [base_prompt]

        # 加载 AGENTS.md
        if self.agents_loader and current_file:
            agents_content = self.agents_loader.load_for_path(current_file)
            if agents_content:
                parts.append("\n\n## 项目上下文\n\n" + agents_content)

        # 合并
        combined = "\n".join(parts)

        # 动态注入
        if self.dynamic_injector:
            combined = self.dynamic_injector.inject_sync(combined)

        return combined

    async def build_system_prompt_async(
        self,
        base_prompt: str,
        current_file: Path | str | None = None,
    ) -> str:
        """
        异步构建完整的系统提示词

        Args:
            base_prompt: 基础系统提示词
            current_file: 当前操作的文件路径

        Returns:
            完整的系统提示词
        """
        parts = [base_prompt]

        # 加载 AGENTS.md
        if self.agents_loader and current_file:
            agents_content = self.agents_loader.load_for_path(current_file)
            if agents_content:
                parts.append("\n\n## 项目上下文\n\n" + agents_content)

        # 合并
        combined = "\n".join(parts)

        # 动态注入
        if self.dynamic_injector:
            combined = await self.dynamic_injector.inject(combined)

        return combined

    def load_agents_md(self) -> str:
        """加载根目录的 AGENTS.md"""
        if self.agents_loader:
            return self.agents_loader.load_for_path(self.workspace)
        return ""

    def get_relevant_context(self, query: str) -> str:
        """获取与查询相关的上下文（简化版）"""
        # 可以实现更智能的上下文检索
        return self.load_agents_md()

    def build_dynamic_prompt(self) -> str:
        """构建动态提示"""
        return self.load_agents_md()

    def refresh_cache(self) -> None:
        """刷新 AGENTS.md 缓存"""
        if self.agents_loader:
            self.agents_loader.clear_cache()
