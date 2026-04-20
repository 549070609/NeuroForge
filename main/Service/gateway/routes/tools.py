"""Tool management routes — backed by pyagentforge ToolRegistry."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pyagentforge import BaseTool, ToolRegistry, register_core_tools

from ...schemas import ExecuteToolRequest, ExecuteToolResponse, ToolInfo

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_tool_registry() -> ToolRegistry:
    """
    构建注册了所有核心工具的 ToolRegistry。

    每次请求独立构建（无状态），保证线程安全。
    """
    registry = ToolRegistry()
    register_core_tools(registry)
    return registry


def _tool_to_info(name: str, tool: BaseTool) -> ToolInfo:
    """将 BaseTool 转换为 ToolInfo schema。"""
    try:
        schema: dict[str, Any] = tool.to_anthropic_schema()
    except Exception:
        schema = {}

    description = schema.get("description", "")
    input_schema = schema.get("input_schema", {})
    parameters = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}

    return ToolInfo(
        name=name,
        description=description,
        parameters=parameters,
    )


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools() -> list[ToolInfo]:
    """
    列出所有可用工具。

    工具列表来自 pyagentforge ToolRegistry，动态枚举。

    Returns:
        工具列表，每项包含 name、description、parameters schema。
    """
    registry = _build_tool_registry()
    return [
        _tool_to_info(name, tool)
        for name, tool in registry.get_all().items()
    ]


@router.post("/tools/{tool_name}/execute", response_model=ExecuteToolResponse)
async def execute_tool(
    tool_name: str,
    request: ExecuteToolRequest,
) -> ExecuteToolResponse:
    """
    直接执行指定工具。

    工具在默认系统上下文中运行（非工作区沙箱）。
    生产环境中请通过 /api/v1/proxy/execute 执行，以获得工作区隔离。

    Path params:
        tool_name: 工具名称（来自 GET /tools 的 name 字段）

    Request body:
        tool_name: 工具名称（与路径参数一致）
        parameters: 工具参数字典

    Returns:
        tool_name: 工具名称
        result: 执行结果
        error: 错误信息（成功时为 null）
    """
    registry = _build_tool_registry()
    tool = registry.get(tool_name)

    if tool is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. See GET /api/v1/tools for available tools.",
        )

    try:
        result = await tool.execute(**request.parameters)
        return ExecuteToolResponse(
            tool_name=tool_name,
            result=result,
            error=None,
        )
    except TypeError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid tool parameters: {e}",
        ) from e
    except Exception as e:
        logger.exception("Tool execution failed: tool=%s", tool_name)
        raise HTTPException(
            status_code=500,
            detail=f"Tool execution failed: {e}",
        ) from e
