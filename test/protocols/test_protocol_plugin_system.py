"""Protocol adapter 插件化端到端测试。

覆盖：
1. 内置 OpenAI / Anthropic adapter 位于 pyagentforge.plugins.protocol.* 子包。
2. ModelConfig.api_type 接受任意字符串（不再是硬编码 Literal）。
3. 自定义 adapter 通过 register_protocol_adapter 即可被 LLMClient 识别。
4. protocols 模块提供向后兼容的 class re-export。
5. 未注册 api_type 在调用时抛出 Unsupported api_type。
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from pyagentforge.client import LLMClient
from pyagentforge.kernel.message import ProviderResponse, TextBlock
from pyagentforge.kernel.model_registry import ModelConfig, ModelRegistry
from pyagentforge.protocols import (
    PROTOCOL_ADAPTERS,
    BaseProtocolAdapter,
    register_protocol_adapter,
)


# ------------------------------------------------------------------ #
# 1) 内置 adapter 的物理位置与自动装配
# ------------------------------------------------------------------ #

def test_builtin_adapters_live_under_plugins_protocol():
    """OpenAI / Anthropic 具体实现必须位于 plugins.protocol 子包下（而非 kernel）。"""
    from pyagentforge.plugins.protocol.anthropic.messages import AnthropicMessagesProtocol
    from pyagentforge.plugins.protocol.openai.chat import OpenAIChatProtocol
    from pyagentforge.plugins.protocol.openai.responses import OpenAIResponsesProtocol

    assert OpenAIChatProtocol.__module__ == "pyagentforge.plugins.protocol.openai.chat"
    assert OpenAIResponsesProtocol.__module__ == "pyagentforge.plugins.protocol.openai.responses"
    assert AnthropicMessagesProtocol.__module__ == (
        "pyagentforge.plugins.protocol.anthropic.messages"
    )


def test_builtin_adapters_auto_bootstrapped():
    """import pyagentforge.protocols 后三个内置协议必已在 registry 中。"""
    assert "openai-completions" in PROTOCOL_ADAPTERS
    assert "openai-responses" in PROTOCOL_ADAPTERS
    assert "anthropic-messages" in PROTOCOL_ADAPTERS


def test_backward_compat_reexport_from_protocols_module():
    """旧代码 ``from pyagentforge.protocols import OpenAIChatProtocol`` 必须仍可用。"""
    from pyagentforge import protocols as p

    cls = p.OpenAIChatProtocol
    assert issubclass(cls, BaseProtocolAdapter)
    assert cls().api_type == "openai-completions"


# ------------------------------------------------------------------ #
# 2) ApiType 开放：ModelConfig.api_type 接受任意字符串
# ------------------------------------------------------------------ #

def test_model_config_accepts_arbitrary_api_type_string():
    """api_type 不再受 Literal 约束，任意字符串均可通过 pydantic 校验。"""
    cfg = ModelConfig(
        id="m",
        name="m",
        provider="pv",
        api_type="my-brand-new-protocol-v2",
        base_url="https://example.invalid/v1",
    )
    assert cfg.api_type == "my-brand-new-protocol-v2"


# ------------------------------------------------------------------ #
# 3) 自定义 adapter 零改 kernel 接入
# ------------------------------------------------------------------ #

class _EchoProtocol(BaseProtocolAdapter):
    """最小自定义协议：POST base_url/echo，返回体直接当作文本回答。"""

    api_type = "test-echo-v1"
    endpoint = "/echo"

    def build_request(
        self, request_params: dict[str, Any], config: ModelConfig
    ) -> dict[str, Any]:
        return {
            "model": config.resolved_model_name,
            "messages": request_params.get("messages", []),
        }

    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        return ProviderResponse(
            content=[TextBlock(text=str(response.get("echo", "")))],
            stop_reason="end_turn",
            usage={"input_tokens": 0, "output_tokens": 0},
        )


@pytest.fixture
def echo_registered():
    register_protocol_adapter(_EchoProtocol(), override=True)
    yield
    PROTOCOL_ADAPTERS.unregister("test-echo-v1")


@pytest.mark.asyncio
async def test_custom_adapter_usable_end_to_end(echo_registered):
    """通过 register_protocol_adapter 注册后，LLMClient 立即可调度该协议。"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/echo")
        return httpx.Response(200, json={"echo": "hello from plugin"})

    transport = httpx.MockTransport(handler)

    registry = ModelRegistry(load_from_config=False)
    registry.register_model(
        ModelConfig(
            id="plugin-model",
            name="plugin-model",
            provider="plugin-vendor",
            api_type="test-echo-v1",
            base_url="https://example.invalid/v1",
            api_key="k",
            model_name="plugin-model",
        )
    )

    client = LLMClient(registry=registry, transport=transport)
    try:
        resp = await client.create_message(
            model_id="plugin-model",
            messages=[{"role": "user", "content": "hi"}],
        )
    finally:
        await client.aclose()

    assert resp.content[0].text == "hello from plugin"


# ------------------------------------------------------------------ #
# 4) 未注册 api_type 在调用时抛 Unsupported api_type（运行时注册表校验）
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_unregistered_api_type_raises_at_call_time():
    registry = ModelRegistry(load_from_config=False)
    registry.register_model(
        ModelConfig(
            id="ghost",
            name="ghost",
            provider="ghost-vendor",
            api_type="no-such-protocol-ever",
            base_url="https://example.invalid/v1",
            api_key="k",
        )
    )

    client = LLMClient(registry=registry)
    try:
        with pytest.raises(ValueError, match="Unsupported api_type"):
            await client.create_message(
                model_id="ghost",
                messages=[{"role": "user", "content": "x"}],
            )
    finally:
        await client.aclose()


# ------------------------------------------------------------------ #
# 5) Bootstrap 幂等性
# ------------------------------------------------------------------ #

def test_bootstrap_is_idempotent():
    """重复调用 bootstrap_adapters 不应破坏现有注册。"""
    from pyagentforge.protocols import bootstrap_adapters

    before = set(PROTOCOL_ADAPTERS.keys())
    bootstrap_adapters()
    bootstrap_adapters()
    after = set(PROTOCOL_ADAPTERS.keys())
    assert before.issubset(after)
    # 核心三个内置始终在
    assert {"openai-completions", "openai-responses", "anthropic-messages"}.issubset(after)
