"""
SSE Event Types - Core event definitions for Server-Sent Events.

Event Types:
    connected: Connection established
    stream: Text streaming
    tool_start: Tool execution started
    tool_result: Tool execution result
    complete: Execution complete
    error: Error occurred
    plugin:{id}:{name}: Plugin-specific events (namespaced)

Example SSE Event:
    event: stream
    data: {"content": "Hello", "index": 0}
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """SSE event types."""

    # Connection events
    CONNECTED = "connected"

    # Streaming events
    STREAM = "stream"

    # Tool events
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"

    # Completion events
    COMPLETE = "complete"

    # Error events
    ERROR = "error"

    # Plugin events (use plugin:{id}:{name} format)
    PLUGIN = "plugin"

    @classmethod
    def is_plugin_event(cls, event_type: str) -> bool:
        """Check if event type is a plugin event."""
        return event_type.startswith("plugin:")


class BaseEvent:
    """Base class for all events."""

    event_type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        raise NotImplementedError

    def to_sse(self) -> str:
        """Convert to SSE format string."""
        import json

        data = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"event: {self.event_type}\ndata: {data}\n\n"


class ConnectedEvent(BaseEvent):
    """Connection established event."""

    event_type = EventType.CONNECTED

    def __init__(self, session_id: str):
        self.session_id = session_id

    def to_dict(self) -> dict[str, Any]:
        return {"session_id": self.session_id, "message": "Connected"}


class StreamEvent(BaseEvent):
    """Text streaming event."""

    event_type = EventType.STREAM

    def __init__(self, content: str, index: int = 0, done: bool = False):
        self.content = content
        self.index = index
        self.done = done

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "index": self.index,
            "done": self.done,
        }


class ToolStartEvent(BaseEvent):
    """Tool execution started event."""

    event_type = EventType.TOOL_START

    def __init__(self, tool_name: str, tool_input: dict[str, Any], call_id: str | None = None):
        self.tool_name = tool_name
        self.tool_input = tool_input
        self.call_id = call_id

    def to_dict(self) -> dict[str, Any]:
        data = {
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
        }
        if self.call_id:
            data["call_id"] = self.call_id
        return data


class ToolResultEvent(BaseEvent):
    """Tool execution result event."""

    event_type = EventType.TOOL_RESULT

    def __init__(
        self,
        tool_name: str,
        result: Any,
        call_id: str | None = None,
        error: str | None = None,
    ):
        self.tool_name = tool_name
        self.result = result
        self.call_id = call_id
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        data = {
            "tool_name": self.tool_name,
            "result": self.result,
        }
        if self.call_id:
            data["call_id"] = self.call_id
        if self.error:
            data["error"] = self.error
        return data


class CompleteEvent(BaseEvent):
    """Execution complete event."""

    event_type = EventType.COMPLETE

    def __init__(
        self,
        message: str = "Complete",
        token_count: int | None = None,
        duration_ms: float | None = None,
    ):
        self.message = message
        self.token_count = token_count
        self.duration_ms = duration_ms

    def to_dict(self) -> dict[str, Any]:
        data = {"message": self.message}
        if self.token_count is not None:
            data["token_count"] = self.token_count
        if self.duration_ms is not None:
            data["duration_ms"] = self.duration_ms
        return data


class ErrorEvent(BaseEvent):
    """Error event."""

    event_type = EventType.ERROR

    def __init__(self, error: str, code: str | None = None, details: dict | None = None):
        self.error = error
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        data = {"error": self.error}
        if self.code:
            data["code"] = self.code
        if self.details:
            data["details"] = self.details
        return data


class PluginEvent(BaseEvent):
    """Plugin-specific event with namespace isolation."""

    event_type = EventType.PLUGIN

    def __init__(self, plugin_id: str, event_name: str, data: dict[str, Any]):
        self.plugin_id = plugin_id
        self.event_name = event_name
        self.data = data

    @property
    def full_event_type(self) -> str:
        """Get full event type with namespace."""
        return f"plugin:{self.plugin_id}:{self.event_name}"

    def to_dict(self) -> dict[str, Any]:
        return self.data

    def to_sse(self) -> str:
        """Convert to SSE format with namespaced event type."""
        import json

        data = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"event: {self.full_event_type}\ndata: {data}\n\n"
