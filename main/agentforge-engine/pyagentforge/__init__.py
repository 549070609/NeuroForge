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

# ============================================================================
# Factory functions (v2.0 - 新架构)
# ============================================================================
from typing import Any, Dict, Optional
import logging


async def create_engine(
    model_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    plugin_config: Optional[PluginConfig] = None,
    working_dir: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    **kwargs,
) -> AgentEngine:
    """
    创建配置好的 AgentEngine

    Args:
        model_id: 模型 ID，未传时自动解析默认模型
        config: Agent 配置
        plugin_config: 插件配置
        working_dir: 工作目录
        llm_client: LLM 客户端（可选，用于测试）
        **kwargs: 其他参数

    Returns:
        配置好的 AgentEngine

    Example:
        >>> engine = await create_engine(
        ...     model_id="claude-sonnet-4",
        ...     config={"system_prompt": "You are a helpful assistant."},
        ... )
    """
    resolved_model_id = model_id or _resolve_default_model_id()
    tool_registry = ToolRegistry()
    register_core_tools(tool_registry, working_dir=working_dir)

    agent_config = AgentConfig(**config) if config else AgentConfig()

    engine = AgentEngine(
        model_id=resolved_model_id,
        tool_registry=tool_registry,
        config=agent_config,
        llm_client=llm_client,
        **kwargs,
    )

    if plugin_config:
        plugin_manager = PluginManager(engine=engine)
        await plugin_manager.initialize(
            plugin_config.to_dict(),
            working_dir=working_dir,
        )
        engine.plugin_manager = plugin_manager

        for tool in plugin_manager.get_tools_from_plugins():
            tool_registry.register(tool)

    return engine


def create_minimal_engine(
    model_id: Optional[str] = None,
    working_dir: Optional[str] = None,
    llm_client: Optional[LLMClient] = None,
    **kwargs,
) -> AgentEngine:
    """
    创建最小化引擎（无插件）

    Args:
        model_id: 模型 ID
        working_dir: 工作目录
        llm_client: LLM 客户端（可选）
        **kwargs: 其他参数

    Returns:
        最小化 AgentEngine
    """
    resolved_model_id = model_id or _resolve_default_model_id()
    tool_registry = ToolRegistry()
    register_core_tools(tool_registry, working_dir=working_dir)

    return AgentEngine(
        model_id=resolved_model_id,
        tool_registry=tool_registry,
        llm_client=llm_client,
        **kwargs,
    )


def _resolve_default_model_id() -> str:
    registry = get_registry()
    models = registry.get_all_models()
    if models:
        return models[0].id
    return "default"


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
    # Factory (v2.0)
    "create_engine",
    "create_minimal_engine",
]
