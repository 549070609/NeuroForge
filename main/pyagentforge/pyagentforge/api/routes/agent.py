"""
Agent API 路由

管理 Agent 配置
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ============ 请求/响应模型 ============


class AgentCreateRequest(BaseModel):
    """创建 Agent 请求"""

    name: str = Field(..., description="Agent 名称")
    description: str | None = Field(default=None, description="Agent 描述")
    system_prompt: str = Field(..., description="系统提示词")
    allowed_tools: list[str] = Field(default=["*"], description="允许的工具")
    model: str = Field(default="claude-sonnet-4-20250514", description="使用的模型")


class AgentUpdateRequest(BaseModel):
    """更新 Agent 请求"""

    description: str | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    is_active: bool | None = None


class AgentResponse(BaseModel):
    """Agent 响应"""

    id: str
    name: str
    description: str | None
    model: str
    is_active: bool


# ============ Agent 存储 (简化实现) ============

_agents: dict[str, dict[str, Any]] = {}


# ============ API 端点 ============


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(request: AgentCreateRequest) -> AgentResponse:
    """创建 Agent"""
    import uuid

    agent_id = str(uuid.uuid4())

    agent_data = {
        "id": agent_id,
        "name": request.name,
        "description": request.description,
        "system_prompt": request.system_prompt,
        "allowed_tools": request.allowed_tools,
        "model": request.model,
        "is_active": True,
    }

    _agents[agent_id] = agent_data

    logger.info(
        "Created agent",
        extra_data={"agent_id": agent_id, "name": request.name},
    )

    return AgentResponse(
        id=agent_id,
        name=request.name,
        description=request.description,
        model=request.model,
        is_active=True,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str) -> AgentResponse:
    """获取 Agent 详情"""
    if agent_id not in _agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    agent = _agents[agent_id]

    return AgentResponse(
        id=agent["id"],
        name=agent["name"],
        description=agent["description"],
        model=agent["model"],
        is_active=agent["is_active"],
    )


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, request: AgentUpdateRequest) -> AgentResponse:
    """更新 Agent"""
    if agent_id not in _agents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    agent = _agents[agent_id]

    if request.description is not None:
        agent["description"] = request.description
    if request.system_prompt is not None:
        agent["system_prompt"] = request.system_prompt
    if request.allowed_tools is not None:
        agent["allowed_tools"] = request.allowed_tools
    if request.is_active is not None:
        agent["is_active"] = request.is_active

    logger.info(
        "Updated agent",
        extra_data={"agent_id": agent_id},
    )

    return AgentResponse(
        id=agent["id"],
        name=agent["name"],
        description=agent["description"],
        model=agent["model"],
        is_active=agent["is_active"],
    )


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: str) -> None:
    """删除 Agent"""
    if agent_id in _agents:
        del _agents[agent_id]
        logger.info(
            "Deleted agent",
            extra_data={"agent_id": agent_id},
        )


@router.get("")
async def list_agents() -> dict[str, list[dict[str, Any]]]:
    """列出所有 Agent"""
    return {
        "agents": [
            {
                "id": agent["id"],
                "name": agent["name"],
                "description": agent["description"],
                "model": agent["model"],
                "is_active": agent["is_active"],
            }
            for agent in _agents.values()
        ]
    }
