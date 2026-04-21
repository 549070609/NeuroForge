"""
Request Context Middleware (P0-5 / P1-2)

职责：
  1. 为每个请求生成或透传 `X-Request-ID`
  2. 将 `request_id` 注入 contextvars，贯穿整个请求处理链
  3. 在响应头回写 `X-Request-ID`

P1-2: 从 BaseHTTPMiddleware 迁移到纯 ASGI 中间件，
消除 body 缓存问题，兼容 SSE / 流式响应。
"""

from __future__ import annotations

import contextvars
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send


request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    """读取当前请求的 request_id（无则返回空串）。"""
    return request_id_var.get()


def _ensure_state(scope: Scope) -> dict:
    """确保 scope['state'] 是 plain dict（避免 Starlette 双层 State 包装）。"""
    if "state" not in scope:
        scope["state"] = {}
    return scope["state"]


class RequestContextMiddleware:
    """纯 ASGI 中间件：注入 / 回写 X-Request-ID，并存入 contextvars。"""

    HEADER = "X-Request-ID"
    _HEADER_LOWER = b"x-request-id"

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request_id = self._extract_request_id(scope) or uuid.uuid4().hex[:16]

        state = _ensure_state(scope)
        state["request_id"] = request_id

        token = request_id_var.set(request_id)

        async def send_with_request_id(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((self._HEADER_LOWER, request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_var.reset(token)

    @staticmethod
    def _extract_request_id(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key == b"x-request-id":
                return value.decode("latin-1")
        return None
