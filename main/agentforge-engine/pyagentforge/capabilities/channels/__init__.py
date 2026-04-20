"""
Channel Adapters - 消息通道适配器

提供统一的多通道消息接入能力。

核心组件:
- BaseChannel: 通道适配器抽象基类
- ChannelMessage: 统一消息格式
- ChannelStatus: 通道状态枚举
- SendMessageResult: 消息发送结果
"""

from pyagentforge.capabilities.channels.base import (
    BaseChannel,
    ChannelMessage,
    ChannelStatus,
    SendMessageResult,
)

__all__ = [
    "ChannelStatus",
    "ChannelMessage",
    "SendMessageResult",
    "BaseChannel",
]
