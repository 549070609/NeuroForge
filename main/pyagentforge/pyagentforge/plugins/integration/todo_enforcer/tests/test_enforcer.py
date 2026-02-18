"""
Tests for Todo Enforcer
"""

import pytest

from pyagentforge.core.todo_tracker import (
    Todo,
    TodoPriority,
    TodoStatus,
    TodoTracker,
)


class TestTodo:
    """Tests for Todo dataclass"""

    def test_create_todo(self):
        """Test creating a todo"""
        todo = Todo(
            id="todo-1",
            content="Test task",
            status=TodoStatus.PENDING,
            priority=TodoPriority.NORMAL,
        )

        assert todo.id == "todo-1"
        assert todo.content == "Test task"
        assert todo.status == TodoStatus.PENDING
        assert not todo.is_complete

    def test_mark_complete(self):
        """Test marking todo as complete"""
        todo = Todo(id="1", content="Task")

        todo.mark_complete()

        assert todo.is_complete
        assert todo.status == TodoStatus.COMPLETED
        assert todo.completed_at is not None

    def test_mark_in_progress(self):
        """Test marking todo as in progress"""
        todo = Todo(id="1", content="Task")

        todo.mark_in_progress()

        assert todo.status == TodoStatus.IN_PROGRESS
        assert not todo.is_complete

    def test_to_dict(self):
        """Test serialization"""
        todo = Todo(
            id="1",
            content="Task",
            status=TodoStatus.PENDING,
            priority=TodoPriority.HIGH,
        )

        data = todo.to_dict()

        assert data["id"] == "1"
        assert data["content"] == "Task"
        assert data["status"] == "pending"
        assert data["priority"] == "high"


class TestTodoTracker:
    """Tests for TodoTracker"""

    def test_parse_from_text(self):
        """Test parsing todos from text"""
        tracker = TodoTracker()

        text = """
Tasks:
- [ ] First task
- [x] Second task (completed)
- [X] Third task (also completed)
* [ ] Fourth task
"""
        todos = tracker.parse_from_text(text)

        assert len(todos) == 4
        assert todos[0].status == TodoStatus.PENDING
        assert todos[1].status == TodoStatus.COMPLETED
        assert todos[2].status == TodoStatus.COMPLETED

    def test_detect_priority(self):
        """Test priority detection"""
        tracker = TodoTracker()

        text = """
- [ ] Critical task !!!
- [ ] High priority task !!
- [ ] Normal task
- [ ] Low priority task ?
"""
        todos = tracker.parse_from_text(text)

        assert todos[0].priority == TodoPriority.CRITICAL
        assert todos[1].priority == TodoPriority.HIGH
        assert todos[2].priority == TodoPriority.NORMAL
        assert todos[3].priority == TodoPriority.LOW

    def test_update_from_response(self):
        """Test updating from response"""
        tracker = TodoTracker()

        text1 = """
- [ ] Task 1
- [ ] Task 2
"""
        added, completed = tracker.update_from_response(text1)

        assert added == 2
        assert completed == 0
        assert tracker.get_incomplete_count() == 2

        # Now complete one task
        text2 = """
- [x] Task 1
- [ ] Task 2
"""
        added, completed = tracker.update_from_response(text2)

        assert added == 0
        assert completed == 1
        assert tracker.get_incomplete_count() == 1

    def test_progress_report(self):
        """Test progress report"""
        tracker = TodoTracker()

        assert tracker.get_progress_report() == "0/0 (N/A)"

        tracker.update_from_response("""
- [x] Task 1
- [ ] Task 2
- [ ] Task 3
""")

        report = tracker.get_progress_report()
        assert "1/3" in report
        assert "33%" in report

    def test_get_incomplete_todos(self):
        """Test getting incomplete todos"""
        tracker = TodoTracker()

        tracker.update_from_response("""
- [x] Task 1
- [ ] Task 2
- [ ] Task 3
""")

        incomplete = tracker.get_incomplete_todos()

        assert len(incomplete) == 2
        assert all(not t.is_complete for t in incomplete)

    def test_get_reminder_message(self):
        """Test reminder message generation"""
        tracker = TodoTracker()

        # No todos
        assert tracker.get_reminder_message() == ""

        tracker.update_from_response("""
- [ ] Task 1
- [ ] Task 2
""")

        reminder = tracker.get_reminder_message()

        assert "2 tasks remaining" in reminder
        assert "Task 1" in reminder
        assert "Task 2" in reminder

    def test_clear(self):
        """Test clearing todos"""
        tracker = TodoTracker()

        tracker.update_from_response("- [ ] Task 1")
        assert tracker.get_total_count() == 1

        tracker.clear()
        assert tracker.get_total_count() == 0

    def test_chinese_content(self):
        """Test Chinese content handling"""
        tracker = TodoTracker()

        text = """
- [ ] 完成功能开发
- [x] 编写测试用例
- [ ] 重要：代码审查
"""
        todos = tracker.parse_from_text(text)

        assert len(todos) == 3
        assert "完成功能开发" in todos[0].content
        assert todos[1].status == TodoStatus.COMPLETED
        assert todos[2].priority == TodoPriority.HIGH  # "重要" detected

    def test_detailed_report(self):
        """Test detailed report generation"""
        tracker = TodoTracker()

        tracker.update_from_response("""
- [x] Task 1
- [ ] Task 2
- [ ] Task 3 !!!
""")

        report = tracker.get_detailed_report()

        assert "Total: 3" in report
        assert "Completed: 1" in report
        assert "Incomplete: 2" in report
        assert "33%" in report
