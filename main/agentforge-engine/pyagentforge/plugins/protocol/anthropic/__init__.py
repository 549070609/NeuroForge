"""Anthropic 系协议适配插件。

包含：
- ``AnthropicMessagesProtocol`` (``api_type = anthropic-messages``)：Anthropic Messages API。
"""

from __future__ import annotations

from pyagentforge.plugins.protocol.anthropic.messages import AnthropicMessagesProtocol

__all__ = ["AnthropicMessagesProtocol"]
