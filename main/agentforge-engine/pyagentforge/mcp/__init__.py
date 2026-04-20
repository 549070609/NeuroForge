"""
MCP 协议模块

包含 MCP Server 和 MCP Client 实现，支持多种传输方式
"""

from pyagentforge.mcp.client import (
    MCPClient,
    MCPClientManager,
    MCPToolWrapper,
)
from pyagentforge.mcp.server import (
    MCPRequest,
    MCPResource,
    MCPResourceManager,
    MCPResponse,
    MCPServer,
    MCPServerInfo,
    MCPToolInfo,
)
from pyagentforge.mcp.transport import (
    HTTPTransport,
    # 配置
    MCPConfig,
    # 传输层
    MCPTransport,
    SSETransport,
    StdioTransport,
    TransportType,
    # 工厂函数
    create_transport,
    create_transport_from_dict,
)

__all__ = [
    # Server
    "MCPServer",
    "MCPServerInfo",
    "MCPRequest",
    "MCPResponse",
    "MCPToolInfo",
    "MCPResource",
    "MCPResourceManager",
    # Client
    "MCPClient",
    "MCPToolWrapper",
    "MCPClientManager",
    # Transport
    "MCPConfig",
    "TransportType",
    "MCPTransport",
    "HTTPTransport",
    "StdioTransport",
    "SSETransport",
    "create_transport",
    "create_transport_from_dict",
]
