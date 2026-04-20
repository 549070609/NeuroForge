"""
Ralph Loop Plugin

Auto-continuation plugin that keeps the agent working until task completion.
"""

from typing import TYPE_CHECKING, Any

from pyagentforge.plugins.integration.ralph_loop.ralph_loop import CompletionChecker
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.plugins.integration.ralph_loop.engine import RalphLoopEngine
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.kernel.context import ContextManager

logger = get_logger(__name__)


class RalphLoopPlugin(Plugin):
    """
    Ralph Loop Plugin

    Features:
    - Auto-continuation until task completion
    - Todo tracking from agent responses
    - Stop keyword detection
    - Iteration limit enforcement
    - Smart continuation prompts
    """

    metadata = PluginMetadata(
        id="integration.ralph_loop",
        name="Ralph Loop Auto-Continuation",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="Auto-continuation system that keeps agent working until task completion",
        author="PyAgentForge",
        provides=["ralph_loop", "auto_continuation"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._engine: RalphLoopEngine | None = None
        self._max_iterations: int = 50
        self._enabled: bool = True
        self._skip_agents: list[str] = []  # Agents that shouldn't trigger continuation

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Load config
        config = self.context.config or {}
        self._enabled = config.get("enabled", True)
        self._max_iterations = config.get("max_iterations", 50)
        self._skip_agents = config.get("skip_agents", [])

        # Create engine
        completion_checker = CompletionChecker(
            stop_keywords=config.get("stop_keywords"),
            max_iterations=self._max_iterations,
        )
        self._engine = RalphLoopEngine(
            completion_checker=completion_checker,
            max_iterations=self._max_iterations,
            on_state_change=self._on_state_change,
        )

        # Register hooks
        self.context.hook_registry.register(
            HookType.ON_AFTER_LLM_CALL,
            self,
            self._on_after_llm_call,
        )
        self.context.hook_registry.register(
            HookType.ON_TASK_COMPLETE,
            self,
            self._on_task_complete,
        )

        self.context.logger.info(
            "Ralph loop plugin activated",
            extra_data={
                "max_iterations": self._max_iterations,
                "enabled": self._enabled,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """Deactivate plugin"""
        self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    def _on_state_change(self, state) -> None:
        """Handle state changes"""
        self.context.logger.debug(
            f"Ralph loop state changed: {state.status.value}",
            extra_data={
                "session_id": state.session_id,
                "iteration": state.iteration,
                "progress": state.progress_report,
            },
        )

    async def _on_after_llm_call(
        self,
        response: Any,
        context: "ContextManager",
        session_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any] | None:
        """
        Hook: After LLM call - check completion and inject continuation

        Args:
            response: LLM response
            context: Context manager
            session_id: Session identifier

        Returns:
            Optional continuation info
        """
        if not self._enabled or self._engine is None:
            return None

        # Get or create session ID
        if session_id is None:
            session_id = "default"

        # Get response text
        response_text = getattr(response, "text", str(response))

        # Increment iteration
        self._engine.increment_iteration(session_id)

        # Update todos from response
        state = self._engine.get_or_create_state(session_id)
        if state:
            self._engine.completion_checker.update_todos(state, response_text)

        # Check if should continue
        should_cont, reason = self._engine.should_continue(session_id, response_text)

        if not should_cont:
            self.context.logger.info(
                f"Task completed: {reason}",
                extra_data={"session_id": session_id},
            )
            return {
                "task_completed": True,
                "reason": reason,
                "progress": state.progress_report if state else "",
            }

        # Inject continuation prompt
        continuation_prompt = self._engine.build_continuation_prompt(session_id)
        context.add_user_message(continuation_prompt)

        self.context.logger.info(
            "Injected continuation prompt",
            extra_data={
                "session_id": session_id,
                "iteration": state.iteration if state else 0,
            },
        )

        return {
            "task_completed": False,
            "continuation_injected": True,
            "progress": state.progress_report if state else "",
        }

    async def _on_task_complete(
        self,
        session_id: str,
        result: str,
        **kwargs,
    ) -> None:
        """
        Hook: On task complete - cleanup

        Args:
            session_id: Session identifier
            result: Task result
        """
        if self._engine is None:
            return

        # Stop the loop
        self._engine.stop(session_id, "Task completed")

        self.context.logger.info(
            "Ralph loop stopped - task complete",
            extra_data={"session_id": session_id},
        )

    def get_engine(self) -> RalphLoopEngine | None:
        """Get the Ralph loop engine"""
        return self._engine

    def get_progress(self, session_id: str = "default") -> str:
        """Get progress report for a session"""
        if self._engine is None:
            return "Ralph loop not initialized"
        return self._engine.get_progress_report(session_id)

    def force_stop(self, session_id: str = "default") -> None:
        """Force stop the loop for a session"""
        if self._engine:
            self._engine.stop(session_id, "Force stopped by user")

    def reset(self, session_id: str = "default") -> None:
        """Reset loop state"""
        if self._engine:
            self._engine.reset(session_id)
