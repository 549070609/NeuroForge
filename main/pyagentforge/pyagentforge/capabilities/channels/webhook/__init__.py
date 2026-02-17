"""
Webhook Channel - Webhook 接收通道

提供通用的 Webhook 接收能力，支持 HMAC 签名验证。
"""

from pyagentforge.capabilities.channels.webhook.channel import WebhookChannel

__all__ = ["WebhookChannel"]
