"""OpenAI 系协议适配插件。

包含：
- ``OpenAIChatProtocol`` (``api_type = openai-completions``)：OpenAI Chat Completions 兼容端点。
- ``OpenAIResponsesProtocol`` (``api_type = openai-responses``)：OpenAI Responses API。

本模块本身不会自动注册到全局 ``PROTOCOL_ADAPTERS``，而是通过
``pyagentforge.protocol_adapters`` 这个 entry_points 组由 kernel 启动时自动发现，
或由 :func:`pyagentforge.protocols._load_bundled_adapters` 作为兜底加载。
"""

from __future__ import annotations

from pyagentforge.plugins.protocol.openai.chat import OpenAIChatProtocol
from pyagentforge.plugins.protocol.openai.responses import OpenAIResponsesProtocol

__all__ = ["OpenAIChatProtocol", "OpenAIResponsesProtocol"]
