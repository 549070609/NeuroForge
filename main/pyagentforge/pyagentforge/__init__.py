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
    # Core components
    AgentEngine,
    ContextManager,
    ToolExecutor,
    ToolRegistry,
    # Message types
    Message,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ProviderResponse,
    # Base classes
    BaseTool,
    BaseProvider,
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
    from pyagentforge.kernel.engine import AgentConfig
    from pyagentforge.kernel.core_tools import register_core_tools

    # 创建工具注册表并注册核心工具
    tool_registry = ToolRegistry()
    register_core_tools(tool_registry, working_dir=working_dir)

    # 创建 Agent 配置
    agent_config = AgentConfig(**config) if config else AgentConfig()

    # 创建引擎
    engine = AgentEngine(
        provider=provider,
        tool_registry=tool_registry,
        config=agent_config,
        **kwargs,
    )

    # 如果有插件配置，初始化插件系统
    if plugin_config:
        plugin_manager = PluginManager(engine=engine)
        await plugin_manager.initialize(
            plugin_config.to_dict(),
            working_dir=working_dir,
        )
        engine.plugin_manager = plugin_manager

        # 注册插件提供的工具
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
    from pyagentforge.kernel.core_tools import register_core_tools

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
    "ContextManager",
    "ToolExecutor",
    "ToolRegistry",
    "Message",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ProviderResponse",
    "BaseTool",
    "BaseProvider",
    # Plugin (v2.0)
    "Plugin",
    "PluginMetadata",
    "PluginContext",
    "PluginType",
    "PluginManager",
    "HookType",
    # Config (v2.0)
    "PluginConfig",
    # Factory (v2.0)
    "create_engine",
    "create_minimal_engine",
]
