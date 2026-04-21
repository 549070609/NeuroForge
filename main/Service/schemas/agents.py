"""
Agent Schemas - API 请求和响应模型

定义 Agent 相关的 API 数据结构。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return a tz-aware UTC datetime (P1-10: 保留 tzinfo)."""
    return datetime.now(timezone.utc)

# ==================== Agent Schemas ====================


class AgentInfoResponse(BaseModel):
    """Agent 信息响应"""

    id: str = Field(description="Agent ID")
    name: str = Field(description="Agent 名称")
    namespace: str = Field(description="命名空间")
    origin: str = Field(description="来源类型")
    description: str = Field(description="描述")
    tags: list[str] = Field(default_factory=list, description="标签")
    category: str = Field(description="类别")
    is_readonly: bool = Field(description="是否只读")
    max_concurrent: int = Field(description="最大并发数")
    tools: list[str] = Field(default_factory=list, description="允许的工具")
    denied_tools: list[str] = Field(default_factory=list, description="拒绝的工具")


class AgentListResponse(BaseModel):
    """Agent 列表响应"""

    agents: list[AgentInfoResponse]
    total: int = Field(description="总数")
    namespaces: list[str] = Field(default_factory=list, description="命名空间列表")


class NamespaceInfo(BaseModel):
    """命名空间信息"""

    name: str = Field(description="命名空间名称")
    agent_count: int = Field(description="Agent 数量")
    agents: list[str] = Field(default_factory=list, description="Agent ID 列表")


class NamespaceListResponse(BaseModel):
    """命名空间列表响应"""

    namespaces: list[NamespaceInfo]
    total: int = Field(description="总数")


# ==================== Agent Execution Schemas ====================


class AgentExecuteRequest(BaseModel):
    """Agent 执行请求"""

    task: str = Field(description="任务描述")
    context: dict[str, Any] | None = Field(default=None, description="额外上下文")
    namespace: str | None = Field(default=None, description="命名空间 (用于解析 Agent ID)")
    options: dict[str, Any] | None = Field(default=None, description="执行选项")


class ErrorDetail(BaseModel):
    """P1-10: 错误详情子模型"""

    code: str = Field(description="错误类型代码")
    message: str = Field(description="错误描述")


class AgentExecuteResponse(BaseModel):
    """Agent 执行响应（P1-10: Literal status + tz-aware datetime）"""

    agent_id: str = Field(description="执行的 Agent ID")
    status: Literal["completed", "error", "timeout", "cancelled"] = Field(
        description="执行状态",
    )
    result: str | None = Field(default=None, description="执行结果")
    plan_id: str | None = Field(default=None, description="生成的计划 ID (如果是 Plan Agent)")
    error: ErrorDetail | None = Field(default=None, description="错误信息")
    started_at: datetime = Field(default_factory=_utcnow, description="开始时间 (UTC)")
    completed_at: datetime | None = Field(default=None, description="完成时间 (UTC)")


# ==================== Plan Schemas ====================


class StepCreate(BaseModel):
    """步骤创建请求"""

    title: str = Field(description="步骤标题")
    description: str | None = Field(default=None, description="详细描述")
    dependencies: list[str] | None = Field(default=None, description="依赖的步骤 ID")
    estimated_time: str | None = Field(default=None, description="预估时间")
    acceptance_criteria: list[str] | None = Field(default=None, description="验收标准")
    files_affected: list[str] | None = Field(default=None, description="影响的文件")


class PlanCreate(BaseModel):
    """计划创建请求"""

    title: str = Field(description="计划标题")
    objective: str = Field(description="目标描述")
    context: str | None = Field(default=None, description="背景上下文")
    steps: list[StepCreate] | None = Field(default=None, description="步骤列表")
    priority: Literal["high", "medium", "low"] = Field(default="medium", description="优先级")
    namespace: str = Field(default="default", description="命名空间")
    estimated_complexity: Literal["high", "medium", "low"] = Field(
        default="medium", description="预估复杂度"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="扩展元数据")


class StepResponse(BaseModel):
    """步骤响应"""

    id: str
    title: str
    status: str
    description: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    estimated_time: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    files_affected: list[str] = Field(default_factory=list)
    notes: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class PlanResponse(BaseModel):
    """计划响应"""

    id: str
    title: str
    objective: str
    status: str
    priority: str
    namespace: str
    estimated_complexity: str
    created: str
    updated: str
    context: str | None = None
    steps: list[StepResponse] = Field(default_factory=list)
    progress: float = Field(description="进度百分比")
    change_log: list[dict[str, str]] = Field(default_factory=list)


class PlanListResponse(BaseModel):
    """计划列表响应"""

    plans: list[PlanResponse]
    total: int = Field(description="总数")


class StepUpdateRequest(BaseModel):
    """步骤更新请求"""

    status: Literal["pending", "in_progress", "completed", "blocked", "skipped"] | None = Field(
        default=None, description="新状态"
    )
    notes: str | None = Field(default=None, description="备注")


class StepAddRequest(BaseModel):
    """添加步骤请求"""

    title: str = Field(description="步骤标题")
    description: str | None = Field(default=None, description="详细描述")
    dependencies: list[str] | None = Field(default=None, description="依赖的步骤 ID")
    estimated_time: str | None = Field(default=None, description="预估时间")
    acceptance_criteria: list[str] | None = Field(default=None, description="验收标准")
    files_affected: list[str] | None = Field(default=None, description="影响的文件")


# ==================== Stats Schemas ====================


class AgentStatsResponse(BaseModel):
    """Agent 统计响应"""

    total_agents: int
    total_namespaces: int
    by_origin: dict[str, int]
    namespaces: list[str]


class PlanStatsResponse(BaseModel):
    """计划统计响应"""

    total_plans: int
    by_status: dict[str, int]
