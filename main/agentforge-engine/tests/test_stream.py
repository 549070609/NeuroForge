"""
流式 SSE 单元测试：协议层解析 + LLMClient 流式通道 + StreamTransformer 钩子。

所有用例基于 httpx.MockTransport，无需真实网络；亦不依赖任何厂商。
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from pyagentforge import (
    HookContext,
    LLMClient,
    ModelConfig,
    ModelRegistry,
    StreamEvent,
    clear_all_hooks,
    register_response_transformer,
    register_stream_transformer,
)
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.protocols import OpenAIChatProtocol


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_hooks():
    clear_all_hooks()
    yield
    clear_all_hooks()


def _build_registry() -> ModelRegistry:
    reg = ModelRegistry(load_from_config=False)
    reg.register_model(
        ModelConfig(
            id="stream-test-model",
            name="Stream Test Model",
            provider="stream-test-vendor",
            api_type="openai-completions",
            model_name="stream-test-model",
            base_url="https://example.invalid/v1",
            api_key="dummy-key",
        )
    )
    return reg


def _sse_chunks(chunks: list[dict[str, Any]]) -> bytes:
    """把 dict 列表打包为 SSE 字节流（OpenAI 风格）。"""
    parts: list[str] = []
    for chunk in chunks:
        parts.append(f"data: {json.dumps(chunk)}\n\n")
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


def _build_sse_transport(body: bytes, status_code: int = 200) -> httpx.MockTransport:
    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            content=body,
            headers={"content-type": "text/event-stream"},
        )

    return httpx.MockTransport(_handler)


# ---------------------------------------------------------------------------
# 协议层：OpenAIChatProtocol SSE 解析
# ---------------------------------------------------------------------------


class TestOpenAIChatStreamParsing:
    def setup_method(self) -> None:
        self.adapter = OpenAIChatProtocol()

    def test_ignores_empty_and_comment_lines(self) -> None:
        assert self.adapter.parse_stream_line("") is None
        assert self.adapter.parse_stream_line("   ") is None
        assert self.adapter.parse_stream_line(": heartbeat") is None

    def test_done_sentinel(self) -> None:
        event = self.adapter.parse_stream_line("data: [DONE]")
        assert event is not None
        assert event.type == "done"

    def test_malformed_json_is_ignored(self) -> None:
        assert self.adapter.parse_stream_line("data: {not json") is None

    def test_text_delta(self) -> None:
        payload = {"choices": [{"delta": {"content": "hello"}, "index": 0, "finish_reason": None}]}
        event = self.adapter.parse_stream_line(f"data: {json.dumps(payload)}")
        assert event is not None
        assert event.type == "text_delta"
        assert event.text == "hello"

    def test_tool_call_delta(self) -> None:
        payload = {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": '{"c'},
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ]
        }
        event = self.adapter.parse_stream_line(f"data: {json.dumps(payload)}")
        assert event is not None
        assert event.type == "tool_call_delta"
        assert event.tool_call_id == "call_1"
        assert event.tool_call_name == "get_weather"
        assert event.tool_call_arguments_delta == '{"c'
        assert event.tool_call_index == 0

    def test_done_with_usage(self) -> None:
        payload = {
            "choices": [{"delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        event = self.adapter.parse_stream_line(f"data: {json.dumps(payload)}")
        assert event is not None
        assert event.type == "done"
        assert event.stop_reason == "end_turn"
        assert event.usage == {"input_tokens": 10, "output_tokens": 20}

    def test_finish_reason_length_maps_to_max_tokens(self) -> None:
        payload = {"choices": [{"delta": {}, "finish_reason": "length"}]}
        event = self.adapter.parse_stream_line(f"data: {json.dumps(payload)}")
        assert event is not None
        assert event.stop_reason == "max_tokens"

    def test_finish_reason_tool_calls_maps_to_tool_use(self) -> None:
        payload = {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}
        event = self.adapter.parse_stream_line(f"data: {json.dumps(payload)}")
        assert event is not None
        assert event.stop_reason == "tool_use"

    def test_standalone_usage_chunk(self) -> None:
        payload = {"usage": {"prompt_tokens": 3, "completion_tokens": 4}}
        event = self.adapter.parse_stream_line(f"data: {json.dumps(payload)}")
        assert event is not None
        assert event.type == "usage"
        assert event.usage == {"input_tokens": 3, "output_tokens": 4}


# ---------------------------------------------------------------------------
# 协议层：aggregate_stream 聚合
# ---------------------------------------------------------------------------


class TestAggregateStream:
    def setup_method(self) -> None:
        self.adapter = OpenAIChatProtocol()
        self.config = ModelConfig(
            id="x",
            name="x",
            provider="x",
            api_type="openai-completions",
            model_name="x",
        )

    def test_aggregate_text_deltas(self) -> None:
        events = [
            StreamEvent(type="text_delta", text="hel"),
            StreamEvent(type="text_delta", text="lo"),
            StreamEvent(type="done", stop_reason="end_turn"),
        ]
        resp = self.adapter.aggregate_stream(events, self.config)
        assert resp.text == "hello"
        assert resp.stop_reason == "end_turn"

    def test_aggregate_tool_call_fragments(self) -> None:
        events = [
            StreamEvent(
                type="tool_call_delta",
                tool_call_id="call_42",
                tool_call_name="get_weather",
                tool_call_index=0,
            ),
            StreamEvent(
                type="tool_call_delta",
                tool_call_arguments_delta='{"city":',
                tool_call_index=0,
            ),
            StreamEvent(
                type="tool_call_delta",
                tool_call_arguments_delta='"Beijing"}',
                tool_call_index=0,
            ),
            StreamEvent(type="done", stop_reason="tool_use"),
        ]
        resp = self.adapter.aggregate_stream(events, self.config)
        assert resp.has_tool_calls
        call = resp.tool_calls[0]
        assert call.id == "call_42"
        assert call.name == "get_weather"
        assert call.input == {"city": "Beijing"}
        assert resp.stop_reason == "tool_use"

    def test_aggregate_usage(self) -> None:
        events = [
            StreamEvent(type="text_delta", text="hi"),
            StreamEvent(
                type="done",
                stop_reason="end_turn",
                usage={"input_tokens": 5, "output_tokens": 2},
            ),
        ]
        resp = self.adapter.aggregate_stream(events, self.config)
        assert resp.usage == {"input_tokens": 5, "output_tokens": 2}


# ---------------------------------------------------------------------------
# LLMClient.stream_message 端到端（MockTransport）
# ---------------------------------------------------------------------------


def _simple_text_stream() -> bytes:
    return _sse_chunks([
        {"choices": [{"delta": {"content": "Hel"}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "lo"}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "!"}, "index": 0, "finish_reason": None}]},
        {"choices": [{"delta": {}, "index": 0, "finish_reason": "stop"}]},
    ])


class TestLLMClientStream:
    @pytest.mark.asyncio
    async def test_stream_yields_deltas_then_provider_response(self) -> None:
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(_simple_text_stream()),
        )
        events: list[Any] = []
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "hi"}],
        ):
            events.append(chunk)

        # 末尾必为 ProviderResponse
        assert isinstance(events[-1], ProviderResponse)
        assert events[-1].text == "Hello!"

        # 前面至少有 3 个 text_delta + 1 个 done
        intermediates = events[:-1]
        text_deltas = [e for e in intermediates if isinstance(e, StreamEvent) and e.type == "text_delta"]
        assert len(text_deltas) == 3
        assert "".join(e.text or "" for e in text_deltas) == "Hello!"
        dones = [e for e in intermediates if isinstance(e, StreamEvent) and e.type == "done"]
        assert len(dones) == 1

    @pytest.mark.asyncio
    async def test_stream_transformer_can_modify_events(self) -> None:
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(_simple_text_stream()),
        )

        def upper(ctx: HookContext, event: StreamEvent) -> StreamEvent:
            if event.type == "text_delta" and event.text:
                return StreamEvent(type="text_delta", text=event.text.upper(), raw=event.raw)
            return event

        register_stream_transformer(upper)

        text_deltas = []
        final: ProviderResponse | None = None
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "hi"}],
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
            elif isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                text_deltas.append(chunk.text)

        assert text_deltas == ["HEL", "LO", "!"]
        # 注意：aggregate_stream 使用 collected（原始 event），不受 transformer 影响。
        # 这是刻意设计：transformer 只影响对外 yield，不污染聚合结果。
        assert final is not None
        assert final.text == "Hello!"

    @pytest.mark.asyncio
    async def test_stream_transformer_can_drop_events(self) -> None:
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(_simple_text_stream()),
        )

        def drop_text(ctx: HookContext, event: StreamEvent) -> StreamEvent | None:
            if event.type == "text_delta":
                return None
            return event

        register_stream_transformer(drop_text)

        text_deltas = []
        final: ProviderResponse | None = None
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "hi"}],
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
            elif isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                text_deltas.append(chunk)

        assert text_deltas == []
        # 终态仍完整（基于未过滤的 collected 聚合）
        assert final is not None
        assert final.text == "Hello!"

    @pytest.mark.asyncio
    async def test_response_transformer_runs_on_final(self) -> None:
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(_simple_text_stream()),
        )

        def mark(ctx: HookContext, resp: ProviderResponse) -> ProviderResponse:
            return resp.model_copy(update={"reasoning": "via-stream"})

        register_response_transformer(mark)

        final: ProviderResponse | None = None
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "hi"}],
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk

        assert final is not None
        assert final.reasoning == "via-stream"

    @pytest.mark.asyncio
    async def test_stream_tool_call_aggregated(self) -> None:
        body = _sse_chunks([
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "add", "arguments": ""},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": '{"a":'},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {"arguments": "1,\"b\":2}"},
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        ])
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(body),
        )

        final: ProviderResponse | None = None
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "add 1 and 2"}],
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk

        assert final is not None
        assert final.has_tool_calls
        call: ToolUseBlock = final.tool_calls[0]
        assert call.name == "add"
        assert call.input == {"a": 1, "b": 2}
        assert final.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_unknown_model_raises(self) -> None:
        client = LLMClient(registry=_build_registry())
        with pytest.raises(ValueError, match="not found"):
            async for _ in client.stream_message(
                model_id="does-not-exist",
                messages=[{"role": "user", "content": "hi"}],
            ):
                pass

    @pytest.mark.asyncio
    async def test_break_mid_stream_releases_connection(self) -> None:
        """中途 break 后，再发同一模型的请求仍能成功。"""
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(_simple_text_stream()),
        )
        # 第一次：中途 break
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "first"}],
        ):
            if isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                break

        # 第二次：完整消费
        events: list[Any] = []
        async for chunk in client.stream_message(
            model_id="stream-test-model",
            messages=[{"role": "user", "content": "second"}],
        ):
            events.append(chunk)

        assert isinstance(events[-1], ProviderResponse)
        assert events[-1].text == "Hello!"

    @pytest.mark.asyncio
    async def test_http_error_raises(self) -> None:
        client = LLMClient(
            registry=_build_registry(),
            transport=_build_sse_transport(b'{"error":"bad request"}', status_code=400),
        )
        with pytest.raises(httpx.HTTPStatusError):
            async for _ in client.stream_message(
                model_id="stream-test-model",
                messages=[{"role": "user", "content": "hi"}],
            ):
                pass
