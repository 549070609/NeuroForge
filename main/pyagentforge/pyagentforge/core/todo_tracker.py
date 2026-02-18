"""
Todo Tracker

Track and enforce todos from agent responses.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TodoStatus(str, Enum):
    """Todo status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class TodoPriority(str, Enum):
    """Todo priority"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Todo:
    """Todo item"""

    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING
    priority: TodoPriority = TodoPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    source: str = "response"  # response, user, system

    def mark_complete(self) -> None:
        """Mark todo as complete"""
        self.status = TodoStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        self.updated_at = self.completed_at

    def mark_in_progress(self) -> None:
        """Mark todo as in progress"""
        self.status = TodoStatus.IN_PROGRESS
        self.updated_at = datetime.now().isoformat()

    @property
    def is_complete(self) -> bool:
        """Check if todo is complete"""
        return self.status == TodoStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if todo is pending"""
        return self.status == TodoStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "source": self.source,
        }


class TodoTracker:
    """
    Todo Tracker

    Parse, track, and report on todos from agent responses.
    """

    # Patterns for extracting todos
    CHECKBOX_PATTERNS = [
        # Markdown checkbox with dash or bullet
        r"^\s*[-*]\s*\[([ xX])\]\s*(.+)$",
        # Numbered list with checkbox
        r"^\s*\d+\.\s*\[([ xX])\]\s*(.+)$",
        # Plain checkbox
        r"^\s*\[([ xX])\]\s*(.+)$",
    ]

    # Priority indicators in content
    PRIORITY_INDICATORS = {
        TodoPriority.CRITICAL: ["!!!", "critical", "urgent", "紧急", "关键"],
        TodoPriority.HIGH: ["!!", "high", "important", "重要", "优先"],
        TodoPriority.LOW: ["?", "low", "optional", "可选", "低优先级"],
    }

    def __init__(self):
        """Initialize todo tracker"""
        self._todos: dict[str, Todo] = {}
        self._id_counter = 0

    def _generate_id(self) -> str:
        """Generate unique todo ID"""
        self._id_counter += 1
        return f"todo-{self._id_counter}"

    def _detect_priority(self, content: str) -> TodoPriority:
        """Detect priority from content"""
        content_lower = content.lower()

        for priority, indicators in self.PRIORITY_INDICATORS.items():
            for indicator in indicators:
                if indicator in content_lower:
                    return priority

        return TodoPriority.NORMAL

    def _clean_content(self, content: str) -> str:
        """Clean todo content"""
        # Remove priority indicators
        for indicators in self.PRIORITY_INDICATORS.values():
            for indicator in indicators:
                content = content.replace(indicator, "")

        # Remove extra whitespace
        content = " ".join(content.split())

        return content.strip()

    def parse_from_text(self, text: str) -> list[Todo]:
        """
        Parse todos from text

        Args:
            text: Text to parse

        Returns:
            List of parsed todos
        """
        todos = []
        lines = text.split("\n")

        for line in lines:
            for pattern in self.CHECKBOX_PATTERNS:
                match = re.match(pattern, line.strip())
                if match:
                    status_char = match.group(1)
                    raw_content = match.group(2).strip()

                    # Detect status
                    status = (
                        TodoStatus.COMPLETED
                        if status_char.lower() == "x"
                        else TodoStatus.PENDING
                    )

                    # Detect priority
                    priority = self._detect_priority(raw_content)

                    # Clean content
                    content = self._clean_content(raw_content)

                    if content:  # Skip empty content
                        todo = Todo(
                            id=self._generate_id(),
                            content=content,
                            status=status,
                            priority=priority,
                        )
                        todos.append(todo)
                    break

        return todos

    def update_from_response(self, text: str) -> tuple[int, int]:
        """
        Update todos from agent response

        Args:
            text: Response text

        Returns:
            (new_todos, newly_completed)
        """
        new_todos = self.parse_from_text(text)

        added = 0
        completed = 0

        for new_todo in new_todos:
            # Check if todo already exists (by content)
            existing = self._find_by_content(new_todo.content)

            if existing is None:
                # New todo
                self._todos[new_todo.id] = new_todo
                added += 1
            elif not existing.is_complete and new_todo.is_complete:
                # Todo was completed
                existing.mark_complete()
                completed += 1

        return added, completed

    def _find_by_content(self, content: str) -> Todo | None:
        """Find todo by content (fuzzy match)"""
        content_clean = content.lower().strip()

        for todo in self._todos.values():
            if todo.content.lower().strip() == content_clean:
                return todo

        return None

    def get_incomplete_count(self) -> int:
        """Get count of incomplete todos"""
        return sum(1 for t in self._todos.values() if not t.is_complete)

    def get_complete_count(self) -> int:
        """Get count of complete todos"""
        return sum(1 for t in self._todos.values() if t.is_complete)

    def get_total_count(self) -> int:
        """Get total count of todos"""
        return len(self._todos)

    def get_progress_report(self) -> str:
        """
        Get progress report

        Returns:
            Progress report string like "3/5 (60%)"
        """
        total = self.get_total_count()
        complete = self.get_complete_count()

        if total == 0:
            return "0/0 (N/A)"

        percentage = (complete / total) * 100
        return f"{complete}/{total} ({percentage:.0f}%)"

    def get_detailed_report(self) -> str:
        """Get detailed progress report"""
        lines = ["Todo Progress Report:"]
        lines.append(f"  Total: {self.get_total_count()}")
        lines.append(f"  Completed: {self.get_complete_count()}")
        lines.append(f"  Incomplete: {self.get_incomplete_count()}")
        lines.append(f"  Progress: {self.get_progress_report()}")

        incomplete = self.get_incomplete_todos()
        if incomplete:
            lines.append("\nIncomplete todos:")
            for todo in incomplete:
                status_icon = "○" if todo.is_pending else "◐"
                lines.append(f"  {status_icon} [{todo.priority.value}] {todo.content}")

        return "\n".join(lines)

    def get_incomplete_todos(self) -> list[Todo]:
        """Get list of incomplete todos"""
        return [t for t in self._todos.values() if not t.is_complete]

    def get_todos_by_priority(self, priority: TodoPriority) -> list[Todo]:
        """Get todos by priority"""
        return [t for t in self._todos.values() if t.priority == priority]

    def get_reminder_message(self) -> str:
        """
        Get reminder message for incomplete todos

        Returns:
            Reminder message to inject
        """
        incomplete = self.get_incomplete_todos()

        if not incomplete:
            return ""

        if len(incomplete) == 1:
            return f"Reminder: 1 task remaining - {incomplete[0].content}"

        lines = [
            f"Reminder: {len(incomplete)} tasks remaining:",
        ]

        # Sort by priority
        priority_order = [
            TodoPriority.CRITICAL,
            TodoPriority.HIGH,
            TodoPriority.NORMAL,
            TodoPriority.LOW,
        ]

        for priority in priority_order:
            priority_todos = [t for t in incomplete if t.priority == priority]
            for todo in priority_todos:
                status_icon = "○" if todo.is_pending else "◐"
                lines.append(f"  {status_icon} {todo.content}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all todos"""
        self._todos.clear()
        self._id_counter = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "todos": [t.to_dict() for t in self._todos.values()],
            "total": self.get_total_count(),
            "completed": self.get_complete_count(),
            "incomplete": self.get_incomplete_count(),
            "progress": self.get_progress_report(),
        }
