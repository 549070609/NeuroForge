"""
并行子代理执行器

支持多个子代理同时运行
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel

from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class SubagentStatus(str, Enum):
    """子代理状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class SubagentTask:
    """子代理任务"""

    id: str
    description: str
    prompt: str
    agent_type: str
    status: SubagentStatus = SubagentStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubagentResult:
    """子代理执行结果"""

    task_id: str
    agent_type: str
    status: SubagentStatus
    result: str | None
    error: str | None
    duration_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)


# Agent 类型配置
AGENT_TYPES = {
    "explore": {
        "system_prompt": "You are an exploration agent. Search and gather information efficiently.",
        "tools": ["read", "glob", "grep", "bash"],
    },
    "plan": {
        "system_prompt": "You are a planning agent. Analyze tasks and create structured plans.",
        "tools": ["read", "write", "edit"],
    },
    "code": {
        "system_prompt": "You are a coding agent. Write, modify, and debug code.",
        "tools": "*",  # 所有工具
    },
    "review": {
        "system_prompt": "You are a review agent. Analyze code quality and suggest improvements.",
        "tools": ["read", "glob", "grep"],
    },
}


def get_agent_type_config(agent_type: str) -> dict[str, Any]:
    """获取代理类型配置"""
    return AGENT_TYPES.get(agent_type, AGENT_TYPES["explore"])


