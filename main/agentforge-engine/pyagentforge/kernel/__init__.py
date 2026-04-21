"""
PyAgentForge Kernel

核心模块 - 包含 Agent 执行的最小可用组件
"""

from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.checkpoint import (
    BaseCheckpointer,
    Checkpoint,
    FileCheckpointer,
    MemoryCheckpointer,
)
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentEngine
from pyagentforge.kernel.errors import (
    AgentCancelledError,
    AgentError,
    AgentMaxIterationsError,
    AgentProviderError,
    AgentTimeoutError,
    AgentToolError,
)
from pyagentforge.kernel.executor import PermissionChecker, ToolExecutor, ToolRegistry
from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from pyagentforge.kernel.model_registry import (
    ModelConfig,
    ModelRegistry,
    get_model,
    get_registry,
    register_model,
)

# BaseTool canonical path is pyagentforge.tools.base; re-export here for
# backward compatibility with `from pyagentforge.kernel import BaseTool`.
from pyagentforge.tools.base import BaseTool

__all__ = [
    "Message",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ThinkingBlock",
    "ProviderResponse",
    "BaseTool",
    "BaseProvider",
    "ContextManager",
    "ToolExecutor",
    "ToolRegistry",
    "PermissionChecker",
    "AgentEngine",
    "AgentError",
    "AgentTimeoutError",
    "AgentCancelledError",
    "AgentMaxIterationsError",
    "AgentProviderError",
    "AgentToolError",
    "ModelRegistry",
    "ModelConfig",
    "get_registry",
    "register_model",
    "get_model",
    "BaseCheckpointer",
    "Checkpoint",
    "FileCheckpointer",
    "MemoryCheckpointer",
]
