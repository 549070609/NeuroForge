"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return a naive UTC datetime (timezone stripped for backward compat)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

from .agents import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentInfoResponse,
    AgentListResponse,
    AgentStatsResponse,
    NamespaceInfo,
    NamespaceListResponse,
    PlanCreate,
    PlanListResponse,
    PlanResponse,
    PlanStatsResponse,
    StepAddRequest,
    StepCreate,
    StepResponse,
    StepUpdateRequest,
)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=_utcnow)


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    code: str | None = None
    details: dict[str, Any] | None = None


class ToolInfo(BaseModel):
    """Tool information."""

    name: str
    description: str
    parameters: dict[str, Any]


class ExecuteToolRequest(BaseModel):
    """Request to execute a tool."""

    tool_name: str
    parameters: dict[str, Any]


class ExecuteToolResponse(BaseModel):
    """Response for tool execution."""

    tool_name: str
    result: Any
    error: str | None = None


__all__ = [
    "HealthResponse",
    "ErrorResponse",
    "ToolInfo",
    "ExecuteToolRequest",
    "ExecuteToolResponse",
    "AgentInfoResponse",
    "AgentListResponse",
    "AgentExecuteRequest",
    "AgentExecuteResponse",
    "AgentStatsResponse",
    "NamespaceInfo",
    "NamespaceListResponse",
    "PlanCreate",
    "PlanResponse",
    "PlanListResponse",
    "PlanStatsResponse",
    "StepCreate",
    "StepResponse",
    "StepUpdateRequest",
    "StepAddRequest",
]
