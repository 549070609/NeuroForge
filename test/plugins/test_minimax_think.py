"""
MiniMax ``<think>`` 剥离参考插件单元测试（不依赖真实网络）。

覆盖：
- 同步 ResponseTransformer：单段 / 多段 / 无 think / 跨多 TextBlock
- 流式 StreamTransformer：完整 tag / 跨 chunk 拆分 / 多段 think 交错 / 状态隔离
- 仅作用于指定 provider（matcher 验证）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

# 将 engine 源与 live 目录挂到 sys.path
_ROOT = Path(__file__).resolve().parents[2]
_ENGINE_SRC = _ROOT / "main" / "agentforge-engine"
_LIVE_DIR = _ROOT / "test" / "live"
for p in (_ENGINE_SRC, _LIVE_DIR):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from pyagentforge import (
    LLMClient,
    ModelConfig,
    ModelRegistry,
    StreamEvent,
    clear_all_hooks,
)
from pyagentforge.kernel.hooks import HookContext
from pyagentforge.kernel.message import ProviderResponse, TextBlock
from plugins import minimax_think


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_hooks():
    clear_all_hooks()
    yield
    clear_all_hooks()


def _make_ctx(provider: str = "minimax") -> HookContext:
    cfg = ModelConfig(
        id="m", name="m", provider=provider, api_type="openai-completions", model_name="m"
    )
    return HookContext(model_id="m", model_config=cfg)


def _make_resp(texts: list[str]) -> ProviderResponse:
    return ProviderResponse(
        content=[TextBlock(text=t) for t in texts],
        stop_reason="end_turn",
    )


# ---------------------------------------------------------------------------
# 同步：ResponseTransformer
# ---------------------------------------------------------------------------


class TestSyncStrip:
    def test_single_think_block(self):
        out = minimax_think._strip_think_sync(
            _make_ctx(),
            _make_resp(["<think>internal reasoning</think>Hello!"]),
        )
        assert out.text == "Hello!"
        assert out.reasoning == "internal reasoning"

    def test_multiple_think_blocks(self):
        out = minimax_think._strip_think_sync(
            _make_ctx(),
            _make_resp(["<think>step 1</think>Partial<think>step 2</think> answer."]),
        )
        assert out.text == "Partial answer."
        assert "step 1" in out.reasoning
        assert "step 2" in out.reasoning

    def test_no_think_passthrough(self):
        resp = _make_resp(["Just a normal answer."])
        out = minimax_think._strip_think_sync(_make_ctx(), resp)
        assert out is resp  # 零拷贝快路径
        assert out.reasoning is None

    def test_multiple_text_blocks(self):
        out = minimax_think._strip_think_sync(
            _make_ctx(),
            _make_resp(["<think>A</think>first", "<think>B</think>second"]),
        )
        # ProviderResponse.text 以换行拼接多个 TextBlock
        assert "first" in out.text and "second" in out.text
        assert "<think>" not in out.text
        assert "A" in out.reasoning and "B" in out.reasoning

    def test_think_only_block_removed_entirely(self):
        """<think>...</think> 是整个 block 的全部内容：该 TextBlock 应被丢弃。"""
        out = minimax_think._strip_think_sync(
            _make_ctx(),
            _make_resp(["<think>only reasoning</think>", "visible"]),
        )
        # 只剩 "visible" 块
        assert len([b for b in out.content if isinstance(b, TextBlock)]) == 1
        assert out.text == "visible"
        assert out.reasoning == "only reasoning"

    def test_preserves_existing_reasoning(self):
        resp = _make_resp(["<think>new</think>body"]).model_copy(update={"reasoning": "prior"})
        out = minimax_think._strip_think_sync(_make_ctx(), resp)
        assert "prior" in out.reasoning
        assert "new" in out.reasoning


# ---------------------------------------------------------------------------
# 流式：StreamTransformer 状态机
# ---------------------------------------------------------------------------


class TestStreamStripper:
    def _run(self, chunks: list[str], ctx: HookContext | None = None):
        ctx = ctx or _make_ctx()
        stripper = minimax_think._MinimaxThinkStripper()
        visible: list[str] = []
        for text in chunks:
            ev = StreamEvent(type="text_delta", text=text)
            out = stripper(ctx, ev)
            if out is not None:
                assert out.type == "text_delta"
                visible.append(out.text or "")
        # 发 done 清理
        done_out = stripper(ctx, StreamEvent(type="done", stop_reason="end_turn"))
        assert done_out is not None and done_out.type == "done"
        return "".join(visible), stripper

    def test_full_think_then_answer_single_chunk(self):
        visible, _ = self._run(["<think>abc</think>hello"])
        assert visible == "hello"

    def test_think_split_across_chunks(self):
        visible, stripper = self._run(["<thi", "nk>rea", "son</thi", "nk>done"])
        assert visible == "done"

    def test_close_tag_split_across_chunks(self):
        visible, _ = self._run(["<think>inner", " more</th", "ink>visible"])
        assert visible == "visible"

    def test_multiple_think_blocks_streaming(self):
        visible, _ = self._run([
            "<think>a</think>part1 ",
            "<think>b</think>part2",
        ])
        assert visible == "part1 part2"

    def test_no_think_passthrough_streaming(self):
        visible, _ = self._run(["hello ", "world"])
        assert visible == "hello world"

    def test_state_is_per_context(self):
        stripper = minimax_think._MinimaxThinkStripper()
        ctx_a, ctx_b = _make_ctx(), _make_ctx()

        # A 进入 think 但未闭合
        stripper(ctx_a, StreamEvent(type="text_delta", text="<think>secret"))
        # B 发正常文本，不应被 A 的 in_think 影响
        out_b = stripper(ctx_b, StreamEvent(type="text_delta", text="hello"))
        assert out_b is not None and out_b.text == "hello"

        # A 收尾
        out_a = stripper(ctx_a, StreamEvent(type="text_delta", text="</think>bye"))
        assert out_a is not None and out_a.text == "bye"

    def test_done_cleans_state(self):
        stripper = minimax_think._MinimaxThinkStripper()
        ctx = _make_ctx()
        stripper(ctx, StreamEvent(type="text_delta", text="<think>x</think>hi"))
        assert id(ctx) in stripper._states
        stripper(ctx, StreamEvent(type="done", stop_reason="end_turn"))
        assert id(ctx) not in stripper._states


# ---------------------------------------------------------------------------
# Matcher：仅作用于 provider == "minimax"
# ---------------------------------------------------------------------------


def _sse_body(chunks: list[dict]) -> bytes:
    parts = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    parts.append("data: [DONE]\n\n")
    return "".join(parts).encode("utf-8")


def _mock_transport(body: bytes) -> httpx.MockTransport:
    def _handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    return httpx.MockTransport(_handler)


def _registry_with(provider: str) -> ModelRegistry:
    reg = ModelRegistry(load_from_config=False)
    reg.register_model(
        ModelConfig(
            id="m",
            name="m",
            provider=provider,
            api_type="openai-completions",
            model_name="m",
            base_url="https://example.invalid/v1",
            api_key="k",
        )
    )
    return reg


class TestEndToEndIntegration:
    @pytest.mark.asyncio
    async def test_stream_strips_think_for_matching_provider(self):
        minimax_think.install("minimax")
        body = _sse_body([
            {"choices": [{"delta": {"content": "<thi"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "nk>reason</think>"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "Hello"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ])
        client = LLMClient(registry=_registry_with("minimax"), transport=_mock_transport(body))

        visible: list[str] = []
        final: ProviderResponse | None = None
        async for chunk in client.stream_message(
            model_id="m",
            messages=[{"role": "user", "content": "hi"}],
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
            elif isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                visible.append(chunk.text or "")

        assert "".join(visible) == "Hello"
        # 终态（由 response_transformer 再次剥离）应只剩 "Hello"
        assert final is not None
        assert final.text == "Hello"
        assert final.reasoning and "reason" in final.reasoning

    @pytest.mark.asyncio
    async def test_does_not_affect_other_provider(self):
        """matcher 严格按 provider 过滤：其它厂商不应被剥离。"""
        minimax_think.install("minimax")
        body = _sse_body([
            {"choices": [{"delta": {"content": "<think>kept</think>body"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ])
        client = LLMClient(registry=_registry_with("other-vendor"), transport=_mock_transport(body))

        visible: list[str] = []
        async for chunk in client.stream_message(
            model_id="m",
            messages=[{"role": "user", "content": "hi"}],
        ):
            if isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                visible.append(chunk.text or "")

        # 未匹配到 minimax，tag 应原样保留
        assert "<think>" in "".join(visible)

    @pytest.mark.asyncio
    async def test_uninstall_restores_behavior(self):
        uninstall = minimax_think.install("minimax")
        uninstall()  # 立刻卸载

        body = _sse_body([
            {"choices": [{"delta": {"content": "<think>kept</think>body"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ])
        client = LLMClient(registry=_registry_with("minimax"), transport=_mock_transport(body))

        visible = []
        async for chunk in client.stream_message(
            model_id="m", messages=[{"role": "user", "content": "hi"}]
        ):
            if isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                visible.append(chunk.text or "")

        assert "<think>" in "".join(visible)
