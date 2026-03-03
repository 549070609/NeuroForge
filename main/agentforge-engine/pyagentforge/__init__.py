"""
PyAgentForge - 通用型 AI Agent 服务底座

核心理念: 模型即代理，代码即配置

v3.0.0: 四层架构重构 + Channel 系统 + Automation + Telemetry
"""

__version__ = "3.0.0"
__author__ = "PyAgentForge Team"

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
    BaseProvider,
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
# Provider 工厂 & Provider 实现类
# ============================================================================
from pyagentforge.providers.factory import create_provider, create_provider_from_config
from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.providers.openai_provider import OpenAIProvider
from pyagentforge.providers.google_provider import GoogleProvider

# ============================================================================
# 模型注册（ModelRegistry, ModelConfig, ProviderType）
# ============================================================================
from pyagentforge.kernel.model_registry import (
    ModelRegistry,
    ModelConfig,
    ProviderType,
    get_registry,
    register_model,
    register_provider,
    get_model,
)

# ============================================================================
# 权限检查（PermissionChecker — Service 层 permission_bridge 使用）
# ============================================================================
from pyagentforge.kernel.executor import PermissionChecker

# ============================================================================
# 国产 LLM 注册中心
# ============================================================================
from pyagentforge.providers.llm.registry import ChineseLLMRegistry

# ============================================================================
# 配置管理
# ============================================================================
from pyagentforge.config.settings import get_settings as get_engine_settings

# ============================================================================
# Factory functions (v2.0 - 新架构)
# ============================================================================
from typing import Any, Dict, Optional
import logging


async def create_engine(
    provider: BaseProvider,
    config: Optional[Dict[str, Any]] = None,
    plugin_config: Optional[PluginConfig] = None,
    working_dir: Optional[str] = None,
    **kwargs,
) -> AgentEngine:
    """
    创建配置好的 AgentEngine

    Args:
        provider: LLM 提供商
        config: Agent 配置
        plugin_config: 插件配置
        working_dir: 工作目录
        **kwargs: 其他参数

    Returns:
        配置好的 AgentEngine
    """
    tool_registry = ToolRegistry()
    register_core_tools(tool_registry, working_dir=working_dir)

    agent_config = AgentConfig(**config) if config else AgentConfig()

    engine = AgentEngine(
        provider=provider,
        tool_registry=tool_registry,
        config=agent_config,
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
    provider: BaseProvider,
    working_dir: Optional[str] = None,
    **kwargs,
) -> AgentEngine:
    """
    创建最小化引擎（无插件）

    Args:
        provider: LLM 提供商
        working_dir: 工作目录
        **kwargs: 其他参数

    Returns:
        最小化 AgentEngine
    """
    tool_registry = ToolRegistry()
    register_core_tools(tool_registry, working_dir=working_dir)

    return AgentEngine(
        provider=provider,
        tool_registry=tool_registry,
        **kwargs,
    )


__all__ = [
    # Version
    "__version__",
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
    "BaseProvider",
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
    # Provider 工厂与实现
    "create_provider",
    "create_provider_from_config",
    "AnthropicProvider",
    "OpenAIProvider",
    "GoogleProvider",
    # 模型注册
    "ModelRegistry",
    "ModelConfig",
    "ProviderType",
    "get_registry",
    "register_model",
    "register_provider",
    "get_model",
    # 权限检查
    "PermissionChecker",
    # 国产 LLM
    "ChineseLLMRegistry",
    # 配置
    "get_engine_settings",
    # Factory (v2.0)
    "create_engine",
    "create_minimal_engine",
]
