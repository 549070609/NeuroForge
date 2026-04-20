"""
命令系统

提供用户自定义命令和动态命令注入功能
"""

from pyagentforge.agents.commands.models import Command, CommandMetadata
from pyagentforge.agents.commands.parser import (
    CommandParseError,
    CommandParser,
    DynamicCommandExecutor,
)
from pyagentforge.agents.commands.loader import CommandLoader
from pyagentforge.agents.commands.registry import CommandRegistry, get_command_registry
from pyagentforge.agents.commands.tool import CommandTool, ListCommandsTool

__all__ = [
    # 模型
    "Command",
    "CommandMetadata",
    # 解析器
    "CommandParser",
    "CommandParseError",
    "DynamicCommandExecutor",
    # 加载器
    "CommandLoader",
    # 注册表
    "CommandRegistry",
    "get_command_registry",
    # 工具
    "CommandTool",
    "ListCommandsTool",
]
