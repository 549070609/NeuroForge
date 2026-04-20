"""
WebChat Channel - Web 聊天通道实现

提供 WebChat 会话与消息通道能力。
对外 REST/WebSocket 入口由 `main/Service` 网关统一承载。
"""

import uuid
from datetime import datetime
from typing import Any

from pyagentforge.capabilities.channels.base import (
    BaseChannel,
    ChannelMessage,
    ChannelStatus,
    SendMessageResult,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class WebChatChannel(BaseChannel):
    """
    WebChat 通道

    提供 Web 客户端会话与消息编排能力。
    该模块不直接暴露 HTTP/WebSocket 路由；
    对外接口由 Service 网关完成挂载。

    Session 管理：
    - 使用 session_key 格式: webchat:{session_id}
    - 支持 session 创建、查询、过期

    Examples:
        >>> channel = WebChatChannel({"max_sessions": 100})
        >>> await channel.initialize()
        >>> await channel.start()
        >>> # 路由由 Service 网关层挂载
    """

    name = "webchat"
    version = "1.0.0"

    def __init__(self, config: dict[str, Any]):
        """
        初始化 WebChat 通道

        Args:
            config: 配置字典
                - max_sessions: 最大会话数 (默认 1000)
                - session_timeout: 会话超时秒数 (默认 3600)
        """
        super().__init__(config)

        self.max_sessions = config.get("max_sessions", 1000)
        self.session_timeout = config.get("session_timeout", 3600)

        # 会话存储: session_id -> session_data
        self._sessions: dict[str, dict[str, Any]] = {}

        # WebSocket 连接存储: session_id -> websocket
        self._websockets: dict[str, Any] = {}

        logger.info(
            "WebChat channel created",
            extra_data={
                "max_sessions": self.max_sessions,
                "session_timeout": self.session_timeout,
            }
        )

    async def initialize(self) -> None:
        """
        初始化通道

        准备会话存储，验证配置。
        """
        self._set_status(ChannelStatus.CONNECTING)

        # 验证配置
        if self.max_sessions <= 0:
            raise ValueError("max_sessions must be positive")
        if self.session_timeout <= 0:
            raise ValueError("session_timeout must be positive")

        self._set_status(ChannelStatus.CONNECTED)

        logger.info(
            "WebChat channel initialized",
            extra_data={"status": self.status.value}
        )

    async def start(self) -> None:
        """
        启动通道

        开始接受消息。实际的消息接收由 HTTP 服务器处理。
        """
        if self.status != ChannelStatus.CONNECTED:
            raise RuntimeError("Channel must be initialized before starting")

        logger.info("WebChat channel started")

    async def stop(self) -> None:
        """
        停止通道

        关闭所有 WebSocket 连接，清理会话。
        """
        # 关闭所有 WebSocket
        for session_id, ws in list(self._websockets.items()):
            try:
                await ws.close()
            except Exception as e:
                logger.warning(
                    f"Error closing WebSocket for session {session_id}: {e}"
                )

        self._websockets.clear()
        self._sessions.clear()
        self._set_status(ChannelStatus.DISCONNECTED)

        logger.info("WebChat channel stopped")

    async def send_message(
        self,
        to: str,
        content: str,
        **kwargs: Any
    ) -> SendMessageResult:
        """
        发送消息到客户端

        Args:
            to: session_id
            content: 消息内容
            **kwargs:
                - message_type: 消息类型 (text, stream, error)
                - stream_chunk: 流式块数据
                - is_final: 是否最后一帧 (流式)

        Returns:
            发送结果
        """
        session_id = to
        message_id = str(uuid.uuid4())

        # 检查会话是否存在
        if session_id not in self._sessions:
            return SendMessageResult(
                success=False,
                error=f"Session not found: {session_id}"
            )

        message_type = kwargs.get("message_type", "text")

        # 通过 WebSocket 发送
        if session_id in self._websockets:
            try:
                ws = self._websockets[session_id]
                message = {
                    "id": message_id,
                    "type": message_type,
                    "content": content,
                    "timestamp": datetime.now().isoformat(),
                    **kwargs,
                }

                # 发送 JSON 消息
                await ws.send_json(message)

                logger.debug(
                    f"Sent message to session {session_id}",
                    extra_data={"message_id": message_id}
                )

                return SendMessageResult(
                    success=True,
                    message_id=message_id
                )

            except Exception as e:
                logger.error(
                    f"Failed to send message to session {session_id}: {e}"
                )
                return SendMessageResult(
                    success=False,
                    error=str(e)
                )
        else:
            # 没有 WebSocket 连接，消息入队等待轮询
            if "message_queue" not in self._sessions[session_id]:
                self._sessions[session_id]["message_queue"] = []

            self._sessions[session_id]["message_queue"].append({
                "id": message_id,
                "type": message_type,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                **kwargs,
            })

            return SendMessageResult(
                success=True,
                message_id=message_id
            )

    async def get_channel_info(self) -> dict[str, Any]:
        """
        获取通道信息

        Returns:
            通道信息字典
        """
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "active_sessions": len(self._sessions),
            "active_websockets": len(self._websockets),
            "max_sessions": self.max_sessions,
            "session_timeout": self.session_timeout,
        }

    # === WebChat 特有方法 ===

    def create_session(self, session_id: str | None = None) -> str:
        """
        创建新会话

        Args:
            session_id: 可选的会话 ID，不提供则自动生成

        Returns:
            session_id

        Raises:
            ValueError: 达到最大会话数限制
        """
        if len(self._sessions) >= self.max_sessions:
            raise ValueError(f"Maximum sessions reached: {self.max_sessions}")

        if session_id is None:
            session_id = str(uuid.uuid4())

        self._sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "message_queue": [],
        }

        logger.info(f"Created session: {session_id}")

        return session_id

    def get_or_create_session(self, session_id: str) -> str:
        """
        获取或创建会话

        Args:
            session_id: 会话 ID

        Returns:
            session_id
        """
        if session_id in self._sessions:
            # 更新最后活动时间
            self._sessions[session_id]["last_activity"] = datetime.now()
            return session_id
        else:
            return self.create_session(session_id)

    def register_websocket(self, session_id: str, websocket: Any) -> None:
        """
        注册 WebSocket 连接

        Args:
            session_id: 会话 ID
            websocket: WebSocket 连接对象
        """
        # 确保会话存在
        self.get_or_create_session(session_id)

        self._websockets[session_id] = websocket

        logger.info(f"Registered WebSocket for session: {session_id}")

    def unregister_websocket(self, session_id: str) -> None:
        """
        注销 WebSocket 连接

        Args:
            session_id: 会话 ID
        """
        if session_id in self._websockets:
            del self._websockets[session_id]
            logger.info(f"Unregistered WebSocket for session: {session_id}")

    async def receive_message(
        self,
        session_id: str,
        content: str,
        sender: str | None = None
    ) -> None:
        """
        接收来自客户端的消息

        创建 ChannelMessage 并触发回调。

        Args:
            session_id: 会话 ID
            content: 消息内容
            sender: 发送者标识 (可选)
        """
        # 确保会话存在
        self.get_or_create_session(session_id)

        # 更新最后活动时间
        self._sessions[session_id]["last_activity"] = datetime.now()

        # 创建消息
        message = ChannelMessage(
            session_key=f"webchat:{session_id}",
            content=content,
            sender=sender or session_id,
            channel=self.name,
        )

        # 触发回调
        await self._emit_message(message)

        logger.debug(
            f"Received message from session {session_id}",
            extra_data={"content_length": len(content)}
        )

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        """
        获取会话的待发送消息队列

        Args:
            session_id: 会话 ID

        Returns:
            消息列表
        """
        if session_id not in self._sessions:
            return []

        messages = self._sessions[session_id].get("message_queue", [])
        # 清空队列
        self._sessions[session_id]["message_queue"] = []

        return messages

    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            清理的会话数
        """
        now = datetime.now()
        expired = []

        for session_id, session_data in self._sessions.items():
            last_activity = session_data.get("last_activity", session_data["created_at"])
            age = (now - last_activity).total_seconds()

            if age > self.session_timeout:
                expired.append(session_id)

        # 删除过期会话
        for session_id in expired:
            del self._sessions[session_id]
            if session_id in self._websockets:
                del self._websockets[session_id]

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)
