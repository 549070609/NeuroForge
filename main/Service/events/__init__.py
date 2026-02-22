"""Event module - SSE event types and emitter."""

from .filter import EventFilter, match_pattern, should_emit_event
from .types import (
    BaseEvent,
    CompleteEvent,
    ConnectedEvent,
    ErrorEvent,
    EventType,
    PluginEvent,
    StreamEvent,
    ToolResultEvent,
    ToolStartEvent,
)

__all__ = [
    "EventType",
    "BaseEvent",
    "ConnectedEvent",
    "StreamEvent",
    "ToolStartEvent",
    "ToolResultEvent",
    "CompleteEvent",
    "ErrorEvent",
    "PluginEvent",
    "EventFilter",
    "match_pattern",
    "should_emit_event",
]
