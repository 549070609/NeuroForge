"""
Authentication Middleware (P0-8 / P1-2).

P0-8 加固：
- 使用 `secrets.compare_digest` 做常量时间比较，防止时序旁路
- 支持多 key（`settings.api_keys: dict[api_key, client_id]`）
- 认证成功将 `client_id` 注入 `scope.state.client_id`，供后续限流使用

P1-2: 从 BaseHTTPMiddleware 迁移到纯 ASGI 中间件，
消除 body 缓存问题，兼容 SSE / 流式响应。
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import TYPE_CHECKING

from starlette.types import ASGIApp, Receive, Scope, Send

from .request_context import _ensure_state

if TYPE_CHECKING:
    from ...config.settings import ServiceSettings


def _hash_key(key: str) -> bytes:
    """对 key 做 SHA-256，确保 compare_digest 使用等长比较目标。"""
    return hashlib.sha256(key.encode("utf-8")).digest()


async def _send_json_response(
    send: Send,
    status_code: int,
    body: dict,
    *,
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> None:
    """通过底层 ASGI send 直接返回 JSON 响应（短路）。"""
    payload = json.dumps(body).encode("utf-8")
    headers: list[tuple[bytes, bytes]] = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(payload)).encode("latin-1")),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": payload})


class AuthMiddleware:
    """
    纯 ASGI 认证中间件（时序安全）。

    认证优先级：
      1. 若 `settings.api_keys` 非空，查表并返回对应 `client_id`
      2. 否则比对 `settings.api_key`（兼容单 key 历史配置）
      3. 若两者都未配置，跳过认证（向后兼容）
    """

    _PUBLIC_PATHS: frozenset[str] = frozenset(
        {"/", "/health", "/health/deep", "/docs", "/redoc", "/openapi.json"}
    )

    def __init__(self, app: ASGIApp, settings: "ServiceSettings") -> None:
        self.app = app
        self._header_lower = settings.api_key_header.lower().encode("latin-1")

        self._key_hashes: dict[bytes, str] = {}
        if settings.api_keys:
            for key, client_id in settings.api_keys.items():
                self._key_hashes[_hash_key(key)] = client_id
        elif settings.api_key:
            self._key_hashes[_hash_key(settings.api_key)] = "default"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self._PUBLIC_PATHS or not self._key_hashes:
            await self.app(scope, receive, send)
            return

        provided_key = self._extract_header(scope)
        if not provided_key:
            await _send_json_response(
                send, 401, {"detail": "API key required"},
                extra_headers=[(b"www-authenticate", b'ApiKey realm="API"')],
            )
            return

        # P0-8 时序安全：遍历全部 hash 消除时序差异
        provided_hash = _hash_key(provided_key)
        matched_client_id: str | None = None
        for known_hash, client_id in self._key_hashes.items():
            if secrets.compare_digest(provided_hash, known_hash):
                matched_client_id = client_id

        if matched_client_id is None:
            await _send_json_response(send, 403, {"detail": "Invalid API key"})
            return

        state = _ensure_state(scope)
        state["client_id"] = matched_client_id
        await self.app(scope, receive, send)

    def _extract_header(self, scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key == self._header_lower:
                return value.decode("latin-1")
        return None
