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
# Configuration (v2.0 - 新架构)
# ============================================================================
from pyagentforge.config.plugin_config import PluginConfig

# ============================================================================
# 配置管理
# ============================================================================
from pyagentforge.config.settings import get_settings as get_engine_settings
from pyagentforge.kernel.background_manager import BackgroundManager
from pyagentforge.kernel.concurrency_manager import ConcurrencyConfig, ConcurrencyManager

# ============================================================================
# Kernel exports (v2.0 - 新架构)
# ============================================================================
from pyagentforge.kernel import (
    AgentEngine,
    BaseTool,
    ContextManager,
    Message,
    ProviderResponse,
    TextBlock,
    ThinkingBlock,
    ToolExecutor,
    ToolRegistry,
    ToolResultBlock,
    ToolUseBlock,
)

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
# AgentConfig — 直接从 kernel.engine 导出（Service 层高频使用）
# ============================================================================
from pyagentforge.kernel.engine import AgentConfig

# ============================================================================
# 权限检查（PermissionChecker — Service 层 permission_bridge 使用）
# ============================================================================
from pyagentforge.kernel.executor import PermissionChecker

# ============================================================================
# 模型注册（ModelRegistry, ModelConfig）
# ============================================================================
from pyagentforge.kernel.hooks import (
    HookContext,
    RequestInterceptor,
    RequestPayload,
    ResponseTransformer,
    StreamTransformer,
    clear_all_hooks,
    match_any,
    match_api_type,
    match_model_prefix,
    match_provider,
    register_request_interceptor,
    register_response_transformer,
    register_stream_transformer,
)
from pyagentforge.kernel.model_registry import (
    ModelConfig,
    ModelRegistry,
    get_model,
    get_registry,
    register_model,
)
from pyagentforge.protocols import (
    BaseProtocolAdapter,
    ProtocolAdapterRegistry,
    StreamEvent,
    get_protocol_adapter,
    register_protocol_adapter,
)

# ============================================================================
# Plugin system exports (v2.0 - 新架构)
# ============================================================================
from pyagentforge.plugin import (
    HookType,
    Plugin,
    PluginContext,
    PluginManager,
    PluginMetadata,
    PluginType,
)

# ============================================================================
# 内置工具类（全量导出，Service 层按需使用）
# ============================================================================
from pyagentforge.tools.builtin import (
    ApplyPatchTool,
    BashTool,
    BatchTool,
    CodeSearchTool,
    ConfirmTool,
    ContextCompactTool,
    DiffTool,
    EditTool,
    ExternalDirectoryTool,
    GlobTool,
    GrepTool,
    InvalidTool,
    LSPTool,
    LsTool,
    MultiEditTool,
    PlanEnterTool,
    PlanExitTool,
    PlanTool,
    QuestionTool,
    ReadTool,
    TaskTool,
    TodoReadTool,
    TodoWriteTool,
    ToolSuggestionTool,
    TruncationTool,
    WebFetchTool,
    WebSearchTool,
    WorkspaceTool,
    WriteTool,
    register_core_tools,
)
from pyagentforge.workflow import (
    END as WORKFLOW_END,
)

# ============================================================================
# Workflow 编排系统
# ============================================================================
from pyagentforge.workflow import (
    EngineFactory,
    StepNode,
    StepTrace,
    WorkflowExecutor,
    WorkflowGraph,
    WorkflowResult,
)

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
    # Hooks (LLM 请求/响应/流式扩展点)
    "HookContext",
    "RequestPayload",
    "RequestInterceptor",
    "ResponseTransformer",
    "StreamTransformer",
    "register_request_interceptor",
    "register_response_transformer",
    "register_stream_transformer",
    "clear_all_hooks",
    "match_any",
    "match_api_type",
    "match_model_prefix",
    "match_provider",
    # Protocol adapter registry
    "BaseProtocolAdapter",
    "ProtocolAdapterRegistry",
    "StreamEvent",
    "register_protocol_adapter",
    "get_protocol_adapter",
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
