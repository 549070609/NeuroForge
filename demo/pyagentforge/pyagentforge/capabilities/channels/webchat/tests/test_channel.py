"""
WebChat Channel Tests
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from pyagentforge.capabilities.channels.webchat import WebChatChannel
from pyagentforge.capabilities.channels.base import ChannelStatus, ChannelMessage


class TestWebChatChannel:
    """WebChat 通道测试"""

    @pytest.fixture
    def channel(self):
        """创建通道实例"""
        return WebChatChannel({
            "max_sessions": 10,
            "session_timeout": 3600,
        })

    @pytest.mark.asyncio
    async def test_initialize(self, channel):
        """测试初始化"""
        assert channel.status == ChannelStatus.DISCONNECTED

        await channel.initialize()

        assert channel.status == ChannelStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_initialize_with_invalid_config(self):
        """测试无效配置"""
        # 无效 max_sessions
        channel = WebChatChannel({"max_sessions": 0})
        with pytest.raises(ValueError):
            await channel.initialize()

        # 无效 session_timeout
        channel = WebChatChannel({"session_timeout": -1})
        with pytest.raises(ValueError):
            await channel.initialize()

    @pytest.mark.asyncio
    async def test_start_stop(self, channel):
        """测试启动和停止"""
        await channel.initialize()
        await channel.start()

        # 停止
        await channel.stop()

        assert channel.status == ChannelStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_create_session(self, channel):
        """测试创建会话"""
        await channel.initialize()

        session_id = channel.create_session()

        assert session_id is not None
        assert session_id in channel._sessions
        assert len(channel._sessions) == 1

    @pytest.mark.asyncio
    async def test_create_session_with_custom_id(self, channel):
        """测试创建自定义 ID 会话"""
        await channel.initialize()

        session_id = channel.create_session("custom-session-123")

        assert session_id == "custom-session-123"
        assert "custom-session-123" in channel._sessions

    @pytest.mark.asyncio
    async def test_create_session_max_limit(self, channel):
        """测试会话数限制"""
        await channel.initialize()

        # 创建最大数量的会话
        for i in range(channel.max_sessions):
            channel.create_session()

        # 应该抛出异常
        with pytest.raises(ValueError, match="Maximum sessions reached"):
            channel.create_session()

    @pytest.mark.asyncio
    async def test_get_or_create_session(self, channel):
        """测试获取或创建会话"""
        await channel.initialize()

        # 创建新会话
        session_id = channel.get_or_create_session("session-1")
        assert session_id == "session-1"

        # 获取现有会话
        session_id2 = channel.get_or_create_session("session-1")
        assert session_id2 == "session-1"
        assert len(channel._sessions) == 1

    @pytest.mark.asyncio
    async def test_register_websocket(self, channel):
        """测试注册 WebSocket"""
        await channel.initialize()

        ws = MagicMock()
        channel.register_websocket("session-1", ws)

        assert "session-1" in channel._websockets
        assert channel._websockets["session-1"] == ws

    @pytest.mark.asyncio
    async def test_unregister_websocket(self, channel):
        """测试注销 WebSocket"""
        await channel.initialize()

        ws = MagicMock()
        channel.register_websocket("session-1", ws)
        channel.unregister_websocket("session-1")

        assert "session-1" not in channel._websockets

    @pytest.mark.asyncio
    async def test_send_message_via_websocket(self, channel):
        """测试通过 WebSocket 发送消息"""
        await channel.initialize()

        # 创建会话和 WebSocket
        session_id = channel.create_session()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        channel.register_websocket(session_id, ws)

        # 发送消息
        result = await channel.send_message(
            to=session_id,
            content="Hello, World!"
        )

        assert result.success is True
        assert result.message_id is not None
        assert ws.send_json.called

    @pytest.mark.asyncio
    async def test_send_message_without_websocket(self, channel):
        """测试无 WebSocket 时发送消息（入队）"""
        await channel.initialize()

        session_id = channel.create_session()

        # 发送消息（无 WebSocket）
        result = await channel.send_message(
            to=session_id,
            content="Hello, World!"
        )

        assert result.success is True

        # 检查消息队列
        messages = channel.get_session_messages(session_id)
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_session(self, channel):
        """测试发送到不存在的会话"""
        await channel.initialize()

        result = await channel.send_message(
            to="nonexistent",
            content="Test"
        )

        assert result.success is False
        assert "Session not found" in result.error

    @pytest.mark.asyncio
    async def test_receive_message(self, channel):
        """测试接收消息"""
        await channel.initialize()

        received_messages = []

        async def callback(msg: ChannelMessage):
            received_messages.append(msg)

        channel.on_message(callback)

        # 接收消息
        await channel.receive_message(
            session_id="session-1",
            content="Test message",
            sender="user-123"
        )

        assert len(received_messages) == 1
        assert received_messages[0].content == "Test message"
        assert received_messages[0].sender == "user-123"
        assert received_messages[0].channel == "webchat"
        assert received_messages[0].session_key == "webchat:session-1"

    @pytest.mark.asyncio
    async def test_get_channel_info(self, channel):
        """测试获取通道信息"""
        await channel.initialize()

        channel.create_session("s1")
        channel.create_session("s2")

        info = await channel.get_channel_info()

        assert info["name"] == "webchat"
        assert info["version"] == "1.0.0"
        assert info["status"] == "connected"
        assert info["active_sessions"] == 2
        assert info["max_sessions"] == 10

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, channel):
        """测试清理过期会话"""
        await channel.initialize()

        # 创建会话
        session_id = channel.create_session()

        # 手动设置最后活动时间为很久以前
        channel._sessions[session_id]["last_activity"] = (
            datetime.now() - timedelta(seconds=channel.session_timeout + 1)
        )

        # 清理过期会话
        cleaned = channel.cleanup_expired_sessions()

        assert cleaned == 1
        assert session_id not in channel._sessions

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_with_websocket(self, channel):
        """测试清理带 WebSocket 的过期会话"""
        await channel.initialize()

        # 创建会话和 WebSocket
        session_id = channel.create_session()
        ws = MagicMock()
        channel.register_websocket(session_id, ws)

        # 设置过期
        channel._sessions[session_id]["last_activity"] = (
            datetime.now() - timedelta(seconds=channel.session_timeout + 1)
        )

        # 清理
        cleaned = channel.cleanup_expired_sessions()

        assert cleaned == 1
        assert session_id not in channel._sessions
        assert session_id not in channel._websockets

    @pytest.mark.asyncio
    async def test_message_queue_management(self, channel):
        """测试消息队列管理"""
        await channel.initialize()

        session_id = channel.create_session()

        # 发送多条消息
        for i in range(5):
            await channel.send_message(
                to=session_id,
                content=f"Message {i}"
            )

        # 获取消息队列
        messages = channel.get_session_messages(session_id)

        assert len(messages) == 5

        # 队列应该被清空
        messages2 = channel.get_session_messages(session_id)
        assert len(messages2) == 0


class TestWebChatChannelStreaming:
    """流式消息测试"""

    @pytest.fixture
    def channel(self):
        """创建通道实例"""
        return WebChatChannel({})

    @pytest.mark.asyncio
    async def test_send_streaming_message(self, channel):
        """测试发送流式消息"""
        await channel.initialize()

        session_id = channel.create_session()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        channel.register_websocket(session_id, ws)

        # 发送流式块
        result = await channel.send_message(
            to=session_id,
            content="Chunk 1",
            message_type="stream",
            stream_chunk=1,
            is_final=False
        )

        assert result.success is True

        # 验证发送的消息
        call_args = ws.send_json.call_args
        message = call_args[0][0]

        assert message["type"] == "stream"
        assert message["content"] == "Chunk 1"
        assert message["stream_chunk"] == 1
        assert message["is_final"] is False

    @pytest.mark.asyncio
    async def test_send_final_stream_chunk(self, channel):
        """测试发送最后一个流式块"""
        await channel.initialize()

        session_id = channel.create_session()
        ws = MagicMock()
        ws.send_json = AsyncMock()
        channel.register_websocket(session_id, ws)

        # 发送最后一个块
        result = await channel.send_message(
            to=session_id,
            content="Final chunk",
            message_type="stream",
            stream_chunk=10,
            is_final=True
        )

        assert result.success is True

        # 验证发送的消息
        call_args = ws.send_json.call_args
        message = call_args[0][0]

        assert message["is_final"] is True
