"""
MCP 协议模块

包含 MCP Server 和 MCP Client 实现，支持多种传输方式
"""

from pyagentforge.mcp.server import (
    MCPServer,
    MCPServerInfo,
    MCPRequest,
    MCPResponse,
    MCPToolInfo,
    MCPResource,
    MCPResourceManager,
)
from pyagentforge.mcp.client import (
    MCPClient,
    MCPToolWrapper,
    MCPClientManager,
)
from pyagentforge.mcp.transport import (
    # 配置
    MCPConfig,
    TransportType,
    # 传输层
    MCPTransport,
    HTTPTransport,
    StdioTransport,
    SSETransport,
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
