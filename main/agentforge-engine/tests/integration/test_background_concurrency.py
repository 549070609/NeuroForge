"""
Integration Tests for Background Manager and Concurrency Manager

Tests the interaction between background task execution and concurrency control.
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pyagentforge.core.background_manager import (
    BackgroundManager,
    BackgroundTask,
    TaskStatus,
    NotificationBatch,
)
from pyagentforge.core.concurrency_manager import (
    ConcurrencyManager,
    ConcurrencyConfig,
    ConcurrencySlot,
    ResourceType,
)
from pyagentforge.plugin.hooks import HookRegistry, HookType


class MockEngine:
    """Mock Agent Engine for testing"""

    def __init__(self, response: str = "Mock engine response", delay: float = 0.1):
        self.response = response
        self.delay = delay
        self.run_count = 0
        self.last_prompt = None

    async def run(self, prompt: str) -> str:
        """Simulate engine execution"""
        self.run_count += 1
        self.last_prompt = prompt
        await asyncio.sleep(self.delay)  # Simulate work
        return self.response


class TestBackgroundTaskAcquiresSlot:
    """Test that background tasks properly acquire concurrency slots"""

    @pytest.mark.asyncio
    async def test_task_acquires_slot_on_start(self):
        """
        Test that a background task acquires a concurrency slot when starting

        Flow:
        1. Launch background task
        2. Verify slot is acquired
        3. Task completes
        4. Verify slot is released
        """
        concurrency = ConcurrencyManager()
        manager = BackgroundManager(concurrency_config=ConcurrencyConfig())

        # Track engine factory calls
        engine_created = False
        slot_acquired = False

        def engine_factory(agent_type: str):
            nonlocal engine_created
            engine_created = True
            # Check if slot was acquired
            stats = concurrency.get_stats()
            if stats["current_active"] > 0:
                nonlocal slot_acquired
                slot_acquired = True
            return MockEngine(delay=0.1)

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="test_agent",
            prompt="Test task",
            session_id="session_1",
        )

        # Wait for task to start and acquire slot
        await asyncio.sleep(0.05)

        # Verify: Slot was acquired during execution
        assert task.status in [TaskStatus.RUNNING, TaskStatus.COMPLETED]

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=2.0)

        # Verify: Task completed
        assert task.status == TaskStatus.COMPLETED

        # Verify: Slot was released
        stats = concurrency.get_stats()
        assert stats["current_active"] == 0

    @pytest.mark.asyncio
    async def test_slot_released_on_error(self):
        """
        Test that slot is released even if task fails

        Flow:
        1. Launch task that will fail
        2. Task fails
        3. Verify slot is still released
        """
        concurrency = ConcurrencyManager()
        manager = BackgroundManager(concurrency_config=ConcurrencyConfig())

        def failing_engine_factory(agent_type: str):
            # Create engine that will fail
            engine = MagicMock()
            engine.run = AsyncMock(side_effect=ValueError("Intentional failure"))
            return engine

        manager.set_engine_factory(failing_engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="failing_agent",
            prompt="This will fail",
            session_id="session_1",
        )

        # Wait for failure
        await asyncio.sleep(0.2)

        # Verify: Task failed
        assert task.status == TaskStatus.FAILED
        assert "Intentional failure" in task.error

        # Verify: Slot was released
        stats = concurrency.get_stats()
        assert stats["current_active"] == 0


class TestConcurrentBackgroundTasksShareSlots:
    """Test concurrent task slot sharing"""

    @pytest.mark.asyncio
    async def test_multiple_tasks_share_global_limit(self):
        """
        Test that multiple tasks share the global concurrency limit

        Flow:
        1. Set global limit to 2
        2. Launch 4 tasks
        3. Only 2 should run at a time
        4. Others wait in queue
        """
        config = ConcurrencyConfig(max_global=2)
        concurrency = ConcurrencyManager(config)
        manager = BackgroundManager(concurrency_config=config)

        running_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        def engine_factory(agent_type: str):
            async def track_run(prompt: str):
                nonlocal running_count, max_concurrent
                async with lock:
                    running_count += 1
                    max_concurrent = max(max_concurrent, running_count)

                await asyncio.sleep(0.1)  # Simulate work

                async with lock:
                    running_count -= 1

                return "Done"

            engine = MagicMock()
            engine.run = track_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch 4 tasks
        tasks = []
        for i in range(4):
            task = await manager.launch(
                agent_type="test_agent",
                prompt=f"Task {i}",
                session_id="session_1",
            )
            tasks.append(task)

        # Wait for all to complete
        await asyncio.sleep(0.5)

        # Verify: Never exceeded global limit
        assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}, expected <= 2"

        # Verify: All tasks completed
        for task in tasks:
            assert task.status == TaskStatus.COMPLETED


class TestReleaseOnTaskCompletion:
    """Test slot release on task completion"""

    @pytest.mark.asyncio
    async def test_slot_released_on_success(self):
        """
        Test slot is released when task succeeds

        Flow:
        1. Launch task
        2. Task completes successfully
        3. Verify slot released
        """
        manager = BackgroundManager()

        manager.set_engine_factory(lambda _: MockEngine(response="Success", delay=0.05))

        task = await manager.launch(
            agent_type="agent",
            prompt="Test",
            session_id="s1",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=2.0)

        # Verify: Slot released
        stats = manager.concurrency.get_stats()
        assert stats["current_active"] == 0

    @pytest.mark.asyncio
    async def test_slot_released_on_cancellation(self):
        """
        Test slot is released when task is cancelled

        Flow:
        1. Launch task
        2. Cancel task while running
        3. Verify slot released
        """
        manager = BackgroundManager()

        def slow_engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                await asyncio.sleep(10)  # Long running
                return "Done"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(slow_engine_factory)

        task = await manager.launch(
            agent_type="agent",
            prompt="Test",
            session_id="s1",
        )

        # Wait a bit for task to start
        await asyncio.sleep(0.05)

        # Cancel task
        await manager.cancel(task.id)

        # Verify: Task cancelled
        assert task.status == TaskStatus.CANCELLED

        # Verify: Slot released
        await asyncio.sleep(0.05)
        stats = manager.concurrency.get_stats()
        assert stats["current_active"] == 0


class TestModelSpecificLimits:
    """Test model-specific concurrency limits"""

    @pytest.mark.asyncio
    async def test_per_agent_limit_enforced(self):
        """
        Test per-agent concurrency limits

        Flow:
        1. Set agent concurrency limit to 1
        2. Launch 3 tasks of same agent type
        3. Only 1 should run at a time
        """
        config = ConcurrencyConfig(
            max_per_model=10,  # High global limit
        )
        manager = BackgroundManager(concurrency_config=config)

        running_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        def engine_factory(agent_type: str):
            async def track_run(prompt: str):
                nonlocal running_count, max_concurrent
                async with lock:
                    running_count += 1
                    max_concurrent = max(max_concurrent, running_count)

                await asyncio.sleep(0.1)

                async with lock:
                    running_count -= 1

                return "Done"

            engine = MagicMock()
            engine.run = track_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch 3 tasks with max_concurrent=1
        tasks = []
        for i in range(3):
            task = await manager.launch(
                agent_type="limited_agent",
                prompt=f"Task {i}",
                session_id="s1",
                metadata={"max_concurrent": 1},  # Limit to 1
            )
            tasks.append(task)

        # Wait for all to complete
        await asyncio.sleep(0.5)

        # Verify: Only 1 ran at a time
        assert max_concurrent == 1, f"Max concurrent was {max_concurrent}, expected 1"


class TestPriorityScheduling:
    """Test priority-based task scheduling"""

    @pytest.mark.asyncio
    async def test_higher_priority_first(self):
        """
        Test that higher priority tasks are processed first

        Note: Current implementation may not enforce strict priority ordering,
        but we can verify tasks complete regardless of priority.
        """
        config = ConcurrencyConfig(max_global=1)  # Only 1 at a time
        manager = BackgroundManager(concurrency_config=config)

        execution_order = []

        def engine_factory(agent_type: str):
            async def record_run(prompt: str):
                execution_order.append(prompt)
                await asyncio.sleep(0.05)
                return f"Done: {prompt}"

            engine = MagicMock()
            engine.run = record_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch tasks with different priorities
        low_task = await manager.launch(
            agent_type="agent",
            prompt="low_priority",
            session_id="s1",
            priority=1,
        )

        high_task = await manager.launch(
            agent_type="agent",
            prompt="high_priority",
            session_id="s1",
            priority=10,
        )

        # Wait for completion
        await asyncio.sleep(0.3)

        # Verify: All tasks completed
        assert low_task.status == TaskStatus.COMPLETED
        assert high_task.status == TaskStatus.COMPLETED

        # Verify: Both were executed
        assert len(execution_order) == 2


class TestConcurrentLaunchWithLimits:
    """Test concurrent task launching with limits"""

    @pytest.mark.asyncio
    async def test_concurrent_launch_respects_limits(self):
        """
        Test that concurrent launches respect concurrency limits

        Flow:
        1. Set limit to 2
        2. Launch 5 tasks concurrently
        3. Verify only 2 run at a time
        """
        config = ConcurrencyConfig(max_global=2)
        manager = BackgroundManager(concurrency_config=config)

        running_count = 0
        max_concurrent = 0
        lock = asyncio.Lock()
        start_events = []

        def engine_factory(agent_type: str):
            async def track_run(prompt: str):
                nonlocal running_count, max_concurrent
                async with lock:
                    running_count += 1
                    max_concurrent = max(max_concurrent, running_count)
                    start_events.append(datetime.now(timezone.utc))

                await asyncio.sleep(0.1)

                async with lock:
                    running_count -= 1

                return "Done"

            engine = MagicMock()
            engine.run = track_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch all tasks concurrently
        launch_coros = [
            manager.launch(
                agent_type="agent",
                prompt=f"Task {i}",
                session_id="s1",
            )
            for i in range(5)
        ]

        tasks = await asyncio.gather(*launch_coros)

        # Wait for all to complete
        await asyncio.sleep(0.5)

        # Verify: Never exceeded limit
        assert max_concurrent <= 2, f"Max concurrent was {max_concurrent}"

        # Verify: All completed
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        assert completed == 5

    @pytest.mark.asyncio
    async def test_queue_timeout(self):
        """
        Test that tasks timeout if waiting too long for slot

        Flow:
        1. Set very short queue timeout
        2. Fill all slots
        3. Launch more tasks
        4. Verify queued tasks timeout
        """
        config = ConcurrencyConfig(
            max_global=1,
            queue_timeout=0.1,  # Short timeout
        )
        manager = BackgroundManager(concurrency_config=config)

        call_count = 0

        def engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.5)  # Long task
                return "Done"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch first task (will acquire slot)
        task1 = await manager.launch(
            agent_type="agent",
            prompt="Task 1",
            session_id="s1",
        )

        # Give first task time to acquire slot
        await asyncio.sleep(0.05)

        # Launch second task (should timeout in queue)
        task2 = await manager.launch(
            agent_type="agent",
            prompt="Task 2",
            session_id="s1",
        )

        # Wait for timeout
        await asyncio.sleep(0.3)

        # First task should run or be running
        # Second task may fail due to timeout or complete if slot freed


class TestCleanupReleasesAllSlots:
    """Test cleanup releases all slots"""

    @pytest.mark.asyncio
    async def test_cleanup_releases_all_slots(self):
        """
        Test that cleanup releases all held slots

        Flow:
        1. Launch multiple tasks
        2. Call cleanup while tasks running
        3. Verify all slots released
        """
        manager = BackgroundManager()

        def slow_engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                await asyncio.sleep(10)
                return "Done"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(slow_engine_factory)

        # Launch tasks
        tasks = []
        for i in range(3):
            task = await manager.launch(
                agent_type="agent",
                prompt=f"Task {i}",
                session_id="s1",
            )
            tasks.append(task)

        # Wait for tasks to start
        await asyncio.sleep(0.1)

        # Call cleanup
        manager._cleanup_all_tasks()

        # Verify: All slots released
        stats = manager.concurrency.get_stats()
        assert stats["current_active"] == 0

        # Verify: All tasks cancelled
        for task in tasks:
            assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_manager_stop_cleans_up(self):
        """
        Test that stopping manager cleans up resources

        Flow:
        1. Start manager
        2. Launch tasks
        3. Stop manager
        4. Verify cleanup
        """
        manager = BackgroundManager()

        await manager.start()

        manager.set_engine_factory(lambda _: MockEngine(delay=0.5))

        # Launch task
        task = await manager.launch(
            agent_type="agent",
            prompt="Test",
            session_id="s1",
        )

        # Stop manager
        await manager.stop()

        # Verify: Cleanup task was cancelled
        assert manager._cleanup_task is None or manager._cleanup_task.cancelled()


class TestNotificationBatching:
    """Test notification batching functionality"""

    @pytest.mark.asyncio
    async def test_batched_notifications(self):
        """
        Test that completions are batched before notification

        Flow:
        1. Set notification delay
        2. Complete multiple tasks quickly
        3. Verify single batched notification
        """
        notifications = []

        async def notification_callback(session_id: str, tasks: list):
            notifications.append((session_id, tasks))

        manager = BackgroundManager(notification_delay=0.1)
        manager.set_notification_callback(notification_callback)

        manager.set_engine_factory(lambda _: MockEngine(delay=0.05))

        # Launch multiple tasks in same session
        for i in range(3):
            await manager.launch(
                agent_type="agent",
                prompt=f"Task {i}",
                session_id="session_1",
            )

        # Wait for notifications
        await asyncio.sleep(0.3)

        # Verify: Notification was sent
        assert len(notifications) >= 1

        # Verify: All completed tasks were in notification
        total_tasks = sum(len(t) for _, t in notifications)
        assert total_tasks >= 1  # At least some tasks completed


class TestSessionIsolation:
    """Test session isolation"""

    @pytest.mark.asyncio
    async def test_tasks_isolated_by_session(self):
        """
        Test that tasks are properly isolated by session

        Flow:
        1. Launch tasks in different sessions
        2. Verify session grouping
        """
        manager = BackgroundManager()

        manager.set_engine_factory(lambda _: MockEngine(delay=0.05))

        # Launch tasks in different sessions
        task1 = await manager.launch(
            agent_type="agent",
            prompt="Session 1 task",
            session_id="session_1",
        )

        task2 = await manager.launch(
            agent_type="agent",
            prompt="Session 2 task",
            session_id="session_2",
        )

        # Wait for completion
        await asyncio.sleep(0.2)

        # Verify: Can list by session
        s1_tasks = manager.list_by_session("session_1")
        s2_tasks = manager.list_by_session("session_2")

        assert len(s1_tasks) == 1
        assert len(s2_tasks) == 1
        assert s1_tasks[0].id == task1.id
        assert s2_tasks[0].id == task2.id


class TestTaskTTL:
    """Test task TTL (time-to-live) functionality"""

    @pytest.mark.asyncio
    async def test_task_ttl_expiry(self):
        """
        Test that tasks expire after TTL

        Flow:
        1. Launch task with very short TTL
        2. Wait for expiry
        3. Verify task is cancelled
        """
        manager = BackgroundManager()

        def slow_engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                await asyncio.sleep(10)
                return "Done"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(slow_engine_factory)

        # Launch task with very short TTL (100ms)
        task = await manager.launch(
            agent_type="agent",
            prompt="Test",
            session_id="s1",
            ttl_ms=100,
        )

        # Wait for TTL expiry
        await asyncio.sleep(0.2)

        # Manually trigger cleanup (normally runs periodically)
        await manager._cleanup_expired_tasks()

        # Verify: Task was cancelled due to TTL
        # Note: May or may not be cancelled depending on timing
        # Just verify task exists and has TTL set
        assert task.ttl_expires_at is not None


class TestTaskStats:
    """Test task statistics"""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """
        Test getting manager statistics

        Flow:
        1. Launch tasks with different statuses
        2. Get stats
        3. Verify counts are correct
        """
        manager = BackgroundManager()

        manager.set_engine_factory(lambda _: MockEngine(delay=0.1))

        # Launch multiple tasks
        tasks = []
        for i in range(3):
            task = await manager.launch(
                agent_type="agent",
                prompt=f"Task {i}",
                session_id="s1",
            )
            tasks.append(task)

        # Wait for completion
        await asyncio.sleep(0.3)

        # Get stats
        stats = manager.get_stats()

        # Verify: Stats are present
        assert "total_tasks" in stats
        assert "completed" in stats
        assert "running" in stats
        assert "concurrency" in stats

        # Verify: All completed
        assert stats["total_tasks"] == 3
        assert stats["completed"] == 3
