"""
Ralph Loop Engine

Core engine for auto-continuation logic.
"""

from typing import TYPE_CHECKING, Any, Callable

from pyagentforge.core.ralph_loop import (
    CompletionChecker,
    LoopStatus,
    RalphLoopState,
    TodoItem,
)
from pyagentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from pyagentforge.core.context import ContextManager

logger = get_logger(__name__)


class RalphLoopEngine:
    """
    Ralph Loop Engine

    Manages the auto-continuation loop:
    1. Track iteration count
    2. Extract and track todos
    3. Check completion conditions
    4. Generate continuation prompts
    """

    # Continuation prompt templates
    CONTINUATION_PROMPTS = [
        # Template 1: Todo-based continuation
        """Please continue working on the remaining tasks.

{progress_report}

Incomplete tasks:
{incomplete_todos}

Continue from where you left off.""",

        # Template 2: General continuation
        """The task is not yet complete. Please continue working on it.

{progress_report}

What's left to do?""",

        # Template 3: Encouraging continuation
        """Great progress so far! But there's still more work to do.

{progress_report}

Let's continue and complete all remaining tasks.""",
    ]

    def __init__(
        self,
        completion_checker: CompletionChecker | None = None,
        max_iterations: int = 50,
        on_state_change: Callable[[RalphLoopState], None] | None = None,
    ):
        """
        Initialize Ralph Loop Engine

        Args:
            completion_checker: Custom completion checker
            max_iterations: Maximum iterations before stopping
            on_state_change: Callback for state changes
        """
        self.completion_checker = completion_checker or CompletionChecker(
            max_iterations=max_iterations
        )
        self.max_iterations = max_iterations
        self.on_state_change = on_state_change

        # State storage (session_id -> state)
        self._states: dict[str, RalphLoopState] = {}

    def create_state(
        self,
        session_id: str,
        task: str = "",
        max_iterations: int | None = None,
    ) -> RalphLoopState:
        """
        Create a new loop state for a session

        Args:
            session_id: Session identifier
            task: Task description
            max_iterations: Override max iterations

        Returns:
            New RalphLoopState
        """
        state = RalphLoopState(
            session_id=session_id,
            task=task,
            max_iterations=max_iterations or self.max_iterations,
            status=LoopStatus.IDLE,
        )
        self._states[session_id] = state

        logger.info(
            "Created Ralph loop state",
            extra_data={
                "session_id": session_id,
                "max_iterations": state.max_iterations,
            },
        )

        return state

    def get_state(self, session_id: str) -> RalphLoopState | None:
        """Get state for a session"""
        return self._states.get(session_id)

    def get_or_create_state(
        self,
        session_id: str,
        task: str = "",
    ) -> RalphLoopState:
        """Get or create state for a session"""
        state = self.get_state(session_id)
        if state is None:
            state = self.create_state(session_id, task)
        return state

    def should_continue(
        self,
        session_id: str,
        response_text: str,
    ) -> tuple[bool, str]:
        """
        Check if the loop should continue

        Args:
            session_id: Session identifier
            response_text: Agent response text

        Returns:
            (should_continue, reason)
        """
        state = self.get_state(session_id)
        if state is None:
            return False, "No state found for session"

        # Update todos from response
        self.completion_checker.update_todos(state, response_text)

        # Check completion
        should_stop, reason = self.completion_checker.check_completion(
            state, response_text
        )

        if should_stop:
            state.status = LoopStatus.COMPLETED
            self._notify_state_change(state)
            return False, reason

        return True, ""

    def increment_iteration(self, session_id: str) -> int:
        """
        Increment iteration count

        Returns:
            New iteration count
        """
        state = self.get_state(session_id)
        if state is None:
            return 0

        state.iteration += 1
        state.last_iteration_at = datetime.now().isoformat()

        if state.status == LoopStatus.IDLE:
            state.status = LoopStatus.RUNNING

        self._notify_state_change(state)

        logger.debug(
            f"Ralph loop iteration {state.iteration}/{state.max_iterations}",
            extra_data={
                "session_id": session_id,
                "iteration": state.iteration,
            },
        )

        return state.iteration

    def build_continuation_prompt(
        self,
        session_id: str,
    ) -> str:
        """
        Build continuation prompt for the agent

        Args:
            session_id: Session identifier

        Returns:
            Continuation prompt
        """
        state = self.get_state(session_id)
        if state is None:
            return "Please continue with the task."

        # Select template based on iteration
        template_idx = state.iteration % len(self.CONTINUATION_PROMPTS)
        template = self.CONTINUATION_PROMPTS[template_idx]

        # Build incomplete todos list
        incomplete_todos = [
            f"- [ ] {t.content}"
            for t in state.todos
            if not t.is_complete
        ]

        return template.format(
            progress_report=state.progress_report,
            incomplete_todos="\n".join(incomplete_todos) if incomplete_todos else "No specific tasks tracked",
        )

    def inject_continuation(
        self,
        context: "ContextManager",
        session_id: str,
    ) -> bool:
        """
        Inject continuation prompt into context

        Args:
            context: Context manager
            session_id: Session identifier

        Returns:
            True if injected, False if should stop
        """
        should_cont, reason = self.should_continue(
            session_id,
            "",  # Will be checked separately
        )

        if not should_cont:
            logger.info(
                f"Ralph loop stopping: {reason}",
                extra_data={"session_id": session_id},
            )
            return False

        # Build and inject continuation prompt
        continuation = self.build_continuation_prompt(session_id)
        context.add_user_message(continuation)

        state = self.get_state(session_id)
        if state:
            state.status = LoopStatus.CONTINUING
            self._notify_state_change(state)

        logger.info(
            "Injected continuation prompt",
            extra_data={
                "session_id": session_id,
                "iteration": state.iteration if state else 0,
            },
        )

        return True

    def mark_recovering(self, session_id: str) -> None:
        """Mark session as recovering from error"""
        state = self.get_state(session_id)
        if state:
            state.is_recovering = True
            self._notify_state_change(state)
            logger.info(
                f"Ralph loop marked as recovering",
                extra_data={"session_id": session_id},
            )

    def mark_recovery_complete(self, session_id: str) -> None:
        """Mark recovery complete"""
        state = self.get_state(session_id)
        if state:
            state.is_recovering = False
            self._notify_state_change(state)
            logger.info(
                "Ralph loop recovery complete",
                extra_data={"session_id": session_id},
            )

    def stop(self, session_id: str, reason: str = "") -> None:
        """Stop the loop for a session"""
        state = self.get_state(session_id)
        if state:
            state.status = LoopStatus.STOPPED
            self._notify_state_change(state)
            logger.info(
                f"Ralph loop stopped: {reason}",
                extra_data={"session_id": session_id},
            )

    def reset(self, session_id: str) -> None:
        """Reset loop state for a session"""
        if session_id in self._states:
            del self._states[session_id]
            logger.info(
                "Ralph loop reset",
                extra_data={"session_id": session_id},
            )

    def get_progress_report(self, session_id: str) -> str:
        """Get progress report for a session"""
        state = self.get_state(session_id)
        if state is None:
            return "No active loop"

        return state.progress_report

    def _notify_state_change(self, state: RalphLoopState) -> None:
        """Notify state change callback"""
        if self.on_state_change:
            try:
                self.on_state_change(state)
            except Exception as e:
                logger.error(f"Error in state change callback: {e}")


# Import datetime for the increment_iteration method
from datetime import datetime
