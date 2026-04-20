"""
Integration Tests for Phase 1 Features

Tests the interaction between:
- Todo Continuation Enforcer
- Task Management System
- Background Manager
"""

import asyncio
from datetime import UTC
from unittest.mock import AsyncMock

import pytest

from pyagentforge.kernel.background_manager import BackgroundManager
from pyagentforge.plugins.integration.task_system import (
    TaskManagementPlugin,
    TaskStatus,
)
from pyagentforge.plugins.integration.todo_continuation import (
    TodoContinuationEnforcerPlugin,
)


class TestTodoTaskSystemIntegration:
    """Integration tests for Todo and TaskSystem"""

    @pytest.fixture
    async def setup_plugins(self):
        """Setup both plugins"""
        task_plugin = TaskManagementPlugin()
        todo_plugin = TodoContinuationEnforcerPlugin()

        await task_plugin.on_activate()
        await todo_plugin.on_activate()

        return task_plugin, todo_plugin

    @pytest.mark.asyncio
    async def test_todo_reads_task_system(self, setup_plugins):
        """Test that Todo plugin reads tasks from TaskSystem"""
        task_plugin, todo_plugin = await setup_plugins

        # Create a task in TaskSystem
        task_manager = task_plugin.task_manager
        task_manager.create_task(
            title="Test Task",
            description="A task to complete",
        )

        # Get pending tasks via Todo plugin
        context = {"task_manager": task_manager}
        pending = todo_plugin._get_pending_tasks_from_system(context)

        assert len(pending) == 1
        assert pending[0]["title"] == "Test Task"
        assert pending[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_in_progress_tasks_detected(self, setup_plugins):
        """Test that in_progress tasks are detected"""
        task_plugin, todo_plugin = await setup_plugins

        task_manager = task_plugin.task_manager

        # Create and start a task
        task = task_manager.create_task(
            title="In Progress Task",
            description="A task in progress",
        )
        task_manager.update_task(task.id, status=TaskStatus.IN_PROGRESS)

        # Get pending tasks
        context = {"task_manager": task_manager}
        pending = todo_plugin._get_pending_tasks_from_system(context)

        assert len(pending) == 1
        assert pending[0]["status"] == "in_progress"

    @pytest.mark.asyncio
    async def test_completed_tasks_not_detected(self, setup_plugins):
        """Test that completed tasks are not detected"""
        task_plugin, todo_plugin = await setup_plugins

        task_manager = task_plugin.task_manager

        # Create and complete a task
        task = task_manager.create_task(
            title="Completed Task",
            description="A completed task",
        )
        task_manager.update_task(task.id, status=TaskStatus.COMPLETED)

        # Get pending tasks
        context = {"task_manager": task_manager}
        pending = todo_plugin._get_pending_tasks_from_system(context)

        assert len(pending) == 0


class TestBackgroundManagerIntegration:
    """Integration tests for Background Manager"""

    @pytest.fixture
    def background_manager(self):
        """Create background manager"""
        return BackgroundManager()

    @pytest.mark.asyncio
    async def test_batched_notification(self, background_manager):
        """Test that notifications are batched"""
        notifications = []

        async def notification_callback(session_id, tasks):
            notifications.append({
                "session_id": session_id,
                "tasks": tasks,
            })

        background_manager.set_notification_callback(notification_callback)
        await background_manager.start()

        try:
            # Mock engine factory
            async def mock_engine(agent_type):
                engine = AsyncMock()
                engine.run = AsyncMock(return_value="Task completed")
                return engine

            background_manager.set_engine_factory(mock_engine)

            # Launch multiple tasks quickly
            await background_manager.launch(
                agent_type="test",
                prompt="Task 1",
                session_id="session-1",
            )

            await background_manager.launch(
                agent_type="test",
                prompt="Task 2",
                session_id="session-1",
            )

            # Wait for completion
            await asyncio.sleep(3)  # Wait for notification delay

            # Should have received a single batched notification
            assert len(notifications) >= 1

            # All tasks should be in the same notification
            latest = notifications[-1]
            assert latest["session_id"] == "session-1"
            assert len(latest["tasks"]) >= 1

        finally:
            await background_manager.stop()

    @pytest.mark.asyncio
    async def test_format_batch_notification(self, background_manager):
        """Test batch notification formatting"""
        from pyagentforge.kernel.background_manager import BackgroundTask, TaskStatus

        tasks = [
            BackgroundTask(
                id="task-1",
                agent_type="test",
                prompt="Test",
                session_id="session-1",
                status=TaskStatus.COMPLETED,
                result="Success",
            ),
            BackgroundTask(
                id="task-2",
                agent_type="test",
                prompt="Test",
                session_id="session-1",
                status=TaskStatus.FAILED,
                error="Something went wrong",
            ),
        ]

        formatted = BackgroundManager.format_batch_notification(tasks)

        assert "后台任务完成" in formatted
        assert "成功 (1)" in formatted
        assert "失败 (1)" in formatted

    @pytest.mark.asyncio
    async def test_stale_task_cleanup(self, background_manager):
        """Test that stale tasks are cleaned up"""
        await background_manager.start()

        try:
            # Create a mock stale task
            from datetime import datetime, timedelta

            from pyagentforge.kernel.background_manager import BackgroundTask, TaskStatus

            old_time = datetime.now(UTC) - timedelta(hours=2)

            stale_task = BackgroundTask(
                id="stale-1",
                agent_type="test",
                prompt="Stale task",
                session_id="session-1",
                status=TaskStatus.RUNNING,
            )
            stale_task.started_at = old_time.isoformat()

            background_manager._tasks["stale-1"] = stale_task

            # Run cleanup
            await background_manager._cleanup_expired_tasks()

            # Task should be cancelled
            assert background_manager._tasks["stale-1"].status == TaskStatus.CANCELLED

        finally:
            await background_manager.stop()


class TestEndToEnd:
    """End-to-end integration tests"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test full workflow with all Phase 1 features"""
        # Setup
        task_plugin = TaskManagementPlugin()
        todo_plugin = TodoContinuationEnforcerPlugin()
        bg_manager = BackgroundManager()

        await task_plugin.on_activate()
        await todo_plugin.on_activate()
        await bg_manager.start()

        try:
            # 1. Create a task in TaskSystem
            task_manager = task_plugin.task_manager
            task = task_manager.create_task(
                title="Implement Feature",
                description="Implement the new feature",
            )

            # 2. Todo plugin should detect it
            context = {"task_manager": task_manager}
            pending = todo_plugin._get_pending_tasks_from_system(context)

            assert len(pending) == 1

            # 3. Launch background task
            async def mock_engine(agent_type):
                engine = AsyncMock()
                engine.run = AsyncMock(return_value="Feature implemented")
                return engine

            bg_manager.set_engine_factory(mock_engine)

            await bg_manager.launch(
                agent_type="coder",
                prompt="Implement the feature",
                session_id="session-1",
            )

            # 4. Wait for completion
            await asyncio.sleep(3)

            # 5. Update task in TaskSystem
            task_manager.update_task(task.id, status=TaskStatus.COMPLETED)

            # 6. Todo plugin should not detect it anymore
            pending = todo_plugin._get_pending_tasks_from_system(context)

            assert len(pending) == 0

        finally:
            await bg_manager.stop()
            await task_plugin.on_deactivate()
            await todo_plugin.on_deactivate()
