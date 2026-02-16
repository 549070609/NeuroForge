"""
REST API Plugin

Provides REST API interface for Agent interaction
"""

import logging
from typing import Any, Optional

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class RESTAPIPlugin(Plugin):
    """REST API Interface Plugin"""

    metadata = PluginMetadata(
        id="interface.rest_api",
        name="REST API",
        version="1.0.0",
        type=PluginType.INTERFACE,
        description="REST API interface for remote Agent interaction and integration",
        author="PyAgentForge",
        provides=["interface.rest"],
        dependencies=["integration.events"],
    )

    def __init__(self):
        super().__init__()
        self._app = None
        self._server = None
        self._is_running = False
        self._routes: dict[str, dict] = {}

    async def on_plugin_activate(self) -> None:
        """Activate REST API plugin"""
        await super().on_plugin_activate()

        # Get configuration
        config = self.context.config or {}
        self._host = config.get("host", "0.0.0.0")
        self._port = config.get("port", 8000)
        self._cors = config.get("cors", True)
        self._auth_enabled = config.get("auth_enabled", False)

        self.context.logger.info(
            f"REST API plugin initialized (host={self._host}, port={self._port})"
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin and stop server"""
        if self._is_running:
            await self.stop()
        await super().on_plugin_deactivate()

    async def start(self) -> bool:
        """Start the REST API server

        Returns:
            True if server started successfully
        """
        try:
            # Placeholder for actual server startup
            # Would typically use FastAPI, Flask, or aiohttp
            self._app = {
                "host": self._host,
                "port": self._port,
                "cors": self._cors,
                "auth_enabled": self._auth_enabled,
            }
            self._is_running = True
            self.context.logger.info(
                f"REST API server started on http://{self._host}:{self._port}"
            )
            return True
        except Exception as e:
            self.context.logger.error(f"Failed to start REST API server: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the REST API server"""
        if self._is_running:
            self._is_running = False
            self._app = None
            self._server = None
            self.context.logger.info("REST API server stopped")
            return True
        return False

    def register_route(
        self,
        method: str,
        path: str,
        handler: callable,
        auth_required: bool = False,
    ) -> None:
        """Register a custom route

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            path: URL path
            handler: Async function to handle the request
            auth_required: Whether authentication is required
        """
        route_key = f"{method.upper()}:{path}"
        self._routes[route_key] = {
            "method": method.upper(),
            "path": path,
            "handler": handler,
            "auth_required": auth_required,
        }
        self.context.logger.info(f"Registered route: {method} {path}")

    def get_routes(self) -> dict[str, dict]:
        """Get all registered routes"""
        return self._routes.copy()

    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._is_running

    @property
    def base_url(self) -> str:
        """Get the base URL of the server"""
        return f"http://{self._host}:{self._port}"
