"""
Background Agents Plugin

Provides background agent execution functionality.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pyagentforge.kernel.background_manager import BackgroundManager, BackgroundTask, TaskStatus
from pyagentforge.kernel.concurrency_manager import ConcurrencyConfig
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class BackgroundAgentsPlugin(Plugin):
    """
    Background Agents Plugin

    Features:
    - Launch background agent tasks
    - Concurrency control
    - Batched completion notifications
    - Task status tracking
    - Priority-based scheduling
    """

    metadata = PluginMetadata(
        id="integration.background_agents",
        name="Background Agents",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Background agent execution with concurrency control",
        author="PyAgentForge",
        provides=["background_manager", "background_agents"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._manager: BackgroundManager | None = None
        self._enabled: bool = True
        self._engine_factory: Callable | None = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)

        # Create concurrency config
        concurrency_config = ConcurrencyConfig(
            max_per_model=config.get("max_per_model", 2),
            max_per_provider=config.get("max_per_provider", 5),
            max_global=config.get("max_global", 20),
            queue_timeout=config.get("queue_timeout", 300.0),
            enable_queue=config.get("enable_queue", True),
        )

        # Create manager
        self._manager = BackgroundManager(
            concurrency_config=concurrency_config,
            notification_delay=config.get("notification_delay", 2.0),
        )

        # Set notification callback
        self._manager.set_notification_callback(self._on_tasks_completed)

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_TASK_COMPLETE,
            self,
            self._on_task_complete,
        )

        self.context.logger.info(
            "Background agents plugin activated",
            extra_data={
                "enabled": self._enabled,
                "max_global": concurrency_config.max_global,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        # Cancel all running tasks
        if self._manager:
            for task in self._manager.list_active():
                await self._manager.cancel(task.id)

        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    def set_engine_factory(self, factory: Callable) -> None:
        """
        Set the engine factory for creating isolated engines

        Args:
            factory: Factory function(agent_type) -> AgentEngine
        """
        self._engine_factory = factory
        if self._manager:
            self._manager.set_engine_factory(factory)

    async def _on_tasks_completed(self, session_id: str, tasks: list[BackgroundTask]) -> None:
        """
        Callback when batch of tasks complete

        Args:
            session_id: Session ID
            tasks: Completed tasks
        """
        # Build notification message
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        failed = [t for t in tasks if t.status == TaskStatus.FAILED]

        summary_parts = []
        if completed:
            summary_parts.append(f"✅ {len(completed)} task(s) completed")
        if failed:
            summary_parts.append(f"❌ {len(failed)} task(s) failed")

        summary = " | ".join(summary_parts)

        self.context.logger.info(
            f"Background tasks completed: {summary}",
            extra_data={
                "session_id": session_id,
                "completed": len(completed),
                "failed": len(failed),
            },
        )

        # Could inject notification into context here if needed

    async def _on_task_complete(
        self,
        session_id: str,
        result: str,
        **kwargs,
    ) -> None:
        """Hook: On task complete"""
        # Check for any pending background tasks
        if self._manager is None:
            return

        active = self._manager.list_by_session(session_id)
        pending = [t for t in active if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]

        if pending:
            self.context.logger.info(
                f"Waiting for {len(pending)} background task(s)",
                extra_data={"session_id": session_id},
            )

    def get_manager(self) -> BackgroundManager | None:
        """Get the background manager"""
        return self._manager

    async def launch(
        self,
        agent_type: str,
        prompt: str,
        session_id: str,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> BackgroundTask | None:
        """
        Launch a background task

        Args:
            agent_type: Agent type
            prompt: Task prompt
            session_id: Session ID
            priority: Priority (higher = more important)
            metadata: Optional metadata

        Returns:
            BackgroundTask or None
        """
        if not self._enabled or self._manager is None:
            return None

        if self._engine_factory is None:
            logger.warning("Engine factory not set, cannot launch background task")
            return None

        return await self._manager.launch(
            agent_type=agent_type,
            prompt=prompt,
            session_id=session_id,
            priority=priority,
            metadata=metadata,
        )

    def get_status(self, task_id: str) -> BackgroundTask | None:
        """Get task status"""
        if self._manager is None:
            return None
        return self._manager.get_status(task_id)

    def list_active(self) -> list[BackgroundTask]:
        """List all active tasks"""
        if self._manager is None:
            return []
        return self._manager.list_active()

    def list_by_session(self, session_id: str) -> list[BackgroundTask]:
        """List tasks for a session"""
        if self._manager is None:
            return []
        return self._manager.list_by_session(session_id)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a task"""
        if self._manager is None:
            return False
        return await self._manager.cancel(task_id)

    async def wait_for_completion(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> BackgroundTask | None:
        """Wait for a task to complete"""
        if self._manager is None:
            return None
        return await self._manager.wait_for_completion(task_id, timeout)

    def get_stats(self) -> dict[str, Any]:
        """Get statistics"""
        if self._manager is None:
            return {}
        return self._manager.get_stats()
