"""
Proxy Schemas - API 请求和响应模型

定义代理服务相关的 API 数据结构。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ==================== Workspace Schemas ====================


class WorkspaceCreate(BaseModel):
    """创建工作区域请求"""

    workspace_id: str = Field(description="工作区域 ID")
    root_path: str = Field(description="工作区域根路径")
    namespace: str = Field(default="default", description="命名空间")
    allowed_tools: list[str] = Field(default=["*"], description="允许的工具列表")
    denied_tools: list[str] = Field(default=[], description="拒绝的工具列表")
    is_readonly: bool = Field(default=False, description="是否只读")
    denied_paths: list[str] = Field(default=[], description="拒绝访问的路径模式")
    max_file_size: int = Field(default=10485760, description="最大文件大小 (字节)")
    enable_symlinks: bool = Field(default=False, description="是否允许符号链接")


class WorkspaceResponse(BaseModel):
    """工作区域响应"""

    workspace_id: str = Field(description="工作区域 ID")
    root_path: str = Field(description="工作区域根路径")
    namespace: str = Field(description="命名空间")
    is_readonly: bool = Field(description="是否只读")
    allowed_tools: list[str] = Field(description="允许的工具列表")
    denied_tools: list[str] = Field(description="拒绝的工具列表")


class WorkspaceListResponse(BaseModel):
    """工作区域列表响应"""

    workspaces: list[str] = Field(description="工作区域 ID 列表")
    total: int = Field(description="总数")


# ==================== Agent Config Override Schemas ====================


class AgentConfigOverride(BaseModel):
    """Agent 运行时配置覆盖

    所有字段均为可选，仅提供的字段会覆盖 agent.yaml 中的默认值。
    优先级：运行时覆盖 > agent.yaml 定义 > 系统默认值。
    """

    provider: str | None = Field(default=None, description="LLM 提供商 (anthropic/openai/google)")
    model: str | None = Field(default=None, description="模型 ID")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int | None = Field(default=None, gt=0, description="最大 token 数")
    max_iterations: int | None = Field(default=None, gt=0, description="最大迭代次数")
    system_prompt: str | None = Field(default=None, description="覆盖系统提示词")
    extra: dict[str, Any] | None = Field(default=None, description="其他扩展配置")


# ==================== Session Schemas ====================


class SessionCreate(BaseModel):
    """创建会话请求"""

    workspace_id: str = Field(description="工作区域 ID")
    agent_id: str = Field(description="Agent ID")
    metadata: dict[str, Any] | None = Field(default=None, description="元数据")
    agent_config: AgentConfigOverride | None = Field(
        default=None, description="Agent 运行时配置覆盖（优先级高于 agent.yaml）"
    )


class SessionResponse(BaseModel):
    """会话响应"""

    session_id: str = Field(description="会话 ID")
    workspace_id: str = Field(description="工作区域 ID")
    agent_id: str = Field(description="Agent ID")
    status: str = Field(description="会话状态")
    message_count: int = Field(description="消息数量")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class SessionListResponse(BaseModel):
    """会话列表响应"""

    sessions: list[SessionResponse] = Field(description="会话列表")
    total: int = Field(description="总数")


# ==================== Execute Schemas ====================


class ProxyExecuteRequest(BaseModel):
    """执行请求"""

    session_id: str = Field(description="会话 ID")
    prompt: str = Field(description="用户输入")
    context: dict[str, Any] | None = Field(default=None, description="执行上下文")


class ProxyExecuteResponse(BaseModel):
    """执行响应"""

    session_id: str = Field(description="会话 ID")
    success: bool = Field(description="是否成功")
    output: str = Field(description="输出内容")
    error: str | None = Field(default=None, description="错误信息")
    iterations: int = Field(default=0, description="迭代次数")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ProxyStreamEvent(BaseModel):
    """流式事件

    phase 字段标识当前输出所处的执行阶段（从 1 开始递增）。
    前端可据此实现分段渲染：Phase 1 快速直达回复、Phase 2+ 深度分析。
    """

    type: Literal[
        "stream",
        "tool_start",
        "tool_result",
        "complete",
        "error",
        "phase_start",
    ] = Field(description="事件类型")
    phase: int | None = Field(default=None, description="当前执行阶段 (1=快速响应, 2+=深度分析)")
    # For phase_start events
    phase_label: str | None = Field(default=None, description="阶段标签 (如 '快速响应', '深度分析')")
    # For stream events
    event: Any | None = Field(default=None, description="流式事件数据")
    # For tool_start events
    tool_name: str | None = Field(default=None, description="工具名称")
    tool_id: str | None = Field(default=None, description="工具调用 ID")
    # For tool_result events
    result: str | None = Field(default=None, description="工具执行结果")
    # For complete events
    text: str | None = Field(default=None, description="完成文本")
    # For error events
    message: str | None = Field(default=None, description="错误消息")


# ==================== Stats Schemas ====================


class ProxyStatsResponse(BaseModel):
    """代理服务统计响应"""

    workspaces: dict[str, Any] = Field(description="工作区域统计")
    sessions: dict[str, Any] = Field(description="会话统计")
    executor_cache_size: int = Field(description="执行器缓存大小")
