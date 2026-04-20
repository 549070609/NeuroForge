"""
MCP 传输层实现

支持多种传输方式：HTTP、stdio、SSE
"""

import asyncio
import contextlib
import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TransportType(Enum):
    """传输类型"""
    HTTP = "http"
    STDIO = "stdio"
    SSE = "sse"


@dataclass
class MCPConfig:
    """MCP 配置"""
    transport: TransportType = TransportType.HTTP

    # HTTP 配置
    url: str = ""
    timeout: int = 30
    headers: dict[str, str] = field(default_factory=dict)

    # stdio 配置
    command: str = ""  # 启动命令，如 "npx @modelcontextprotocol/server-filesystem"
    args: list[str] = field(default_factory=list)  # 命令参数
    env: dict[str, str] = field(default_factory=dict)  # 环境变量
    cwd: str | None = None  # 工作目录

    # SSE 配置
    sse_url: str = ""


class MCPTransport(ABC):
    """MCP 传输层抽象基类"""

    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass

    @abstractmethod
    async def send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """发送 JSON-RPC 请求"""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """检查是否已连接"""
        pass


class HTTPTransport(MCPTransport):
    """HTTP 传输层"""

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self._connected = False

        # 延迟导入 httpx
        try:
            import httpx
            self._client = httpx.AsyncClient(timeout=config.timeout)
        except ImportError as e:
            raise ImportError(
                "httpx is required for HTTP transport. Install it with: pip install httpx"
            ) from e

    async def connect(self) -> bool:
        """建立连接"""
        self._connected = True
        logger.info(
            "HTTP transport connected",
            extra_data={"url": self.config.url},
        )
        return True

    async def disconnect(self) -> None:
        """断开连接"""
        await self._client.aclose()
        self._connected = False
        logger.info("HTTP transport disconnected")

    async def send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """发送 HTTP 请求"""
        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        headers = {"Content-Type": "application/json"}
        headers.update(self.config.headers)

        response = await self._client.post(
            f"{self.config.url}/mcp",
            json=request_body,
            headers=headers,
        )

        response.raise_for_status()
        return response.json()

    async def is_connected(self) -> bool:
        return self._connected


class StdioTransport(MCPTransport):
    """
    stdio 传输层

    通过标准输入输出与子进程通信
    """

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._reader_lock = asyncio.Lock()
        self._writer_lock = asyncio.Lock()
        self._request_id = 0
        self._pending_responses: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._buffer = ""

    async def connect(self) -> bool:
        """启动子进程并建立连接"""
        try:
            # 构建命令
            cmd = self.config.command.split() if self.config.command else []
            cmd.extend(self.config.args)

            if not cmd:
                raise ValueError("No command specified for stdio transport")

            # 准备环境变量
            env = os.environ.copy()
            env.update(self.config.env)

            # 启动子进程
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=self.config.cwd,
            )

            # 启动响应读取任务
            self._reader_task = asyncio.create_task(self._read_responses())

            logger.info(
                "stdio transport connected",
                extra_data={"command": self.config.command, "pid": self._process.pid},
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to start stdio transport",
                extra_data={"command": self.config.command, "error": str(e)},
            )
            return False

    async def disconnect(self) -> None:
        """终止子进程"""
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
            except Exception:
                pass

            logger.info(
                "stdio transport disconnected",
                extra_data={"pid": self._process.pid if self._process else None},
            )

        self._process = None

    async def send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """发送请求到子进程"""
        if not self._process or not self._process.stdin:
            raise RuntimeError("stdio transport not connected")

        # 生成请求 ID
        self._request_id += 1
        request_id = self._request_id

        # 创建 Future 用于等待响应
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self._pending_responses[request_id] = future

        # 构建请求
        request_body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params,
        }

        # 发送请求
        message = json.dumps(request_body) + "\n"

        try:
            self._process.stdin.write(message.encode("utf-8"))
            await self._process.stdin.drain()

            logger.debug(
                "stdio request sent",
                extra_data={"method": method, "id": request_id},
            )

            # 等待响应（带超时）
            return await asyncio.wait_for(future, timeout=60)

        except TimeoutError:
            self._pending_responses.pop(request_id, None)
            raise RuntimeError(f"stdio request timed out: {method}") from None
        except Exception as e:
            self._pending_responses.pop(request_id, None)
            raise RuntimeError(f"stdio request failed: {e}") from e

    async def _read_responses(self) -> None:
        """持续读取子进程的响应"""
        if not self._process or not self._process.stdout:
            return

        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    # EOF
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    response = json.loads(line_str)

                    # 查找对应的 Future
                    request_id = response.get("id")
                    if request_id is not None and request_id in self._pending_responses:
                        future = self._pending_responses.pop(request_id)
                        if not future.done():
                            future.set_result(response)

                    logger.debug(
                        "stdio response received",
                        extra_data={"id": request_id},
                    )

                except json.JSONDecodeError as e:
                    logger.warning(
                        "Invalid JSON response from stdio",
                        extra_data={"line": line_str[:100], "error": str(e)},
                    )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "stdio reader error",
                extra_data={"error": str(e)},
            )

    async def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def read_stderr(self) -> AsyncIterator[str]:
        """读取标准错误输出"""
        if not self._process or not self._process.stderr:
            return

        try:
            while True:
                line = await self._process.stderr.readline()
                if not line:
                    break
                yield line.decode("utf-8").strip()
        except Exception:
            pass


