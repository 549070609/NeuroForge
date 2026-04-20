"""
事件总线系统

提供组件间解耦的事件发布订阅机制
"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class EventType(StrEnum):
    """事件类型"""

    # Agent 事件
    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_ERROR = "agent.error"

    # 工具事件
    TOOL_STARTED = "tool.started"
    TOOL_COMPLETED = "tool.completed"
    TOOL_ERROR = "tool.error"

    # 会话事件
    SESSION_CREATED = "session.created"
    SESSION_CLOSED = "session.closed"

    # 消息事件
    MESSAGE_RECEIVED = "message.received"
    MESSAGE_SENT = "message.sent"

    # 技能事件
    SKILL_LOADED = "skill.loaded"
    SKILL_UNLOADED = "skill.unloaded"

    # 子代理事件
    SUBAGENT_STARTED = "subagent.started"
    SUBAGENT_COMPLETED = "subagent.completed"

    # MCP 事件
    MCP_CONNECTED = "mcp.connected"
    MCP_DISCONNECTED = "mcp.disconnected"

    # 自定义事件
    CUSTOM = "custom"


@dataclass
class Event:
    """事件对象"""

    type: EventType | str
    data: dict[str, Any]
    source: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value if isinstance(self.type, EventType) else self.type,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# 回调类型
SyncCallback = Callable[[Event], None]
AsyncCallback = Callable[[Event], Coroutine[Any, Any, None]]
Callback = SyncCallback | AsyncCallback


class EventHandler:
    """事件处理器"""

    def __init__(
        self,
        callback: Callback,
        event_types: list[EventType | str] | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> None:
        """
        初始化事件处理器

        Args:
            callback: 回调函数
            event_types: 订阅的事件类型列表，None 表示所有类型
            priority: 优先级，数值越大越先执行
            once: 是否只执行一次
        """
        self.callback = callback
        self.event_types = set(event_types) if event_types else None
        self.priority = priority
        self.once = once
        self._call_count = 0

    def matches(self, event_type: EventType | str) -> bool:
        """检查是否匹配事件类型"""
        if self.event_types is None:
            return True
        return event_type in self.event_types

    async def execute(self, event: Event) -> None:
        """执行回调"""
        try:
            if asyncio.iscoroutinefunction(self.callback):
                await self.callback(event)
            else:
                self.callback(event)
            self._call_count += 1
        except Exception as e:
            logger.error(
                "Event handler error",
                extra_data={
                    "event_type": event.type,
                    "error": str(e),
                },
            )
            raise


class EventBus:
    """事件总线"""

    def __init__(self, name: str = "default") -> None:
        """
        初始化事件总线

        Args:
            name: 总线名称
        """
        self.name = name
        self._handlers: list[EventHandler] = []
        self._event_history: list[Event] = []
        self._max_history = 100
        self._lock = asyncio.Lock()

        # 统计
        self._stats = {
            "events_emitted": 0,
            "handlers_called": 0,
            "errors": 0,
        }

        logger.debug(
            "Event bus created",
            extra_data={"name": name},
        )

    def subscribe(
        self,
        callback: Callback,
        event_types: EventType | str | list[EventType | str] | None = None,
        priority: int = 0,
        once: bool = False,
    ) -> EventHandler:
        """
        订阅事件

        Args:
            callback: 回调函数
            event_types: 订阅的事件类型
            priority: 优先级
            once: 是否只执行一次

        Returns:
            EventHandler 实例
        """
        if isinstance(event_types, (EventType, str)):
            event_types = [event_types]

        handler = EventHandler(
            callback=callback,
            event_types=event_types,
            priority=priority,
            once=once,
        )
        self._handlers.append(handler)
        self._handlers.sort(key=lambda h: h.priority, reverse=True)

        logger.debug(
            "Event handler subscribed",
            extra_data={
                "event_types": [str(t) for t in event_types] if event_types else "all",
                "priority": priority,
            },
        )

        return handler

    def unsubscribe(self, handler: EventHandler) -> bool:
        """
        取消订阅

        Args:
            handler: 要移除的处理器

        Returns:
            是否成功移除
        """
        try:
            self._handlers.remove(handler)
            return True
        except ValueError:
            return False

    def on(
        self,
        event_types: EventType | str | list[EventType | str] | None = None,
        priority: int = 0,
    ) -> Callable[[Callback], Callback]:
        """
        装饰器方式订阅事件

        Args:
            event_types: 订阅的事件类型
            priority: 优先级

        Returns:
            装饰器
        """
        def decorator(func: Callback) -> Callback:
            self.subscribe(func, event_types, priority)
            return func

        return decorator

    def once(
        self,
        event_types: EventType | str | list[EventType | str] | None = None,
        priority: int = 0,
    ) -> Callable[[Callback], Callback]:
        """
        装饰器方式订阅一次性事件

        Args:
            event_types: 订阅的事件类型
            priority: 优先级

        Returns:
            装饰器
        """
        def decorator(func: Callback) -> Callback:
            self.subscribe(func, event_types, priority, once=True)
            return func

        return decorator

    async def emit(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        """
        发送事件

        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件来源
            metadata: 元数据

        Returns:
            Event 实例
        """
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
            metadata=metadata or {},
        )

        self._stats["events_emitted"] += 1

        # 记录历史
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # 执行处理器
        handlers_to_remove = []

        async with self._lock:
            for handler in self._handlers:
                if not handler.matches(event_type):
                    continue

                try:
                    await handler.execute(event)
                    self._stats["handlers_called"] += 1

                    if handler.once:
                        handlers_to_remove.append(handler)

                except Exception:
                    self._stats["errors"] += 1

            # 移除一次性处理器
            for handler in handlers_to_remove:
                self._handlers.remove(handler)

        logger.debug(
            "Event emitted",
            extra_data={
                "type": event_type.value if isinstance(event_type, EventType) else event_type,
                "handlers_called": len(handlers_to_remove) + 1,
            },
        )

        return event

    def emit_sync(
        self,
        event_type: EventType | str,
        data: dict[str, Any] | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        """
        同步发送事件

        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件来源
            metadata: 元数据

        Returns:
            Event 实例
        """
        try:
            asyncio.get_running_loop()
            # 如果已经在异步上下文中，创建任务
            return asyncio.create_task(
                self.emit(event_type, data, source, metadata)
            )  # type: ignore
        except RuntimeError:
            # 不在异步上下文中，运行新事件循环
            return asyncio.run(self.emit(event_type, data, source, metadata))

    def get_history(
        self,
        event_type: EventType | str | None = None,
        limit: int = 10,
    ) -> list[Event]:
        """
        获取事件历史

        Args:
            event_type: 过滤的事件类型
            limit: 最大数量

        Returns:
            事件列表
        """
        events = self._event_history

        if event_type:
            events = [e for e in events if e.type == event_type]

        return events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "handlers_count": len(self._handlers),
            "history_size": len(self._event_history),
        }

    def clear_handlers(self) -> None:
        """清除所有处理器"""
        self._handlers.clear()
        logger.info("All event handlers cleared")

    def clear_history(self) -> None:
        """清除事件历史"""
        self._event_history.clear()
        logger.info("Event history cleared")


# 全局事件总线实例
_global_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus("global")
    return _global_bus


def create_event_bus(name: str) -> EventBus:
    """创建新的事件总线"""
    return EventBus(name)
