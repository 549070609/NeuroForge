"""
Webhook Channel Tests
"""

import pytest
import hmac
import hashlib
import json
from unittest.mock import MagicMock

from pyagentforge.capabilities.channels.webhook import WebhookChannel
from pyagentforge.capabilities.channels.base import ChannelStatus


class TestWebhookChannel:
    """Webhook 通道测试"""

    @pytest.fixture
    def channel(self):
        """创建通道实例"""
        return WebhookChannel({})

    @pytest.fixture
    def channel_with_secret(self):
        """创建带默认密钥的通道"""
        return WebhookChannel({"default_secret": "default_key"})

    @pytest.mark.asyncio
    async def test_initialize(self, channel):
        """测试初始化"""
        assert channel.status == ChannelStatus.DISCONNECTED

        await channel.initialize()

        assert channel.status == ChannelStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_start_stop(self, channel):
        """测试启动和停止"""
        await channel.initialize()
        await channel.start()

        # 停止
        await channel.stop()

        assert channel.status == ChannelStatus.DISCONNECTED
        assert len(channel._handlers) == 0

    @pytest.mark.asyncio
    async def test_register_handler(self, channel):
        """测试注册处理器"""
        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/test", handler)

        assert "/test" in channel._handlers
        assert channel._handlers["/test"]["handler"] == handler

    @pytest.mark.asyncio
    async def test_register_handler_with_secret(self, channel):
        """测试注册带密钥的处理器"""
        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/secure", handler, secret="my_secret")

        assert channel._handlers["/secure"]["secret"] == "my_secret"

    @pytest.mark.asyncio
    async def test_unregister_handler(self, channel):
        """测试注销处理器"""
        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/test", handler)

        result = channel.unregister_handler("/test")

        assert result is True
        assert "/test" not in channel._handlers

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_handler(self, channel):
        """测试注销不存在的处理器"""
        result = channel.unregister_handler("/nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_webhook(self, channel):
        """测试处理 Webhook"""
        await channel.initialize()

        received = []

        async def handler(payload, headers):
            received.append(payload)
            return {"status": "ok"}

        channel.register_handler("/test", handler)

        result = await channel.handle_webhook(
            path="/test",
            payload={"event": "push"},
            headers={}
        )

        assert result == {"status": "ok"}
        assert len(received) == 1
        assert received[0] == {"event": "push"}

    @pytest.mark.asyncio
    async def test_handle_webhook_unregistered_path(self, channel):
        """测试处理未注册的路径"""
        await channel.initialize()

        with pytest.raises(ValueError, match="No handler registered"):
            await channel.handle_webhook(
                path="/unregistered",
                payload={},
                headers={}
            )

    @pytest.mark.asyncio
    async def test_handle_webhook_with_signature(self, channel):
        """测试带签名的 Webhook"""
        await channel.initialize()

        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/secure", handler, secret="my_secret")

        # 生成有效签名
        payload = {"test": "data"}
        signature = "sha256=" + hmac.new(
            b"my_secret",
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()

        # 应该成功
        result = await channel.handle_webhook(
            path="/secure",
            payload=payload,
            headers={"X-Hub-Signature-256": signature}
        )

        assert result == "ok"

        # 无效签名应该失败
        with pytest.raises(PermissionError, match="signature verification failed"):
            await channel.handle_webhook(
                path="/secure",
                payload=payload,
                headers={"X-Hub-Signature-256": "invalid"}
            )

    @pytest.mark.asyncio
    async def test_handle_webhook_with_default_secret(self, channel_with_secret):
        """测试使用默认密钥"""
        await channel_with_secret.initialize()

        async def handler(payload, headers):
            return "ok"

        # 注册时不指定密钥，应该使用默认密钥
        channel_with_secret.register_handler("/secure", handler)

        # 使用默认密钥生成签名
        payload = {"test": "data"}
        signature = "sha256=" + hmac.new(
            b"default_key",
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()

        result = await channel_with_secret.handle_webhook(
            path="/secure",
            payload=payload,
            headers={"X-Hub-Signature-256": signature}
        )

        assert result == "ok"

    @pytest.mark.asyncio
    async def test_webhook_message_emission(self, channel):
        """测试 Webhook 消息触发"""
        await channel.initialize()

        received_messages = []

        async def message_callback(msg):
            received_messages.append(msg)

        channel.on_message(message_callback)

        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/github/webhook", handler, auto_create_session=True)

        await channel.handle_webhook(
            path="/github/webhook",
            payload={"event": "push"},
            headers={"User-Agent": "GitHub-Hookshot"}
        )

        assert len(received_messages) == 1
        assert received_messages[0].channel == "webhook"
        assert received_messages[0].session_key == "webhook:github:webhook"
        assert received_messages[0].sender == "GitHub-Hookshot"

    @pytest.mark.asyncio
    async def test_webhook_no_message_emission(self, channel):
        """测试禁用消息触发"""
        await channel.initialize()

        received_messages = []

        async def message_callback(msg):
            received_messages.append(msg)

        channel.on_message(message_callback)

        async def handler(payload, headers):
            return "ok"

        # 禁用自动创建会话
        channel.register_handler(
            "/test",
            handler,
            auto_create_session=False
        )

        await channel.handle_webhook(
            path="/test",
            payload={},
            headers={}
        )

        # 不应该触发消息
        assert len(received_messages) == 0

    @pytest.mark.asyncio
    async def test_send_message_not_supported(self, channel):
        """测试发送消息不支持"""
        await channel.initialize()

        result = await channel.send_message(
            to="test",
            content="test"
        )

        assert result.success is False
        assert "does not support sending" in result.error

    @pytest.mark.asyncio
    async def test_get_channel_info(self, channel):
        """测试获取通道信息"""
        await channel.initialize()

        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/test1", handler)
        channel.register_handler("/test2", handler, secret="secret")

        info = await channel.get_channel_info()

        assert info["name"] == "webhook"
        assert info["status"] == "connected"
        assert info["registered_webhooks"] == 2
        assert "/test1" in info["webhook_paths"]
        assert "/test2" in info["webhook_paths"]

    @pytest.mark.asyncio
    async def test_list_handlers(self, channel):
        """测试列出处理器"""
        async def handler(payload, headers):
            return "ok"

        channel.register_handler("/test1", handler)
        channel.register_handler("/test2", handler, secret="secret")
        channel.register_handler("/test3", handler, auto_create_session=False)

        handlers = channel.list_handlers()

        assert len(handlers) == 3
        assert any(h["path"] == "/test1" and not h["has_secret"] for h in handlers)
        assert any(h["path"] == "/test2" and h["has_secret"] for h in handlers)
        assert any(h["path"] == "/test3" and not h["auto_create_session"] for h in handlers)

    @pytest.mark.asyncio
    async def test_sync_handler(self, channel):
        """测试同步处理器"""
        await channel.initialize()

        def sync_handler(payload, headers):
            return {"sync": True}

        channel.register_handler("/sync", sync_handler)

        result = await channel.handle_webhook(
            path="/sync",
            payload={},
            headers={}
        )

        assert result == {"sync": True}

    @pytest.mark.asyncio
    async def test_handler_exception(self, channel):
        """测试处理器抛出异常"""
        await channel.initialize()

        async def error_handler(payload, headers):
            raise ValueError("Handler error")

        channel.register_handler("/error", error_handler)

        with pytest.raises(ValueError, match="Handler error"):
            await channel.handle_webhook(
                path="/error",
                payload={},
                headers={}
            )


class TestWebhookSignature:
    """Webhook 签名测试"""

    @pytest.fixture
    def channel(self):
        """创建通道实例"""
        return WebhookChannel({})

    def test_verify_valid_signature(self, channel):
        """测试验证有效签名"""
        payload = {"test": "data"}
        secret = "my_secret"

        signature = "sha256=" + hmac.new(
            secret.encode(),
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()

        result = channel._verify_signature(payload, signature, secret)

        assert result is True

    def test_verify_invalid_signature(self, channel):
        """测试验证无效签名"""
        payload = {"test": "data"}
        secret = "my_secret"

        result = channel._verify_signature(payload, "sha256=invalid", secret)

        assert result is False

    def test_verify_wrong_secret(self, channel):
        """测试错误密钥"""
        payload = {"test": "data"}

        signature = "sha256=" + hmac.new(
            b"correct_secret",
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()

        result = channel._verify_signature(payload, signature, "wrong_secret")

        assert result is False

    def test_verify_malformed_signature(self, channel):
        """测试格式错误的签名"""
        payload = {"test": "data"}

        result = channel._verify_signature(payload, "not_sha256_format", "secret")

        assert result is False
