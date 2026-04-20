"""LLMClient 测试用例。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pyagentforge import LLMClient
from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.kernel.model_registry import ModelConfig, ModelRegistry


def build_registry(api_type: str = "openai-completions") -> ModelRegistry:
    registry = ModelRegistry(load_from_config=False)
    registry.register_model(
        ModelConfig(
            id="default",
            name="Default Model",
            provider="custom",
            api_type=api_type,
            base_url="https://example.test/v1",
            api_key="test-key",
            model_name="default-model",
        )
    )
    return registry


class TestLLMClient:
    def test_client_initialization(self) -> None:
        client = LLMClient(registry=build_registry())
        assert client is not None
        assert client.registry is not None
        assert client._http_clients == {}

    def test_client_with_custom_registry(self) -> None:
        registry = build_registry()
        client = LLMClient(registry=registry)
        assert client.registry is registry

    @pytest.mark.asyncio
    async def test_create_message_model_not_found(self) -> None:
        client = LLMClient(registry=build_registry())
        with pytest.raises(ValueError, match="Model configuration error"):
            await client.create_message(model_id="nonexistent-model", messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_create_message_success(self) -> None:
        client = LLMClient(registry=build_registry("openai-completions"))
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._get_or_create_client = MagicMock(return_value=mock_http)

        response = await client.create_message(
            model_id="default",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response.text == "Hello!"
        assert response.stop_reason == "end_turn"
        mock_http.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_count_tokens(self) -> None:
        client = LLMClient(registry=build_registry())
        messages = [
            {"role": "user", "content": "Hello world"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        count = await client.count_tokens(model_id="default", messages=messages)
        assert count > 0

    @pytest.mark.asyncio
    async def test_http_client_cache(self) -> None:
        # _get_or_create_client 现按 (running_loop, timeout) 维度缓存，
        # 必须在 async 上下文中调用。
        client = LLMClient(registry=build_registry())
        client1 = client._get_or_create_client(120)
        client2 = client._get_or_create_client(120)
        client3 = client._get_or_create_client(60)
        assert client1 is client2
        assert client1 is not client3

    @pytest.mark.asyncio
    async def test_aclose_clears_cache(self) -> None:
        client = LLMClient(registry=build_registry())
        await client.aclose()
        assert len(client._http_clients) == 0

    @pytest.mark.asyncio
    async def test_stream_message(self) -> None:
        # stream_message 现走真实 SSE 通道，通过 httpx.MockTransport 注入伪事件流
        import json as _json
        import httpx as _httpx

        sse_body = (
            f"data: {_json.dumps({'choices': [{'delta': {'content': 'Hello '}, 'finish_reason': None}]})}\n\n"
            f"data: {_json.dumps({'choices': [{'delta': {'content': 'world'}, 'finish_reason': None}]})}\n\n"
            f"data: {_json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})}\n\n"
            "data: [DONE]\n\n"
        ).encode("utf-8")

        def _handler(_req: _httpx.Request) -> _httpx.Response:
            return _httpx.Response(
                200, content=sse_body, headers={"content-type": "text/event-stream"}
            )

        client = LLMClient(
            registry=build_registry("openai-completions"),
            transport=_httpx.MockTransport(_handler),
        )

        chunks = []
        async for chunk in client.stream_message(
            model_id="default",
            messages=[{"role": "user", "content": "test"}],
        ):
            chunks.append(chunk)

        # 末尾必为 ProviderResponse
        assert isinstance(chunks[-1], ProviderResponse)
        assert chunks[-1].text == "Hello world"
        assert chunks[-1].usage == {"input_tokens": 10, "output_tokens": 5}
        # 中间应包含至少 2 个 text_delta
        from pyagentforge import StreamEvent

        text_deltas = [c for c in chunks[:-1] if isinstance(c, StreamEvent) and c.type == "text_delta"]
        assert len(text_deltas) == 2


class TestLLMClientErrorHandling:
    @pytest.mark.asyncio
    async def test_runtime_config_failed_fallback_to_file_config(self) -> None:
        registry = ModelRegistry(load_from_config=False)
        registry._config_models["default"] = ModelConfig(
            id="default",
            name="Default Model Config",
            provider="config",
            api_type="openai-completions",
            base_url="https://example.test/v1",
            api_key="test-key",
            model_name="default-model",
        )
        registry.register_model(
            ModelConfig(
                id="default",
                name="Default Model Runtime",
                provider="runtime",
                api_type="openai-completions",
                api_key="test-key",
                model_name="default-model",
            )
        )
        client = LLMClient(registry=registry)
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "fallback-success", "tool_calls": []}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        mock_response.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        client._get_or_create_client = MagicMock(return_value=mock_http)

        response = await client.create_message(
            model_id="default",
            messages=[{"role": "user", "content": "Hello"}],
        )

        assert response.text == "fallback-success"

    @pytest.mark.asyncio
    async def test_missing_base_url(self) -> None:
        registry = ModelRegistry(load_from_config=False)
        registry.register_model(
            ModelConfig(
                id="default",
                name="Default Model",
                provider="custom",
                api_type="openai-completions",
                api_key="test-key",
            )
        )
        client = LLMClient(registry=registry)
        with pytest.raises(ValueError, match="Base URL is required"):
            await client.create_message(model_id="default", messages=[{"role": "user", "content": "test"}])

    @pytest.mark.asyncio
    async def test_protocol_not_found(self) -> None:
        registry = ModelRegistry(load_from_config=False)
        registry.register_model(
            ModelConfig(
                id="default",
                name="Default Model",
                provider="custom",
                api_type="custom",
                base_url="https://example.test/v1",
                api_key="test-key",
            )
        )
        client = LLMClient(registry=registry)
        with pytest.raises(ValueError, match="Unsupported api_type"):
            await client.create_message(model_id="default", messages=[{"role": "user", "content": "test"}])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
