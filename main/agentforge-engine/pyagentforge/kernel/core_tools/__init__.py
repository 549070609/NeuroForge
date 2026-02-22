"""
核心工具包

包含 Agent 执行所需的最小工具集
"""

from pyagentforge.kernel.core_tools.bash import BashTool
from pyagentforge.kernel.core_tools.read import ReadTool
from pyagentforge.kernel.core_tools.write import WriteTool
from pyagentforge.kernel.core_tools.edit import EditTool
from pyagentforge.kernel.core_tools.glob import GlobTool
from pyagentforge.kernel.core_tools.grep import GrepTool

__all__ = [
    "BashTool",
    "ReadTool",
    "WriteTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "register_core_tools",
]


def register_core_tools(registry, working_dir: str | None = None) -> None:
    """
    注册所有核心工具到注册表

    Args:
        registry: ToolRegistry 实例
        working_dir: 工具的工作目录
    """
    registry.register(BashTool(working_dir=working_dir))
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
