"""Routes for migrated legacy pyagentforge runtime API."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from ...core import ServiceRegistry
from ...schemas.legacy_runtime import (
    AgentCreateRequest,
    AgentResponse,
    AgentUpdateRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    MessageResponse,
    SendMessageRequest,
    SessionDetail,
)
from ...services.legacy_runtime_service import LegacyRuntimeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Legacy Runtime"])
websocket_router = APIRouter(tags=["Legacy Runtime"])


def get_legacy_runtime_service() -> LegacyRuntimeService:
    """Resolve LegacyRuntimeService from registry."""
    registry = ServiceRegistry()
    service = registry.get("legacy_runtime")
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Legacy runtime service not available",
        )
    return service


@router.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: CreateSessionRequest,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> CreateSessionResponse:
    payload = await service.create_session(
        agent_id=request.agent_id,
        system_prompt=request.system_prompt,
    )
    return CreateSessionResponse(**payload)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> SessionDetail:
    try:
        data = await service.get_session_detail(session_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return SessionDetail(**data)


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> MessageResponse:
    try:
        data = await service.send_message(session_id, request.message)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return MessageResponse(**data)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> None:
    await service.delete_session(session_id)


@router.get("/sessions")
async def list_sessions(
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> dict[str, list[dict]]:
    return {"sessions": service.list_sessions()}


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreateRequest,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> AgentResponse:
    payload = service.create_agent(request.model_dump())
    return AgentResponse(**payload)


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> AgentResponse:
    try:
        payload = service.get_agent(agent_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return AgentResponse(**payload)


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> AgentResponse:
    try:
        payload = service.update_agent(agent_id, request.model_dump(exclude_unset=True))
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )
    return AgentResponse(**payload)


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> None:
    service.delete_agent(agent_id)


@router.get("/agents")
async def list_agents(
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> dict[str, list[dict]]:
    return {"agents": service.list_agents()}


@websocket_router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    service: LegacyRuntimeService = Depends(get_legacy_runtime_service),
) -> None:
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            message = data.get("message", "")
            if not message:
                continue

            await websocket.send_json({"type": "start", "session_id": session_id})

            try:
                async for event in service.stream_message(session_id, message):
                    if isinstance(event, dict):
                        await websocket.send_json(event)
            except KeyError:
                await websocket.send_json(
                    {"type": "error", "message": f"Session not found: {session_id}"}
                )
            except Exception as exc:
                logger.error("WebSocket runtime error: %s", exc)
                await websocket.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        return