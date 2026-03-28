"""
PyAgentForge - 通用型 AI Agent 服务底座

核心理念: 模型即代理，代码即配置

v3.0.0: 四层架构重构 + Channel 系统 + Automation + Telemetry
v4.0.0: Provider 统一化重构 - 移除所有 Provider，使用 LLMClient 统一接口
"""

__version__ = "4.0.0"
__author__ = "PyAgentForge Team"

# ============================================================================
# v4.0 新增：统一 LLM 客户端
# ============================================================================
from pyagentforge.client import LLMClient

# ============================================================================
# Kernel exports (v2.0 - 新架构)
# ============================================================================
from pyagentforge.kernel import (
    AgentEngine,
    ContextManager,
    ToolExecutor,
    ToolRegistry,
    Message,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
    ProviderResponse,
    BaseTool,
)

# ============================================================================
# AgentConfig — 直接从 kernel.engine 导出（Service 层高频使用）
# ============================================================================
from pyagentforge.kernel.engine import AgentConfig

# ============================================================================
# 工具注册工具函数
# ============================================================================
from pyagentforge.kernel.core_tools import (
    register_core_tools,
    BashTool,
    ReadTool,
    WriteTool,
    EditTool,
    GlobTool,
    GrepTool,
)

# ============================================================================
# 内置工具类（全量导出，Service 层按需使用）
# ============================================================================
from pyagentforge.tools.builtin import (
    LsTool,
    LSPTool,
    QuestionTool,
    ConfirmTool,
    CodeSearchTool,
    ApplyPatchTool,
    DiffTool,
    PlanTool,
    PlanEnterTool,
    PlanExitTool,
    TruncationTool,
    ContextCompactTool,
    InvalidTool,
    ToolSuggestionTool,
    ExternalDirectoryTool,
    WorkspaceTool,
    WebFetchTool,
    WebSearchTool,
    TodoWriteTool,
    TodoReadTool,
    MultiEditTool,
    BatchTool,
    TaskTool,
)

# ============================================================================
# Plugin system exports (v2.0 - 新架构)
# ============================================================================
from pyagentforge.plugin import (
    Plugin,
    PluginMetadata,
    PluginContext,
    PluginType,
    PluginManager,
    HookType,
)

# ============================================================================
# Configuration (v2.0 - 新架构)
# ============================================================================
from pyagentforge.config.plugin_config import PluginConfig

# ============================================================================
# 模型注册（ModelRegistry, ModelConfig）
# ============================================================================
from pyagentforge.kernel.model_registry import (
    ModelRegistry,
    ModelConfig,
    get_registry,
    register_model,
    get_model,
)

# ============================================================================
# 权限检查（PermissionChecker — Service 层 permission_bridge 使用）
# ============================================================================
from pyagentforge.kernel.executor import PermissionChecker

# ============================================================================
# Checkpoint 系统
# ============================================================================
from pyagentforge.kernel.checkpoint import (
    BaseCheckpointer,
    Checkpoint,
    FileCheckpointer,
    MemoryCheckpointer,
)

# ============================================================================
# Workflow 编排系统
# ============================================================================
from pyagentforge.workflow import (
    WorkflowGraph,
    WorkflowExecutor,
    WorkflowResult,
    StepNode,
    StepTrace,
    EngineFactory,
    END as WORKFLOW_END,
)

# ============================================================================
# 配置管理
# ============================================================================
from pyagentforge.config.settings import get_settings as get_engine_settings
from pyagentforge.core.background_manager import BackgroundManager
from pyagentforge.core.concurrency_manager import ConcurrencyConfig, ConcurrencyManager

__all__ = [
    # Version
    "__version__",
    # v4.0 新增：统一 LLM 客户端
    "LLMClient",
    # Kernel (v2.0)
    "AgentEngine",
    "AgentConfig",
    "ContextManager",
    "ToolExecutor",
    "ToolRegistry",
    "Message",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ThinkingBlock",
    "ProviderResponse",
    "BaseTool",
    # 核心工具类
    "BashTool",
    "ReadTool",
    "WriteTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "register_core_tools",
    # 内置工具类
    "LsTool",
    "LSPTool",
    "QuestionTool",
    "ConfirmTool",
    "CodeSearchTool",
    "ApplyPatchTool",
    "DiffTool",
    "PlanTool",
    "PlanEnterTool",
    "PlanExitTool",
    "TruncationTool",
    "ContextCompactTool",
    "InvalidTool",
    "ToolSuggestionTool",
    "ExternalDirectoryTool",
    "WorkspaceTool",
    "WebFetchTool",
    "WebSearchTool",
    "TodoWriteTool",
    "TodoReadTool",
    "MultiEditTool",
    "BatchTool",
    "TaskTool",
    # Plugin (v2.0)
    "Plugin",
    "PluginMetadata",
    "PluginContext",
    "PluginType",
    "PluginManager",
    "HookType",
    # Config (v2.0)
    "PluginConfig",
    # 模型注册
    "ModelRegistry",
    "ModelConfig",
    "get_registry",
    "register_model",
    "get_model",
    # 权限检查
    "PermissionChecker",
    # 配置
    "get_engine_settings",
    # Runtime managers
    "BackgroundManager",
    "ConcurrencyConfig",
    "ConcurrencyManager",
    # Checkpoint
    "BaseCheckpointer",
    "Checkpoint",
    "FileCheckpointer",
    "MemoryCheckpointer",
    # Workflow
    "WorkflowGraph",
    "WorkflowExecutor",
    "WorkflowResult",
    "StepNode",
    "StepTrace",
    "EngineFactory",
    "WORKFLOW_END",
]
