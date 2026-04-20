"""
Ralph Loop Engine

Auto-continuation system that keeps the agent working until task completion.
Auto-continuation pattern for task completion tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class LoopStatus(StrEnum):
    """Ralph loop status"""

    IDLE = "idle"
    RUNNING = "running"
    CONTINUING = "continuing"
    COMPLETED = "completed"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class TodoItem:
    """Todo item from agent response"""

    id: str
    content: str
    status: str = "pending"  # pending, in_progress, completed
    priority: str = "normal"  # low, normal, high

    @property
    def is_complete(self) -> bool:
        """Check if todo is complete"""
        return self.status.lower() in ("completed", "done", "✓", "x")

    @property
    def is_pending(self) -> bool:
        """Check if todo is pending"""
        return self.status.lower() in ("pending", "todo", " ", "")


@dataclass
class RalphLoopState:
    """
    Ralph loop state - tracks the auto-continuation session

    Named after Ralph from Wreck-It Ralph who "never stops trying"
    """

    session_id: str
    task: str = ""
    iteration: int = 0
    max_iterations: int = 50
    status: LoopStatus = LoopStatus.IDLE

    # Todo tracking
    todos: list[TodoItem] = field(default_factory=list)
    completed_todos: int = 0

    # Timing
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_iteration_at: str = ""

    # Stop conditions
    stop_keywords_detected: bool = False
    stop_keywords: list[str] = field(
        default_factory=lambda: [
            "task completed",
            "任务完成",
            "all done",
            "全部完成",
            "finished",
            "已完成",
            "nothing more to do",
            "没有更多要做的",
        ]
    )

    # Recovery support
    is_recovering: bool = False

    @property
    def has_incomplete_todos(self) -> bool:
        """Check if there are incomplete todos"""
        return any(not todo.is_complete for todo in self.todos)

    @property
    def incomplete_todo_count(self) -> int:
        """Get count of incomplete todos"""
        return sum(1 for todo in self.todos if not todo.is_complete)

    @property
    def total_todo_count(self) -> int:
        """Get total count of todos"""
        return len(self.todos)

    @property
    def progress_percentage(self) -> float:
        """Get completion percentage"""
        if self.total_todo_count == 0:
            return 100.0
        return (self.completed_todos / self.total_todo_count) * 100

    @property
    def should_stop(self) -> bool:
        """Check if loop should stop"""
        return (
            self.iteration >= self.max_iterations
            or self.stop_keywords_detected
            or (self.todos and not self.has_incomplete_todos)
        )

    @property
    def progress_report(self) -> str:
        """Get progress report string"""
        if self.total_todo_count == 0:
            return "No todos tracked"

        return f"Progress: {self.completed_todos}/{self.total_todo_count} ({self.progress_percentage:.0f}%)"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "task": self.task,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "status": self.status.value,
            "todos": [
                {
                    "id": t.id,
                    "content": t.content,
                    "status": t.status,
                    "priority": t.priority,
                }
                for t in self.todos
            ],
            "completed_todos": self.completed_todos,
            "progress_percentage": self.progress_percentage,
            "started_at": self.started_at,
            "last_iteration_at": self.last_iteration_at,
            "stop_keywords_detected": self.stop_keywords_detected,
            "is_recovering": self.is_recovering,
        }


class CompletionChecker:
    """
    Check if task is complete based on multiple signals

    Priority:
    1. Iteration limit exceeded -> Stop
    2. All todos complete -> Stop
    3. Stop keywords detected -> Stop
    4. Default -> Continue
    """

    def __init__(
        self,
        stop_keywords: list[str] | None = None,
        max_iterations: int = 50,
    ):
        self.stop_keywords = stop_keywords or [
            "task completed",
            "任务完成",
            "all done",
            "全部完成",
            "finished",
            "已完成",
            "nothing more to do",
            "没有更多要做的",
            "implementation complete",
            "实现完成",
        ]
        self.max_iterations = max_iterations

    def check_completion(
        self,
        state: RalphLoopState,
        response_text: str,
    ) -> tuple[bool, str]:
        """
        Check if the task is complete

        Args:
            state: Current loop state
            response_text: Agent response text

        Returns:
            (should_stop, reason)
        """
        # 1. Check iteration limit
        if state.iteration >= self.max_iterations:
            return True, f"Iteration limit reached ({self.max_iterations})"

        # 2. Check stop keywords
        response_lower = response_text.lower()
        for keyword in self.stop_keywords:
            if keyword.lower() in response_lower:
                state.stop_keywords_detected = True
                return True, f"Stop keyword detected: '{keyword}'"

        # 3. Check todos completion
        if state.todos and not state.has_incomplete_todos:
            return True, "All todos completed"

        # 4. Continue
        return False, ""

    def extract_todos(self, text: str) -> list[TodoItem]:
        """
        Extract todos from markdown checkboxes

        Supports formats:
        - [ ] pending task
        - [x] completed task
        - [X] completed task
        - - [ ] task with dash
        - * [ ] task with bullet
        """
        import re

        todos = []
        lines = text.split("\n")

        for i, line in enumerate(lines):
            # Match markdown checkbox patterns
            match = re.match(
                r"^\s*[-*]\s*\[([ xX])\]\s*(.+)$",
                line.strip(),
            )
            if match:
                status_char = match.group(1)
                content = match.group(2).strip()

                status = "completed" if status_char.lower() == "x" else "pending"

                todos.append(
                    TodoItem(
                        id=f"todo-{i}",
                        content=content,
                        status=status,
                    )
                )

        return todos

    def update_todos(
        self,
        state: RalphLoopState,
        response_text: str,
    ) -> int:
        """
        Update todos in state from response

        Returns:
            Number of newly completed todos
        """
        new_todos = self.extract_todos(response_text)

        if not new_todos:
            return 0

        # Merge with existing todos
        existing_contents = {t.content for t in state.todos}

        for new_todo in new_todos:
            if new_todo.content not in existing_contents:
                state.todos.append(new_todo)

        # Count completed
        completed = sum(1 for t in state.todos if t.is_complete)
        newly_completed = completed - state.completed_todos
        state.completed_todos = completed

        return newly_completed
