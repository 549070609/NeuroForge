"""
Task Persistence Plugin

Persists tasks to disk and restores them on restart.
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.plugin.base import Plugin, PluginContext, PluginMetadata, PluginType
from pyagentforge.plugins.integration.task_persistence.task_store import (
    StoredTask,
    TaskStore,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TaskPersistencePlugin(Plugin):
    """
    Task Persistence Plugin

    Persists tasks to disk and restores them on restart.

    Features:
    - Saves tasks to JSON files
    - Restores pending/in-progress tasks on activation
    - Cleans up old completed tasks
    - Integrates with task_system plugin if available
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            id="integration.task_persistence",
            name="Task Persistence",
            version="1.0.0",
            type=PluginType.INTEGRATION,
            description="Persists tasks to disk and restores them on restart",
            author="PyAgentForge Team",
            dependencies=["integration.task_system"],  # Optional dependency
            provides=["task_persistence"],
            priority=200,  # High priority - load after task_system
        )

    def __init__(self):
        super().__init__()
        self._store: TaskStore | None = None
        self._task_system: Any = None  # Reference to TaskManager
        self._auto_save: bool = True
        self._auto_restore: bool = True
        self._cleanup_days: int = 7

    async def on_plugin_load(self, context: PluginContext) -> None:
        """插件加载时初始化"""
        await super().on_plugin_load(context)

        # Get configuration
        config = context.config.get("integration.task_persistence", {})
        storage_path = config.get("storage_path", ".agent/tasks")
        self._auto_save = config.get("auto_save", True)
        self._auto_restore = config.get("auto_restore", True)
        self._cleanup_days = config.get("cleanup_days", 7)

        # Initialize store
        self._store = TaskStore(storage_path=storage_path)

        context.logger.info(
            f"Task Persistence plugin loaded "
            f"(auto_save: {self._auto_save}, auto_restore: {self._auto_restore})"
        )

    async def on_plugin_activate(self) -> None:
        """插件激活时"""
        await super().on_plugin_activate()

        # Initialize store
        if self._store:
            self._store.initialize()

        # Restore pending tasks
        if self._auto_restore:
            await self._restore_pending_tasks()

        # Cleanup old tasks
        if self._cleanup_days > 0 and self._store:
            deleted = self._store.cleanup_completed(self._cleanup_days)
            if deleted > 0 and self.context:
                self.context.logger.info(f"Cleaned up {deleted} old completed tasks")

        if self.context:
            self.context.logger.info("Task Persistence plugin activated")

    def get_tools(self) -> list[BaseTool]:
        """返回插件提供的工具"""
        return []

    async def _restore_pending_tasks(self) -> None:
        """Restore pending and in-progress tasks"""
        if not self._store:
            return

        try:
            # Get pending tasks
            pending = self._store.get_pending_tasks()
            in_progress = self._store.get_in_progress_tasks()

            total = len(pending) + len(in_progress)

            if total == 0:
                if self.context:
                    self.context.logger.debug("No pending tasks to restore")
                return

            if self.context:
                self.context.logger.info(
                    f"Restoring {len(pending)} pending and {len(in_progress)} in-progress tasks"
                )

            # If task_system is available, sync tasks
            if self._task_system:
                await self._sync_with_task_system(pending + in_progress)
            else:
                # Just log the tasks
                if self.context:
                    for task in pending[:5]:  # Show first 5
                        self.context.logger.info(
                            f"  - [{task.id}] {task.title} (pending)"
                        )
                    if len(pending) > 5:
                        self.context.logger.info(
                            f"  ... and {len(pending) - 5} more pending tasks"
                        )

        except Exception as e:
            if self.context:
                self.context.logger.error(f"Failed to restore tasks: {e}")

    async def _sync_with_task_system(self, tasks: list[StoredTask]) -> None:
        """Sync restored tasks with task_system"""
        if not self._task_system:
            return

        try:
            for stored_task in tasks:
                # Check if task already exists
                existing = self._task_system.get_task(stored_task.id)

                if not existing:
                    # Create task in task_system
                    self._task_system.create_task(
                        title=stored_task.title,
                        description=stored_task.description,
                        priority=type('Priority', (), {'value': stored_task.priority})(),
                        blocked_by=stored_task.blocked_by,
                    )
                    # Note: We can't set the ID directly, so we lose the original ID
                    # This is a limitation of the current task_system

        except Exception as e:
            if self.context:
                self.context.logger.error(f"Failed to sync with task_system: {e}")

    async def _on_task_complete(self, result: str, context: dict[str, Any]) -> None:
        """
        Task completion hook - save completed task

        Args:
            result: Task result
            context: Execution context
        """
        if not self._auto_save or not self._store:
            return

        # Get task info from context if available
        task_info = context.get("task")
        if not task_info:
            return

        try:
            # Create stored task
            stored = StoredTask(
                id=task_info.get("id", ""),
                title=task_info.get("title", "Unknown"),
                description=task_info.get("description", ""),
                status="completed",
                priority=task_info.get("priority", "medium"),
                blocked_by=task_info.get("blockedBy", []),
                blocks=task_info.get("blocks", []),
                result=result[:1000] if result else None,  # Truncate result
            )

            self._store.save_task(stored)

            if self.context:
                self.context.logger.debug(f"Saved completed task {stored.id}")

        except Exception as e:
            if self.context:
                self.context.logger.error(f"Failed to save task: {e}")

    def save_task(self, task_id: str) -> bool:
        """
        Manually save a task

        Args:
            task_id: Task ID to save

        Returns:
            True if saved successfully
        """
        if not self._store or not self._task_system:
            return False

        try:
            task = self._task_system.get_task(task_id)
            if not task:
                return False

            stored = StoredTask(
                id=task.id,
                title=task.title,
                description=task.description,
                status=task.status.value if hasattr(task.status, "value") else str(task.status),
                priority=task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                blocked_by=task.blockedBy,
                blocks=task.blocks,
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at,
            )

            self._store.save_task(stored)
            return True

        except Exception as e:
            if self.context:
                self.context.logger.error(f"Failed to save task {task_id}: {e}")
            return False

    def load_task(self, task_id: str) -> StoredTask | None:
        """
        Load a task from storage

        Args:
            task_id: Task ID to load

        Returns:
            StoredTask or None
        """
        if not self._store:
            return None

        return self._store.load_task(task_id)

    def get_all_stored_tasks(self) -> list[StoredTask]:
        """Get all stored tasks"""
        if not self._store:
            return []
        return self._store.list_tasks()

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        if not self._store:
            return {"error": "Store not initialized"}
        return self._store.get_stats()

    def cleanup(self, days_old: int | None = None) -> int:
        """
        Cleanup old completed tasks

        Args:
            days_old: Override default days_old setting

        Returns:
            Number of tasks deleted
        """
        if not self._store:
            return 0

        days = days_old or self._cleanup_days
        return self._store.cleanup_completed(days)


# Plugin export
__all__ = [
    "TaskPersistencePlugin",
    "TaskStore",
    "StoredTask",
]
