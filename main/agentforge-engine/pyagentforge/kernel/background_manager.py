"""
Background Manager

Manages background agent tasks with isolated execution.
"""

import asyncio
import atexit
import contextlib
import inspect
import signal
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pyagentforge.kernel.concurrency_manager import ConcurrencyConfig, ConcurrencyManager
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)

# 前向引用
if TYPE_CHECKING:
    from pyagentforge.plugin.hooks import HookRegistry

# v4.0: 稳定性检测常量
MIN_STABILITY_TIME_MS = 10_000  # 10 秒最小运行时间
MIN_STABLE_POLLS = 3  # 连续 3 次无消息变化判定完成

# v4.0: 任务 TTL 常量
TASK_TTL_MS = 30 * 60 * 1000  # 30 分钟过期

# v4.1: 清理常量
CLEANUP_INTERVAL_SECONDS = 60  # 每 60 秒清理一次
STALE_TASK_THRESHOLD_MS = 60 * 60 * 1000  # 1 小时无响应判定为陈旧


class TaskStatus(StrEnum):
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
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int = 0
    priority: int = 0  # Higher = more priority

    # v4.2: Task System correlation
    task_id: str | None = None  # Link to Task system

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # v4.0: 稳定性检测
    running_time_ms: int = 0
    stable_polls: int = 0
    last_message_count: int = 0

    # v4.0: TTL 支持
    ttl_expires_at: str | None = None

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
            "task_id": self.task_id,
        }


