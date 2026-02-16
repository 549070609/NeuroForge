"""
命令系统

提供用户自定义命令和动态命令注入功能
"""

from pyagentforge.commands.models import Command, CommandMetadata
from pyagentforge.commands.parser import (
    CommandParseError,
    CommandParser,
    DynamicCommandExecutor,
)
from pyagentforge.commands.loader import CommandLoader
from pyagentforge.commands.registry import CommandRegistry, get_command_registry
from pyagentforge.commands.tool import CommandTool, ListCommandsTool

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
