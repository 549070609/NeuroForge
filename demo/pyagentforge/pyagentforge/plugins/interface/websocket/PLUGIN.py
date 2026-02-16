"""
WebSocket Plugin

Provides WebSocket interface for real-time Agent communication
"""

import logging
from typing import Any, Optional, Callable, Awaitable
from datetime import datetime

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class WebSocketPlugin(Plugin):
    """WebSocket Interface Plugin"""

    metadata = PluginMetadata(
        id="interface.websocket",
        name="WebSocket",
        version="1.0.0",
        type=PluginType.INTERFACE,
        description="WebSocket interface for real-time bidirectional Agent communication",
        author="PyAgentForge",
        provides=["interface.websocket"],
        dependencies=["interface.rest_api"],
    )

    def __init__(self):
        super().__init__()
        self._websocket_server = None
        self._is_running = False
        self._connections: dict[str, Any] = {}
        self._message_handlers: dict[str, Callable] = {}
        self._connection_handlers: dict[str, Callable] = {}

    async def on_plugin_activate(self) -> None:
        """Activate WebSocket plugin"""
        await super().on_plugin_activate()

        # Get configuration
        config = self.context.config or {}
        self._path = config.get("path", "/ws")
        self._max_connections = config.get("max_connections", 100)
        self._heartbeat_interval = config.get("heartbeat_interval", 30)

        self.context.logger.info(
            f"WebSocket plugin initialized (path={self._path})"
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin and close all connections"""
        if self._is_running:
            await self.stop()
        await super().on_plugin_deactivate()

    async def start(self) -> bool:
        """Start the WebSocket server

        Returns:
            True if server started successfully
        """
        try:
            # WebSocket typically mounts on the REST API server
            self._websocket_server = {
                "path": self._path,
                "max_connections": self._max_connections,
            }
            self._is_running = True
            self.context.logger.info(
                f"WebSocket server started at {self._path}"
            )
            return True
        except Exception as e:
            self.context.logger.error(f"Failed to start WebSocket server: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the WebSocket server and close all connections"""
        if self._is_running:
            # Close all connections
            for conn_id in list(self._connections.keys()):
                await self.close_connection(conn_id)

            self._is_running = False
            self._websocket_server = None
            self.context.logger.info("WebSocket server stopped")
            return True
        return False

    async def handle_connection(self, connection_id: str, websocket: Any) -> None:
        """Handle a new WebSocket connection

        Args:
            connection_id: Unique connection identifier
            websocket: WebSocket connection object
        """
        self._connections[connection_id] = {
            "id": connection_id,
            "websocket": websocket,
            "connected_at": datetime.now(),
            "last_activity": datetime.now(),
        }

        # Call connection handler if registered
        if "on_connect" in self._connection_handlers:
            await self._connection_handlers["on_connect"](connection_id)

        self.context.logger.info(f"WebSocket connection established: {connection_id}")

    async def close_connection(self, connection_id: str) -> bool:
        """Close a WebSocket connection

        Args:
            connection_id: Connection to close

        Returns:
            True if connection was closed
        """
        if connection_id in self._connections:
            # Call disconnect handler if registered
            if "on_disconnect" in self._connection_handlers:
                await self._connection_handlers["on_disconnect"](connection_id)

            del self._connections[connection_id]
            self.context.logger.info(f"WebSocket connection closed: {connection_id}")
            return True
        return False

    async def send_message(self, connection_id: str, message: dict) -> bool:
        """Send a message to a specific connection

        Args:
            connection_id: Target connection
            message: Message payload

        Returns:
            True if message was sent
        """
        if connection_id not in self._connections:
            return False

        try:
            # Placeholder for actual send
            # Would use websocket.send_json(message) or similar
            self._connections[connection_id]["last_activity"] = datetime.now()
            return True
        except Exception as e:
            self.context.logger.error(f"Error sending message to {connection_id}: {e}")
            return False

    async def broadcast(self, message: dict, exclude: list[str] = None) -> int:
        """Broadcast a message to all connections

        Args:
            message: Message payload
            exclude: Connection IDs to exclude

        Returns:
            Number of connections messaged
        """
        exclude = exclude or []
        count = 0

        for conn_id in self._connections:
            if conn_id not in exclude:
                if await self.send_message(conn_id, message):
                    count += 1

        return count

    def register_message_handler(
        self,
        message_type: str,
        handler: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        """Register a handler for a specific message type

        Args:
            message_type: Type of message to handle
            handler: Async function(connection_id, message) -> None
        """
        self._message_handlers[message_type] = handler
        self.context.logger.info(f"Registered handler for message type: {message_type}")

    def register_connection_handler(
        self,
        event: str,
        handler: Callable[[str], Awaitable[None]],
    ) -> None:
        """Register a handler for connection events

        Args:
            event: Event name ('on_connect' or 'on_disconnect')
            handler: Async function(connection_id) -> None
        """
        if event not in ["on_connect", "on_disconnect"]:
            raise ValueError(f"Invalid event: {event}")
        self._connection_handlers[event] = handler

    def get_active_connections(self) -> list[str]:
        """Get list of active connection IDs"""
        return list(self._connections.keys())

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self._connections)

    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._is_running
