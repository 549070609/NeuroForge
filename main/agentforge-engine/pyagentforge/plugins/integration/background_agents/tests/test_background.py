"""
Tests for Background Manager
"""

import pytest
import asyncio

from pyagentforge.core.background_manager import (
    BackgroundManager,
    BackgroundTask,
    TaskStatus,
)
from pyagentforge.core.concurrency_manager import (
    ConcurrencyConfig,
    ConcurrencyManager,
    ResourceType,
)


class TestConcurrencyManager:
    """Tests for ConcurrencyManager"""

    def test_create_manager(self):
        """Test creating manager"""
        config = ConcurrencyConfig(max_global=10)
        manager = ConcurrencyManager(config)

        assert manager.config.max_global == 10

    @pytest.mark.asyncio
    async def test_acquire_release(self):
        """Test acquire and release"""
        manager = ConcurrencyManager()

        slot_id = await manager.acquire(
            model="gpt-4",
            provider="openai",
            agent="explore",
            session_id="test",
            task_id="task-1",
        )

        assert slot_id is not None
        assert manager._stats["total_acquired"] == 1

        manager.release(slot_id)
        assert manager._stats["total_released"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """Test concurrent limit enforcement"""
        config = ConcurrencyConfig(max_global=2)
        manager = ConcurrencyManager(config)

        # Acquire two slots
        slot1 = await manager.acquire(session_id="test", task_id="1")
        slot2 = await manager.acquire(session_id="test", task_id="2")

        assert slot1 is not None
        assert slot2 is not None

        # Third should timeout
        slot3 = await manager.acquire(
            session_id="test",
            task_id="3",
            timeout=0.1,
        )
        assert slot3 is None

        # Release one
        manager.release(slot1)

        # Now should work
        slot4 = await manager.acquire(
            session_id="test",
            task_id="4",
            timeout=0.5,
        )
        assert slot4 is not None

    def test_get_stats(self):
        """Test getting statistics"""
        manager = ConcurrencyManager()
        stats = manager.get_stats()

        assert "total_acquired" in stats
        assert "current_active" in stats


class TestBackgroundTask:
    """Tests for BackgroundTask"""

    def test_create_task(self):
        """Test creating task"""
        task = BackgroundTask(
            id="task-1",
            agent_type="explore",
            prompt="Search for TODO comments",
            session_id="session-1",
        )

        assert task.id == "task-1"
        assert task.status == TaskStatus.PENDING
        assert task.agent_type == "explore"

    def test_to_dict(self):
        """Test serialization"""
        task = BackgroundTask(
            id="task-1",
            agent_type="explore",
            prompt="Search",
            session_id="session-1",
        )

        data = task.to_dict()

        assert data["id"] == "task-1"
        assert data["status"] == "pending"


class TestBackgroundManager:
    """Tests for BackgroundManager"""

    def test_create_manager(self):
        """Test creating manager"""
        manager = BackgroundManager()

        assert manager.concurrency is not None

    @pytest.mark.asyncio
    async def test_launch_task(self):
        """Test launching a task"""
        manager = BackgroundManager()

        # Mock engine factory
        async def mock_factory(agent_type):
            class MockEngine:
                async def run(self, prompt):
                    await asyncio.sleep(0.1)
                    return "Task completed"

            return MockEngine()

        manager.set_engine_factory(mock_factory)

        task = await manager.launch(
            agent_type="explore",
            prompt="Test prompt",
            session_id="session-1",
        )

        assert task is not None
        assert task.status == TaskStatus.PENDING or task.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting task status"""
        manager = BackgroundManager()

        async def mock_factory(agent_type):
            class MockEngine:
                async def run(self, prompt):
                    await asyncio.sleep(1)
                    return "done"

            return MockEngine()

        manager.set_engine_factory(mock_factory)

        task = await manager.launch(
            agent_type="explore",
            prompt="test",
            session_id="session-1",
        )

        status = manager.get_status(task.id)
        assert status is not None

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test cancelling a task"""
        manager = BackgroundManager()

        async def mock_factory(agent_type):
            class MockEngine:
                async def run(self, prompt):
                    await asyncio.sleep(10)  # Long running
                    return "done"

            return MockEngine()

        manager.set_engine_factory(mock_factory)

        task = await manager.launch(
            agent_type="explore",
            prompt="test",
            session_id="session-1",
        )

        # Wait a bit for task to start
        await asyncio.sleep(0.1)

        # Cancel
        cancelled = await manager.cancel(task.id)
        assert cancelled

        # Check status
        status = manager.get_status(task.id)
        assert status.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_list_active(self):
        """Test listing active tasks"""
        manager = BackgroundManager()

        async def mock_factory(agent_type):
            class MockEngine:
                async def run(self, prompt):
                    await asyncio.sleep(1)
                    return "done"

            return MockEngine()

        manager.set_engine_factory(mock_factory)

        await manager.launch(agent_type="explore", prompt="test1", session_id="s1")
        await manager.launch(agent_type="explore", prompt="test2", session_id="s2")

        active = manager.list_active()
        assert len(active) >= 2

    def test_get_stats(self):
        """Test getting statistics"""
        manager = BackgroundManager()
        stats = manager.get_stats()

        assert "total_tasks" in stats
        assert "concurrency" in stats


class TestTaskStatus:
    """Tests for TaskStatus enum"""

    def test_status_values(self):
        """Test status enum values"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.CANCELLED.value == "cancelled"
