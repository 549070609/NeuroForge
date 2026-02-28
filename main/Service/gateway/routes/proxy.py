"""
Proxy API Routes - 代理服务相关的 REST API 端点

提供:
- 工作区域管理
- 会话管理
- Agent 执行 (同步和流式)
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ...schemas.proxy import (
    AgentConfigOverride,
    ProxyExecuteRequest,
    ProxyExecuteResponse,
    ProxyStatsResponse,
    ProxyStreamEvent,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proxy", tags=["Proxy"])


# ==================== 依赖注入 ====================


def get_proxy_service() -> Any:
    """获取 AgentProxyService 实例"""
    from ...core.registry import ServiceRegistry
    from ...services.proxy.agent_proxy_service import AgentProxyService

    registry = ServiceRegistry()
    service = registry.get("proxy")
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Proxy service not available",
        )
    return service


# ==================== 工作区域端点 ====================


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(request: WorkspaceCreate) -> WorkspaceResponse:
    """
    创建工作区域

    - **workspace_id**: 工作区域唯一标识符
    - **root_path**: 工作区域根路径
    - **namespace**: 命名空间 (默认: default)
    - **is_readonly**: 是否只读模式
    """
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

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces() -> WorkspaceListResponse:
    """列出所有工作区域"""
    service = get_proxy_service()
    workspaces = service.list_workspaces()
    return WorkspaceListResponse(workspaces=workspaces, total=len(workspaces))


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str) -> WorkspaceResponse:
    """
    获取工作区域详情

    - **workspace_id**: 工作区域 ID
    """
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
    """
    移除工作区域

    注意：这不会删除文件系统上的目录。

    - **workspace_id**: 要移除的工作区域 ID
    """
    service = get_proxy_service()
    success = await service.remove_workspace(workspace_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace not found: {workspace_id}",
        )

    return {"status": "ok", "message": f"Workspace {workspace_id} removed"}


# ==================== 会话端点 ====================


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(request: SessionCreate) -> SessionResponse:
    """
    创建会话

    - **workspace_id**: 工作区域 ID
    - **agent_id**: 要使用的 Agent ID
    - **metadata**: 可选的元数据
    """
    service = get_proxy_service()

    try:
        agent_config = (
            request.agent_config.model_dump(exclude_none=True)
            if request.agent_config
            else None
        )
        session = await service.create_session(
            workspace_id=request.workspace_id,
            agent_id=request.agent_id,
            metadata=request.metadata,
            agent_config=agent_config,
        )
        return SessionResponse(**session.to_dict())

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    workspace_id: str | None = None,
    agent_id: str | None = None,
) -> SessionListResponse:
    """
    列出会话

    - **workspace_id**: 可选，按工作区域过滤
    - **agent_id**: 可选，按 Agent 过滤
    """
    service = get_proxy_service()
    sessions = await service.list_sessions(workspace_id=workspace_id, agent_id=agent_id)

    return SessionListResponse(
        sessions=[SessionResponse(**s.to_dict()) for s in sessions],
        total=len(sessions),
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    """
    获取会话详情

    - **session_id**: 会话 ID
    """
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
    """
    删除会话

    - **session_id**: 要删除的会话 ID
    """
    service = get_proxy_service()
    success = await service.delete_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    return {"status": "ok", "message": f"Session {session_id} deleted"}


# ==================== 执行端点 ====================


@router.post("/execute", response_model=ProxyExecuteResponse)
async def execute(request: ProxyExecuteRequest) -> ProxyExecuteResponse:
    """
    执行 Agent

    - **session_id**: 会话 ID
    - **prompt**: 用户输入
    - **context**: 可选的执行上下文
    """
    service = get_proxy_service()

    try:
        result = await service.execute(
            session_id=request.session_id,
            prompt=request.prompt,
            context=request.context,
        )

        return ProxyExecuteResponse(
            session_id=request.session_id,
            success=result.success,
            output=result.output,
            error=result.error,
            iterations=result.iterations,
            metadata=result.metadata,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/execute/stream")
async def execute_stream(request: ProxyExecuteRequest) -> StreamingResponse:
    """
    流式执行 Agent

    返回 Server-Sent Events (SSE) 格式的流式响应。

    - **session_id**: 会话 ID
    - **prompt**: 用户输入
    - **context**: 可选的执行上下文
    """
    service = get_proxy_service()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in service.execute_stream(
                session_id=request.session_id,
                prompt=request.prompt,
                context=request.context,
            ):
                # 将事件转换为 SSE 格式
                event_data = ProxyStreamEvent(**event).model_dump_json()
                yield f"data: {event_data}\n\n"

        except ValueError as e:
            error_event = ProxyStreamEvent(type="error", message=str(e))
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


# ==================== 统计端点 ====================


@router.get("/stats", response_model=ProxyStatsResponse)
async def get_stats() -> ProxyStatsResponse:
    """获取代理服务统计信息"""
    service = get_proxy_service()
    stats = service.get_stats()

    return ProxyStatsResponse(**stats)
