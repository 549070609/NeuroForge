"""
Agent API Routes - Agent 相关的 REST API 端点

提供:
- Agent 列表和详情
- Agent 执行
- 命名空间管理
- 计划 CRUD 操作
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from ...schemas.agents import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentInfoResponse,
    AgentListResponse,
    AgentStatsResponse,
    NamespaceListResponse,
    PlanCreate,
    PlanListResponse,
    PlanResponse,
    PlanStatsResponse,
    StepAddRequest,
    StepUpdateRequest,
)
from ...services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["Agents"])

# 计划相关的单独路由
plan_router = APIRouter(prefix="/plans", tags=["Plans"])


# ==================== 依赖注入 ====================


def get_agent_service() -> AgentService:
    """获取 AgentService 实例"""
    from ...core.registry import AGENT_SERVICE_KEY, ServiceRegistry

    registry = ServiceRegistry()
    service = registry.get(AGENT_SERVICE_KEY)
    if service is None:
        # 如果服务未注册，创建一个临时实例
        service = AgentService(registry)
    return service


# ==================== Agent 端点 ====================


@router.get("", response_model=AgentListResponse)
async def list_agents(
    namespace: Annotated[str | None, Query(description="Filter by namespace")] = None,
    tags: Annotated[
        str | None, Query(description="Filter by tags (comma-separated)")
    ] = None,
) -> AgentListResponse:
    """
    列出所有可用的 Agent

    - **namespace**: 可选，按命名空间过滤
    - **tags**: 可选，按标签过滤 (逗号分隔)
    """
    service = get_agent_service()
    tag_list = tags.split(",") if tags else None
    return service.list_agents(namespace=namespace, tags=tag_list)


@router.get("/stats", response_model=AgentStatsResponse)
async def get_agent_stats() -> AgentStatsResponse:
    """获取 Agent 统计信息"""
    service = get_agent_service()
    return service.get_stats()


@router.get("/namespaces", response_model=NamespaceListResponse)
async def list_namespaces() -> NamespaceListResponse:
    """列出所有命名空间"""
    service = get_agent_service()
    return service.list_namespaces()


@router.get("/refresh")
async def refresh_agents() -> dict[str, str]:
    """刷新 Agent 目录缓存"""
    service = get_agent_service()
    service.refresh()
    return {"status": "ok", "message": "Agent directory refreshed"}


@router.get("/{agent_id}", response_model=AgentInfoResponse)
async def get_agent(agent_id: str) -> AgentInfoResponse:
    """
    获取 Agent 详情

    - **agent_id**: Agent ID (如 'plan' 或 'team-alpha{custom-agent')
    """
    service = get_agent_service()
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )
    return agent


@router.post("/{agent_id}/execute", response_model=AgentExecuteResponse)
async def execute_agent(
    agent_id: str,
    request: AgentExecuteRequest,
) -> AgentExecuteResponse:
    """
    执行 Agent

    - **agent_id**: 要执行的 Agent ID
    - **request**: 包含任务描述和可选上下文
    """
    service = get_agent_service()

    # 检查 Agent 是否存在
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    # 执行 Agent
    result = await service.execute_agent(
        agent_id=agent_id,
        task=request.task,
        context=request.context,
        options=request.options,
    )

    from datetime import datetime, timezone

    def _utcnow():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    return AgentExecuteResponse(
        agent_id=agent_id,
        status=result.get("status", "error"),
        result=result.get("result"),
        plan_id=result.get("plan_id"),
        error=result.get("error"),
        started_at=datetime.fromisoformat(result["started_at"].rstrip("Z"))
        if result.get("started_at")
        else _utcnow(),
        completed_at=datetime.fromisoformat(result["completed_at"].rstrip("Z"))
        if result.get("completed_at")
        else None,
    )


# ==================== Plan 端点 ====================


@plan_router.get("", response_model=PlanListResponse)
async def list_plans(
    namespace: Annotated[str | None, Query(description="Filter by namespace")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
) -> PlanListResponse:
    """
    列出所有计划

    - **namespace**: 可选，按命名空间过滤
    - **status**: 可选，按状态过滤 (active/completed/paused/cancelled)
    """
    service = get_agent_service()
    return service.list_plans(namespace=namespace, status=status)


@plan_router.get("/stats", response_model=PlanStatsResponse)
async def get_plan_stats() -> PlanStatsResponse:
    """获取计划统计信息"""
    service = get_agent_service()
    return service.get_plan_stats()


@plan_router.post("", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_plan(request: PlanCreate) -> PlanResponse:
    """
    创建新计划

    请求体包含:
    - **title**: 计划标题
    - **objective**: 目标描述
    - **steps**: 步骤列表 (可选)
    - **priority**: 优先级 (high/medium/low)
    - **namespace**: 命名空间
    """
    service = get_agent_service()
    plan = service.create_plan(request)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create plan",
        )
    return plan


@plan_router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str) -> PlanResponse:
    """
    获取计划详情

    - **plan_id**: 计划 ID (如 'plan-20240221-abc123')
    """
    service = get_agent_service()
    plan = service.get_plan(plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_id}",
        )
    return plan


@plan_router.delete("/{plan_id}")
async def delete_plan(plan_id: str) -> dict[str, str]:
    """
    删除计划

    - **plan_id**: 要删除的计划 ID
    """
    service = get_agent_service()
    success = service.delete_plan(plan_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_id}",
        )
    return {"status": "ok", "message": f"Plan {plan_id} deleted"}


@plan_router.patch("/{plan_id}/steps/{step_id}", response_model=PlanResponse)
async def update_step(
    plan_id: str,
    step_id: str,
    request: StepUpdateRequest,
) -> PlanResponse:
    """
    更新步骤状态

    - **plan_id**: 计划 ID
    - **step_id**: 步骤 ID
    - **status**: 新状态 (pending/in_progress/completed/blocked/skipped)
    - **notes**: 备注 (可选)
    """
    service = get_agent_service()
    plan = service.update_step(plan_id, step_id, request)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan or step not found: {plan_id}/{step_id}",
        )
    return plan


@plan_router.post("/{plan_id}/steps", response_model=PlanResponse)
async def add_step(
    plan_id: str,
    request: StepAddRequest,
) -> PlanResponse:
    """
    添加步骤到计划

    - **plan_id**: 计划 ID
    - **title**: 步骤标题
    - **description**: 详细描述 (可选)
    - **dependencies**: 依赖的步骤 ID (可选)
    """
    service = get_agent_service()
    plan = service.add_step(plan_id, request)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan not found: {plan_id}",
        )
    return plan
