"""
Error Handler Middleware — RFC 7807 (application/problem+json)

将所有未捕获异常转换为统一的 Problem Details 响应。

P1-2: 从 BaseHTTPMiddleware 迁移到纯 ASGI 中间件，
消除 body 缓存问题，兼容 SSE / 流式响应。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


# ── 业务异常 → (HTTP status, error code, title) 映射表 ──────────
# key 为异常类名，避免强制 import 所有异常模块

_EXCEPTION_MAP: dict[str, tuple[int, str, str]] = {
    "AgentTimeoutError": (504, "agent_timeout", "Agent execution timed out"),
    "AgentCancelledError": (499, "agent_cancelled", "Agent execution was cancelled"),
    "AgentMaxIterationsError": (
        422,
        "agent_max_iterations",
        "Agent exceeded maximum iterations",
    ),
    "AgentProviderError": (502, "agent_provider_error", "LLM provider error"),
    "AgentToolError": (500, "agent_tool_error", "Tool execution failed"),
    "AgentError": (500, "agent_error", "Agent execution error"),
}


def _build_problem(
    *,
    status: int,
    code: str,
    title: str,
    detail: str | None = None,
    instance: str = "",
    request_id: str = "",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 RFC 7807 Problem Details 字典。"""
    body: dict[str, Any] = {
        "type": f"about:blank#{code}",
        "title": title,
        "status": status,
        "code": code,
        "instance": instance,
        "request_id": request_id,
    }
    if detail is not None:
        body["detail"] = detail
    if extras:
        body.update(extras)
    return body


def _resolve_exception(exc: Exception) -> tuple[int, str, str]:
    """解析异常类型到 (status, code, title)，支持 MRO 回退匹配。"""
    cls_name = type(exc).__name__
    if cls_name in _EXCEPTION_MAP:
        return _EXCEPTION_MAP[cls_name]
    for base in type(exc).__mro__:
        if base.__name__ in _EXCEPTION_MAP:
            return _EXCEPTION_MAP[base.__name__]
    return (500, "internal_error", "Internal server error")


class ErrorHandlerMiddleware:
    """
    纯 ASGI 全局错误处理中间件 — RFC 7807 application/problem+json

    通过 settings.expose_error_details 控制是否向客户端暴露内部异常字符串。
    不缓存 body，SSE / 流式响应正常透传。
    """

    def __init__(self, app: ASGIApp, expose_error_details: bool = False) -> None:
        self.app = app
        self._expose_details = expose_error_details

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: dict) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            if response_started:
                raise

            logger.exception("Unexpected error: %s", e)

            state = scope.get("state", {})
            request_id = (
                state.get("request_id", "")
                if isinstance(state, dict)
                else getattr(state, "request_id", "")
            ) or uuid.uuid4().hex[:16]

            status_code, code, title = _resolve_exception(e)
            detail = str(e) if self._expose_details else None
            instance = scope.get("path", "")

            body = _build_problem(
                status=status_code,
                code=code,
                title=title,
                detail=detail,
                instance=instance,
                request_id=request_id,
            )

            payload = json.dumps(body).encode("utf-8")
            headers: list[tuple[bytes, bytes]] = [
                (b"content-type", b"application/problem+json"),
                (b"content-length", str(len(payload)).encode("latin-1")),
                (b"x-request-id", request_id.encode("latin-1")),
            ]
            await send({
                "type": "http.response.start",
                "status": status_code,
                "headers": headers,
            })
            await send({"type": "http.response.body", "body": payload})
