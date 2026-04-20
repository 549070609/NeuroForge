"""
LLMClient 跨 event loop 安全复用测试

验证：
- 同一 LLMClient 实例在两个独立 event loop 上依次调用不会触发
  ``RuntimeError: Event loop is closed``
- ``_get_or_create_client`` 为不同 loop 返回不同 httpx 实例
- 已关闭 loop 的缓存条目会在下次调用时被清理
- ``aclose()`` 与 ``async with`` 均能正确释放资源
- Hook pipeline（P1a）在跨 loop 场景下依然生效
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from pyagentforge import (
    HookContext,
    LLMClient,
    ModelConfig,
    ModelRegistry,
    RequestPayload,
    clear_all_hooks,
    register_request_interceptor,
)
from pyagentforge.kernel.message import ProviderResponse


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
            id="loop-test-model",
            name="Loop Test Model",
            provider="loop-test-vendor",
            api_type="openai-completions",
            model_name="loop-test-model",
            base_url="https://example.invalid/v1",
            api_key="dummy-key",
        )
    )
    return reg


def _fake_handler(request: httpx.Request) -> httpx.Response:
    payload = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "ok"},
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    return httpx.Response(200, content=json.dumps(payload).encode("utf-8"))


def _build_client() -> LLMClient:
    return LLMClient(
        registry=_build_registry(),
        transport=httpx.MockTransport(_fake_handler),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoopSafeHttpClientCache:
    def test_cross_loop_create_message_no_event_loop_closed(self):
        """两次独立 loop 调用 create_message，不得抛 Event loop is closed。"""
        client = _build_client()

        async def _call() -> ProviderResponse:
            return await client.create_message(
                model_id="loop-test-model",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=16,
            )

        loop_a = asyncio.new_event_loop()
        try:
            resp_a = loop_a.run_until_complete(_call())
        finally:
            loop_a.close()

        loop_b = asyncio.new_event_loop()
        try:
            resp_b = loop_b.run_until_complete(_call())
        finally:
            loop_b.close()

        assert resp_a.text == "ok"
        assert resp_b.text == "ok"

    def test_different_loops_get_different_httpx_clients(self):
        client = _build_client()
        seen: list[httpx.AsyncClient] = []

        async def _grab() -> None:
            seen.append(client._get_or_create_client(120))

        loop_a = asyncio.new_event_loop()
        try:
            loop_a.run_until_complete(_grab())
        finally:
            loop_a.close()

        loop_b = asyncio.new_event_loop()
        try:
            loop_b.run_until_complete(_grab())
        finally:
            loop_b.close()

        assert seen[0] is not seen[1]

    @pytest.mark.asyncio
    async def test_same_loop_reuses_httpx_client(self):
        client = _build_client()

        a = client._get_or_create_client(120)
        b = client._get_or_create_client(120)
        assert a is b

    @pytest.mark.asyncio
    async def test_different_timeout_separate_clients(self):
        client = _build_client()

        a = client._get_or_create_client(30)
        b = client._get_or_create_client(60)
        assert a is not b

    def test_stale_loop_entries_cleaned_on_next_call(self):
        """为已关闭 loop 预留的缓存条目应在下次 _get_or_create_client 时清理。"""
        client = _build_client()

        loop_a = asyncio.new_event_loop()

        async def _on_a() -> None:
            client._get_or_create_client(120)

        try:
            loop_a.run_until_complete(_on_a())
        finally:
            loop_a.close()

        # 此时至少有一个条目绑定到已关闭 loop
        assert any(l.is_closed() for l, _ in client._http_clients.values())

        loop_b = asyncio.new_event_loop()

        async def _on_b() -> None:
            client._get_or_create_client(120)

        try:
            loop_b.run_until_complete(_on_b())
        finally:
            loop_b.close()

        # 已关闭 loop 条目应在 loop_b 调用时被清理
        # （loop_b 调用时它还活着，清理发生在插入 loop_b 条目之前）
        # 断言仅检查 loop_a 的遗留条目不再存在：
        loops_in_cache = [l for (l, _c) in client._http_clients.values()]
        assert loop_a not in loops_in_cache

    @pytest.mark.asyncio
    async def test_aclose_closes_current_loop_clients(self):
        client = _build_client()

        httpx_client = client._get_or_create_client(120)
        assert client._http_clients
        await client.aclose()
        assert not client._http_clients
        # 二次 aclose 不应出错
        await client.aclose()
        assert httpx_client.is_closed

    @pytest.mark.asyncio
    async def test_async_with_closes_on_exit(self):
        registry = _build_registry()
        async with LLMClient(
            registry=registry, transport=httpx.MockTransport(_fake_handler)
        ) as client:
            resp = await client.create_message(
                model_id="loop-test-model",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=16,
            )
            assert resp.text == "ok"
        assert not client._http_clients


class TestRequestInterceptorStillWorksAcrossLoops:
    """确保 P1a 的 hook 机制在跨 loop 场景下依然成立。"""

    def test_interceptor_fires_on_each_loop(self):
        client = _build_client()

        call_count = {"n": 0}

        def interceptor(ctx: HookContext, req: RequestPayload) -> RequestPayload:
            call_count["n"] += 1
            req.headers["X-Counter"] = str(call_count["n"])
            return req

        register_request_interceptor(interceptor)

        async def _call() -> None:
            await client.create_message(
                model_id="loop-test-model",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=16,
            )

        loop_a = asyncio.new_event_loop()
        try:
            loop_a.run_until_complete(_call())
        finally:
            loop_a.close()

        loop_b = asyncio.new_event_loop()
        try:
            loop_b.run_until_complete(_call())
        finally:
            loop_b.close()

        assert call_count["n"] == 2
