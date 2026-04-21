"""P0-5 RequestContext + 结构化日志回归测试"""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Service.config.settings import ServiceSettings, _JSONFormatter, configure_logging
from Service.gateway.middleware.request_context import (
    RequestContextMiddleware,
    get_request_id,
    request_id_var,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    async def _echo():
        return {"request_id": get_request_id()}

    return app


class TestRequestContext:
    def test_generates_id_when_missing(self):
        client = TestClient(_make_app())
        resp = client.get("/echo")
        assert resp.status_code == 200
        # response header 与 body 中的 request_id 一致
        header_id = resp.headers["x-request-id"]
        body_id = resp.json()["request_id"]
        assert header_id == body_id
        assert len(header_id) > 0

    def test_passes_through_incoming_id(self):
        client = TestClient(_make_app())
        resp = client.get("/echo", headers={"X-Request-ID": "trace-abc-123"})
        assert resp.headers["x-request-id"] == "trace-abc-123"
        assert resp.json()["request_id"] == "trace-abc-123"

    def test_each_request_has_unique_id(self):
        client = TestClient(_make_app())
        ids = {client.get("/echo").headers["x-request-id"] for _ in range(5)}
        assert len(ids) == 5

    def test_contextvar_reset_after_request(self):
        """请求结束后 contextvar 应 reset，不泄漏到后续代码。"""
        client = TestClient(_make_app())
        client.get("/echo", headers={"X-Request-ID": "abc"})
        # 请求外读取应为默认空串
        assert request_id_var.get() == ""


class TestJSONLogging:
    """JSON formatter 正确序列化 + 自动注入 request_id。"""

    def test_formatter_produces_valid_json(self):
        fmt = _JSONFormatter()
        rec = logging.LogRecord(
            "svc", logging.INFO, "f.py", 1, "hello %s", ("world",), None
        )
        out = fmt.format(rec)
        data = json.loads(out)
        assert data["message"] == "hello world"
        assert data["level"] == "INFO"
        assert data["logger"] == "svc"
        assert "ts" in data

    def test_formatter_includes_request_id_when_set(self):
        fmt = _JSONFormatter()
        token = request_id_var.set("req-xyz")
        try:
            rec = logging.LogRecord("svc", logging.INFO, "f.py", 1, "msg", (), None)
            data = json.loads(fmt.format(rec))
            assert data["request_id"] == "req-xyz"
        finally:
            request_id_var.reset(token)

    def test_formatter_omits_request_id_when_unset(self):
        fmt = _JSONFormatter()
        rec = logging.LogRecord("svc", logging.INFO, "f.py", 1, "msg", (), None)
        data = json.loads(fmt.format(rec))
        assert "request_id" not in data

    def test_formatter_passes_through_extra_fields(self):
        fmt = _JSONFormatter()
        rec = logging.LogRecord("svc", logging.INFO, "f.py", 1, "msg", (), None)
        rec.session_id = "sess-42"
        rec.iteration = 3
        data = json.loads(fmt.format(rec))
        assert data["session_id"] == "sess-42"
        assert data["iteration"] == 3

    def test_configure_logging_json_mode_attaches_json_formatter(self):
        settings = ServiceSettings(log_json=True, log_level="INFO")
        configure_logging(settings)
        root = logging.getLogger()
        assert len(root.handlers) >= 1
        assert isinstance(root.handlers[0].formatter, _JSONFormatter)

    def test_configure_logging_plain_mode_attaches_text_formatter(self):
        settings = ServiceSettings(log_json=False, log_level="INFO")
        configure_logging(settings)
        root = logging.getLogger()
        assert not isinstance(root.handlers[0].formatter, _JSONFormatter)
