"""
Batch 工具

批量执行工具调用
"""

import asyncio
from typing import Any

from pyagentforge.core.executor import ToolExecutor
from pyagentforge.core.message import ToolUseBlock
from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class BatchTool(BaseTool):
    """Batch 工具 - 批量执行工具调用"""

    name = "batch"
    description = """批量执行多个工具调用。

使用场景:
- 并行读取多个文件
- 批量执行命令
- 提高效率

所有操作并行执行，结果汇总返回。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "invocations": {
                "type": "array",
                "description": "工具调用列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["tool_name", "arguments"],
                },
            },
            "parallel": {
                "type": "boolean",
                "description": "是否并行执行",
                "default": True,
            },
        },
        "required": ["invocations"],
    }
    timeout = 120
    risk_level = "medium"

    def __init__(
        self,
        tool_registry: ToolRegistry,
        executor: ToolExecutor,
    ) -> None:
        self.registry = tool_registry
        self.executor = executor

    async def execute(
        self,
        invocations: list[dict[str, Any]],
        parallel: bool = True,
    ) -> str:
        """执行批量工具调用"""
        logger.info(
            "Executing batch",
            extra_data={"count": len(invocations), "parallel": parallel},
        )

        results = []

        if parallel:
            # 并行执行
            tasks = []
            for i, inv in enumerate(invocations):
                tool_name = inv.get("tool_name")
                args = inv.get("arguments", {})
                tasks.append(self._execute_single(i, tool_name, args))

            results = await asyncio.gather(*tasks)
        else:
            # 顺序执行
            for i, inv in enumerate(invocations):
                tool_name = inv.get("tool_name")
                args = inv.get("arguments", {})
                result = await self._execute_single(i, tool_name, args)
                results.append(result)

        # 格式化结果
        lines = [f"Batch execution: {len(invocations)} invocations\n"]

        success = 0
        failed = 0

        for i, result in enumerate(results):
            tool_name = invocations[i].get("tool_name", "unknown")
            if result.startswith("Error"):
                failed += 1
                lines.append(f"## [{i+1}] {tool_name} - FAILED")
            else:
                success += 1
                lines.append(f"## [{i+1}] {tool_name} - SUCCESS")

            # 截断过长结果
            display_result = result[:2000] if len(result) > 2000 else result
            lines.append(f"```\n{display_result}\n```\n")

        lines.append(f"Summary: {success} succeeded, {failed} failed")
        return "\n".join(lines)

    async def _execute_single(
        self,
        index: int,
        tool_name: str,
        args: dict[str, Any],
    ) -> str:
        """执行单个工具调用"""
        try:
            tool = self.registry.get(tool_name)
            if tool is None:
                return f"Error: Tool '{tool_name}' not found"

            result = await tool.execute(**args)
            return result

        except Exception as e:
            logger.error(
                "Batch invocation error",
                extra_data={"index": index, "tool": tool_name, "error": str(e)},
            )
            return f"Error: {str(e)}"
