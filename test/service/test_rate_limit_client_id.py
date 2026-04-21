"""P0-8 限流键解析 + X-Forwarded-For 信任回归测试（P1-2 纯 ASGI 版本）"""

from __future__ import annotations

import pytest

from Service.config.settings import ServiceSettings
from Service.gateway.middleware.rate_limit import RateLimiter, RateLimitMiddleware


def _make_scope(*, client_host: str, client_id: str | None = None,
                xff: str | None = None) -> dict:
    """构建 ASGI scope dict（纯 ASGI 接口：不再使用 Request 对象）。"""
    headers: list[tuple[bytes, bytes]] = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode("latin-1")))
    state: dict = {}
    if client_id is not None:
        state["client_id"] = client_id
    return {
        "type": "http",
        "client": (client_host, 0),
        "headers": headers,
        "state": state,
    }


def _mw(**overrides) -> RateLimitMiddleware:
    settings = ServiceSettings(rate_limit_enabled=True, **overrides)
    mw = RateLimitMiddleware.__new__(RateLimitMiddleware)
    mw.enabled = True
    mw._max_requests = settings.rate_limit_requests
    mw._window = settings.rate_limit_window
    mw._trusted_proxies = frozenset(settings.trusted_proxies or [])
    return mw


class TestResolveClientKey:
    def test_authenticated_uses_client_id(self):
        mw = _mw()
        key = mw._resolve_client_key(
            _make_scope(client_host="1.1.1.1", client_id="acme")
        )
        assert key == "cid:acme"

    def test_unauthenticated_uses_direct_ip(self):
        mw = _mw()
        key = mw._resolve_client_key(
            _make_scope(client_host="1.1.1.1")
        )
        assert key == "ip:1.1.1.1"

    def test_untrusted_proxy_xff_ignored(self):
        """来源不在 trusted_proxies：忽略 X-Forwarded-For。"""
        mw = _mw(trusted_proxies=["10.0.0.1"])
        scope = _make_scope(client_host="2.2.2.2", xff="1.1.1.1")
        assert mw._resolve_client_key(scope) == "ip:2.2.2.2"

    def test_trusted_proxy_parses_xff(self):
        """来源是受信代理：使用 X-Forwarded-For 最右非代理 IP。"""
        mw = _mw(trusted_proxies=["10.0.0.1"])
        scope = _make_scope(client_host="10.0.0.1", xff="1.1.1.1")
        assert mw._resolve_client_key(scope) == "ip:1.1.1.1"

    def test_trusted_chain_rightmost_non_proxy(self):
        """链式代理：从右往左找第一个非受信 IP。"""
        mw = _mw(trusted_proxies=["10.0.0.1", "10.0.0.2"])
        scope = _make_scope(
            client_host="10.0.0.1",
            xff="8.8.8.8, 7.7.7.7, 10.0.0.2",
        )
        assert mw._resolve_client_key(scope) == "ip:7.7.7.7"

    def test_trusted_proxy_without_xff_falls_back_to_direct(self):
        mw = _mw(trusted_proxies=["10.0.0.1"])
        scope = _make_scope(client_host="10.0.0.1")
        assert mw._resolve_client_key(scope) == "ip:10.0.0.1"


class TestRateLimiter:
    """基础 RateLimiter 行为。"""

    @pytest.mark.asyncio
    async def test_separate_keys_counted_independently(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        ok1, _ = await limiter.is_allowed("A")
        ok2, _ = await limiter.is_allowed("A")
        ok3, _ = await limiter.is_allowed("A")
        assert ok1 and ok2 and not ok3

        # 另一个 key 独立计数
        okB, _ = await limiter.is_allowed("B")
        assert okB
