"""
命令工具

提供 Command 工具，允许 Agent 执行用户自定义命令
"""

from pathlib import Path
from typing import Any

from pydantic import Field

from pyagentforge.commands.registry import get_command_registry, CommandRegistry
from pyagentforge.tools.base import BaseTool


class CommandTool(BaseTool):
    """
    命令工具 - 执行用户自定义命令

    用法: /command_name 或 command_name
    可以传递额外参数作为 user_input
    """

    name: str = "command"
    description: str = """Execute a user-defined command.

Usage: /command_name or command_name
The command system provides shortcuts for common tasks like:
- /commit - Git commit with auto-generated message
- /review - Code review
- /test - Run tests

Use 'list' as command name to see all available commands."""

    # 工具参数
    command_name: str = Field(
        ...,
        description="Command name to execute (with or without / prefix, or 'list' to show all)",
    )
    user_input: str = Field(
        default="",
        description="Additional input to pass to the command",
    )
    inject_dynamic: bool = Field(
        default=True,
        description="Whether to inject dynamic command output (!`cmd` syntax)",
    )

    # 注册表引用
    registry: CommandRegistry | None = Field(default=None, exclude=True)

    def __init__(self, registry: CommandRegistry | None = None, **data: Any) -> None:
        super().__init__(**data)
        self.registry = registry or get_command_registry()

    async def execute(self) -> str:
        """执行命令"""
        cmd_name = self.command_name.strip()

        # 列出所有命令
        if cmd_name.lower() == "list":
            return self._format_command_list()

        # 移除 / 前缀
        if cmd_name.startswith("/"):
            cmd_name = cmd_name[1:]

        # 检查命令是否存在
        if not self.registry.has_command(cmd_name):
            available = self.registry.get_command_names()
            return f"Error: Command '/{cmd_name}' not found.\nAvailable commands: {', '.join(available)}"

        # 获取命令提示词
        try:
            if self.inject_dynamic:
                prompt = await self.registry.get_prompt_for_command_async(
                    cmd_name,
                    self.user_input,
                    inject_dynamic=True,
                )
            else:
                prompt = self.registry.get_prompt_for_command(
                    cmd_name,
                    self.user_input,
                    inject_dynamic=False,
                )

            return f"[Command: /{cmd_name}]\n\n{prompt}"

        except Exception as e:
            return f"Error executing command '/{cmd_name}': {e}"

    def _format_command_list(self) -> str:
        """格式化命令列表"""
        commands = self.registry.get_all_commands()
        if not commands:
            return "No commands available. Create command files in the commands directory."

        lines = ["Available Commands:", ""]
        for cmd in sorted(commands, key=lambda c: c.name):
            aliases = f" (aliases: {', '.join(cmd.metadata.alias)})" if cmd.metadata.alias else ""
            lines.append(f"  /{cmd.name}: {cmd.metadata.description}{aliases}")

        return "\n".join(lines)


class ListCommandsTool(BaseTool):
    """列出所有可用命令"""

    name: str = "list_commands"
    description: str = "List all available user-defined commands."

    registry: CommandRegistry | None = Field(default=None, exclude=True)

    def __init__(self, registry: CommandRegistry | None = None, **data: Any) -> None:
        super().__init__(**data)
        self.registry = registry or get_command_registry()

    async def execute(self) -> str:
        """列出命令"""
        return self.registry.get_descriptions()


# 工具注册函数
def register_command_tools(registry: CommandRegistry | None = None) -> list[type[BaseTool]]:
    """
    注册命令相关工具

    Args:
        registry: 命令注册表

    Returns:
        工具类列表
    """
    return [
        lambda: CommandTool(registry=registry),
        lambda: ListCommandsTool(registry=registry),
    ]
