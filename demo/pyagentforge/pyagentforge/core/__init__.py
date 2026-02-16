"""
核心引擎模块

包含 Agent 执行循环、上下文管理、消息类型、事件总线、并行执行等核心组件
"""

from pyagentforge.core.engine import AgentEngine
from pyagentforge.core.context import ContextManager
from pyagentforge.core.message import Message, TextBlock, ToolUseBlock, ToolResultBlock
from pyagentforge.core.executor import ToolExecutor
from pyagentforge.core.events import EventBus, Event, EventType, get_event_bus, create_event_bus
from pyagentforge.core.parallel import (
    ParallelSubagentExecutor,
    SubagentTask,
    SubagentResult,
    SubagentStatus,
    ParallelTaskTool,
)
from pyagentforge.core.compaction import (
    Compactor,
    CompactionSettings,
    CompactionResult,
)
from pyagentforge.core.thinking import (
    ThinkingLevel,
    ThinkingConfig,
    ThinkingBlock,
    supports_thinking,
    create_thinking_config,
)
from pyagentforge.core.model_registry import (
    ModelRegistry,
    ModelConfig,
    ProviderType,
    get_registry,
    register_model,
    get_model,
    register_provider,
)
from pyagentforge.core.context_aware import (
    AgentsMdLoader,
    DynamicPromptInjector,
    ContextAwarePromptManager,
)
from pyagentforge.core.failover import (
    ProviderPool,
    FailoverConfig,
    FailoverCondition,
    LoadBalanceStrategy,
    ProviderHealth,
    create_provider_pool_from_config,
)
from pyagentforge.core.persistence import (
    SessionPersistence,
    SessionManager,
    SessionMetadata,
    SessionState,
    SessionSummary,
    SessionSnapshot,
)

__all__ = [
    # 引擎和上下文
    "AgentEngine",
    "ContextManager",
    # 消息类型
    "Message",
    "TextBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ToolExecutor",
    # 事件总线
    "EventBus",
    "Event",
    "EventType",
    "get_event_bus",
    "create_event_bus",
    # 并行执行
    "ParallelSubagentExecutor",
    "SubagentTask",
    "SubagentResult",
    "SubagentStatus",
    "ParallelTaskTool",
    # 上下文压缩
    "Compactor",
    "CompactionSettings",
    "CompactionResult",
    # 思考级别控制
    "ThinkingLevel",
    "ThinkingConfig",
    "ThinkingBlock",
    "supports_thinking",
    "create_thinking_config",
    # 模型注册
    "ModelRegistry",
    "ModelConfig",
    "ProviderType",
    "get_registry",
    "register_model",
    "get_model",
    "register_provider",
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
