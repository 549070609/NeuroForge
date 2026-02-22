"""
WebChat Channel - Web 聊天通道

提供 WebChat 会话与消息通道能力。
对外 REST/WebSocket 入口由 `main/Service` 网关统一承载。
"""

from pyagentforge.capabilities.channels.webchat.channel import WebChatChannel

__all__ = ["WebChatChannel"]
