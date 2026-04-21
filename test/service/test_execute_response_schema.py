"""
P1-10 AgentExecuteResponse 响应契约回归测试

验证：
  1. status 字段为 Literal 枚举，非法值被拒绝
  2. started_at / completed_at 是 tz-aware UTC datetime
  3. error 字段为 ErrorDetail 结构（code + message）
  4. _utcnow() 返回 tz-aware datetime
  5. JSON 序列化后 datetime 包含 timezone 信息
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from Service.schemas.agents import (
    AgentExecuteResponse,
    ErrorDetail,
    _utcnow,
)


# ── _utcnow tz-aware ──────────────────────────────────────────

class TestUtcNow:
    def test_returns_tz_aware(self):
        now = _utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc


# ── ErrorDetail ────────────────────────────────────────────────

class TestErrorDetail:
    def test_valid(self):
        err = ErrorDetail(code="AgentTimeoutError", message="timed out")
        assert err.code == "AgentTimeoutError"
        assert err.message == "timed out"


# ── AgentExecuteResponse ──────────────────────────────────────

class TestAgentExecuteResponse:
    def test_completed_response(self):
        resp = AgentExecuteResponse(
            agent_id="plan",
            status="completed",
            result="done",
        )
        assert resp.status == "completed"
        assert resp.error is None
        assert resp.started_at.tzinfo is not None

    def test_error_response_with_detail(self):
        resp = AgentExecuteResponse(
            agent_id="plan",
            status="error",
            error=ErrorDetail(code="AgentProviderError", message="LLM down"),
        )
        assert resp.error is not None
        assert resp.error.code == "AgentProviderError"

    def test_error_response_with_dict(self):
        """error 字段也接受 dict 自动解析为 ErrorDetail。"""
        resp = AgentExecuteResponse(
            agent_id="plan",
            status="error",
            error={"code": "Timeout", "message": "too slow"},
        )
        assert isinstance(resp.error, ErrorDetail)
        assert resp.error.code == "Timeout"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            AgentExecuteResponse(
                agent_id="plan",
                status="unknown_status",
            )

    def test_tz_aware_datetimes(self):
        now = datetime.now(timezone.utc)
        resp = AgentExecuteResponse(
            agent_id="plan",
            status="completed",
            started_at=now,
            completed_at=now,
        )
        assert resp.started_at.tzinfo is not None
        assert resp.completed_at.tzinfo is not None

    def test_json_serialization_includes_timezone(self):
        resp = AgentExecuteResponse(
            agent_id="plan",
            status="completed",
            result="ok",
        )
        data = resp.model_dump_json()
        # tz-aware datetime 序列化后应包含 +00:00 或 Z
        assert "+00:00" in data or "Z" in data

    def test_literal_status_values(self):
        for st in ("completed", "error", "timeout", "cancelled"):
            resp = AgentExecuteResponse(agent_id="x", status=st)
            assert resp.status == st
