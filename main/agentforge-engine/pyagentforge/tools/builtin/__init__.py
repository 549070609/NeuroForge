"""内置工具模块"""

# P0 核心工具
from pyagentforge.tools.builtin.apply_patch import ApplyPatchTool, DiffTool
from pyagentforge.tools.builtin.bash import BashTool
from pyagentforge.tools.builtin.batch import BatchTool

# P1 重要工具
from pyagentforge.tools.builtin.codesearch import CodeSearchTool
from pyagentforge.tools.builtin.edit import EditTool
from pyagentforge.tools.builtin.external_directory import ExternalDirectoryTool, WorkspaceTool
from pyagentforge.tools.builtin.glob import GlobTool
from pyagentforge.tools.builtin.grep import GrepTool
from pyagentforge.tools.builtin.invalid import InvalidTool, ToolSuggestionTool
from pyagentforge.tools.builtin.ls import LsTool
from pyagentforge.tools.builtin.lsp import LSPTool
from pyagentforge.tools.builtin.multiedit import MultiEditTool
from pyagentforge.tools.builtin.plan import PlanEnterTool, PlanExitTool, PlanTool
from pyagentforge.tools.builtin.question import ConfirmTool, QuestionTool
from pyagentforge.tools.builtin.read import ReadTool
from pyagentforge.tools.builtin.task import TaskTool
from pyagentforge.tools.builtin.todo import TodoReadTool, TodoWriteTool

# P2 可选工具
from pyagentforge.tools.builtin.truncation import ContextCompactTool, TruncationTool

# 扩展工具
from pyagentforge.tools.builtin.webfetch import WebFetchTool
from pyagentforge.tools.builtin.websearch import WebSearchTool
from pyagentforge.tools.builtin.write import WriteTool

__all__ = [
    # P0 核心工具
    "BashTool",
    "ReadTool",
    "WriteTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "LsTool",
    "LSPTool",
    "QuestionTool",
    "ConfirmTool",
    # P1 重要工具
    "CodeSearchTool",
    "ApplyPatchTool",
    "DiffTool",
    "PlanTool",
    "PlanEnterTool",
    "PlanExitTool",
    # P2 可选工具
    "TruncationTool",
    "ContextCompactTool",
    "InvalidTool",
    "ToolSuggestionTool",
    "ExternalDirectoryTool",
    "WorkspaceTool",
    # 扩展工具
    "WebFetchTool",
    "WebSearchTool",
    "TodoWriteTool",
    "TodoReadTool",
    "MultiEditTool",
    "BatchTool",
    "TaskTool",
    # Registration helper
    "register_core_tools",
]


def register_core_tools(registry, working_dir: str | None = None) -> None:
    """Register the six canonical built-in tools into a ToolRegistry.

    Args:
        registry: Target ToolRegistry instance.
        working_dir: Optional working directory handed to ``BashTool``.
    """
    registry.register(BashTool(working_dir=working_dir))
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
