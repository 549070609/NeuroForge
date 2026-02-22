"""Schemas for migrated legacy pyagentforge runtime API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Request body for creating a runtime session."""

    agent_id: str | None = Field(default=None, description="Optional legacy agent identifier")
    system_prompt: str | None = Field(default=None, description="Optional session system prompt")


class CreateSessionResponse(BaseModel):
    """Response body for session creation."""

    session_id: str
    status: str


class SendMessageRequest(BaseModel):
    """Request body for sending a message to a session."""

    message: str = Field(..., description="User message content")
    stream: bool = Field(default=False, description="Reserved compatibility flag")


class MessageResponse(BaseModel):
    """Response body for a session message result."""

    role: str
    content: str


class SessionDetail(BaseModel):
    """Session detail payload."""

    session_id: str
    status: str
    message_count: int
    messages: list[dict[str, Any]]


class AgentCreateRequest(BaseModel):
    """Request body for creating a legacy runtime agent profile."""

    name: str = Field(..., description="Agent name")
    description: str | None = Field(default=None, description="Optional agent description")
    system_prompt: str = Field(
        default="You are a helpful AI assistant.",
        description="System prompt associated with the agent",
    )
    allowed_tools: list[str] = Field(default_factory=lambda: ["*"], description="Allowed tools")
    model: str = Field(default="claude-sonnet-4-20250514", description="Model id")


class AgentUpdateRequest(BaseModel):
    """Request body for updating a legacy runtime agent profile."""

    description: str | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    """Legacy runtime agent response payload."""

    id: str
    name: str
    description: str | None
    model: str
    is_active: bool