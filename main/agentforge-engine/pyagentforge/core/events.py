"""
事件总线系统 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.plugins.integration.events.events
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.events import EventBus, EventType
- 新: from pyagentforge.plugins.integration.events.events import EventBus, EventType
"""

# 重导出所有内容
from pyagentforge.plugins.integration.events.events import (
    EventType,
    Event,
    EventHandler,
    EventBus,
    SyncCallback,
    AsyncCallback,
    Callback,
    get_event_bus,
    create_event_bus,
)

__all__ = [
    "EventType",
    "Event",
    "EventHandler",
    "EventBus",
    "SyncCallback",
    "AsyncCallback",
    "Callback",
    "get_event_bus",
    "create_event_bus",
]

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.events is deprecated. "
    "Use pyagentforge.plugins.integration.events.events instead.",
    DeprecationWarning,
    stacklevel=2,
)
