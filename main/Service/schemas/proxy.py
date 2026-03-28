"""Proxy schemas for workspace/session, execution, workflow, and tracing APIs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    workspace_id: str = Field(description="Workspace ID")
    root_path: str = Field(description="Workspace root path")
    namespace: str = Field(default="default", description="Namespace")
    allowed_tools: list[str] = Field(default=["*"], description="Allowed tools")
    denied_tools: list[str] = Field(default=[], description="Denied tools")
    is_readonly: bool = Field(default=False, description="Read-only mode")
    denied_paths: list[str] = Field(default=[], description="Denied path patterns")
    max_file_size: int = Field(default=10485760, description="Max file size")
    enable_symlinks: bool = Field(default=False, description="Allow symlinks")


class WorkspaceResponse(BaseModel):
    workspace_id: str = Field(description="Workspace ID")
    root_path: str = Field(description="Workspace root path")
    namespace: str = Field(description="Namespace")
    is_readonly: bool = Field(description="Read-only mode")
    allowed_tools: list[str] = Field(description="Allowed tools")
    denied_tools: list[str] = Field(description="Denied tools")


class WorkspaceListResponse(BaseModel):
    workspaces: list[str] = Field(description="Workspace ID list")
    total: int = Field(description="Total")


class AgentConfigOverride(BaseModel):
    provider: str | None = Field(default=None, description="Provider")
    model: str | None = Field(default=None, description="Model ID")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="Temperature")
    max_tokens: int | None = Field(default=None, gt=0, description="Max tokens")
    max_iterations: int | None = Field(default=None, gt=0, description="Max iterations")
    system_prompt: str | None = Field(default=None, description="Override system prompt")
    extra: dict[str, Any] | None = Field(default=None, description="Extra config")


class SessionCreate(BaseModel):
    workspace_id: str = Field(description="Workspace ID")
    agent_id: str = Field(description="Agent ID")
    metadata: dict[str, Any] | None = Field(default=None, description="Metadata")
    agent_config: AgentConfigOverride | None = Field(default=None, description="Runtime config override")


class SessionResponse(BaseModel):
    session_id: str = Field(description="Session ID")
    workspace_id: str = Field(description="Workspace ID")
    agent_id: str = Field(description="Agent ID")
    status: str = Field(description="Session status")
    message_count: int = Field(description="Message count")
    created_at: str = Field(description="Created timestamp")
    updated_at: str = Field(description="Updated timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    trace_id: str | None = Field(default=None, description="Last trace ID")


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse] = Field(description="Session list")
    total: int = Field(description="Total")


class ProxyExecuteRequest(BaseModel):
    session_id: str = Field(description="Session ID")
    prompt: str = Field(description="User prompt")
    context: dict[str, Any] | None = Field(default=None, description="Execution context")
    trace_id: str | None = Field(default=None, description="Optional upstream trace ID")


class ProxyExecuteResponse(BaseModel):
    session_id: str = Field(description="Session ID")
    success: bool = Field(description="Success")
    output: str = Field(description="Output")
    error: str | None = Field(default=None, description="Error")
    iterations: int = Field(default=0, description="Iteration count")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    trace_id: str | None = Field(default=None, description="Trace ID")
    span_id: str | None = Field(default=None, description="Root span ID")


class ProxyStreamEvent(BaseModel):
    type: Literal[
        "stream",
        "tool_start",
        "tool_result",
        "complete",
        "error",
        "phase_start",
    ] = Field(description="Event type")
    phase: int | None = Field(default=None, description="Execution phase")
    phase_label: str | None = Field(default=None, description="Phase label")
    event: Any | None = Field(default=None, description="Stream payload")
    tool_name: str | None = Field(default=None, description="Tool name")
    tool_id: str | None = Field(default=None, description="Tool call ID")
    result: str | None = Field(default=None, description="Tool result")
    text: str | None = Field(default=None, description="Completion text")
    message: str | None = Field(default=None, description="Error message")
    trace_id: str | None = Field(default=None, description="Trace ID")
    span_id: str | None = Field(default=None, description="Span ID")


class WorkflowCreateRequest(BaseModel):
    session_id: str = Field(description="Session ID")
    task: str = Field(description="Workflow task")
    workflow_type: Literal["graph", "team"] = Field(default="graph", description="Workflow runtime")
    metadata: dict[str, Any] | None = Field(default=None, description="Workflow metadata")
    idempotency_key: str | None = Field(default=None, description="Idempotency key")


class WorkflowResponse(BaseModel):
    id: str = Field(description="Workflow ID")
    session_id: str = Field(description="Session ID")
    task: str = Field(description="Task")
    workflow_type: str = Field(description="Workflow type")
    status: str = Field(description="Workflow status")
    thread_id: str = Field(description="Workflow thread ID")
    result: str | None = Field(default=None, description="Workflow result")
    error: str | None = Field(default=None, description="Workflow error")
    trace_id: str | None = Field(default=None, description="Trace ID")
    steps: list[dict[str, Any]] = Field(default_factory=list, description="Step traces")
    elapsed_ms: int = Field(default=0, description="Elapsed ms")
    created_at: str = Field(description="Created timestamp")
    updated_at: str = Field(description="Updated timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    version: int | None = Field(default=None, description="Store version")


class TraceResponse(BaseModel):
    trace_id: str = Field(description="Trace ID")
    scope: str = Field(description="Trace scope")
    session_id: str | None = Field(default=None, description="Session ID")
    workflow_id: str | None = Field(default=None, description="Workflow ID")
    summary: dict[str, Any] = Field(default_factory=dict, description="Trace summary")
    spans: list[dict[str, Any]] = Field(default_factory=list, description="Span list")
    updated_at: str = Field(description="Updated timestamp")


class ProxyStatsResponse(BaseModel):
    workspaces: dict[str, Any] = Field(description="Workspace stats")
    sessions: dict[str, Any] = Field(description="Session stats")
    executor_cache_size: int = Field(description="Executor cache size")
    workflows: dict[str, Any] = Field(default_factory=dict, description="Workflow stats")
    traces: dict[str, Any] = Field(default_factory=dict, description="Trace stats")
    store_backend: str | None = Field(default=None, description="Storage backend")
