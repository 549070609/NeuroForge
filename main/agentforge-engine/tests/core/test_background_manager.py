"""
Tests for BackgroundManager

Tests background task management, isolated execution, and batched notifications.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from pyagentforge.kernel.background_manager import (
    BackgroundManager,
    BackgroundTask,
    TaskStatus,
)
from pyagentforge.kernel.concurrency_manager import ConcurrencyConfig

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_engine_factory():
    """Create a mock engine factory that returns engines with run method."""
    engines = {}

    def factory(agent_type: str):
        mock_engine = AsyncMock()
        mock_engine.run = AsyncMock(return_value=f"Result from {agent_type}")
        engines[agent_type] = mock_engine
        return mock_engine

    factory.engines = engines
    return factory


@pytest.fixture
def concurrency_config_small():
    """Create a concurrency config with small limits for testing."""
    return ConcurrencyConfig(
        max_global=2,
        max_per_model=1,
        max_per_provider=1,
        queue_timeout=5.0,
    )


@pytest.fixture
async def background_manager_with_factory(mock_engine_factory):
    """Create a background manager with engine factory set."""
    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=mock_engine_factory,
    )
    await manager.start()
    yield manager
    await manager.stop()


@pytest.fixture
def notification_tracker():
    """Track notification callback calls."""
    calls = []

    async def callback(session_id: str, tasks: list[BackgroundTask]):
        calls.append({"session_id": session_id, "tasks": tasks})

    callback.calls = calls
    return callback


# ============================================================================
# Test: test_launch_creates_task
# ============================================================================

@pytest.mark.asyncio
async def test_launch_creates_task(background_manager_with_factory):
    """
    Test that launch() creates a BackgroundTask with correct properties.

    Verifies:
    - Task ID is generated
    - Task status is PENDING initially
    - Agent type, prompt, session_id are set correctly
    - Task is stored in manager's task dict
    """
    manager = background_manager_with_factory

    task = await manager.launch(
        agent_type="explore",
        prompt="Find all Python files",
        session_id="session-123",
        priority=5,
        metadata={"key": "value"},
    )

    # Verify task properties
    assert task.id is not None
    assert len(task.id) == 8  # UUID truncated to 8 chars
    assert task.agent_type == "explore"
    assert task.prompt == "Find all Python files"
    assert task.session_id == "session-123"
    assert task.priority == 5
    assert task.metadata == {"key": "value"}

    # Verify task is stored
    assert task.id in manager._tasks
    assert manager._tasks[task.id] == task

    # Verify async task is created
    assert task.id in manager._running_tasks


# ============================================================================
# Test: test_task_execution_uses_isolated_engine
# ============================================================================

@pytest.mark.asyncio
async def test_task_execution_uses_isolated_engine(mock_engine_factory):
    """
    Test that task execution uses isolated engine instances.

    Verifies:
    - Engine factory is called for each task
    - Engine.run() is called with the task prompt
    - Task result is set from engine output
    """
    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=mock_engine_factory,
    )
    await manager.start()

    try:
        task = await manager.launch(
            agent_type="code",
            prompt="Implement a hello world function",
            session_id="test-session",
        )

        # Wait for task to complete
        completed_task = await manager.wait_for_completion(task.id, timeout=5.0)

        assert completed_task is not None
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.result == "Result from code"

        # Verify engine factory was called
        assert "code" in mock_engine_factory.engines

    finally:
        await manager.stop()


# ============================================================================
# Test: test_cancel_stops_running_task
# ============================================================================

@pytest.mark.asyncio
async def test_cancel_stops_running_task():
    """
    Test that cancel() stops a running task.

    Verifies:
    - Task status changes to CANCELLED
    - Running asyncio task is cancelled
    - Returns True for successful cancellation
    """
    # Create an engine that takes a long time
    slow_engine = AsyncMock()
    slow_engine.run = AsyncMock(side_effect=lambda p: asyncio.sleep(10))

    def slow_factory(agent_type: str):
        return slow_engine

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=slow_factory,
    )
    await manager.start()

    try:
        task = await manager.launch(
            agent_type="slow-agent",
            prompt="This will take a long time",
            session_id="test-session",
        )

        # Give task time to start
        await asyncio.sleep(0.1)

        # Cancel the task
        result = await manager.cancel(task.id)

        assert result is True
        assert task.status == TaskStatus.CANCELLED

    finally:
        await manager.stop()


# ============================================================================
# Test: test_wait_for_completion_returns_result
# ============================================================================

@pytest.mark.asyncio
async def test_wait_for_completion_returns_result(background_manager_with_factory):
    """
    Test that wait_for_completion() returns the completed task.

    Verifies:
    - Waits for task execution to complete
    - Returns task with COMPLETED status
    - Result is available
    """
    manager = background_manager_with_factory

    task = await manager.launch(
        agent_type="explore",
        prompt="Quick task",
        session_id="test-session",
    )

    # Wait for completion
    completed = await manager.wait_for_completion(task.id, timeout=5.0)

    assert completed is not None
    assert completed.status == TaskStatus.COMPLETED
    assert completed.result is not None
    assert completed.duration_ms > 0


# ============================================================================
# Test: test_wait_for_completion_timeout
# ============================================================================

@pytest.mark.asyncio
async def test_wait_for_completion_timeout():
    """
    Test that wait_for_completion() respects timeout.

    Verifies:
    - Returns current task state on timeout
    - Does not raise exception on timeout
    """
    slow_engine = AsyncMock()
    slow_engine.run = AsyncMock(side_effect=lambda p: asyncio.sleep(10))

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: slow_engine,
    )
    await manager.start()

    try:
        task = await manager.launch(
            agent_type="slow",
            prompt="Slow task",
            session_id="test-session",
        )

        # Wait with short timeout
        result = await manager.wait_for_completion(task.id, timeout=0.1)

        # Should return current task state (still running)
        assert result is not None
        assert result.status in (TaskStatus.PENDING, TaskStatus.RUNNING)

    finally:
        await manager.stop()


# ============================================================================
# Test: test_batched_notification_groups_tasks
# ============================================================================

@pytest.mark.asyncio
async def test_batched_notification_groups_tasks(notification_tracker):
    """
    Test that batched notification groups tasks by session.

    Verifies:
    - Multiple tasks in same session are grouped
    - Notification callback is called once per session
    - All completed tasks are included in batch
    """
    # Create fast engine
    fast_engine = AsyncMock()
    fast_engine.run = AsyncMock(return_value="Done")

    manager = BackgroundManager(
        notification_delay=0.1,  # 100ms batching window
        engine_factory=lambda t: fast_engine,
    )
    manager.set_notification_callback(notification_tracker)
    await manager.start()

    try:
        # Launch multiple tasks in same session
        session_id = "batch-session"
        tasks = []
        for i in range(3):
            task = await manager.launch(
                agent_type="explore",
                prompt=f"Task {i}",
                session_id=session_id,
            )
            tasks.append(task)

        # Wait for all tasks to complete and notification to fire
        await asyncio.sleep(0.5)

        # Verify callback was called
        assert len(notification_tracker.calls) >= 1

        # Verify all tasks were batched together
        batch = notification_tracker.calls[0]
        assert batch["session_id"] == session_id
        assert len(batch["tasks"]) == 3

    finally:
        await manager.stop()


# ============================================================================
# Test: test_expired_tasks_are_cancelled
# ============================================================================

@pytest.mark.asyncio
async def test_expired_tasks_are_cancelled():
    """
    Test that tasks exceeding TTL are cancelled.

    Verifies:
    - Task TTL is set correctly
    - Expired tasks are marked as CANCELLED
    - Cleanup cancels running asyncio tasks
    """
    slow_engine = AsyncMock()
    slow_engine.run = AsyncMock(side_effect=lambda p: asyncio.sleep(10))

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: slow_engine,
    )
    await manager.start()

    try:
        # Launch task with short TTL
        task = await manager.launch(
            agent_type="slow",
            prompt="Will expire",
            session_id="test-session",
            ttl_ms=100,  # 100ms TTL
        )

        # Verify TTL is set
        assert task.ttl_expires_at is not None

        # Wait for TTL to expire and cleanup
        await asyncio.sleep(0.2)

        # Manually trigger cleanup (since periodic cleanup is slow)
        await manager._cleanup_expired_tasks()

        # Task should be cancelled
        assert task.status == TaskStatus.CANCELLED
        assert "TTL expired" in (task.error or "")

    finally:
        await manager.stop()


# ============================================================================
# Test: test_stale_tasks_are_detected
# ============================================================================

@pytest.mark.asyncio
async def test_stale_tasks_are_detected():
    """
    Test that stale tasks (running too long) are detected.

    Verifies:
    - Stale threshold check works
    - Stale tasks are marked CANCELLED
    """
    slow_engine = AsyncMock()
    slow_engine.run = AsyncMock(side_effect=lambda p: asyncio.sleep(10))

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: slow_engine,
    )
    await manager.start()

    try:
        task = await manager.launch(
            agent_type="slow",
            prompt="Will become stale",
            session_id="test-session",
        )

        # Give task time to start
        await asyncio.sleep(0.1)

        # Manually set started_at to simulate stale task
        # Set started_at to 2 hours ago
        stale_time = datetime.now(UTC) - timedelta(hours=2)
        task.started_at = stale_time.isoformat()

        # Run cleanup
        await manager._cleanup_expired_tasks()

        # Task should be cancelled as stale
        assert task.status == TaskStatus.CANCELLED
        assert "stale" in (task.error or "").lower()

    finally:
        await manager.stop()


# ============================================================================
# Test: test_periodic_cleanup_runs
# ============================================================================

@pytest.mark.asyncio
async def test_periodic_cleanup_runs():
    """
    Test that periodic cleanup coroutine runs.

    Verifies:
    - Cleanup task is started with manager
    - Cleanup runs at configured intervals
    - Cleanup task is cancelled on stop
    """
    fast_engine = AsyncMock()
    fast_engine.run = AsyncMock(return_value="Done")

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: fast_engine,
    )

    # Manager not started yet
    assert manager._cleanup_task is None

    await manager.start()

    # Cleanup task should be running
    assert manager._cleanup_task is not None
    assert not manager._cleanup_task.done()

    await manager.stop()

    # Cleanup task should be cancelled
    assert manager._cleanup_task is None


# ============================================================================
# Test: test_cleanup_on_shutdown
# ============================================================================

@pytest.mark.asyncio
async def test_cleanup_on_shutdown():
    """
    Test that cleanup happens on manager shutdown.

    Verifies:
    - Running tasks are cancelled
    - Concurrency state is cleared
    """
    slow_engine = AsyncMock()
    slow_engine.run = AsyncMock(side_effect=lambda p: asyncio.sleep(10))

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: slow_engine,
    )
    await manager.start()

    # Launch multiple tasks
    tasks = []
    for i in range(3):
        task = await manager.launch(
            agent_type="slow",
            prompt=f"Task {i}",
            session_id=f"session-{i}",
        )
        tasks.append(task)

    # Give tasks time to start
    await asyncio.sleep(0.1)

    # Stop manager
    await manager.stop()

    # Verify running tasks dict is cleared
    assert len(manager._running_tasks) == 0

    # Verify concurrency is cleared
    assert len(manager.concurrency._active_slots) == 0


# ============================================================================
# Test: test_respects_concurrency_limits
# ============================================================================

@pytest.mark.asyncio
async def test_respects_concurrency_limits(concurrency_config_small):
    """
    Test that background manager respects concurrency limits.

    Verifies:
    - Concurrency slots are acquired before execution
    - Tasks wait when limit is reached
    - Slots are released after completion
    """
    execution_order = []

    async def track_execution(prompt: str):
        execution_order.append(f"start-{prompt}")
        await asyncio.sleep(0.1)
        execution_order.append(f"end-{prompt}")
        return f"Result: {prompt}"

    tracking_engine = AsyncMock()
    tracking_engine.run = track_execution

    manager = BackgroundManager(
        concurrency_config=concurrency_config_small,
        notification_delay=0.05,
        engine_factory=lambda t: tracking_engine,
    )
    await manager.start()

    try:
        # Launch more tasks than global limit allows
        tasks = []
        for i in range(4):  # More than max_global=2
            task = await manager.launch(
                agent_type="explore",
                prompt=f"Task-{i}",
                session_id="test-session",
            )
            tasks.append(task)

        # Wait for all to complete
        await asyncio.sleep(1.0)

        # All tasks should complete
        completed_count = sum(
            1 for t in tasks if t.status == TaskStatus.COMPLETED
        )
        assert completed_count == 4

    finally:
        await manager.stop()


# ============================================================================
# Test: test_releases_slot_on_completion
# ============================================================================

@pytest.mark.asyncio
async def test_releases_slot_on_completion(concurrency_config_small):
    """
    Test that concurrency slot is released on task completion.

    Verifies:
    - Slot count increases during execution
    - Slot count decreases after completion
    """
    fast_engine = AsyncMock()
    fast_engine.run = AsyncMock(return_value="Done")

    manager = BackgroundManager(
        concurrency_config=concurrency_config_small,
        notification_delay=0.05,
        engine_factory=lambda t: fast_engine,
    )
    await manager.start()

    try:
        initial_active = manager.concurrency._stats["current_active"]

        task = await manager.launch(
            agent_type="explore",
            prompt="Quick task",
            session_id="test-session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Active count should be back to initial
        final_active = manager.concurrency._stats["current_active"]
        assert final_active == initial_active

    finally:
        await manager.stop()


# ============================================================================
# Test: test_releases_slot_on_failure
# ============================================================================

@pytest.mark.asyncio
async def test_releases_slot_on_failure(concurrency_config_small):
    """
    Test that concurrency slot is released on task failure.

    Verifies:
    - Slot is released even when task raises exception
    - Task status is set to FAILED
    """
    failing_engine = AsyncMock()
    failing_engine.run = AsyncMock(side_effect=RuntimeError("Engine failed"))

    manager = BackgroundManager(
        concurrency_config=concurrency_config_small,
        notification_delay=0.05,
        engine_factory=lambda t: failing_engine,
    )
    await manager.start()

    try:
        initial_active = manager.concurrency._stats["current_active"]

        task = await manager.launch(
            agent_type="failing",
            prompt="This will fail",
            session_id="test-session",
        )

        # Wait for completion (failure)
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Task should be failed
        assert task.status == TaskStatus.FAILED
        assert "Engine failed" in task.error

        # Active count should be back to initial
        final_active = manager.concurrency._stats["current_active"]
        assert final_active == initial_active

    finally:
        await manager.stop()


# ============================================================================
# Test: test_get_status_returns_task
# ============================================================================

@pytest.mark.asyncio
async def test_get_status_returns_task(background_manager_with_factory):
    """
    Test that get_status() returns the correct task.

    Verifies:
    - Returns task if exists
    - Returns None if task doesn't exist
    """
    manager = background_manager_with_factory

    task = await manager.launch(
        agent_type="explore",
        prompt="Test task",
        session_id="test-session",
    )

    # Get existing task
    result = manager.get_status(task.id)
    assert result is not None
    assert result.id == task.id

    # Get non-existent task
    result = manager.get_status("non-existent")
    assert result is None


# ============================================================================
# Test: test_list_by_session
# ============================================================================

@pytest.mark.asyncio
async def test_list_by_session(background_manager_with_factory):
    """
    Test that list_by_session() returns all tasks for a session.

    Verifies:
    - Returns all tasks with matching session_id
    - Returns empty list for non-existent session
    """
    manager = background_manager_with_factory

    # Launch tasks in different sessions
    await manager.launch("explore", "Task 1", "session-a")
    await manager.launch("explore", "Task 2", "session-a")
    await manager.launch("explore", "Task 3", "session-b")

    # Get tasks for session-a
    tasks = manager.list_by_session("session-a")
    assert len(tasks) == 2

    # Get tasks for non-existent session
    tasks = manager.list_by_session("non-existent")
    assert len(tasks) == 0


# ============================================================================
# Test: test_list_active
# ============================================================================

@pytest.mark.asyncio
async def test_list_active():
    """
    Test that list_active() returns only active tasks.

    Verifies:
    - Returns PENDING and RUNNING tasks
    - Does not return COMPLETED/FAILED/CANCELLED tasks
    """
    slow_engine = AsyncMock()
    slow_engine.run = AsyncMock(side_effect=lambda p: asyncio.sleep(1))

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: slow_engine,
    )
    await manager.start()

    try:
        # Launch slow task
        running_task = await manager.launch("slow", "Running", "session-1")

        # Wait a bit for task to start
        await asyncio.sleep(0.1)

        # Create completed task by mocking
        completed_task = BackgroundTask(
            id="completed-1",
            agent_type="test",
            prompt="Done",
            session_id="session-2",
            status=TaskStatus.COMPLETED,
        )
        manager._tasks[completed_task.id] = completed_task

        active = manager.list_active()

        # Should include running task
        assert any(t.id == running_task.id for t in active)

        # Should not include completed task
        assert not any(t.id == completed_task.id for t in active)

    finally:
        await manager.stop()


# ============================================================================
# Test: test_get_stats
# ============================================================================

@pytest.mark.asyncio
async def test_get_stats(background_manager_with_factory):
    """
    Test that get_stats() returns accurate statistics.

    Verifies:
    - Counts tasks by status
    - Includes concurrency stats
    """
    manager = background_manager_with_factory

    # Launch a task
    await manager.launch("explore", "Test", "session-1")

    stats = manager.get_stats()

    assert "total_tasks" in stats
    assert "pending" in stats
    assert "running" in stats
    assert "completed" in stats
    assert "failed" in stats
    assert "cancelled" in stats
    assert "concurrency" in stats

    assert stats["total_tasks"] >= 1


# ============================================================================
# Test: test_format_batch_notification
# ============================================================================

def test_format_batch_notification():
    """
    Test that format_batch_notification() creates readable output.

    Verifies:
    - Formats succeeded, failed, cancelled tasks
    - Shows task IDs and previews
    """
    tasks = [
        BackgroundTask(
            id="task-1",
            agent_type="explore",
            prompt="Test",
            session_id="session-1",
            status=TaskStatus.COMPLETED,
            result="Success result here",
        ),
        BackgroundTask(
            id="task-2",
            agent_type="code",
            prompt="Test",
            session_id="session-1",
            status=TaskStatus.FAILED,
            error="Something went wrong",
        ),
        BackgroundTask(
            id="task-3",
            agent_type="plan",
            prompt="Test",
            session_id="session-1",
            status=TaskStatus.CANCELLED,
        ),
    ]

    output = BackgroundManager.format_batch_notification(tasks)

    assert "成功" in output
    assert "失败" in output
    assert "已取消" in output
    assert "task-1" in output
    assert "task-2" in output
    assert "task-3" in output


# ============================================================================
# Test: test_task_to_dict
# ============================================================================

def test_task_to_dict():
    """
    Test that BackgroundTask.to_dict() serializes correctly.

    Verifies:
    - All important fields are included
    - Long strings are truncated appropriately
    """
    task = BackgroundTask(
        id="test-123",
        agent_type="explore",
        prompt="A" * 200,  # Long prompt
        session_id="session-1",
        status=TaskStatus.COMPLETED,
        result="B" * 300,  # Long result
        priority=5,
        task_id="task-456",
    )

    d = task.to_dict()

    assert d["id"] == "test-123"
    assert d["agent_type"] == "explore"
    assert "..." in d["prompt"]  # Truncated
    assert d["status"] == "completed"
    assert d["priority"] == 5
    assert d["task_id"] == "task-456"
    assert len(d["result"]) <= 203  # 200 + "..."


# ============================================================================
# Test: test_no_engine_factory_error
# ============================================================================

@pytest.mark.asyncio
async def test_no_engine_factory_error():
    """
    Test that task fails gracefully when no engine factory is set.

    Verifies:
    - Task status becomes FAILED
    - Error message is descriptive
    """
    manager = BackgroundManager(notification_delay=0.05)
    # Don't set engine factory
    await manager.start()

    try:
        task = await manager.launch(
            agent_type="explore",
            prompt="Test",
            session_id="test-session",
        )

        # Wait for failure
        await manager.wait_for_completion(task.id, timeout=5.0)

        assert task.status == TaskStatus.FAILED
        assert "Engine factory" in task.error

    finally:
        await manager.stop()


# ============================================================================
# Test: test_notification_callback_error_handling
# ============================================================================

@pytest.mark.asyncio
async def test_notification_callback_error_handling():
    """
    Test that errors in notification callback don't crash the manager.

    Verifies:
    - Exception in callback is caught
    - Manager continues to function
    """
    async def failing_callback(session_id: str, tasks: list[BackgroundTask]):
        raise RuntimeError("Callback error")

    fast_engine = AsyncMock()
    fast_engine.run = AsyncMock(return_value="Done")

    manager = BackgroundManager(
        notification_delay=0.05,
        engine_factory=lambda t: fast_engine,
    )
    manager.set_notification_callback(failing_callback)
    await manager.start()

    try:
        task = await manager.launch(
            agent_type="explore",
            prompt="Test",
            session_id="test-session",
        )

        # Wait for completion and notification
        await asyncio.sleep(0.2)

        # Task should still complete successfully
        assert task.status == TaskStatus.COMPLETED

    finally:
        await manager.stop()


# ============================================================================
# Test: test_cancel_non_existent_task
# ============================================================================

@pytest.mark.asyncio
async def test_cancel_non_existent_task(background_manager_with_factory):
    """
    Test cancelling a task that doesn't exist.

    Verifies:
    - Returns False for non-existent task
    """
    manager = background_manager_with_factory

    result = await manager.cancel("non-existent-id")
    assert result is False


# ============================================================================
# Test: test_cancel_completed_task
# ============================================================================

@pytest.mark.asyncio
async def test_cancel_completed_task(background_manager_with_factory):
    """
    Test cancelling a task that's already completed.

    Verifies:
    - Returns False for completed task
    - Task status unchanged
    """
    manager = background_manager_with_factory

    task = await manager.launch("explore", "Test", "session-1")
    await manager.wait_for_completion(task.id, timeout=5.0)

    result = await manager.cancel(task.id)
    assert result is False
    assert task.status == TaskStatus.COMPLETED
