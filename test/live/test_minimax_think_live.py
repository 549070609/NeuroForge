"""
MiniMax ``<think>`` 剥离参考插件的活体验证（最小冒烟）。

仅在配置了 MINIMAX_API_KEY 时运行；上游 5xx 过载会 xfail。
"""

from __future__ import annotations

import httpx
import pytest

from pyagentforge import StreamEvent
from pyagentforge.kernel.message import ProviderResponse
from plugins import minimax_think


@pytest.fixture
def installed_plugin():
    uninstall = minimax_think.install("minimax")
    yield
    uninstall()


@pytest.mark.asyncio
async def test_live_sync_strips_think(installed_plugin, llm_client, minimax_model_id):
    try:
        resp = await llm_client.create_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": "Reply exactly: PONG"}],
            max_tokens=512,
            temperature=0.0,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            pytest.xfail(f"upstream overload: {exc.response.status_code}")
        raise

    text = resp.text or ""
    print(f"\n[live.sync] visible={text!r} reasoning_len={len(resp.reasoning or '')}")
    assert "<think>" not in text, "ResponseTransformer 应已剥离 <think>"
    assert "</think>" not in text


@pytest.mark.asyncio
async def test_live_stream_strips_think(installed_plugin, llm_client, minimax_model_id):
    visible_chunks: list[str] = []
    final: ProviderResponse | None = None
    try:
        async for chunk in llm_client.stream_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": "Reply exactly: PONG"}],
            max_tokens=512,
            temperature=0.0,
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
            elif isinstance(chunk, StreamEvent) and chunk.type == "text_delta":
                visible_chunks.append(chunk.text or "")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            pytest.xfail(f"upstream overload: {exc.response.status_code}")
        raise

    joined = "".join(visible_chunks)
    print(f"\n[live.stream] visible={joined!r}")
    assert "<think>" not in joined
    assert "</think>" not in joined
    assert final is not None
    assert "<think>" not in (final.text or "")
