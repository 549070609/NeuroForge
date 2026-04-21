"""
P0-9 ErrorHandler RFC 7807 回归测试

验证：
  1. 错误响应符合 RFC 7807 application/problem+json 格式
  2. expose_error_details=False 时不泄露内部异常字符串
  3. expose_error_details=True 时包含 detail
  4. AgentError 子类被正确映射到 HTTP 状态码
  5. 未知异常返回 500 internal_error
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pyagentforge.kernel.errors import (
    AgentCancelledError,
    AgentMaxIterationsError,
    AgentProviderError,
    AgentTimeoutError,
    AgentToolError,
)

from Service.gateway.middleware.error_handler import ErrorHandlerMiddleware, _build_problem
from Service.gateway.middleware.request_context import RequestContextMiddleware


# ── helpers ────────────────────────────────────────────────────

def _make_app(
    *,
    expose_error_details: bool = False,
    exception: Exception | None = None,
) -> FastAPI:
    """构建一个会在路由中抛出指定异常的测试 app。"""
    app = FastAPI()
    # P1-2: RequestContextMiddleware 负责注入 x-request-id
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        ErrorHandlerMiddleware,
        expose_error_details=expose_error_details,
    )

    @app.get("/raise")
    async def _raise():
        raise exception or RuntimeError("boom")

    @app.get("/ok")
    async def _ok():
        return {"status": "ok"}

    return app


# ── RFC 7807 格式 ──────────────────────────────────────────────

class TestRFC7807Format:
    """返回体包含 type / title / status / code / instance / request_id。"""

    def test_500_contains_required_fields(self):
        client = TestClient(_make_app(exception=RuntimeError("oops")), raise_server_exceptions=False)
        resp = client.get("/raise")
        assert resp.status_code == 500
        body = resp.json()
        for key in ("type", "title", "status", "code", "instance", "request_id"):
            assert key in body, f"missing key: {key}"
        assert body["status"] == 500
        assert body["code"] == "internal_error"

    def test_content_type_is_problem_json(self):
        client = TestClient(_make_app(exception=RuntimeError("oops")), raise_server_exceptions=False)
        resp = client.get("/raise")
        assert "application/problem+json" in resp.headers["content-type"]

    def test_request_id_header_present(self):
        client = TestClient(_make_app(exception=RuntimeError("oops")), raise_server_exceptions=False)
        resp = client.get("/raise")
        assert "x-request-id" in resp.headers

    def test_ok_response_has_request_id(self):
        client = TestClient(_make_app(), raise_server_exceptions=False)
        resp = client.get("/ok")
        assert resp.status_code == 200
        assert "x-request-id" in resp.headers


# ── expose_error_details 控制 ─────────────────────────────────

class TestExposeErrorDetails:
    """detail 字段受 settings.expose_error_details 控制。"""

    def test_detail_hidden_by_default(self):
        client = TestClient(
            _make_app(expose_error_details=False, exception=RuntimeError("secret")),
            raise_server_exceptions=False,
        )
        body = client.get("/raise").json()
        assert "detail" not in body

    def test_detail_shown_when_enabled(self):
        client = TestClient(
            _make_app(expose_error_details=True, exception=RuntimeError("secret")),
            raise_server_exceptions=False,
        )
        body = client.get("/raise").json()
        assert body.get("detail") == "secret"


# ── 业务异常映射 ──────────────────────────────────────────────

class TestExceptionMapping:
    """AgentError 子类映射到正确的 HTTP 状态码和 error code。"""

    @pytest.mark.parametrize(
        "exc, expected_status, expected_code",
        [
            (AgentTimeoutError(timeout=30), 504, "agent_timeout"),
            (AgentCancelledError(), 499, "agent_cancelled"),
            (AgentMaxIterationsError(max_iterations=10), 422, "agent_max_iterations"),
            (AgentProviderError(), 502, "agent_provider_error"),
            (AgentToolError(tool_name="foo"), 500, "agent_tool_error"),
        ],
    )
    def test_agent_error_mapped(self, exc, expected_status, expected_code):
        client = TestClient(
            _make_app(exception=exc),
            raise_server_exceptions=False,
        )
        resp = client.get("/raise")
        assert resp.status_code == expected_status
        body = resp.json()
        assert body["code"] == expected_code
        assert body["status"] == expected_status

    def test_unknown_exception_returns_500(self):
        client = TestClient(
            _make_app(exception=ValueError("bad")),
            raise_server_exceptions=False,
        )
        resp = client.get("/raise")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "internal_error"


# ── _build_problem 单元测试 ──────────────────────────────────

class TestBuildProblem:
    """_build_problem 工具函数。"""

    def test_minimal(self):
        p = _build_problem(status=404, code="not_found", title="Not Found")
        assert p["status"] == 404
        assert p["code"] == "not_found"
        assert "detail" not in p

    def test_with_detail(self):
        p = _build_problem(status=500, code="err", title="Error", detail="info")
        assert p["detail"] == "info"

    def test_with_extras(self):
        p = _build_problem(
            status=500, code="err", title="Error",
            extras={"retry_after": 60},
        )
        assert p["retry_after"] == 60
