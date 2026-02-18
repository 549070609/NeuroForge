"""
Tests for Ralph Loop Plugin
"""

import pytest

from pyagentforge.core.ralph_loop import (
    CompletionChecker,
    LoopStatus,
    RalphLoopState,
    TodoItem,
)
from pyagentforge.plugins.integration.ralph_loop.engine import RalphLoopEngine


class TestTodoItem:
    """Tests for TodoItem"""

    def test_create_todo(self):
        """Test creating a todo item"""
        todo = TodoItem(
            id="todo-1",
            content="Test task",
            status="pending",
        )

        assert todo.id == "todo-1"
        assert todo.content == "Test task"
        assert todo.status == "pending"
        assert todo.is_pending
        assert not todo.is_complete

    def test_completed_todo(self):
        """Test completed todo detection"""
        completed_statuses = ["completed", "done", "✓", "x"]

        for status in completed_statuses:
            todo = TodoItem(id="1", content="Task", status=status)
            assert todo.is_complete, f"Status '{status}' should be complete"


class TestRalphLoopState:
    """Tests for RalphLoopState"""

    def test_create_state(self):
        """Test creating loop state"""
        state = RalphLoopState(
            session_id="test-session",
            task="Test task",
        )

        assert state.session_id == "test-session"
        assert state.status == LoopStatus.IDLE
        assert state.iteration == 0

    def test_should_stop_iteration_limit(self):
        """Test stop on iteration limit"""
        state = RalphLoopState(
            session_id="test",
            max_iterations=5,
        )
        state.iteration = 5

        assert state.should_stop

    def test_should_stop_keywords(self):
        """Test stop on keywords"""
        state = RalphLoopState(session_id="test")
        state.stop_keywords_detected = True

        assert state.should_stop

    def test_should_stop_all_todos_complete(self):
        """Test stop when all todos complete"""
        state = RalphLoopState(
            session_id="test",
            todos=[
                TodoItem(id="1", content="Task 1", status="completed"),
                TodoItem(id="2", content="Task 2", status="done"),
            ],
        )

        assert state.should_stop

    def test_progress_calculation(self):
        """Test progress calculation"""
        state = RalphLoopState(
            session_id="test",
            todos=[
                TodoItem(id="1", content="Task 1", status="completed"),
                TodoItem(id="2", content="Task 2", status="pending"),
                TodoItem(id="3", content="Task 3", status="pending"),
                TodoItem(id="4", content="Task 4", status="done"),
            ],
            completed_todos=2,
        )

        assert state.total_todo_count == 4
        assert state.incomplete_todo_count == 2
        assert state.progress_percentage == 50.0


class TestCompletionChecker:
    """Tests for CompletionChecker"""

    def test_check_iteration_limit(self):
        """Test iteration limit check"""
        checker = CompletionChecker(max_iterations=5)
        state = RalphLoopState(session_id="test", max_iterations=5)
        state.iteration = 5

        should_stop, reason = checker.check_completion(state, "")
        assert should_stop
        assert "limit" in reason.lower()

    def test_check_stop_keywords(self):
        """Test stop keyword detection"""
        checker = CompletionChecker()
        state = RalphLoopState(session_id="test")

        should_stop, reason = checker.check_completion(
            state, "The task is now completed successfully"
        )
        assert should_stop
        assert "keyword" in reason.lower()

    def test_check_chinese_keywords(self):
        """Test Chinese stop keyword detection"""
        checker = CompletionChecker()
        state = RalphLoopState(session_id="test")

        should_stop, reason = checker.check_completion(state, "任务完成了")
        assert should_stop

    def test_extract_todos(self):
        """Test todo extraction from text"""
        checker = CompletionChecker()

        text = """
Tasks to complete:
- [ ] First pending task
- [x] Completed task
- [X] Another completed task
* [ ] Task with bullet
"""
        todos = checker.extract_todos(text)

        assert len(todos) == 4
        assert todos[0].status == "pending"
        assert todos[1].status == "completed"
        assert todos[2].status == "completed"
        assert todos[3].status == "pending"

    def test_update_todos(self):
        """Test updating todos in state"""
        checker = CompletionChecker()
        state = RalphLoopState(session_id="test")

        text = """
- [ ] Task 1
- [x] Task 2
- [ ] Task 3
"""
        new_completed = checker.update_todos(state, text)

        assert len(state.todos) == 3
        assert state.completed_todos == 1


class TestRalphLoopEngine:
    """Tests for RalphLoopEngine"""

    def test_create_engine(self):
        """Test creating engine"""
        engine = RalphLoopEngine(max_iterations=30)

        assert engine.max_iterations == 30

    def test_create_state(self):
        """Test creating state"""
        engine = RalphLoopEngine()

        state = engine.create_state("test-session", "Test task")

        assert state.session_id == "test-session"
        assert state.task == "Test task"

    def test_should_continue(self):
        """Test should_continue logic"""
        engine = RalphLoopEngine()

        engine.create_state("test-session")
        should_cont, _ = engine.should_continue("test-session", "Working...")

        assert should_cont  # No stop condition met

    def test_increment_iteration(self):
        """Test iteration increment"""
        engine = RalphLoopEngine()
        engine.create_state("test-session")

        it = engine.increment_iteration("test-session")

        assert it == 1

    def test_build_continuation_prompt(self):
        """Test continuation prompt building"""
        engine = RalphLoopEngine()
        state = engine.create_state("test-session")
        state.todos = [
            TodoItem(id="1", content="Task 1", status="completed"),
            TodoItem(id="2", content="Task 2", status="pending"),
        ]
        state.completed_todos = 1

        prompt = engine.build_continuation_prompt("test-session")

        assert "progress" in prompt.lower()
        assert "Task 2" in prompt  # Incomplete task mentioned

    def test_progress_report(self):
        """Test progress report"""
        engine = RalphLoopEngine()
        state = engine.create_state("test-session")
        state.todos = [
            TodoItem(id="1", content="Task 1", status="completed"),
            TodoItem(id="2", content="Task 2", status="pending"),
        ]
        state.completed_todos = 1

        report = engine.get_progress_report("test-session")

        assert "50%" in report or "1/2" in report
