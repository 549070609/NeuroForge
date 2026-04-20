"""
Channel Base 单元测试
"""

import pytest

from pyagentforge.capabilities.channels.base import (
    BaseChannel,
    ChannelMessage,
    ChannelStatus,
    SendMessageResult,
)


class TestChannelStatus:
    """测试 ChannelStatus 枚举"""

    def test_status_values(self):
        """状态值"""
        assert ChannelStatus.DISCONNECTED.value == "disconnected"
        assert ChannelStatus.CONNECTING.value == "connecting"
        assert ChannelStatus.CONNECTED.value == "connected"
        assert ChannelStatus.ERROR.value == "error"

    def test_status_string_comparison(self):
        """字符串比较"""
        assert ChannelStatus.CONNECTED == "connected"
        assert ChannelStatus.DISCONNECTED != "connected"


class TestChannelMessage:
    """测试 ChannelMessage"""

    def test_create_simple_message(self):
        """创建简单消息"""
        msg = ChannelMessage(
            session_key="telegram:123",
            content="Hello!",
            sender="user_456",
            channel="telegram"
        )
        assert msg.session_key == "telegram:123"
        assert msg.content == "Hello!"
        assert msg.sender == "user_456"
        assert msg.channel == "telegram"
        assert msg.metadata == {}
        assert msg.attachments is None
        assert msg.reply_to is None

    def test_create_message_with_metadata(self):
        """带元数据的消息"""
        msg = ChannelMessage(
            session_key="discord:789",
            content="Test",
            sender="user",
            channel="discord",
            metadata={"guild_id": "12345", "channel_name": "general"}
        )
        assert msg.metadata["guild_id"] == "12345"

    def test_create_message_with_attachments(self):
        """带附件的消息"""
        msg = ChannelMessage(
            session_key="telegram:123",
            content="Check this image",
            sender="user",
            channel="telegram",
            attachments=[{"type": "image", "url": "https://example.com/img.jpg"}]
        )
        assert len(msg.attachments) == 1
        assert msg.attachments[0]["type"] == "image"

    def test_message_to_dict(self):
        """消息转字典"""
        msg = ChannelMessage(
            session_key="webchat:abc",
            content="Hi",
            sender="guest",
            channel="webchat",
            reply_to="msg_001"
        )
        d = msg.to_dict()
        assert d["session_key"] == "webchat:abc"
        assert d["content"] == "Hi"
        assert d["sender"] == "guest"
        assert d["channel"] == "webchat"
        assert d["reply_to"] == "msg_001"


class TestSendMessageResult:
    """测试 SendMessageResult"""

    def test_success_result(self):
        """成功结果"""
        result = SendMessageResult(success=True, message_id="msg_123")
        assert result.success is True
        assert result.message_id == "msg_123"
        assert result.error is None

    def test_failure_result(self):
        """失败结果"""
        result = SendMessageResult(success=False, error="Network error")
        assert result.success is False
        assert result.message_id is None
        assert result.error == "Network error"


class ConcreteChannel(BaseChannel):
    """用于测试的具体通道实现"""

    name = "test_channel"
    version = "1.0.0"

    async def initialize(self) -> None:
        self._set_status(ChannelStatus.CONNECTED)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._set_status(ChannelStatus.DISCONNECTED)

    async def send_message(self, to: str, content: str, **kwargs) -> SendMessageResult:
        return SendMessageResult(success=True, message_id="test_msg_001")

    async def get_channel_info(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "version": self.version,
        }


class TestBaseChannel:
    """测试 BaseChannel"""

    def test_cannot_instantiate_abc(self):
        """不能直接实例化抽象类"""
        with pytest.raises(TypeError):
            BaseChannel({})  # type: ignore

    def test_concrete_channel_creation(self):
        """创建具体通道"""
        channel = ConcreteChannel({"token": "test_token"})
        assert channel.name == "test_channel"
        assert channel.version == "1.0.0"
        assert channel.status == ChannelStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_initialize(self):
        """初始化通道"""
        channel = ConcreteChannel({})
        assert channel.status == ChannelStatus.DISCONNECTED
        await channel.initialize()
        assert channel.status == ChannelStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_stop(self):
        """停止通道"""
        channel = ConcreteChannel({})
        await channel.initialize()
        assert channel.status == ChannelStatus.CONNECTED
        await channel.stop()
        assert channel.status == ChannelStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_send_message(self):
        """发送消息"""
        channel = ConcreteChannel({})
        result = await channel.send_message("user_123", "Hello!")
        assert result.success is True
        assert result.message_id == "test_msg_001"

    @pytest.mark.asyncio
    async def test_get_channel_info(self):
        """获取通道信息"""
        channel = ConcreteChannel({})
        await channel.initialize()
        info = await channel.get_channel_info()
        assert info["name"] == "test_channel"
        assert info["status"] == "connected"
        assert info["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_message_callback(self):
        """消息回调"""
        channel = ConcreteChannel({})
        received_messages = []

        async def callback(msg: ChannelMessage):
            received_messages.append(msg)

        channel.on_message(callback)

        # 模拟收到消息
        test_msg = ChannelMessage(
            session_key="test:123",
            content="Test message",
            sender="user",
            channel="test"
        )
        await channel._emit_message(test_msg)

        assert len(received_messages) == 1
        assert received_messages[0].content == "Test message"

    def test_repr(self):
        """字符串表示"""
        channel = ConcreteChannel({})
        repr_str = repr(channel)
        assert "ConcreteChannel" in repr_str
        assert "test_channel" in repr_str
        assert "disconnected" in repr_str
