"""
Parallel Executor Plugin

Provides parallel subagent execution functionality
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class SubagentStatus(str, Enum):
    """Subagent task status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentTask:
    """Subagent task definition"""
    task_id: str
    description: str
    prompt: str
    agent_type: str = "explore"
    status: SubagentStatus = SubagentStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: int = 0


@dataclass
class SubagentResult:
    """Subagent execution result"""
    task_id: str
    status: SubagentStatus
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0


class ParallelExecutorPlugin(Plugin):
    """Parallel subagent executor plugin"""

    metadata = PluginMetadata(
        id="integration.parallel_executor",
        name="Parallel Subagent Executor",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Provides parallel execution of subagent tasks for improved efficiency",
        author="PyAgentForge",
        provides=["parallel_executor"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._tasks: dict[str, SubagentTask] = {}
        self._max_concurrent: int = 3
        self._executor_callback: Optional[Callable] = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Get config
        config = self.context.config or {}
        self._max_concurrent = config.get("max_concurrent", 3)

        self.context.logger.info(
            "Parallel executor plugin initialized",
            extra_data={"max_concurrent": self._max_concurrent},
        )

    def set_executor_callback(self, callback: Callable) -> None:
        """
        Set the callback function for executing subagent tasks

        Args:
            callback: Async function that takes (task_id, prompt, agent_type) and returns result
        """
        self._executor_callback = callback

    async def execute_parallel(
        self,
        tasks: list[dict[str, Any]],
        max_concurrent: Optional[int] = None,
    ) -> list[SubagentResult]:
        """
        Execute multiple subagent tasks in parallel

        Args:
            tasks: List of task definitions with keys: description, prompt, agent_type
            max_concurrent: Maximum concurrent executions (uses config if not provided)

        Returns:
            List of execution results
        """
        if not self._executor_callback:
            self.context.logger.warning(
                "No executor callback set, returning empty results"
            )
            return []

        max_concurrent = max_concurrent or self._max_concurrent
        semaphore = asyncio.Semaphore(max_concurrent)

        # Create task definitions
        import uuid
        for task_def in tasks:
            task_id = str(uuid.uuid4())[:8]
            self._tasks[task_id] = SubagentTask(
                task_id=task_id,
                description=task_def.get("description", "Unnamed task"),
                prompt=task_def.get("prompt", ""),
                agent_type=task_def.get("agent_type", "explore"),
            )

        # Execute tasks with concurrency control
        async def run_with_semaphore(task: SubagentTask) -> SubagentResult:
            async with semaphore:
                return await self._execute_single(task)

        # Run all tasks
        task_list = [self._tasks[t["description"][:8] if "task_id" not in t else t["task_id"]] for t in tasks if t]
        # Actually use the task IDs we created
        task_ids = list(self._tasks.keys())[-len(tasks):]
        task_list = [self._tasks[tid] for tid in task_ids]

        results = await asyncio.gather(
            *[run_with_semaphore(task) for task in task_list],
            return_exceptions=True,
        )

        # Process results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                task_id = task_list[i].task_id
                final_results.append(SubagentResult(
                    task_id=task_id,
                    status=SubagentStatus.FAILED,
                    error=str(result),
                ))
            else:
                final_results.append(result)

        return final_results

    async def _execute_single(self, task: SubagentTask) -> SubagentResult:
        """
        Execute a single subagent task

        Args:
            task: Task definition

        Returns:
            Execution result
        """
        task.status = SubagentStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()

        start_time = datetime.now(timezone.utc)

        try:
            self.context.logger.info(
                "Starting subagent task",
                extra_data={
                    "task_id": task.task_id,
                    "description": task.description,
                    "agent_type": task.agent_type,
                },
            )

            # Execute via callback
            result = await self._executor_callback(
                task.task_id,
                task.prompt,
                task.agent_type,
            )

            task.status = SubagentStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now(timezone.utc).isoformat()

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            task.duration_ms = int(duration)

            self.context.logger.info(
                "Subagent task completed",
                extra_data={
                    "task_id": task.task_id,
                    "duration_ms": task.duration_ms,
                },
            )

            return SubagentResult(
                task_id=task.task_id,
                status=SubagentStatus.COMPLETED,
                result=result,
                duration_ms=task.duration_ms,
            )

        except Exception as e:
            task.status = SubagentStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now(timezone.utc).isoformat()

            duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            task.duration_ms = int(duration)

            self.context.logger.error(
                "Subagent task failed",
                extra_data={
                    "task_id": task.task_id,
                    "error": str(e),
                },
            )

            return SubagentResult(
                task_id=task.task_id,
                status=SubagentStatus.FAILED,
                error=str(e),
                duration_ms=task.duration_ms,
            )

    def get_task_status(self, task_id: str) -> Optional[SubagentTask]:
        """
        Get task status by ID

        Args:
            task_id: Task identifier

        Returns:
            Task definition or None
        """
        return self._tasks.get(task_id)

    def list_active_tasks(self) -> list[SubagentTask]:
        """
        List all active (pending or running) tasks

        Returns:
            List of active tasks
        """
        return [
            task for task in self._tasks.values()
            if task.status in (SubagentStatus.PENDING, SubagentStatus.RUNNING)
        ]

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled, False if not found or already running
        """
        task = self._tasks.get(task_id)
        if task and task.status == SubagentStatus.PENDING:
            task.status = SubagentStatus.CANCELLED
            self.context.logger.info(
                "Task cancelled",
                extra_data={"task_id": task_id},
            )
            return True
        return False
