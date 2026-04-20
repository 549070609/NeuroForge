"""Deprecated WebSocket plugin.

PyAgentForge no longer exposes WebSocket interfaces directly.
Use the unified Service gateway under `main/Service`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType

_DEPRECATION_MESSAGE = (
    "interface.websocket has been removed from pyagentforge. "
    "Use Service gateway websocket routes in main/Service instead."
)


class WebSocketPlugin(Plugin):
    """Compatibility stub for removed WebSocket plugin."""

    metadata = PluginMetadata(
        id="interface.websocket",
        name="WebSocket (Removed)",
        version="1.0.0",
        type=PluginType.INTERFACE,
        description="Removed: WebSocket serving moved to Service gateway",
        author="PyAgentForge",
        provides=[],
        dependencies=[],
    )

    async def on_plugin_activate(self) -> None:
        await super().on_plugin_activate()
        raise RuntimeError(_DEPRECATION_MESSAGE)

    async def start(self) -> bool:
        return False

    async def stop(self) -> bool:
        return True

    async def handle_connection(self, connection_id: str, websocket: Any) -> None:
        raise RuntimeError(_DEPRECATION_MESSAGE)

    async def close_connection(self, connection_id: str) -> bool:
        return False

    async def send_message(self, connection_id: str, message: dict) -> bool:
        return False

    async def broadcast(self, message: dict, exclude: list[str] | None = None) -> int:
        return 0

    def register_message_handler(
        self,
        message_type: str,
        handler: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        raise RuntimeError(_DEPRECATION_MESSAGE)

    def register_connection_handler(
        self,
        event: str,
        handler: Callable[[str], Awaitable[None]],
    ) -> None:
        raise RuntimeError(_DEPRECATION_MESSAGE)

    def get_active_connections(self) -> list[str]:
        return []

    def get_connection_count(self) -> int:
        return 0

    @property
    def is_running(self) -> bool:
        return False
