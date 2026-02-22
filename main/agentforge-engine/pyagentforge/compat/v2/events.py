"""
Events 兼容层

将旧的 pyagentforge.core.events 导入重定向到新位置
"""

# 从新位置导入
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

# 注意: 不再发出弃用警告，因为 core/events.py 已经有警告了