class SSETransport(MCPTransport):
    """
    SSE (Server-Sent Events) 传输层

    通过 SSE 接收服务器推送的消息
    """

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        self._connected = False
        self._client = None
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def connect(self) -> bool:
        """建立 SSE 连接"""
        try:
            import httpx

            self._client = httpx.AsyncClient(timeout=self.config.timeout)
            self._connected = True

            logger.info(
                "SSE transport connected",
                extra_data={"url": self.config.sse_url or self.config.url},
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to connect SSE transport",
                extra_data={"error": str(e)},
            )
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            await self._client.aclose()
        self._connected = False

    async def send_request(
        self,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """发送请求（通过 HTTP）"""
        if not self._client:
            raise RuntimeError("SSE transport not connected")

        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        url = self.config.url or self.config.sse_url.replace("/sse", "")

        response = await self._client.post(
            f"{url}/mcp",
            json=request_body,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()
        return response.json()

    async def listen_events(self) -> AsyncIterator[dict[str, Any]]:
        """监听 SSE 事件"""
        if not self._client:
            return

        sse_url = self.config.sse_url or f"{self.config.url}/sse"

        try:
            async with self._client.stream("GET", sse_url) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            yield data
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(
                "SSE listen error",
                extra_data={"error": str(e)},
            )

    async def is_connected(self) -> bool:
        return self._connected


def create_transport(config: MCPConfig) -> MCPTransport:
    """
    根据配置创建传输层

    Args:
        config: MCP 配置

    Returns:
        传输层实例
    """
    if config.transport == TransportType.HTTP:
        return HTTPTransport(config)
    elif config.transport == TransportType.STDIO:
        return StdioTransport(config)
    elif config.transport == TransportType.SSE:
        return SSETransport(config)
    else:
        raise ValueError(f"Unknown transport type: {config.transport}")


def create_transport_from_dict(config: dict[str, Any]) -> MCPTransport:
    """
    从字典配置创建传输层

    Args:
        config: 配置字典

    Returns:
        传输层实例
    """
    transport_type = TransportType(config.get("transport", "http"))

    mcp_config = MCPConfig(
        transport=transport_type,
        url=config.get("url", ""),
        timeout=config.get("timeout", 30),
        headers=config.get("headers", {}),
        command=config.get("command", ""),
        args=config.get("args", []),
        env=config.get("env", {}),
        cwd=config.get("cwd"),
        sse_url=config.get("sse_url", ""),
    )

    return create_transport(mcp_config)
