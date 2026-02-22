"""
MCP Server 实现

作为 MCP 服务端暴露工具给外部调用
"""

import json
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ============ MCP 协议类型 ============


class MCPRequest(BaseModel):
    """MCP 请求"""

    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class MCPResponse(BaseModel):
    """MCP 响应"""

    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None


class MCPServerInfo(BaseModel):
    """MCP 服务器信息"""

    name: str = "PyAgentForge"
    version: str = "1.0.0"


class MCPToolInfo(BaseModel):
    """MCP 工具信息"""

    name: str
    description: str
    inputSchema: dict[str, Any]


# ============ MCP Server ============


class MCPServer:
    """MCP Server 实现"""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        server_info: MCPServerInfo | None = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.server_info = server_info or MCPServerInfo()
        self._initialized = False

    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """
        处理 MCP 请求

        Args:
            request: MCP 请求

        Returns:
            MCP 响应
        """
        method = request.method
        params = request.params

        logger.debug(
            "MCP request received",
            extra_data={"method": method, "id": request.id},
        )

        try:
            if method == "initialize":
                result = await self._handle_initialize(params)
            elif method == "tools/list":
                result = await self._handle_tools_list()
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "ping":
                result = {"status": "ok"}
            else:
                return MCPResponse(
                    id=request.id,
                    error={
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                )

            return MCPResponse(id=request.id, result=result)

        except Exception as e:
            logger.error(
                "MCP request error",
                extra_data={"method": method, "error": str(e)},
            )
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32603,
                    "message": str(e),
                },
            )

    async def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理初始化请求"""
        self._initialized = True

        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {
                    "listChanged": False,
                },
            },
            "serverInfo": {
                "name": self.server_info.name,
                "version": self.server_info.version,
            },
        }

    async def _handle_tools_list(self) -> dict[str, Any]:
        """处理工具列表请求"""
        tools = []

        for tool in self.tool_registry:
            tools.append(
                MCPToolInfo(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.parameters_schema,
                ).model_dump()
            )

        return {"tools": tools}

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise ValueError("Tool name is required")

        tool = self.tool_registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool not found: {tool_name}")

        result = await tool.execute(**arguments)

        return {
            "content": [
                {
                    "type": "text",
                    "text": result,
                }
            ],
            "isError": result.startswith("Error:"),
        }

    def get_sse_endpoint(self):
        """获取 SSE 端点处理器"""
        from fastapi import Request
        from fastapi.responses import StreamingResponse
        import asyncio

        async def sse_handler(request: Request) -> StreamingResponse:
            async def event_generator():
                while True:
                    if await request.is_disconnected():
                        break
                    await asyncio.sleep(1)
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
            )

        return sse_handler


# ============ MCP Resource (基础实现) ============


class MCPResource(BaseModel):
    """MCP 资源"""

    uri: str
    name: str
    description: str | None = None
    mimeType: str = "text/plain"


class MCPResourceManager:
    """MCP 资源管理器"""

    def __init__(self) -> None:
        self.resources: dict[str, MCPResource] = {}

    def register(self, resource: MCPResource) -> None:
        """注册资源"""
        self.resources[resource.uri] = resource

    def list_resources(self) -> list[MCPResource]:
        """列出所有资源"""
        return list(self.resources.values())

    def get_resource(self, uri: str) -> MCPResource | None:
        """获取资源"""
        return self.resources.get(uri)
