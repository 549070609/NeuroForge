"""
命令注册表

管理命令的注册、查找和执行
"""

from pathlib import Path
from typing import Any, Callable

from pyagentforge.commands.loader import CommandLoader
from pyagentforge.commands.models import Command
from pyagentforge.commands.parser import CommandParser, CommandParseError, DynamicCommandExecutor
from pyagentforge.config.settings import get_settings
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CommandRegistry:
    """命令注册表 - 统一管理所有命令"""

    _instance: "CommandRegistry | None" = None

    def __init__(
        self,
        loader: CommandLoader | None = None,
        auto_load: bool = False,
    ) -> None:
        """
        初始化命令注册表

        Args:
            loader: 命令加载器
            auto_load: 是否自动加载命令
        """
        self.loader = loader or CommandLoader()
        self._handlers: dict[str, Callable] = {}
        self._pre_hooks: list[Callable] = []
        self._post_hooks: list[Callable] = []

        if auto_load:
            self.load_commands()

    @classmethod
    def get_instance(cls) -> "CommandRegistry":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(auto_load=True)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例实例"""
        cls._instance = None

    # ==================== 命令加载 ====================

    def load_commands(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """加载所有命令"""
        return self.loader.load_all(inject_dynamic=inject_dynamic)

    async def load_commands_async(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """异步加载所有命令"""
        return await self.loader.load_all_async(inject_dynamic=inject_dynamic)

    def reload_commands(self, inject_dynamic: bool = True) -> dict[str, Command]:
        """重新加载所有命令"""
        return self.loader.reload(inject_dynamic=inject_dynamic)

    # ==================== 命令注册 ====================

    def register(
        self,
        name: str,
        description: str,
        body: str,
        **metadata_kwargs: Any,
    ) -> Command:
        """
        编程式注册命令

        Args:
            name: 命令名称
            description: 命令描述
            body: 命令内容
            **metadata_kwargs: 其他元数据

        Returns:
            注册的命令对象
        """
        from pyagentforge.commands.models import CommandMetadata

        metadata = CommandMetadata(
            name=name,
            description=description,
            **metadata_kwargs,
        )
        command = Command(metadata=metadata, body=body)
        self.loader.commands[name] = command

        logger.debug(
            "Registered command programmatically",
            extra_data={"name": name},
        )

        return command

    def register_handler(self, name: str, handler: Callable) -> None:
        """
        注册命令处理器 (用于自定义执行逻辑)

        Args:
            name: 命令名称
            handler: 处理函数
        """
        self._handlers[name] = handler
        logger.debug(
            "Registered command handler",
            extra_data={"name": name},
        )

    def unregister(self, name: str) -> bool:
        """
        注销命令

        Args:
            name: 命令名称

        Returns:
            是否成功注销
        """
        if name in self.loader.commands:
            del self.loader.commands[name]
            if name in self._handlers:
                del self._handlers[name]
            return True
        return False

    # ==================== 命令查询 ====================

    def get(self, name: str) -> Command | None:
        """获取命令"""
        return self.loader.get(name)

    def get_command_content(self, name: str, inject_dynamic: bool = False) -> str:
        """获取命令内容"""
        return self.loader.get_command_content(name, inject_dynamic=inject_dynamic)

    def get_all_commands(self) -> list[Command]:
        """获取所有命令 (不含重复)"""
        return list({c.name: c for c in self.loader.commands.values()}.values())

    def get_command_names(self) -> list[str]:
        """获取所有命令名称"""
        return self.loader.get_command_names()

    def get_descriptions(self) -> str:
        """获取命令描述列表"""
        return self.loader.get_descriptions()

    def has_command(self, name: str) -> bool:
        """检查命令是否存在"""
        return name in self.loader

    # ==================== 命令执行 ====================

    def get_prompt_for_command(
        self,
        name: str,
        user_input: str = "",
        inject_dynamic: bool = True,
    ) -> str:
        """
        获取命令的完整提示词

        Args:
            name: 命令名称
            user_input: 用户附加输入
            inject_dynamic: 是否注入动态命令

        Returns:
            完整提示词
        """
        command = self.get(name)
        if command is None:
            return f"Error: Command '/{name}' not found"

        body = command.body

        # 动态命令注入
        if inject_dynamic:
            body = self.loader.dynamic_executor.inject(body)

        # 构建完整提示词
        prompt_parts = [body]

        if user_input:
            prompt_parts.append(f"\n\n## User Input\n{user_input}")

        return "\n".join(prompt_parts)

    async def get_prompt_for_command_async(
        self,
        name: str,
        user_input: str = "",
        inject_dynamic: bool = True,
    ) -> str:
        """异步获取命令的完整提示词"""
        command = self.get(name)
        if command is None:
            return f"Error: Command '/{name}' not found"

        body = command.body

        if inject_dynamic:
            body = await self.loader.dynamic_executor.inject_async(body)

        prompt_parts = [body]

        if user_input:
            prompt_parts.append(f"\n\n## User Input\n{user_input}")

        return "\n".join(prompt_parts)

    # ==================== 钩子系统 ====================

    def add_pre_hook(self, hook: Callable) -> None:
        """添加前置钩子"""
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: Callable) -> None:
        """添加后置钩子"""
        self._post_hooks.append(hook)

    def _run_pre_hooks(self, command_name: str, user_input: str) -> None:
        """运行前置钩子"""
        for hook in self._pre_hooks:
            try:
                hook(command_name, user_input)
            except Exception as e:
                logger.error(
                    "Pre-hook error",
                    extra_data={"hook": str(hook), "error": str(e)},
                )

    def _run_post_hooks(self, command_name: str, result: str) -> None:
        """运行后置钩子"""
        for hook in self._post_hooks:
            try:
                hook(command_name, result)
            except Exception as e:
                logger.error(
                    "Post-hook error",
                    extra_data={"hook": str(hook), "error": str(e)},
                )

    # ==================== 工具方法 ====================

    def create_dynamic_executor(self, working_dir: Path | None = None) -> DynamicCommandExecutor:
        """创建动态命令执行器"""
        return DynamicCommandExecutor(working_dir=working_dir or Path.cwd())

    def __len__(self) -> int:
        return len(self.loader)

    def __contains__(self, name: str) -> bool:
        return name in self.loader

    def __repr__(self) -> str:
        return f"CommandRegistry(commands={len(self)})"


# 便捷函数
def get_command_registry() -> CommandRegistry:
    """获取命令注册表单例"""
    return CommandRegistry.get_instance()