class ParallelSubagentExecutor:
    """并行子代理执行器"""

    def __init__(
        self,
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        max_concurrent: int = 3,
        current_depth: int = 0,
        max_depth: int = 3,
        ask_callback: Callable | None = None,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.max_concurrent = max_concurrent
        self.current_depth = current_depth
        self.max_depth = max_depth
        self.ask_callback = ask_callback
        self._tasks: dict[str, SubagentTask] = {}
        self._results: dict[str, SubagentResult] = {}

    async def execute_parallel(
        self,
        tasks: list[dict[str, Any]],
        timeout: int = 300,
    ) -> list[SubagentResult]:
        """
        并行执行多个子代理任务

        Args:
            tasks: 任务列表，每个任务包含:
                - description: 任务描述
                - prompt: 任务提示
                - agent_type: 代理类型 (explore/plan/code/review)
            timeout: 总超时时间

        Returns:
            执行结果列表
        """
        logger.info(
            "Starting parallel subagent execution",
            extra_data={"num_tasks": len(tasks), "max_concurrent": self.max_concurrent},
        )

        # 检查递归深度
        if self.current_depth >= self.max_depth:
            return [
                SubagentResult(
                    task_id="error",
                    agent_type="none",
                    status=SubagentStatus.FAILED,
                    result=None,
                    error="Maximum subagent depth reached",
                    duration_ms=0,
                )
            ]

        # 创建任务
        subagent_tasks = []
        for i, task_data in enumerate(tasks):
            task = SubagentTask(
                id=f"sub_{i}_{datetime.now(timezone.utc).timestamp():.0f}",
                description=task_data.get("description", f"Task {i+1}"),
                prompt=task_data["prompt"],
                agent_type=task_data.get("agent_type", "explore"),
            )
            self._tasks[task.id] = task
            subagent_tasks.append(task)

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def run_with_semaphore(task: SubagentTask) -> SubagentResult:
            async with semaphore:
                return await self._run_single_task(task, timeout)

        # 并行执行
        results = await asyncio.gather(
            *[run_with_semaphore(task) for task in subagent_tasks],
            return_exceptions=True,
        )

        # 处理结果
        final_results = []
        for task, result in zip(subagent_tasks, results):
            if isinstance(result, Exception):
                final_results.append(
                    SubagentResult(
                        task_id=task.id,
                        agent_type=task.agent_type,
                        status=SubagentStatus.FAILED,
                        result=None,
                        error=str(result),
                        duration_ms=0,
                    )
                )
            else:
                final_results.append(result)
            self._results[task.id] = final_results[-1]

        logger.info(
            "Parallel subagent execution completed",
            extra_data={
                "total": len(final_results),
                "completed": sum(1 for r in final_results if r.status == SubagentStatus.COMPLETED),
                "failed": sum(1 for r in final_results if r.status == SubagentStatus.FAILED),
            },
        )

        return final_results

    async def _run_single_task(
        self,
        task: SubagentTask,
        timeout: int,
    ) -> SubagentResult:
        """执行单个子代理任务"""
        task.status = SubagentStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        start_time = asyncio.get_event_loop().time()

        logger.debug(
            "Starting subagent task",
            extra_data={"task_id": task.id, "agent_type": task.agent_type},
        )

        try:
            # 获取代理类型配置
            type_config = get_agent_type_config(task.agent_type)

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

            # 创建 Agent 配置
            config = AgentConfig(
                system_prompt=type_config["system_prompt"],
            )

            # 创建子代理引擎
            sub_engine = AgentEngine(
                provider=self.provider,
                tool_registry=sub_tools,
                config=config,
                context=sub_context,
                ask_callback=self.ask_callback,
            )
            sub_engine._subagent_depth = self.current_depth + 1

            # 带超时执行
            try:
                result = await asyncio.wait_for(
                    sub_engine.run(task.prompt),
                    timeout=timeout,
                )

                task.status = SubagentStatus.COMPLETED
                task.result = result
                task.progress = 100.0

            except asyncio.TimeoutError:
                task.status = SubagentStatus.TIMEOUT
                task.error = f"Task timed out after {timeout} seconds"

        except Exception as e:
            task.status = SubagentStatus.FAILED
            task.error = str(e)
            logger.error(
                "Subagent task failed",
                extra_data={"task_id": task.id, "error": str(e)},
            )

        finally:
            task.completed_at = datetime.now(timezone.utc)
            end_time = asyncio.get_event_loop().time()
            duration_ms = int((end_time - start_time) * 1000)

        return SubagentResult(
            task_id=task.id,
            agent_type=task.agent_type,
            status=task.status,
            result=task.result,
            error=task.error,
            duration_ms=duration_ms,
            metadata={
                "description": task.description,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            },
        )

    def get_task_status(self, task_id: str) -> SubagentTask | None:
        """获取任务状态"""
        return self._tasks.get(task_id)

    def get_all_statuses(self) -> dict[str, SubagentStatus]:
        """获取所有任务状态"""
        return {tid: task.status for tid, task in self._tasks.items()}

    def get_results_summary(self) -> str:
        """获取结果摘要"""
        lines = ["Parallel Subagent Execution Summary", "=" * 50]

        for task_id, result in self._results.items():
            task = self._tasks.get(task_id)
            status_icon = {
                SubagentStatus.COMPLETED: "✅",
                SubagentStatus.FAILED: "❌",
                SubagentStatus.TIMEOUT: "⏱️",
                SubagentStatus.RUNNING: "🔄",
                SubagentStatus.PENDING: "⏳",
            }.get(result.status, "❓")

            lines.append(f"\n{status_icon} {task.description if task else task_id}")
            lines.append(f"   Type: {result.agent_type}")
            lines.append(f"   Status: {result.status.value}")
            lines.append(f"   Duration: {result.duration_ms}ms")

            if result.error:
                lines.append(f"   Error: {result.error[:100]}")

        # 统计
        completed = sum(1 for r in self._results.values() if r.status == SubagentStatus.COMPLETED)
        failed = sum(1 for r in self._results.values() if r.status in [SubagentStatus.FAILED, SubagentStatus.TIMEOUT])

        lines.append(f"\n{'=' * 50}")
        lines.append(f"Total: {len(self._results)} | Completed: {completed} | Failed: {failed}")

        return "\n".join(lines)


# 并行任务工具
class ParallelTaskTool:
    """并行任务工具 - 用于 Task 工具中"""

    @staticmethod
    async def run_parallel(
        provider: BaseProvider,
        tool_registry: ToolRegistry,
        tasks: list[dict[str, str]],
        max_concurrent: int = 3,
    ) -> str:
        """
        并行运行多个子代理任务

        Args:
            provider: LLM 提供商
            tool_registry: 工具注册表
            tasks: 任务列表
            max_concurrent: 最大并发数

        Returns:
            结果摘要
        """
        executor = ParallelSubagentExecutor(
            provider=provider,
            tool_registry=tool_registry,
            max_concurrent=max_concurrent,
        )

        results = await executor.execute_parallel(tasks)

        # 格式化输出
        output_lines = ["<parallel-subagent-results>"]

        for result in results:
            task = executor.get_task_status(result.task_id)
            output_lines.append(f"\n## {task.description if task else result.task_id}")
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

        output_lines.append("\n</parallel-subagent-results>")

        return "\n".join(output_lines)