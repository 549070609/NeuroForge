"""
Background Manager

Manages background agent tasks with isolated execution.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from pyagentforge.core.concurrency_manager import ConcurrencyConfig, ConcurrencyManager
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Background task status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    """Background task definition"""

    id: str
    agent_type: str
    prompt: str
    session_id: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int = 0
    priority: int = 0  # Higher = more priority

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "session_id": self.session_id,
            "status": self.status.value,
            "result": self.result[:200] if self.result else None,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "priority": self.priority,
        }


@dataclass
class NotificationBatch:
    """Batched notifications"""

    session_id: str
    tasks: list[BackgroundTask] = field(default_factory=list)
    ready_at: str = ""
    notified: bool = False


class BackgroundManager:
    """
    Background Manager

    Features:
    - Launch background tasks with concurrency control
    - Execute in isolated engine instances
    - Batched notifications when tasks complete
    - Task status tracking
    - Priority-based scheduling
    """

    def __init__(
        self,
        concurrency_config: ConcurrencyConfig | None = None,
        notification_delay: float = 2.0,  # Delay before notifying
        engine_factory: Callable | None = None,
    ):
        """
        Initialize background manager

        Args:
            concurrency_config: Concurrency configuration
            notification_delay: Delay before sending batched notifications
            engine_factory: Factory function to create isolated engine instances
        """
        self.concurrency = ConcurrencyManager(concurrency_config)
        self.notification_delay = notification_delay
        self.engine_factory = engine_factory

        self._tasks: dict[str, BackgroundTask] = {}
        self._notification_batches: dict[str, NotificationBatch] = {}
        self._notification_callback: Callable | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}

    def set_notification_callback(self, callback: Callable) -> None:
        """
        Set callback for batched notifications

        Args:
            callback: Async function(session_id, completed_tasks)
        """
        self._notification_callback = callback

    def set_engine_factory(self, factory: Callable) -> None:
        """
        Set engine factory for isolated execution

        Args:
            factory: Factory function(agent_type) -> AgentEngine
        """
        self.engine_factory = factory

    async def launch(
        self,
        agent_type: str,
        prompt: str,
        session_id: str,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> BackgroundTask:
        """
        Launch a background task

        Args:
            agent_type: Type of agent to run
            prompt: Task prompt
            session_id: Session ID for grouping
            priority: Task priority (higher = more important)
            metadata: Optional metadata

        Returns:
            BackgroundTask instance
        """
        task_id = str(uuid.uuid4())[:8]

        task = BackgroundTask(
            id=task_id,
            agent_type=agent_type,
            prompt=prompt,
            session_id=session_id,
            priority=priority,
            metadata=metadata or {},
        )

        self._tasks[task_id] = task

        # Start async execution
        async_task = asyncio.create_task(self._run_task(task))
        self._running_tasks[task_id] = async_task

        logger.info(
            "Launched background task",
            extra_data={
                "task_id": task_id,
                "agent_type": agent_type,
                "session_id": session_id,
            },
        )

        return task

    async def _run_task(self, task: BackgroundTask) -> None:
        """
        Execute a background task

        Args:
            task: Task to execute
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()
        start_time = datetime.now(timezone.utc)

        slot_id = None

        try:
            # Acquire concurrency slot
            slot_id = await self.concurrency.acquire(
                agent=task.agent_type,
                agent_max_concurrent=task.metadata.get("max_concurrent", 3),
                session_id=task.session_id,
                task_id=task.id,
            )

            if slot_id is None:
                raise TimeoutError("Failed to acquire concurrency slot")

            logger.info(
                "Starting background task execution",
                extra_data={"task_id": task.id, "agent_type": task.agent_type},
            )

            # Execute using isolated engine
            if self.engine_factory is None:
                raise RuntimeError("Engine factory not set")

            engine = self.engine_factory(task.agent_type)

            if engine is None:
                raise RuntimeError(f"Failed to create engine for {task.agent_type}")

            result = await engine.run(task.prompt)

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                "Background task completed",
                extra_data={
                    "task_id": task.id,
                    "duration_ms": task.duration_ms,
                },
            )

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
            task.error = "Task cancelled"
            logger.info(
                "Background task cancelled",
                extra_data={"task_id": task.id},
            )

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            logger.error(
                f"Background task failed: {e}",
                extra_data={"task_id": task.id, "error": str(e)},
            )

        finally:
            # Release slot
            if slot_id:
                self.concurrency.release(slot_id)

            # Calculate duration
            if task.started_at:
                end_time = datetime.now(timezone.utc)
                start = datetime.fromisoformat(task.started_at.replace("Z", "+00:00"))
                task.duration_ms = int((end_time - start).total_seconds() * 1000)

            # Queue notification
            await self._queue_completion_notification(task)

            # Cleanup
            self._running_tasks.pop(task.id, None)

    async def _queue_completion_notification(self, task: BackgroundTask) -> None:
        """
        Queue a completion notification

        Args:
            task: Completed task
        """
        session_id = task.session_id

        if session_id not in self._notification_batches:
            self._notification_batches[session_id] = NotificationBatch(
                session_id=session_id,
                ready_at=datetime.now(timezone.utc).isoformat(),
            )

        batch = self._notification_batches[session_id]
        batch.tasks.append(task)

        # Schedule notification
        asyncio.create_task(self._delayed_notify(session_id))

    async def _delayed_notify(self, session_id: str) -> None:
        """
        Send batched notification after delay

        Args:
            session_id: Session to notify
        """
        await asyncio.sleep(self.notification_delay)

        batch = self._notification_batches.get(session_id)
        if batch is None or batch.notified:
            return

        # Check if all tasks in batch are complete
        all_complete = all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
            for t in batch.tasks
        )

        if all_complete and self._notification_callback:
            batch.notified = True

            try:
                await self._notification_callback(session_id, batch.tasks)
                logger.info(
                    "Sent batched notification",
                    extra_data={
                        "session_id": session_id,
                        "task_count": len(batch.tasks),
                    },
                )
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")

    def get_status(self, task_id: str) -> BackgroundTask | None:
        """
        Get task status

        Args:
            task_id: Task ID

        Returns:
            BackgroundTask or None
        """
        return self._tasks.get(task_id)

    def list_by_session(self, session_id: str) -> list[BackgroundTask]:
        """
        List all tasks for a session

        Args:
            session_id: Session ID

        Returns:
            List of tasks
        """
        return [t for t in self._tasks.values() if t.session_id == session_id]

    def list_active(self) -> list[BackgroundTask]:
        """List all active tasks"""
        return [
            t
            for t in self._tasks.values()
            if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
        ]

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a task

        Args:
            task_id: Task ID

        Returns:
            True if cancelled
        """
        task = self._tasks.get(task_id)
        if task is None:
            return False

        if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return False

        # Cancel running async task
        async_task = self._running_tasks.get(task_id)
        if async_task:
            async_task.cancel()

        task.status = TaskStatus.CANCELLED
        logger.info(f"Cancelled task {task_id}")

        return True

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> BackgroundTask | None:
        """
        Wait for a task to complete

        Args:
            task_id: Task ID
            timeout: Optional timeout

        Returns:
            Completed task or None
        """
        async_task = self._running_tasks.get(task_id)
        if async_task is None:
            return self._tasks.get(task_id)

        try:
            await asyncio.wait_for(async_task, timeout=timeout)
        except asyncio.TimeoutError:
            pass

        return self._tasks.get(task_id)

    def get_stats(self) -> dict[str, Any]:
        """Get manager statistics"""
        return {
            "total_tasks": len(self._tasks),
            "pending": sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING),
            "running": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
            "completed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED),
            "cancelled": sum(1 for t in self._tasks.values() if t.status == TaskStatus.CANCELLED),
            "concurrency": self.concurrency.get_stats(),
        }