@dataclass
class NotificationBatch:
    """Batched notifications (v4.1: Enhanced)"""

    session_id: str
    tasks: list[BackgroundTask] = field(default_factory=list)
    ready_at: str = ""
    notified: bool = False
    timer_handle: asyncio.TimerHandle | None = None  # v4.1: 存储定时器句柄


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
        hook_registry: "HookRegistry | None" = None,  # v4.1: 钩子注册表
    ):
        """
        Initialize background manager

        Args:
            concurrency_config: Concurrency configuration
            notification_delay: Delay before sending batched notifications
            engine_factory: Factory function to create isolated engine instances
            hook_registry: v4.1: Hook registry for triggering events
        """
        self.concurrency = ConcurrencyManager(concurrency_config)
        self.notification_delay = notification_delay
        self.engine_factory = engine_factory
        self.hook_registry = hook_registry

        self._tasks: dict[str, BackgroundTask] = {}
        self._notification_batches: dict[str, NotificationBatch] = {}
        self._notification_callback: Callable | None = None
        self._running_tasks: dict[str, asyncio.Task] = {}

        # v4.0: 任务队列系统
        self._queues_by_key: dict[str, list[BackgroundTask]] = {}
        self._processing_keys: set[str] = set()
        self._completion_timers: dict[str, asyncio.TimerHandle] = {}

        # v4.1: 定期清理协程
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

        # v4.0: 注册清理处理器
        self._register_cleanup_handlers()

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

    def set_hook_registry(self, hook_registry: "HookRegistry") -> None:
        """
        v4.1: 设置钩子注册表

        Args:
            hook_registry: Hook registry instance
        """
        self.hook_registry = hook_registry

    async def start(self) -> None:
        """
        v4.1: 启动后台管理器

        启动定期清理协程。
        """
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

        logger.info("Background manager started")

    async def stop(self) -> None:
        """
        v4.1: 停止后台管理器

        停止定期清理协程。
        """
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

        # Cancel and await all running tasks so state is fully drained.
        await self._cancel_running_tasks("Task cancelled: manager stopped")

        # Cancel any queued notification timers.
        for batch in self._notification_batches.values():
            if batch.timer_handle:
                batch.timer_handle.cancel()
                batch.timer_handle = None
        self._notification_batches.clear()

        # Ensure no residual concurrency slots are held.
        self.concurrency.clear()

        logger.info("Background manager stopped")

    async def launch(
        self,
        agent_type: str,
        prompt: str,
        session_id: str,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
        ttl_ms: int | None = None,  # v4.0: 任务 TTL
    ) -> BackgroundTask:
        """
        Launch a background task

        Args:
            agent_type: Type of agent to run
            prompt: Task prompt
            session_id: Session ID for grouping
            priority: Task priority (higher = more important)
            metadata: Optional metadata
            ttl_ms: v4.0: Task TTL in milliseconds (None = default 30 min)

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

        # v4.0: 设置 TTL
        self._set_task_ttl(task, ttl_ms)

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
                "ttl_ms": ttl_ms or TASK_TTL_MS,
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
        task.started_at = datetime.now(UTC).isoformat()
        datetime.now(UTC)

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
            if inspect.isawaitable(engine):
                engine = await engine

            if engine is None:
                raise RuntimeError(f"Failed to create engine for {task.agent_type}")

            result = await engine.run(task.prompt)
            if inspect.isawaitable(result):
                result = await result

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now(UTC).isoformat()

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
                end_time = datetime.now(UTC)
                start = datetime.fromisoformat(task.started_at.replace("Z", "+00:00"))
                duration_ms = int((end_time - start).total_seconds() * 1000)
                # Keep duration strictly positive for completed tasks to avoid flakiness.
                if task.status == TaskStatus.COMPLETED and duration_ms <= 0:
                    duration_ms = 1
                task.duration_ms = duration_ms

            # Queue notification
            await self._queue_completion_notification(task)

            # Cleanup
            self._running_tasks.pop(task.id, None)

    async def _queue_completion_notification(self, task: BackgroundTask) -> None:
        """
        Queue a completion notification (v4.1: Enhanced batching)

        合并同一 session 的通知，等待 2 秒后批量发送。

        Args:
            task: Completed task
        """
        session_id = task.session_id

        # 获取或创建批次
        if session_id not in self._notification_batches:
            self._notification_batches[session_id] = NotificationBatch(
                session_id=session_id,
                ready_at=datetime.now(UTC).isoformat(),
            )

        batch = self._notification_batches[session_id]
        batch.tasks.append(task)

        # 取消之前的定时器（如果有）
        if batch.timer_handle:
            batch.timer_handle.cancel()
            batch.timer_handle = None

        # 设置新的定时器
        loop = asyncio.get_event_loop()
        batch.timer_handle = loop.call_later(
            self.notification_delay,
            lambda: asyncio.create_task(self._send_batch_notification(session_id))
        )

        logger.debug(
            f"Queued task {task.id} for session {session_id}, "
            f"batch size: {len(batch.tasks)}"
        )

    async def _send_batch_notification(self, session_id: str) -> None:
        """
        v4.1: 发送批量通知

        2 秒窗口结束后，统一发送该 session 的所有完成通知。

        Args:
            session_id: Session to notify
        """
        batch = self._notification_batches.get(session_id)
        if batch is None or batch.notified:
            return

        # 标记为已通知
        batch.notified = True

        # 清理定时器
        if batch.timer_handle:
            batch.timer_handle.cancel()
            batch.timer_handle = None

        # 获取所有已完成的任务
        completed_tasks = [
            t for t in batch.tasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
        ]

        if not completed_tasks:
            return

        # 发送通知
        if self._notification_callback:
            try:
                await self._notification_callback(session_id, completed_tasks)

                # 分类统计
                succeeded = sum(1 for t in completed_tasks if t.status == TaskStatus.COMPLETED)
                failed = sum(1 for t in completed_tasks if t.status == TaskStatus.FAILED)
                cancelled = sum(1 for t in completed_tasks if t.status == TaskStatus.CANCELLED)

                logger.info(
                    "Sent batched notification",
                    extra_data={
                        "session_id": session_id,
                        "total": len(completed_tasks),
                        "succeeded": succeeded,
                        "failed": failed,
                        "cancelled": cancelled,
                    },
                )
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")

        # 清理批次
        del self._notification_batches[session_id]

    async def _delayed_notify(self, session_id: str) -> None:
        """
        Send batched notification after delay (Deprecated, use _send_batch_notification)

        保留向后兼容性。

        Args:
            session_id: Session to notify
        """
        await self._send_batch_notification(session_id)

    def get_status(self, task_id: str) -> BackgroundTask | None:
        """
        Get task status

        Args:
            task_id: Task ID

        Returns:
            BackgroundTask or None
        """
        return self._tasks.get(task_id)

    # v4.0: 高级特性

    def _register_cleanup_handlers(self) -> None:
        """
        注册进程清理处理器

        确保 Ctrl+C 或其他终止信号时清理后台任务。

        Note: Windows 不支持 SIGTERM，只注册 SIGINT 和 atexit。
        """
        import platform

        def handle_shutdown(signum, frame):
            logger.info(f"Received signal {signum}, cleaning up background tasks...")
            self._cleanup_all_tasks()

        # 注册 SIGINT (Ctrl+C) - 所有平台都支持
        signal.signal(signal.SIGINT, handle_shutdown)

        # SIGTERM 只在非 Windows 平台注册
        if platform.system() != 'Windows':
            try:
                signal.signal(signal.SIGTERM, handle_shutdown)
                logger.debug("Registered SIGTERM handler")
            except (AttributeError, OSError) as e:
                logger.warning(f"Failed to register SIGTERM handler: {e}")

        # 注册退出处理器 - 所有平台都支持
        atexit.register(self._cleanup_all_tasks)

        logger.debug("Registered cleanup handlers for background tasks")

    def _cleanup_all_tasks(self) -> None:
        """
        v4.0: 清理所有后台任务

        在进程退出时调用。
        """
        now = datetime.now(UTC).isoformat()

        # 取消所有运行中的任务
        for task_id, async_task in list(self._running_tasks.items()):
            if not async_task.done():
                async_task.cancel()
                logger.debug(f"Cancelled task {task_id}")

            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.error = task.error or "Task cancelled"
                task.completed_at = task.completed_at or now

        # 清理并发状态
        self.concurrency.clear()
        self._running_tasks.clear()

        for batch in self._notification_batches.values():
            if batch.timer_handle:
                batch.timer_handle.cancel()
                batch.timer_handle = None
        self._notification_batches.clear()

        logger.info(f"Cleaned up {len(self._running_tasks)} background tasks")

    async def _cancel_running_tasks(self, reason: str) -> None:
        """Cancel all running asyncio tasks and wait for cancellation to settle."""
        running_items = list(self._running_tasks.items())
        if not running_items:
            return

        now = datetime.now(UTC).isoformat()

        for task_id, async_task in running_items:
            if not async_task.done():
                async_task.cancel()

            task = self._tasks.get(task_id)
            if task and task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                task.status = TaskStatus.CANCELLED
                task.error = task.error or reason
                task.completed_at = task.completed_at or now

        await asyncio.gather(
            *(async_task for _, async_task in running_items),
            return_exceptions=True,
        )
        self._running_tasks.clear()

    async def _check_task_stability(self, task: BackgroundTask) -> bool:
        """
        v4.0: 检查任务是否稳定（完成）

        Args:
            task: 后台任务

        Returns:
            True if task is stable (completed)
        """
        # 最小运行时间检查
        if task.running_time_ms < MIN_STABILITY_TIME_MS:
            return False

        # 稳定性轮询检查
        if task.stable_polls >= MIN_STABLE_POLLS:
            logger.debug(
                f"Task {task.id} is stable after {task.stable_polls} polls"
            )
            return True

        return False

    async def _cleanup_expired_tasks(self) -> None:
        """
        v4.1: 清理过期和陈旧任务

        定期检查并清理：
        1. 超过 TTL 的任务
        2. 运行超过 1 小时无响应的任务
        """
        now = datetime.now(UTC)
        cleaned_count = 0

        for task_id, task in list(self._tasks.items()):
            should_cancel = False
            reason = ""

            # 1. 检查 TTL
            if task.ttl_expires_at:
                try:
                    expires_at = datetime.fromisoformat(
                        task.ttl_expires_at.replace("Z", "+00:00")
                    )

                    if now > expires_at:
                        should_cancel = True
                        reason = "TTL expired"
                except Exception as e:
                    logger.warning(f"Failed to parse TTL for task {task_id}: {e}")

            # 2. 检查陈旧任务（仅针对运行中的任务）
            if task.status == TaskStatus.RUNNING and task.started_at:
                try:
                    started_at = datetime.fromisoformat(
                        task.started_at.replace("Z", "+00:00")
                    )
                    running_time_ms = int((now - started_at).total_seconds() * 1000)

                    if running_time_ms > STALE_TASK_THRESHOLD_MS:
                        should_cancel = True
                        reason = "stale (no response for 1 hour)"
                except Exception as e:
                    logger.warning(f"Failed to parse start time for task {task_id}: {e}")

            if should_cancel:
                logger.warning(
                    f"Cleaning up task {task_id}: {reason}"
                )

                # 取消运行中的任务
                async_task = self._running_tasks.get(task_id)
                if async_task and not async_task.done():
                    async_task.cancel()

                # 更新状态
                task.status = TaskStatus.CANCELLED
                task.error = f"Task cancelled: {reason}"
                task.completed_at = now.isoformat()

                # v4.1: 触发陈旧任务钩子
                if "stale" in reason and self.hook_registry:
                    try:
                        from pyagentforge.plugin.hooks import HookType
                        await self.hook_registry.emit(
                            HookType.ON_BACKGROUND_TASK_STALE,
                            task=task,
                            reason=reason,
                        )
                    except Exception as e:
                        logger.error(f"Failed to emit stale task hook: {e}")

                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired/stale tasks")

    async def _periodic_cleanup(self) -> None:
        """
        v4.1: 定期清理协程

        每 60 秒运行一次清理。
        """
        logger.info(f"Started periodic cleanup (interval: {CLEANUP_INTERVAL_SECONDS}s)")

        while self._running:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self._cleanup_expired_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

        logger.info("Periodic cleanup stopped")

    def _set_task_ttl(self, task: BackgroundTask, ttl_ms: int | None = None) -> None:
        """
        v4.0: 设置任务 TTL

        Args:
            task: 后台任务
            ttl_ms: TTL 毫秒数，None 使用默认值
        """
        ttl_ms = ttl_ms or TASK_TTL_MS
        now = datetime.now(UTC)

        # 计算过期时间
        from datetime import timedelta
        expires_at = now + timedelta(milliseconds=ttl_ms)
        task.ttl_expires_at = expires_at.isoformat()

        logger.debug(
            f"Set TTL for task {task.id}: expires at {task.ttl_expires_at}"
        )

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

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(asyncio.shield(async_task), timeout=timeout)

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

    @staticmethod
    def format_batch_notification(tasks: list[BackgroundTask]) -> str:
        """
        v4.1: 格式化批量通知

        生成用户友好的批量通知文本。

        Args:
            tasks: 完成的任务列表

        Returns:
            格式化的通知文本
        """
        succeeded = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]
        cancelled = [t for t in tasks if t.status == TaskStatus.CANCELLED]

        lines = ["后台任务完成："]
        lines.append("")

        if succeeded:
            lines.append(f"✅ 成功 ({len(succeeded)}):")
            for task in succeeded:
                result_preview = ""
                if task.result:
                    # 截取前 100 字符
                    result_preview = task.result[:100]
                    if len(task.result) > 100:
                        result_preview += "..."
                lines.append(f"  - [{task.id}] {task.agent_type}: {result_preview}")
            lines.append("")

        if failed:
            lines.append(f"❌ 失败 ({len(failed)}):")
            for task in failed:
                lines.append(f"  - [{task.id}] {task.agent_type}: {task.error}")
            lines.append("")

        if cancelled:
            lines.append(f"⚠️ 已取消 ({len(cancelled)}):")
            for task in cancelled:
                lines.append(f"  - [{task.id}] {task.agent_type}")
            lines.append("")

        return "\n".join(lines)
