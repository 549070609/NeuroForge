"""P1-3 RateLimitBackend 回归测试 — InMemoryBackend + 清理 + 插拔。"""

from __future__ import annotations

import asyncio

import pytest

from Service.gateway.middleware.rate_limit_backend import InMemoryBackend


pytestmark = pytest.mark.asyncio


class TestInMemoryBackend:
    async def test_allows_within_limit(self):
        backend = InMemoryBackend(max_requests=3, window_seconds=60)
        ok1, rem1 = await backend.is_allowed("a")
        ok2, rem2 = await backend.is_allowed("a")
        assert ok1 is True
        assert ok2 is True
        assert rem1 == 2
        assert rem2 == 1

    async def test_denies_over_limit(self):
        backend = InMemoryBackend(max_requests=2, window_seconds=60)
        await backend.is_allowed("b")
        await backend.is_allowed("b")
        ok, rem = await backend.is_allowed("b")
        assert ok is False
        assert rem == 0

    async def test_separate_keys_independent(self):
        backend = InMemoryBackend(max_requests=1, window_seconds=60)
        ok_a, _ = await backend.is_allowed("a")
        ok_b, _ = await backend.is_allowed("b")
        assert ok_a is True
        assert ok_b is True

    async def test_cleanup_removes_stale_keys(self):
        backend = InMemoryBackend(max_requests=10, window_seconds=0)
        await backend.is_allowed("x")
        await backend.cleanup()
        assert "x" not in backend._requests

    async def test_close_cancels_cleanup_task(self):
        backend = InMemoryBackend(max_requests=10, window_seconds=60, cleanup_interval=0.05)
        await backend.start_cleanup_loop()
        assert backend._cleanup_task is not None
        await backend.close()
        assert backend._cleanup_task.done()

    async def test_pluggable_in_middleware(self):
        """验证 RateLimitMiddleware 可接受自定义 backend。"""
        from Service.config.settings import ServiceSettings
        from Service.gateway.middleware.rate_limit import RateLimitMiddleware

        custom_backend = InMemoryBackend(max_requests=5, window_seconds=30)
        settings = ServiceSettings(rate_limit_enabled=True)
        mw = RateLimitMiddleware(app=None, settings=settings, backend=custom_backend)
        assert mw.backend is custom_backend
