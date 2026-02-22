"""
Todo Enforcer Plugin

Enforces incomplete todos across agent iterations.
"""

from typing import TYPE_CHECKING, Any

from pyagentforge.core.todo_tracker import Todo, TodoPriority, TodoStatus, TodoTracker
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.core.context import ContextManager

logger = get_logger(__name__)


class TodoEnforcerPlugin(Plugin):
    """
    Todo Enforcer Plugin

    Features:
    - Extract todos from agent responses
    - Track incomplete todos
    - Inject reminders for incomplete todos
    - Priority-based enforcement
    - Progress reporting
    """

    metadata = PluginMetadata(
        id="integration.todo_enforcer",
        name="Todo Enforcer",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Enforces incomplete todos across agent iterations",
        author="PyAgentForge",
        provides=["todo_enforcer", "todo_tracking"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._tracker: TodoTracker | None = None
        self._enabled: bool = True
        self._reminder_interval: int = 2  # Remind every N iterations
        self._iteration_count: int = 0

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)
        self._reminder_interval = config.get("reminder_interval", 2)

        # Create tracker
        self._tracker = TodoTracker()

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_AFTER_LLM_CALL,
            self,
            self._on_after_llm_call,
        )
        self.context.hook_registry.register(
            HookType.ON_BEFORE_LLM_CALL,
            self,
            self._on_before_llm_call,
        )

        self.context.logger.info(
            "Todo enforcer plugin activated",
            extra_data={
                "enabled": self._enabled,
                "reminder_interval": self._reminder_interval,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    async def _on_after_llm_call(
        self,
        response: Any,
        context: "ContextManager",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: After LLM call - extract todos from response

        Args:
            response: LLM response
            context: Context manager

        Returns:
            Todo extraction results
        """
        if not self._enabled or self._tracker is None:
            return None

        # Get response text
        response_text = getattr(response, "text", str(response))

        # Parse and update todos
        added, completed = self._tracker.update_from_response(response_text)

        if added > 0 or completed > 0:
            self.context.logger.info(
                "Todos updated",
                extra_data={
                    "added": added,
                    "completed": completed,
                    "progress": self._tracker.get_progress_report(),
                },
            )

        return {
            "todos_added": added,
            "todos_completed": completed,
            "progress": self._tracker.get_progress_report(),
            "incomplete_count": self._tracker.get_incomplete_count(),
        }

    async def _on_before_llm_call(
        self,
        context: "ContextManager",
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: Before LLM call - inject reminder if there are incomplete todos

        Args:
            context: Context manager

        Returns:
            Reminder info if injected
        """
        if not self._enabled or self._tracker is None:
            return None

        self._iteration_count += 1

        # Check if we should inject reminder
        incomplete_count = self._tracker.get_incomplete_count()

        if incomplete_count == 0:
            return None

        # Check reminder interval
        if self._iteration_count % self._reminder_interval != 0:
            return None

        # Get reminder message
        reminder = self._tracker.get_reminder_message()

        if reminder:
            # Inject as system-like user message
            context.add_user_message(f"[System Reminder]\n{reminder}")

            self.context.logger.info(
                "Injected todo reminder",
                extra_data={
                    "incomplete_count": incomplete_count,
                    "progress": self._tracker.get_progress_report(),
                },
            )

            return {
                "reminder_injected": True,
                "incomplete_count": incomplete_count,
                "progress": self._tracker.get_progress_report(),
            }

        return None

    def get_tracker(self) -> TodoTracker | None:
        """Get the todo tracker"""
        return self._tracker

    def get_progress(self) -> str:
        """Get progress report"""
        if self._tracker is None:
            return "Tracker not initialized"
        return self._tracker.get_progress_report()

    def get_detailed_report(self) -> str:
        """Get detailed progress report"""
        if self._tracker is None:
            return "Tracker not initialized"
        return self._tracker.get_detailed_report()

    def get_incomplete_todos(self) -> list[Todo]:
        """Get list of incomplete todos"""
        if self._tracker is None:
            return []
        return self._tracker.get_incomplete_todos()

    def force_reminder(self, context: "ContextManager") -> bool:
        """
        Force inject a reminder

        Args:
            context: Context manager

        Returns:
            True if reminder was injected
        """
        if self._tracker is None:
            return False

        incomplete_count = self._tracker.get_incomplete_count()
        if incomplete_count == 0:
            return False

        reminder = self._tracker.get_reminder_message()
        if reminder:
            context.add_user_message(f"[System Reminder]\n{reminder}")
            return True

        return False

    def clear_todos(self) -> None:
        """Clear all tracked todos"""
        if self._tracker:
            self._tracker.clear()
            self.context.logger.info("Todos cleared")
