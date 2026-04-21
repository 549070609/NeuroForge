"""
Webhook Channel - Webhook 接收通道

提供通用的 Webhook 接收能力，支持 HMAC 签名验证。
"""

import hashlib
import hmac
import json
from collections.abc import Callable
from typing import Any

from pyagentforge.capabilities.channels.base import (
    BaseChannel,
    ChannelMessage,
    ChannelStatus,
    SendMessageResult,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


# Webhook 处理器类型
WebhookHandler = Callable[[dict[str, Any], dict[str, str]], Any]


class WebhookChannel(BaseChannel):
    """
    Webhook 通道

    提供 Webhook 接收能力：
    - 支持多个 Webhook 路径
    - HMAC 签名验证
    - 自动创建 session

    Examples:
        >>> channel = WebhookChannel({})
        >>> await channel.initialize()
        >>>
        >>> # 注册 Webhook 处理器
        >>> channel.register_handler(
        ...     path="/github/webhook",
        ...     handler=my_handler,
        ...     secret="github_secret"
        ... )
        >>>
        >>> # 处理 Webhook 请求
        >>> await channel.handle_webhook(
        ...     path="/github/webhook",
        ...     payload={"event": "push"},
        ...     headers={"X-Hub-Signature-256": "..."}
        ... )
    """

    name = "webhook"
    version = "1.0.0"

    def __init__(self, config: dict[str, Any]):
        """
        初始化 Webhook 通道

        Args:
            config: 配置字典
                - default_secret: 默认签名密钥 (可选)
        """
        super().__init__(config)

        self.default_secret = config.get("default_secret")

        # Webhook 处理器注册表: path -> handler_info
        self._handlers: dict[str, dict[str, Any]] = {}

        logger.info("Webhook channel created")

    async def initialize(self) -> None:
        """
        初始化通道

        准备处理器注册表。
        """
        self._set_status(ChannelStatus.CONNECTING)
        self._set_status(ChannelStatus.CONNECTED)

        logger.info(
            "Webhook channel initialized",
            extra_data={"status": self.status.value}
        )

    async def start(self) -> None:
        """
        启动通道

        开始接受 Webhook 请求。实际请求由 HTTP 服务器处理。
        """
        if self.status != ChannelStatus.CONNECTED:
            raise RuntimeError("Channel must be initialized before starting")

        logger.info(
            "Webhook channel started",
            extra_data={"registered_paths": list(self._handlers.keys())}
        )

    async def stop(self) -> None:
        """
        停止通道

        清理所有处理器。
        """
        self._handlers.clear()
        self._set_status(ChannelStatus.DISCONNECTED)

        logger.info("Webhook channel stopped")

    async def send_message(
        self,
        _to: str = "",
        _content: str = "",
        **_kwargs: Any
    ) -> SendMessageResult:
        """
        发送消息 (Webhook 通道不支持主动发送)

        Webhook 是被动接收通道，不能主动发送消息。

        Returns:
            失败结果
        """
        return SendMessageResult(
            success=False,
            error="Webhook channel does not support sending messages"
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
            "registered_webhooks": len(self._handlers),
            "webhook_paths": list(self._handlers.keys()),
        }

    # === Webhook 特有方法 ===

    def register_handler(
        self,
        path: str,
        handler: WebhookHandler,
        secret: str | None = None,
        auto_create_session: bool = True,
    ) -> None:
        """
        注册 Webhook 处理器

        Args:
            path: Webhook 路径 (如 "/github/webhook")
            handler: 处理函数 (payload, headers) -> response
            secret: 签名验证密钥 (可选)
            auto_create_session: 是否自动创建会话 (默认 True)

        Examples:
            >>> async def github_handler(payload, headers):
            ...     print(f"Received: {payload}")
            ...     return {"status": "ok"}
            >>>
            >>> channel.register_handler(
            ...     "/github/webhook",
            ...     github_handler,
            ...     secret="my_secret"
            ... )
        """
        self._handlers[path] = {
            "handler": handler,
            "secret": secret or self.default_secret,
            "auto_create_session": auto_create_session,
        }

        logger.info(
            "Registered webhook handler",
            extra_data={
                "path": path,
                "has_secret": secret is not None,
                "auto_create_session": auto_create_session,
            }
        )

    def unregister_handler(self, path: str) -> bool:
        """
        注销 Webhook 处理器

        Args:
            path: Webhook 路径

        Returns:
            是否成功注销
        """
        if path in self._handlers:
            del self._handlers[path]
            logger.info(f"Unregistered webhook handler: {path}")
            return True
        return False

    async def handle_webhook(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str]
    ) -> Any:
        """
        处理 Webhook 请求

        验证签名、调用处理器、触发消息回调。

        Args:
            path: Webhook 路径
            payload: 请求体 (JSON)
            headers: 请求头

        Returns:
            处理器返回的响应

        Raises:
            ValueError: 路径未注册
            PermissionError: 签名验证失败
        """
        # 检查路径是否注册
        if path not in self._handlers:
            raise ValueError(f"No handler registered for path: {path}")

        handler_info = self._handlers[path]

        # 验证签名
        if handler_info.get("secret"):
            signature = headers.get("X-Hub-Signature-256", "")
            if not self._verify_signature(
                payload,
                signature,
                handler_info["secret"]
            ):
                raise PermissionError("Webhook signature verification failed")

        # 调用处理器
        handler = handler_info["handler"]

        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                result = await handler(payload, headers)
            else:
                result = handler(payload, headers)

            logger.debug(
                "Webhook handled successfully",
                extra_data={"path": path}
            )

            # 触发消息回调
            if handler_info.get("auto_create_session", True):
                await self._emit_webhook_message(path, payload, headers)

            return result

        except Exception as e:
            logger.error(
                "Webhook handler error",
                extra_data={"path": path, "error": str(e)}
            )
            raise

    async def _emit_webhook_message(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str]
    ) -> None:
        """
        触发 Webhook 消息回调

        将 Webhook 事件转换为 ChannelMessage。

        Args:
            path: Webhook 路径
            payload: 请求体
            headers: 请求头
        """
        # 使用 path 作为 session_key 的一部分
        session_key = f"webhook:{path.strip('/').replace('/', ':')}"

        # 创建消息
        message = ChannelMessage(
            session_key=session_key,
            content=json.dumps(payload),
            sender=headers.get("User-Agent", "webhook"),
            channel=self.name,
            metadata={
                "path": path,
                "headers": headers,
                "payload": payload,
            }
        )

        await self._emit_message(message)

    def _verify_signature(
        self,
        payload: dict[str, Any],
        signature: str,
        secret: str
    ) -> bool:
        """
        验证 Webhook 签名

        Args:
            payload: 请求体
            signature: 签名 (格式: "sha256=...")
            secret: 密钥

        Returns:
            是否验证通过
        """
        try:
            # 计算期望的签名
            expected = "sha256=" + hmac.new(
                secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()

            # 常量时间比较
            return hmac.compare_digest(signature, expected)

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def list_handlers(self) -> list[dict[str, Any]]:
        """
        列出所有注册的处理器

        Returns:
            处理器信息列表
        """
        return [
            {
                "path": path,
                "has_secret": info.get("secret") is not None,
                "auto_create_session": info.get("auto_create_session", True),
            }
            for path, info in self._handlers.items()
        ]
