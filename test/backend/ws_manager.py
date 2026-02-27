"""
WebSocket Connection Manager

Manages multiple WebSocket connections per session, supports targeted message
pushing, and handles connection lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections grouped by session_id."""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = []
            self._connections[session_id].append(ws)
        logger.info("WS connected: session=%s, total=%d", session_id, len(self._connections[session_id]))

    async def disconnect(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(session_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(session_id, None)
        logger.info("WS disconnected: session=%s", session_id)

    async def send_to_session(self, session_id: str, data: dict[str, Any]) -> int:
        """Send a JSON message to all connections in a session.

        Returns:
            Number of connections that received the message successfully.
        """
        conns = self._connections.get(session_id, [])
        if not conns:
            return 0
        dead: list[WebSocket] = []
        sent = 0
        for ws in conns:
            try:
                await ws.send_json(data)
                sent += 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(session_id, ws)
        return sent

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast a message to all connected sessions."""
        for session_id in list(self._connections.keys()):
            await self.send_to_session(session_id, data)

    def get_active_sessions(self) -> list[str]:
        return list(self._connections.keys())

    def has_connections(self, session_id: str) -> bool:
        return bool(self._connections.get(session_id))
