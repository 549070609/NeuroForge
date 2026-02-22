"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# === Common Schemas ===


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    code: str | None = None
    details: dict[str, Any] | None = None


# === Tool Schemas ===


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


# === Agent Schemas ===
# Re-export from agents.py for convenience
from .agents import (
    AgentInfoResponse,
    AgentListResponse,
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentStatsResponse,
    NamespaceInfo,
    NamespaceListResponse,
    PlanCreate,
    PlanResponse,
    PlanListResponse,
    PlanStatsResponse,
    StepCreate,
    StepResponse,
    StepUpdateRequest,
    StepAddRequest,
)

__all__ = [
    # Common
    "HealthResponse",
    "ErrorResponse",
    # Tools
    "ToolInfo",
    "ExecuteToolRequest",
    "ExecuteToolResponse",
    # Agents
    "AgentInfoResponse",
    "AgentListResponse",
    "AgentExecuteRequest",
    "AgentExecuteResponse",
    "AgentStatsResponse",
    "NamespaceInfo",
    "NamespaceListResponse",
    # Plans
    "PlanCreate",
    "PlanResponse",
    "PlanListResponse",
    "PlanStatsResponse",
    "StepCreate",
    "StepResponse",
    "StepUpdateRequest",
    "StepAddRequest",
]
