"""
MCP Server Plugin

Model Context Protocol (MCP) Server implementation for exposing tools and resources
"""

import logging
from typing import Any, List, Optional, Callable

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool


class MCPServerPlugin(Plugin):
    """MCP Server Protocol Plugin"""

    metadata = PluginMetadata(
        id="protocol.mcp_server",
        name="MCP Server",
        version="1.0.0",
        type=PluginType.PROTOCOL,
        description="Model Context Protocol (MCP) server implementation for exposing Agent capabilities",
        author="PyAgentForge",
        provides=["protocol.mcp.server"],
        dependencies=["integration.events"],
    )

    def __init__(self):
        super().__init__()
        self._server = None
        self._registered_tools: dict[str, dict] = {}
        self._registered_resources: dict[str, dict] = {}
        self._is_running = False

    async def on_plugin_activate(self) -> None:
        """Activate MCP Server plugin"""
        await super().on_plugin_activate()
        self.context.logger.info("MCP Server plugin initialized")

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin and stop server"""
        if self._is_running:
            await self.stop()
        await super().on_plugin_deactivate()

    async def start(self, host: str = "localhost", port: int = 3000) -> bool:
        """Start the MCP server

        Args:
            host: Server host address
            port: Server port

        Returns:
            True if server started successfully
        """
        try:
            self._server = {
                "host": host,
                "port": port,
            }
            self._is_running = True
            self.context.logger.info(f"MCP Server started on {host}:{port}")
            return True
        except Exception as e:
            self.context.logger.error(f"Failed to start MCP server: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the MCP server"""
        if self._is_running:
            self._is_running = False
            self._server = None
            self.context.logger.info("MCP Server stopped")
            return True
        return False

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
    ) -> None:
        """Register a tool to be exposed via MCP

        Args:
            name: Tool name
            description: Tool description
            parameters: JSON Schema for parameters
            handler: Async function to handle tool calls
        """
        self._registered_tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler,
        }
        self.context.logger.info(f"Registered MCP tool: {name}")

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str,
        handler: Callable,
    ) -> None:
        """Register a resource to be exposed via MCP

        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            handler: Async function to handle resource reads
        """
        self._registered_resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "handler": handler,
        }
        self.context.logger.info(f"Registered MCP resource: {name}")

    def list_tools(self) -> list[dict]:
        """List all registered tools"""
        return list(self._registered_tools.values())

    def list_resources(self) -> list[dict]:
        """List all registered resources"""
        return list(self._registered_resources.values())

    @property
    def is_running(self) -> bool:
        """Check if server is running"""
        return self._is_running
