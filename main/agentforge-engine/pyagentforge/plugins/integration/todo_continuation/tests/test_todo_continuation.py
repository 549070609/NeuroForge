"""
Tests for Todo Continuation Enforcer
"""

from unittest.mock import MagicMock

import pytest

from pyagentforge.plugins.integration.todo_continuation import TodoContinuationEnforcerPlugin


class TestTodoExtraction:
    """Tests for todo extraction logic"""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance"""
        return TodoContinuationEnforcerPlugin()

    def test_extract_markdown_checkboxes(self, plugin):
        """Test extraction of markdown checkbox items"""
        response = """
        Here are the tasks:
        - [ ] First task
        - [ ] Second task
        - [x] Completed task
        """

        todos = plugin._extract_pending_todos(response)

        assert len(todos) == 2
        assert "First task" in todos
        assert "Second task" in todos
        assert "Completed task" not in todos

    def test_extract_todo_markers(self, plugin):
        """Test extraction of TODO: markers"""
        response = """
        TODO: Implement feature
        FIXME: Fix this bug
        XXX: Hack to fix
        """

        todos = plugin._extract_pending_todos(response)

        assert len(todos) == 3
        assert any("Implement feature" in t for t in todos)
        assert any("Fix this bug" in t for t in todos)

    def test_extract_chinese_markers(self, plugin):
        """Test extraction of Chinese todo markers"""
        response = """
        待办：完成任务A
        待完成：实现功能B
        """

        todos = plugin._extract_pending_todos(response)

        assert len(todos) == 2
        assert any("完成任务A" in t for t in todos)
        assert any("实现功能B" in t for t in todos)

    def test_no_todos(self, plugin):
        """Test response without todos"""
        response = """
        All tasks are complete!
        Everything is done.
        """

        todos = plugin._extract_pending_todos(response)

        assert len(todos) == 0


class TestSkipConditions:
    """Tests for skip conditions"""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance"""
        return TodoContinuationEnforcerPlugin()

    def test_skip_oracle_agent(self, plugin):
        """Test skipping oracle agent"""
        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="oracle",
            context={},
        )

        assert should_skip is True

    def test_skip_librarian_agent(self, plugin):
        """Test skipping librarian agent"""
        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="librarian",
            context={},
        )

        assert should_skip is True

    def test_skip_recovering_session(self, plugin):
        """Test skipping recovering session"""
        plugin._get_session_state("test").is_recovering = True

        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="main",
            context={},
        )

        assert should_skip is True

    def test_skip_with_background_tasks(self, plugin):
        """Test skipping when background tasks are running"""
        # Mock background manager
        mock_bg_manager = MagicMock()
        mock_task = MagicMock()
        mock_task.status = "running"
        mock_bg_manager.list_by_session.return_value = [mock_task]

        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="main",
            context={"background_manager": mock_bg_manager},
        )

        assert should_skip is True

    def test_skip_context_exhausted(self, plugin):
        """Test skipping when context is exhausted"""
        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="main",
            context={"context_usage": 0.96},
        )

        assert should_skip is True

    def test_skip_waiting_for_user(self, plugin):
        """Test skipping when waiting for user input"""
        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="main",
            context={"last_response": "请问您希望怎么做？"},
        )

        assert should_skip is True

    def test_no_skip_normal_case(self, plugin):
        """Test not skipping in normal case"""
        should_skip = plugin.should_skip_continuation(
            session_id="test",
            agent="main",
            context={},
        )

        assert should_skip is False


class TestTaskSystemIntegration:
    """Tests for TaskSystem integration"""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance"""
        return TodoContinuationEnforcerPlugin()

    def test_get_pending_tasks_no_manager(self, plugin):
        """Test getting tasks when TaskSystem not available"""
        tasks = plugin._get_pending_tasks_from_system({})

        assert tasks == []

    def test_get_pending_tasks_with_manager(self, plugin):
        """Test getting tasks from TaskSystem"""
        # Mock task manager
        from pyagentforge.plugins.integration.task_system import TaskStatus

        mock_task = MagicMock()
        mock_task.id = "test-1"
        mock_task.title = "Test Task"
        mock_task.status = TaskStatus.PENDING

        mock_manager = MagicMock()
        mock_manager.list_tasks.return_value = [mock_task]

        tasks = plugin._get_pending_tasks_from_system({
            "task_manager": mock_manager
        })

        assert len(tasks) == 1
        assert tasks[0]["id"] == "test-1"
        assert tasks[0]["title"] == "Test Task"


class TestContinuationPrompt:
    """Tests for continuation prompt building"""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance"""
        return TodoContinuationEnforcerPlugin()

    def test_build_continuation_prompt(self, plugin):
        """Test building continuation prompt"""
        todos = [
            "Task 1",
            "Task 2",
            "Task 3",
        ]

        prompt = plugin._build_continuation_prompt(todos)

        assert "还有以下任务未完成" in prompt
        assert "Task 1" in prompt
        assert "Task 2" in prompt
        assert "Task 3" in prompt
        assert "请继续完成" in prompt


class TestPluginLifecycle:
    """Tests for plugin lifecycle"""

    @pytest.mark.asyncio
    async def test_plugin_activation(self):
        """Test plugin activation"""
        plugin = TodoContinuationEnforcerPlugin()

        await plugin.on_activate()

        # Should have registered hooks
        # (Hooks are registered in the registry, not stored in plugin)

    @pytest.mark.asyncio
    async def test_plugin_deactivation(self):
        """Test plugin deactivation"""
        plugin = TodoContinuationEnforcerPlugin()

        await plugin.on_activate()
        await plugin.on_deactivate()

        # Should have cleared session states
        assert len(plugin._session_states) == 0
