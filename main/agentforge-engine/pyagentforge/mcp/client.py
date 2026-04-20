"""
MCP Client 实现

连接外部 MCP 服务器使用其工具，支持多种传输方式
"""

from typing import Any

from pyagentforge.mcp.transport import (
    MCPConfig,
    MCPTransport,
    TransportType,
    create_transport,
    create_transport_from_dict,
)
from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class MCPClient:
    """
    MCP Client 实现

    支持多种传输方式:
    - HTTP: 标准的 HTTP/REST 通信
    - stdio: 通过标准输入输出与子进程通信
    - SSE: Server-Sent Events
    """

    def __init__(
        self,
        transport: MCPTransport | None = None,
        config: MCPConfig | None = None,
        # 向后兼容: 支持直接传入 URL
        server_url: str | None = None,
        timeout: int = 30,
    ) -> None:
        """
        初始化 MCP 客户端

        Args:
            transport: 传输层实例（优先）
            config: MCP 配置（如果没有 transport）
            server_url: 服务器 URL（向后兼容，自动创建 HTTP 传输）
            timeout: 超时时间（向后兼容）
        """
        if transport:
            self._transport = transport
        elif config:
            self._transport = create_transport(config)
        elif server_url:
            # 向后兼容: 自动创建 HTTP 传输
            http_config = MCPConfig(
                transport=TransportType.HTTP,
                url=server_url,
                timeout=timeout,
            )
            self._transport = create_transport(http_config)
        else:
            raise ValueError("Either transport, config, or server_url must be provided")

        self._tools: dict[str, dict[str, Any]] = {}
        self._initialized = False

    @property
    def transport(self) -> MCPTransport:
        """获取传输层"""
        return self._transport

    @classmethod
    def from_http(
        cls,
        url: str,
        timeout: int = 30,
        headers: dict[str, str] | None = None,
    ) -> "MCPClient":
        """
        创建 HTTP 传输的客户端

        Args:
            url: 服务器 URL
            timeout: 超时时间
            headers: 额外的请求头

        Returns:
            MCPClient 实例
        """
        config = MCPConfig(
            transport=TransportType.HTTP,
            url=url,
            timeout=timeout,
            headers=headers or {},
        )
        return cls(config=config)

    @classmethod
    def from_stdio(
        cls,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> "MCPClient":
        """
        创建 stdio 传输的客户端

        Args:
            command: 启动 MCP 服务器的命令
            args: 命令参数
            env: 环境变量
            cwd: 工作目录

        Returns:
            MCPClient 实例

        示例:
            # 使用 npm 包
            client = MCPClient.from_stdio(
                command="npx",
                args=["@modelcontextprotocol/server-filesystem", "/workspace"]
            )

            # 使用 Python 包
            client = MCPClient.from_stdio(
                command="python",
                args=["-m", "my_mcp_server"],
                env={"API_KEY": "xxx"}
            )
        """
        config = MCPConfig(
            transport=TransportType.STDIO,
            command=command,
            args=args or [],
            env=env or {},
            cwd=cwd,
        )
        return cls(config=config)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "MCPClient":
        """
        从配置字典创建客户端

        Args:
            config: 配置字典

        Returns:
            MCPClient 实例

        示例配置:
            # HTTP 配置
            {
                "transport": "http",
                "url": "http://localhost:8080",
                "timeout": 30
            }

            # stdio 配置
            {
                "transport": "stdio",
                "command": "npx",
                "args": ["@modelcontextprotocol/server-filesystem", "/workspace"],
                "env": {"DEBUG": "1"}
            }
        """
        transport = create_transport_from_dict(config)
        return cls(transport=transport)

    async def connect(self) -> bool:
        """
        连接到 MCP 服务器

        Returns:
            是否连接成功
        """
        try:
            # 先建立传输层连接
            if not await self._transport.connect():
                return False

            # 发送初始化请求
            response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "PyAgentForge",
                    "version": "1.0.0",
                },
            })

            if response.get("result"):
                self._initialized = True
                server_info = response["result"].get("serverInfo", {})
                logger.info(
                    "Connected to MCP server",
                    extra_data={
                        "server_name": server_info.get("name", "unknown"),
                        "server_version": server_info.get("version", "unknown"),
                    },
                )
                return True

            return False

        except Exception as e:
            logger.error(
                "Failed to connect to MCP server",
                extra_data={"error": str(e)},
            )
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        await self._transport.disconnect()
        self._initialized = False

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        获取服务器提供的工具列表

        Returns:
            工具列表
        """
        try:
            response = await self._send_request("tools/list", {})

            tools = response.get("result", {}).get("tools", [])

            for tool in tools:
                self._tools[tool["name"]] = tool

            logger.info(
                "Retrieved MCP tools",
                extra_data={"count": len(tools)},
            )

            return tools

        except Exception as e:
            logger.error(
                "Failed to list tools",
                extra_data={"error": str(e)},
            )
            return []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> str:
        """
        调用远程工具

        Args:
            name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        try:
            response = await self._send_request("tools/call", {
                "name": name,
                "arguments": arguments,
            })

            result = response.get("result", {})
            content = result.get("content", [])

            # 提取文本内容
            text_parts = []
            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))

            result_text = "\n".join(text_parts)

            logger.debug(
                "MCP tool called",
                extra_data={"name": name, "result_length": len(result_text)},
            )

            return result_text

        except Exception as e:
            error_msg = f"Error calling MCP tool '{name}': {str(e)}"
            logger.error(
                "MCP tool call error",
                extra_data={"name": name, "error": str(e)},
            )
            return f"Error: {error_msg}"

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        发送 JSON-RPC 请求

        Args:
            method: 方法名
            params: 参数

        Returns:
            响应
        """
        return await self._transport.send_request(method, params)

    async def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._initialized and await self._transport.is_connected()

    def get_tool_wrapper(self, name: str) -> "MCPToolWrapper | None":
        """
        获取工具包装器

        Args:
            name: 工具名称

        Returns:
            工具包装器或 None
        """
        if name not in self._tools:
            return None

        return MCPToolWrapper(client=self, tool_info=self._tools[name])

    def get_all_tool_wrappers(self) -> list["MCPToolWrapper"]:
        """获取所有工具的包装器"""
        return [
            MCPToolWrapper(client=self, tool_info=tool_info)
            for tool_info in self._tools.values()
        ]


class MCPToolWrapper(BaseTool):
    """MCP 工具包装器 - 将 MCP 工具包装为内部工具"""

    def __init__(
        self,
        client: MCPClient,
        tool_info: dict[str, Any],
    ) -> None:
        self.client = client
        self._tool_info = tool_info

        self.name = tool_info.get("name", "unknown")
        self.description = tool_info.get("description", "")
        self.parameters_schema = tool_info.get("inputSchema", {})

    async def execute(self, **kwargs: Any) -> str:
        """执行工具"""
        return await self.client.call_tool(self.name, kwargs)


class MCPClientManager:
    """MCP 客户端管理器"""

    def __init__(self) -> None:
        self.clients: dict[str, MCPClient] = {}

    async def add_http_server(
        self,
        name: str,
        url: str,
        timeout: int = 30,
    ) -> bool:
        """
        添加 HTTP MCP 服务器

        Args:
            name: 服务器名称
            url: 服务器 URL
            timeout: 超时时间

        Returns:
            是否添加成功
        """
        if name in self.clients:
            return True

        client = MCPClient.from_http(url, timeout)
        if await client.connect():
            self.clients[name] = client
            return True

        return False

    async def add_stdio_server(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> bool:
        """
        添加 stdio MCP 服务器

        Args:
            name: 服务器名称
            command: 启动命令
            args: 命令参数
            env: 环境变量
            cwd: 工作目录

        Returns:
            是否添加成功
        """
        if name in self.clients:
            return True

        client = MCPClient.from_stdio(command, args, env, cwd)
        if await client.connect():
            self.clients[name] = client
            return True

        return False

    async def add_server_from_config(
        self,
        name: str,
        config: dict[str, Any],
    ) -> bool:
        """
        从配置添加服务器

        Args:
            name: 服务器名称
            config: 配置字典

        Returns:
            是否添加成功
        """
        if name in self.clients:
            return True

        client = MCPClient.from_config(config)
        if await client.connect():
            self.clients[name] = client
            return True

        return False

    async def remove_server(self, name: str) -> None:
        """移除服务器"""
        if name in self.clients:
            await self.clients[name].disconnect()
            del self.clients[name]

    def get_client(self, name: str) -> MCPClient | None:
        """获取客户端"""
        return self.clients.get(name)

    async def get_all_tools(self) -> list[MCPToolWrapper]:
        """获取所有服务器的工具"""
        tools = []

        for client in self.clients.values():
            client_tools = await client.list_tools()
            for tool_info in client_tools:
                tools.append(MCPToolWrapper(client, tool_info))

        return tools

    async def disconnect_all(self) -> None:
        """断开所有连接"""
        for name in list(self.clients.keys()):
            await self.remove_server(name)


# ============ 向后兼容 ============

# 保留旧的导入路径
__all__ = [
    "MCPClient",
    "MCPToolWrapper",
    "MCPClientManager",
]
