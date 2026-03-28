"""Proxy API routes for workspace/session execution, workflows, and tracing."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ...schemas.proxy import (
    ProxyExecuteRequest,
    ProxyExecuteResponse,
    ProxyStatsResponse,
    ProxyStreamEvent,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    TraceResponse,
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proxy", tags=["Proxy"])


def get_proxy_service() -> Any:
    """Get AgentProxyService instance."""
    from ...core.registry import ServiceRegistry

    registry = ServiceRegistry()
    service = registry.get("proxy")
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Proxy service not available",
        )
    return service


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(request: WorkspaceCreate) -> WorkspaceResponse:
    service = get_proxy_service()
    try:
        result = service.create_workspace(
            workspace_id=request.workspace_id,
            root_path=request.root_path,
            namespace=request.namespace,
            allowed_tools=request.allowed_tools,
            denied_tools=request.denied_tools,
            is_readonly=request.is_readonly,
            denied_paths=request.denied_paths,
            max_file_size=request.max_file_size,
            enable_symlinks=request.enable_symlinks,
        )
        return WorkspaceResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces() -> WorkspaceListResponse:
    service = get_proxy_service()
    workspaces = service.list_workspaces()
    return WorkspaceListResponse(workspaces=workspaces, total=len(workspaces))


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str) -> WorkspaceResponse:
    service = get_proxy_service()
    result = service.get_workspace(workspace_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found: {workspace_id}",
        )
    return WorkspaceResponse(**result)


@router.delete("/workspaces/{workspace_id}")
async def remove_workspace(workspace_id: str) -> dict[str, str]:
    service = get_proxy_service()
    success = await service.remove_workspace(workspace_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found: {workspace_id}",
        )
    return {"status": "ok", "message": f"Workspace {workspace_id} removed"}


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: SessionCreate) -> SessionResponse:
    service = get_proxy_service()
    try:
        agent_config = request.agent_config.model_dump(exclude_none=True) if request.agent_config else None
        session = await service.create_session(
            workspace_id=request.workspace_id,
            agent_id=request.agent_id,
            metadata=request.metadata,
            agent_config=agent_config,
        )
        return SessionResponse(**session.to_dict())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    workspace_id: str | None = None,
    agent_id: str | None = None,
) -> SessionListResponse:
    service = get_proxy_service()
    sessions = await service.list_sessions(workspace_id=workspace_id, agent_id=agent_id)
    return SessionListResponse(
        sessions=[SessionResponse(**session.to_dict()) for session in sessions],
        total=len(sessions),
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    service = get_proxy_service()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return SessionResponse(**session.to_dict())


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, str]:
    service = get_proxy_service()
    success = await service.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )
    return {"status": "ok", "message": f"Session {session_id} deleted"}


@router.post("/execute", response_model=ProxyExecuteResponse)
async def execute(request: ProxyExecuteRequest) -> ProxyExecuteResponse:
    service = get_proxy_service()
    try:
        result = await service.execute(
            session_id=request.session_id,
            prompt=request.prompt,
            context=request.context,
            trace_id=request.trace_id,
        )
        return ProxyExecuteResponse(
            session_id=request.session_id,
            success=result.success,
            output=result.output,
            error=result.error,
            iterations=result.iterations,
            metadata=result.metadata,
            trace_id=result.metadata.get("trace_id") if result.metadata else None,
            span_id=result.metadata.get("span_id") if result.metadata else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/execute/stream")
async def execute_stream(request: ProxyExecuteRequest) -> StreamingResponse:
    service = get_proxy_service()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in service.execute_stream(
                session_id=request.session_id,
                prompt=request.prompt,
                context=request.context,
                trace_id=request.trace_id,
            ):
                event_data = ProxyStreamEvent(**event).model_dump_json()
                yield f"data: {event_data}\n\n"
        except ValueError as exc:
            error_event = ProxyStreamEvent(type="error", message=str(exc))
            yield f"data: {error_event.model_dump_json()}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(request: WorkflowCreateRequest) -> WorkflowResponse:
    service = get_proxy_service()
    try:
        workflow = await service.create_workflow(
            session_id=request.session_id,
            task=request.task,
            workflow_type=request.workflow_type,
            metadata=request.metadata,
            idempotency_key=request.idempotency_key,
        )
        return WorkflowResponse(**workflow)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str) -> WorkflowResponse:
    service = get_proxy_service()
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow not found: {workflow_id}")
    return WorkflowResponse(**workflow)


@router.post("/workflows/{workflow_id}/start", response_model=WorkflowResponse)
async def start_workflow(workflow_id: str, trace_id: str | None = None) -> WorkflowResponse:
    service = get_proxy_service()
    try:
        workflow = await service.start_workflow(workflow_id, trace_id=trace_id)
        return WorkflowResponse(**workflow)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/pause", response_model=WorkflowResponse)
async def pause_workflow(workflow_id: str) -> WorkflowResponse:
    service = get_proxy_service()
    try:
        workflow = await service.pause_workflow(workflow_id)
        return WorkflowResponse(**workflow)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/workflows/{workflow_id}/resume", response_model=WorkflowResponse)
async def resume_workflow(workflow_id: str, trace_id: str | None = None) -> WorkflowResponse:
    service = get_proxy_service()
    try:
        workflow = await service.resume_workflow(workflow_id, trace_id=trace_id)
        return WorkflowResponse(**workflow)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str) -> TraceResponse:
    service = get_proxy_service()
    trace = await service.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trace not found: {trace_id}")
    return TraceResponse(**trace)


@router.get("/stats", response_model=ProxyStatsResponse)
async def get_stats() -> ProxyStatsResponse:
    service = get_proxy_service()
    stats = await service.get_stats()
    return ProxyStatsResponse(**stats)
