"""全局门禁 · OpenAPI 契约自检

验证 FastAPI app 能稳定生成 OpenAPI schema 且关键路由 / 响应模型齐备。
schemathesis 属性测试依赖此 schema 的正确性，这里作为上游健壮性门禁。
"""

from __future__ import annotations

import pytest
from fastapi.openapi.utils import get_openapi

from Service.config.settings import ServiceSettings
from Service.gateway.app import create_app


@pytest.fixture
def app():
    settings = ServiceSettings(debug=True, rate_limit_enabled=False)
    return create_app(settings=settings)


class TestOpenAPISchema:
    def test_schema_generates(self, app):
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )
        assert schema["openapi"].startswith("3.")
        assert "paths" in schema

    def test_agent_execute_response_in_schema(self, app):
        """P1-10: AgentExecuteResponse 应出现在 components/schemas。"""
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = schema.get("components", {}).get("schemas", {})
        assert "AgentExecuteResponse" in components, (
            f"AgentExecuteResponse missing; found: {sorted(components.keys())}"
        )

    def test_error_detail_in_schema(self, app):
        """P1-10: ErrorDetail 子模型应出现。"""
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = schema.get("components", {}).get("schemas", {})
        assert "ErrorDetail" in components

    def test_status_literal_enum(self, app):
        """P1-10: AgentExecuteResponse.status 应为 Literal 枚举。"""
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = schema.get("components", {}).get("schemas", {})
        resp = components.get("AgentExecuteResponse", {})
        status_field = resp.get("properties", {}).get("status", {})
        # Literal 会生成 enum 或 allOf/$ref
        has_enum = "enum" in status_field or any(
            "enum" in str(v) for v in status_field.values()
        )
        assert has_enum, f"status field not an enum: {status_field}"
