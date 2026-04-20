"""
Channel Base - 通道适配器基类

定义所有消息通道的统一接口和消息格式。
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ChannelStatus(StrEnum):
    """
    通道状态枚举

    Attributes:
        DISCONNECTED: 未连接
        CONNECTING: 连接中
        CONNECTED: 已连接
        ERROR: 错误状态
    """
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class ChannelMessage:
    """
    统一消息格式

    所有通道的消息都被标准化为此格式。

    Attributes:
        session_key: 会话标识，格式 "{channel}:{conversation_id}"
        content: 消息文本内容
        sender: 发送者标识
        channel: 通道类型 (telegram, discord, webchat 等)
        metadata: 元数据 (平台特定信息)
        attachments: 附件列表 (图片、文件等)
        reply_to: 回复的消息 ID

    Examples:
        >>> msg = ChannelMessage(
        ...     session_key="telegram:123",
        ...     content="Hello!",
        ...     sender="user_456",
        ...     channel="telegram"
        ... )
        >>> str(msg.session_key)
        'telegram:123'
    """
    session_key: str
    content: str
    sender: str
    channel: str
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[dict] | None = None
    reply_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_key": self.session_key,
            "content": self.content,
            "sender": self.sender,
            "channel": self.channel,
            "metadata": self.metadata,
            "attachments": self.attachments,
            "reply_to": self.reply_to,
        }


@dataclass
class SendMessageResult:
    """
    消息发送结果

    Attributes:
        success: 是否成功
        message_id: 消息 ID (成功时)
        error: 错误信息 (失败时)
    """
    success: bool
    message_id: str | None = None
    error: str | None = None


# 回调类型
MessageCallback = Callable[[ChannelMessage], Coroutine[Any, Any, None]]


class BaseChannel(ABC):
    """
    通道适配器抽象基类

    所有消息通道必须实现此接口。

    Class Attributes:
        name: 通道名称 (如 "telegram", "discord")
        version: 通道版本

    Attributes:
        config: 通道配置
        status: 当前状态

    Lifecycle:
        1. __init__(config) - 创建实例
        2. initialize() - 初始化连接
        3. start() - 开始监听
        4. [运行中] - 处理消息
        5. stop() - 停止通道
    """

    name: str = "base"
    version: str = "1.0.0"

    def __init__(self, config: dict[str, Any]):
        """
        初始化通道

        Args:
            config: 通道配置字典
        """
        self.config = config
        self._status = ChannelStatus.DISCONNECTED
        self._message_callback: MessageCallback | None = None

    @property
    def status(self) -> ChannelStatus:
        """获取当前状态"""
        return self._status

    def _set_status(self, status: ChannelStatus) -> None:
        """设置状态 (内部方法)"""
        self._status = status

    @abstractmethod
    async def initialize(self) -> None:
        """
        初始化通道连接

        建立连接、验证凭据、加载配置等。
        初始化成功后状态应变为 CONNECTED。
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        启动通道监听

        开始监听入站消息，调用 on_message 注册的回调。
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        停止通道

        断开连接、释放资源。
        停止后状态应变为 DISCONNECTED。
        """
        pass

    @abstractmethod
    async def send_message(
        self,
        to: str,
        content: str,
        **kwargs: Any
    ) -> SendMessageResult:
        """
        发送消息

        Args:
            to: 目标 (会话 ID、用户 ID 等)
            content: 消息内容
            **kwargs: 额外参数 (如 attachments, reply_to 等)

        Returns:
            发送结果
        """
        pass

    def on_message(self, callback: MessageCallback) -> None:
        """
        注册消息回调

        当收到入站消息时调用此回调。

        Args:
            callback: 异步回调函数

        Examples:
            >>> async def handle_message(msg: ChannelMessage):
            ...     print(f"Received: {msg.content}")
            >>> channel.on_message(handle_message)
        """
        self._message_callback = callback

    async def _emit_message(self, message: ChannelMessage) -> None:
        """
        触发消息回调 (内部方法)

        子类在收到消息时应调用此方法。

        Args:
            message: 收到的消息
        """
        if self._message_callback:
            await self._message_callback(message)

    @abstractmethod
    async def get_channel_info(self) -> dict[str, Any]:
        """
        获取通道信息

        Returns:
            通道信息字典，至少包含:
            - name: 通道名称
            - status: 当前状态
            - version: 版本号
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} status={self._status.value}>"
