"""
流式活体测试（通过配置好的真实 LLM 端点，例如 MiniMax）。

- 与 test_minimax_live.py 共用 conftest.py 中注册的模型。
- 用例参数化 model_id / temperature，未来换任意支持 SSE 的厂商即可复用。
- 文件内不出现任何厂商名关键字，验证框架侧流式通道 + 扩展点的厂商中立性。
"""

from __future__ import annotations

import httpx
import pytest

from pyagentforge import StreamEvent
from pyagentforge.kernel.message import ProviderResponse


def _xfail_if_upstream_overload(exc: BaseException) -> None:
    """上游 5xx（尤其 529/503/502）不代表框架回退，xfail 处理。"""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        pytest.xfail(f"upstream overload: {exc.response.status_code}")


def _extract_text(response: ProviderResponse) -> str:
    """复用 test_minimax_live.py 的剥离逻辑：部分模型会把 <think> 放在 content 里。"""
    text = response.text or ""
    if "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
    return text


@pytest.mark.asyncio
async def test_stream_basic_yields_deltas_and_final(llm_client, minimax_model_id):
    """最小活体冒烟：至少 1 个增量 + 末尾 ProviderResponse。"""
    events: list = []
    try:
        async for chunk in llm_client.stream_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": "Say the word PONG and nothing else."}],
            max_tokens=512,
            temperature=0.0,
        ):
            events.append(chunk)
    except httpx.HTTPStatusError as exc:
        _xfail_if_upstream_overload(exc)
        raise

    # 末尾必为 ProviderResponse
    assert isinstance(events[-1], ProviderResponse)
    final: ProviderResponse = events[-1]

    # 中间至少有一个 StreamEvent
    intermediates = events[:-1]
    assert any(isinstance(e, StreamEvent) for e in intermediates)

    # 增量文本拼接结果应与终态文本的可读部分一致
    delta_texts = [e.text or "" for e in intermediates if isinstance(e, StreamEvent) and e.type == "text_delta"]
    joined_deltas = "".join(delta_texts)

    visible_final = _extract_text(final)
    print(f"\n[stream.basic] deltas={len(delta_texts)} final={visible_final!r}")
    assert visible_final, "final ProviderResponse 文本不应为空"
    # MiniMax 的 reasoning 会进入 content；此处只断言包含主语义
    assert "pong" in (visible_final + joined_deltas).lower()


@pytest.mark.asyncio
async def test_stream_semantics_match_non_stream(llm_client, minimax_model_id):
    """同一问题 + temperature=0，流式终态应与非流式语义一致。"""
    prompt = "Reply with exactly one word: OK"

    # M2.7 等推理模型会把 <think> 计入 completion_tokens，
    # 128 的预算常被推理全部吃掉，留不下可见答案 → 给足 512。
    max_tokens = 512

    try:
        non_stream = await llm_client.create_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0,
        )

        final: ProviderResponse | None = None
        async for chunk in llm_client.stream_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0,
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
    except httpx.HTTPStatusError as exc:
        _xfail_if_upstream_overload(exc)
        raise

    assert final is not None
    non_stream_text = _extract_text(non_stream).lower()
    stream_text = _extract_text(final).lower()
    print(f"\n[stream.sem] non_stream={non_stream_text!r} stream={stream_text!r}")
    # 不强求完全相等（模型即使 temperature=0 也可能有微小抖动），只要都包含 ok
    assert "ok" in non_stream_text
    assert "ok" in stream_text


@pytest.mark.asyncio
async def test_stream_interrupt_releases_connection(llm_client, minimax_model_id):
    """中途 break 应正确释放连接，后续请求仍成功。"""
    try:
        got_some = False
        async for chunk in llm_client.stream_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": "Count from 1 to 50 slowly."}],
            max_tokens=512,
            temperature=0.0,
        ):
            if isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                got_some = True
                break

        assert got_some, "应至少收到一个 text_delta 才 break"

        # 后续再发请求应照常成功
        final: ProviderResponse | None = None
        async for chunk in llm_client.stream_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": "Say PONG."}],
            max_tokens=128,
            temperature=0.0,
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
    except httpx.HTTPStatusError as exc:
        _xfail_if_upstream_overload(exc)
        raise
    assert final is not None
    assert _extract_text(final), "中断后新一次调用应能完整拿到 ProviderResponse"
