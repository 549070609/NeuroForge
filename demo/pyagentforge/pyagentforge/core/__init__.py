"""
核心引擎模块 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.kernel 和 pyagentforge.plugins
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 核心组件: from pyagentforge.kernel import AgentEngine, ContextManager, ...
- 思考功能: from pyagentforge.plugins.middleware.thinking.thinking import ...
- 事件总线: from pyagentforge.plugins.integration.events.events import ...
- 并行执行: from pyagentforge.plugins.integration.parallel_executor.executor import ...
- 故障转移: from pyagentforge.plugins.middleware.failover.failover import ...
- 持久化: from pyagentforge.plugins.integration.persistence.persistence import ...
- 上下文感知: from pyagentforge.plugins.integration.context_aware.prompt_manager import ...
"""

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core is deprecated. "
    "Use pyagentforge.kernel or pyagentforge.plugins.* instead.",
    DeprecationWarning,
    stacklevel=2,
)

# 从 kernel 重导出核心组件
from pyagentforge.kernel import (
    # 消息类型
    Message,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ProviderResponse,
    # 核心组件
    AgentEngine,
    ContextManager,
    ToolExecutor,
    ToolRegistry,
    PermissionChecker,
    BaseTool,
    BaseProvider,
    # 模型注册
    ModelRegistry,
    ModelConfig,
    ProviderType,
    ProviderInfo,
    get_registry,
    register_model,
    get_model,
    register_provider,
)

# 从 plugins 重导出扩展功能
from pyagentforge.plugins.middleware.thinking.thinking import (
    ThinkingLevel,
    ThinkingConfig,
    ThinkingBlock,
    THINKING_CAPABLE_MODELS,
    supports_thinking,
    get_thinking_provider,
    get_max_thinking_tokens,
    create_thinking_config,
)

from pyagentforge.plugins.integration.events.events import (
    EventType,
    Event,
    EventHandler,
    EventBus,
    get_event_bus,
    create_event_bus,
)

from pyagentforge.plugins.integration.parallel_executor.executor import (
    SubagentStatus,
    SubagentTask,
    SubagentResult,
    AGENT_TYPES,
    get_agent_type_config,
    ParallelSubagentExecutor,
    ParallelTaskTool,
)

from pyagentforge.plugins.middleware.failover.failover import (
    FailoverCondition,
    LoadBalanceStrategy,
    ProviderHealth,
    FailoverConfig,
    ProviderPool,
    create_provider_pool_from_config,
)

from pyagentforge.plugins.integration.persistence.persistence import (
    SessionMetadata,
    SessionState,
    SessionSummary,
    SessionSnapshot,
    SessionPersistence,
    SessionManager,
)

from pyagentforge.plugins.integration.context_aware.prompt_manager import (
    AgentsMdLoader,
    DynamicPromptInjector,
    ContextAwarePromptManager,
)

# 上下文压缩 (保持原位置)
from pyagentforge.core.compaction import (
    Compactor,
    CompactionSettings,
    CompactionResult,
)

__all__ = [
    # 核心组件 (from kernel)
    "AgentEngine",
    "ContextManager",
    "ToolExecutor",
    "ToolRegistry",
    "PermissionChecker",
    "BaseTool",
    "BaseProvider",
    # 消息类型
    "Message",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ProviderResponse",
    # 模型注册
    "ModelRegistry",
    "ModelConfig",
    "ProviderType",
    "ProviderInfo",
    "get_registry",
    "register_model",
    "get_model",
    "register_provider",
    # 思考级别控制
    "ThinkingLevel",
    "ThinkingConfig",
    "ThinkingBlock",
    "THINKING_CAPABLE_MODELS",
    "supports_thinking",
    "get_thinking_provider",
    "get_max_thinking_tokens",
    "create_thinking_config",
    # 事件总线
    "EventBus",
    "Event",
    "EventType",
    "EventHandler",
    "get_event_bus",
    "create_event_bus",
    # 并行执行
    "ParallelSubagentExecutor",
    "SubagentTask",
    "SubagentResult",
    "SubagentStatus",
    "ParallelTaskTool",
    "AGENT_TYPES",
    "get_agent_type_config",
    # 上下文压缩
    "Compactor",
    "CompactionSettings",
    "CompactionResult",
    # 上下文感知提示
    "AgentsMdLoader",
    "DynamicPromptInjector",
    "ContextAwarePromptManager",
    # Provider 故障转移
    "ProviderPool",
    "FailoverConfig",
    "FailoverCondition",
    "LoadBalanceStrategy",
    "ProviderHealth",
    "create_provider_pool_from_config",
    # 会话持久化
    "SessionPersistence",
    "SessionManager",
    "SessionMetadata",
    "SessionState",
    "SessionSummary",
    "SessionSnapshot",
]
