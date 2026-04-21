"""
Rate Limiting Middleware (P0-8 / P1-2).

Implements a simple in-memory rate limiter using sliding window.

P1-2: 从 BaseHTTPMiddleware 迁移到纯 ASGI 中间件，
消除 body 缓存问题，兼容 SSE / 流式响应。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from starlette.types import ASGIApp, Receive, Scope, Send

from .rate_limit_backend import InMemoryBackend, RateLimitBackend
from .request_context import _ensure_state

if TYPE_CHECKING:
    from ...config.settings import ServiceSettings


class RateLimiter:
    """
    In-memory rate limiter using sliding window.

    Tracks requests per client IP within a time window.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if request is allowed.

        Args:
            client_id: Client identifier (usually IP address)

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Clean old requests
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]

            # Check limit
            current_count = len(self._requests[client_id])
            if current_count >= self.max_requests:
                return False, 0

            # Record request
            self._requests[client_id].append(now)
            return True, self.max_requests - current_count - 1


class RateLimitMiddleware:
    """
    纯 ASGI 限流中间件。

    P0-8: 限流键优先 client_id（认证后注入），回落可信 XFF / 直连 IP。
    P1-2: 纯 ASGI 实现，不缓存 body，兼容 SSE 流式。
    """

    def __init__(
        self,
        app: ASGIApp,
        settings: "ServiceSettings",
        *,
        backend: RateLimitBackend | None = None,
    ) -> None:
        self.app = app
        self._max_requests = settings.rate_limit_requests
        self._window = settings.rate_limit_window
        self.enabled = settings.rate_limit_enabled
        self._trusted_proxies = frozenset(settings.trusted_proxies or [])
        self.backend: RateLimitBackend | None = None

        if self.enabled:
            self.backend = backend or InMemoryBackend(
                max_requests=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window,
            )
            # 向后兼容：保留 .limiter 属性引用
            self.limiter = self.backend

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return

        client_key = self._resolve_client_key(scope)
        allowed, remaining = await self.backend.is_allowed(client_key)

        if not allowed:
            await self._send_rate_limit_response(send)
            return

        rl_headers = [
            (b"x-ratelimit-limit", str(self._max_requests).encode("latin-1")),
            (b"x-ratelimit-remaining", str(remaining).encode("latin-1")),
            (b"x-ratelimit-reset", str(self._window).encode("latin-1")),
        ]

        async def send_with_rl_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(rl_headers)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_rl_headers)

    def _resolve_client_key(self, scope: Scope) -> str:
        """P0-8 限流键解析：
          1. 已认证：优先使用 `state.client_id`
          2. 直连来源在 `trusted_proxies` 白名单中：解析 `X-Forwarded-For` 最右可信段
          3. 否则回落到 `client.host`（真实连接 IP）
        """
        state = scope.get("state", {})
        client_id = state.get("client_id") if isinstance(state, dict) else getattr(state, "client_id", None)
        if client_id:
            return f"cid:{client_id}"

        client = scope.get("client")
        direct_ip = client[0] if client else "unknown"

        if direct_ip in self._trusted_proxies:
            xff = self._get_header(scope, b"x-forwarded-for")
            if xff:
                ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
                for ip in reversed(ips):
                    if ip not in self._trusted_proxies:
                        return f"ip:{ip}"

        return f"ip:{direct_ip}"

    @staticmethod
    def _get_header(scope: Scope, name: bytes) -> str | None:
        for key, value in scope.get("headers", []):
            if key == name:
                return value.decode("latin-1")
        return None

    async def _send_rate_limit_response(self, send: Send) -> None:
        body = json.dumps({"detail": "Rate limit exceeded"}).encode("utf-8")
        headers: list[tuple[bytes, bytes]] = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("latin-1")),
            (b"x-ratelimit-limit", str(self._max_requests).encode("latin-1")),
            (b"x-ratelimit-remaining", b"0"),
            (b"x-ratelimit-reset", str(self._window).encode("latin-1")),
        ]
        await send({"type": "http.response.start", "status": 429, "headers": headers})
        await send({"type": "http.response.body", "body": body})
