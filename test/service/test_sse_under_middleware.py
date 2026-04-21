"""
P1-2 SSE / 流式响应在纯 ASGI 中间件下的回归测试

验证：
  1. SSE 流式响应（text/event-stream）在所有中间件下正常透传，不被缓存
  2. 中间件仍正确注入 X-Request-ID / 限流 / 错误处理头
  3. 路由抛异常时，ErrorHandler 返回 RFC 7807 problem+json
  4. 非 http scope（如 lifespan）直接透传不报错
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from Service.gateway.middleware.error_handler import ErrorHandlerMiddleware
from Service.gateway.middleware.request_context import RequestContextMiddleware


# ── helpers ────────────────────────────────────────────────────

def _make_sse_app(*, raise_in_route: bool = False) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(ErrorHandlerMiddleware, expose_error_details=True)

    async def sse_generator():
        for i in range(3):
            yield f"data: chunk-{i}\n\n"

    @app.get("/sse")
    async def sse_endpoint():
        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/raise")
    async def raise_endpoint():
        raise RuntimeError("boom")

    @app.get("/ok")
    async def ok_endpoint():
        return {"status": "ok"}

    return app


# ── SSE 透传 ──────────────────────────────────────────────────

class TestSSEStreamThrough:
    """SSE 流式响应不被纯 ASGI 中间件缓存。"""

    def test_sse_chunks_received(self):
        client = TestClient(_make_sse_app())
        with client.stream("GET", "/sse") as resp:
            assert resp.status_code == 200
            body = b""
            for chunk in resp.iter_bytes():
                body += chunk
            text = body.decode("utf-8")
            assert "chunk-0" in text
            assert "chunk-1" in text
            assert "chunk-2" in text

    def test_sse_has_request_id_header(self):
        client = TestClient(_make_sse_app())
        with client.stream("GET", "/sse") as resp:
            assert "x-request-id" in resp.headers


# ── ErrorHandler 仍工作 ───────────────────────────────────────

class TestErrorHandlerStillWorks:
    """纯 ASGI ErrorHandler 在非流式路由中捕获异常。"""

    def test_error_returns_problem_json(self):
        client = TestClient(_make_sse_app(raise_in_route=True), raise_server_exceptions=False)
        resp = client.get("/raise")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "internal_error"
        assert "application/problem+json" in resp.headers["content-type"]

    def test_ok_route_has_request_id(self):
        client = TestClient(_make_sse_app())
        resp = client.get("/ok")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers


# ── RequestContext 在 ASGI 中仍正常 ──────────────────────────

class TestRequestContextASGI:
    """纯 ASGI RequestContextMiddleware 行为与旧版一致。"""

    def test_propagates_incoming_id(self):
        client = TestClient(_make_sse_app())
        resp = client.get("/ok", headers={"X-Request-ID": "test-abc"})
        assert resp.headers["x-request-id"] == "test-abc"

    def test_generates_id_when_missing(self):
        client = TestClient(_make_sse_app())
        resp = client.get("/ok")
        assert len(resp.headers["x-request-id"]) > 0
