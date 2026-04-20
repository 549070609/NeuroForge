"""
Task 工具

生成子代理执行聚焦任务，支持并行执行
"""

from typing import Any

from pyagentforge.agents.config import AgentConfig
from pyagentforge.agents.types import get_agent_type_config
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentEngine
from pyagentforge.plugins.integration.parallel_executor.executor import (
    ParallelSubagentExecutor,
    SubagentStatus,
)
from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

# 最大子代理递归深度
MAX_SUBAGENT_DEPTH = 3


class TaskTool(BaseTool):
    """Task 工具 - 生成子代理执行聚焦任务"""

    name = "Task"
    description = """生成子代理执行聚焦任务。

子代理类型:
- explore: 只读探索，搜索和分析代码库
- plan: 规划代理，分析并制定实现计划
- code: 编码代理，实现代码更改
- review: 审查代理，代码审查

支持模式:
- single: 单个任务执行
- parallel: 并行执行多个子代理任务

子代理有独立的上下文，不会污染父代理的消息历史。
只返回最终结果摘要。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "任务简短描述 (3-5 个词)",
            },
            "prompt": {
                "type": "string",
                "description": "给子代理的详细任务描述",
            },
            "subagent_type": {
                "type": "string",
                "enum": ["explore", "plan", "code", "review"],
                "default": "explore",
                "description": "子代理类型",
            },
            "model": {
                "type": "string",
                "description": "可选的模型指定",
            },
            "mode": {
                "type": "string",
                "enum": ["single", "parallel"],
                "default": "single",
                "description": "执行模式: single(单个) 或 parallel(并行)",
            },
            "tasks": {
                "type": "array",
                "description": "并行任务列表 (mode=parallel 时使用)",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "prompt": {"type": "string"},
                        "agent_type": {"type": "string"},
                    },
                    "required": ["prompt"],
                },
            },
            "max_concurrent": {
                "type": "integer",
                "description": "并行执行的最大并发数",
                "default": 3,
            },
        },
        "required": ["description", "prompt"],
    }
    timeout = 300
    risk_level = "medium"

    def __init__(
        self,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        current_depth: int = 0,
        ask_callback: Any = None,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.current_depth = current_depth
        self.ask_callback = ask_callback

    async def execute(
        self,
        description: str,
        prompt: str,
        subagent_type: str = "explore",
        model: str | None = None,
        mode: str = "single",
        tasks: list[dict[str, str]] | None = None,
        max_concurrent: int = 3,
    ) -> str:
        """执行子代理任务"""
        # 检查递归深度
        if self.current_depth >= MAX_SUBAGENT_DEPTH:
            return "Error: Maximum subagent depth reached. Cannot spawn more subagents."

        # 并行模式
        if mode == "parallel" and tasks:
            return await self._execute_parallel(tasks, max_concurrent)

        # 单任务模式
        return await self._execute_single(description, prompt, subagent_type, model)

    async def _execute_single(
        self,
        description: str,
        prompt: str,
        subagent_type: str = "explore",
        _model: str | None = None,
    ) -> str:
        """执行单个子代理任务"""
        logger.info(
            "Starting subagent task",
            extra_data={
                "description": description,
                "subagent_type": subagent_type,
                "depth": self.current_depth,
            },
        )

        # 获取代理类型配置
        type_config = get_agent_type_config(subagent_type)

        # 创建隔离的上下文
        sub_context = ContextManager(
            system_prompt=type_config["system_prompt"],
        )

        # 过滤工具
        allowed_tools = type_config["tools"]
        if allowed_tools == "*":
            sub_tools = self.tool_registry
        else:
            sub_tools = self.tool_registry.filter_by_permission(allowed_tools)

        # 如果还有 Task 工具，需要传递增加的深度
        if sub_tools.has("Task"):
            # 创建新的 Task 工具，增加深度
            sub_task_tool = TaskTool(
                provider=self.provider,
                tool_registry=sub_tools,
                current_depth=self.current_depth + 1,
                ask_callback=self.ask_callback,
            )
            # 替换 Task 工具
            filtered_tools = sub_tools
            sub_tools = ToolRegistry()
            for tool in filtered_tools:
                if tool.name != "Task":
                    sub_tools.register(tool)
            sub_tools.register(sub_task_tool)

        # 创建 Agent 配置
        config = AgentConfig(
            name=subagent_type,
            system_prompt=type_config["system_prompt"],
            allowed_tools=allowed_tools if allowed_tools != "*" else ["*"],
        )

        # 创建子代理引擎
        sub_engine = AgentEngine(
            provider=self.provider,
            tool_registry=sub_tools,
            config=config,
            context=sub_context,
            ask_callback=self.ask_callback,
        )

        try:
            # 运行子代理
            result = await sub_engine.run(prompt)

            logger.info(
                "Subagent task completed",
                extra_data={
                    "description": description,
                    "result_length": len(result),
                },
            )

            # 返回结果摘要
            return f"<subagent-result type='{subagent_type}'>\n{result}\n</subagent-result>"

        except Exception as e:
            error_msg = f"Subagent task failed: {str(e)}"
            logger.error(
                "Subagent task error",
                extra_data={
                    "description": description,
                    "error": str(e),
                },
            )
            return f"Error: {error_msg}"

    async def _execute_parallel(
        self,
        tasks: list[dict[str, str]],
        max_concurrent: int = 3,
    ) -> str:
        """并行执行多个子代理任务"""
        logger.info(
            "Starting parallel subagent tasks",
            extra_data={
                "num_tasks": len(tasks),
                "max_concurrent": max_concurrent,
                "depth": self.current_depth,
            },
        )

        # 创建并行执行器
        executor = ParallelSubagentExecutor(
            provider=self.provider,
            tool_registry=self.tool_registry,
            max_concurrent=max_concurrent,
            current_depth=self.current_depth,
            max_depth=MAX_SUBAGENT_DEPTH,
            ask_callback=self.ask_callback,
        )

        try:
            # 执行并行任务
            results = await executor.execute_parallel(tasks)

            # 格式化结果
            output_lines = ["<parallel-subagent-results>", ""]

            completed = 0
            failed = 0

            for result in results:
                task = executor.get_task_status(result.task_id)
                if result.status == SubagentStatus.COMPLETED:
                    completed += 1
                    output_lines.append(f"## ✅ {task.description if task else result.task_id}")
                else:
                    failed += 1
                    output_lines.append(f"## ❌ {task.description if task else result.task_id}")

                output_lines.append(f"Status: {result.status.value}")
                output_lines.append(f"Duration: {result.duration_ms}ms")

                if result.result:
                    # 截断过长结果
                    display_result = result.result[:2000]
                    if len(result.result) > 2000:
                        display_result += "\n... (truncated)"
                    output_lines.append(f"\nResult:\n{display_result}")

                if result.error:
                    output_lines.append(f"Error: {result.error}")

                output_lines.append("")

            output_lines.append("---")
            output_lines.append(f"Total: {len(results)} | Completed: {completed} | Failed: {failed}")
            output_lines.append("</parallel-subagent-results>")

            return "\n".join(output_lines)

        except Exception as e:
            error_msg = f"Parallel execution failed: {str(e)}"
            logger.error(
                "Parallel execution error",
                extra_data={"error": str(e)},
            )
            return f"Error: {error_msg}"


def check_depth(current_depth: int) -> bool:
    """
    检查是否可以继续创建子代理

    Args:
        current_depth: 当前深度

    Returns:
        True 如果可以继续
    """
    return current_depth < MAX_SUBAGENT_DEPTH
