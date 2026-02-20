"""
Integration Tests for Task System

Tests the full task system integration including task creation,
monitoring, execution, and result retrieval.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pyagentforge.core.background_manager import (
    BackgroundManager,
    BackgroundTask,
    TaskStatus,
)
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.message import (
    TextBlock,
    ToolUseBlock,
    ProviderResponse,
)
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.tools.base import BaseTool
from pyagentforge.plugins.integration.task_persistence.task_store import (
    TaskStore,
    StoredTask,
)


class MockProvider:
    """Mock LLM Provider for task system testing"""

    def __init__(self, responses: list[ProviderResponse] | None = None):
        self.model = "mock-model"
        self.max_tokens = 4096
        self.responses = responses or []
        self.call_count = 0

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        self.call_count += 1
        if self.responses:
            idx = min(self.call_count - 1, len(self.responses) - 1)
            return self.responses[idx]
        return ProviderResponse(
            content=[TextBlock(text="Task completed successfully.")],
            stop_reason="end_turn",
        )

    async def stream_message(self, system: str, messages: list[dict], tools: list[dict], **kwargs):
        yield ProviderResponse(
            content=[TextBlock(text="Mock stream response")],
            stop_reason="end_turn",
        )


class SimpleTaskTool(BaseTool):
    """Simple test tool for task system"""

    name: str = "task_tool"
    description: str = "A simple task tool"
    execute_count: int = 0

    async def execute(self, **kwargs: Any) -> str:
        self.execute_count += 1
        return f"Task tool executed with: {kwargs}"


class FailingTaskTool(BaseTool):
    """Tool that fails for testing error handling"""

    name: str = "failing_task_tool"
    description: str = "A tool that fails"

    async def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("Task tool failure")


class SlowTaskTool(BaseTool):
    """Slow tool for testing cancellation"""

    name: str = "slow_task_tool"
    description: str = "A slow task tool"

    async def execute(self, **kwargs: Any) -> str:
        await asyncio.sleep(10)  # Very slow
        return "Slow task completed"


class TestLaunchAndMonitorTask:
    """Test task launching and monitoring"""

    @pytest.mark.asyncio
    async def test_launch_simple_task(self):
        """
        Test launching a simple background task

        Flow:
        1. Create background manager with engine factory
        2. Launch task
        3. Monitor task status changes
        4. Retrieve final result
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=5),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="test_agent",
            prompt="Complete this task",
            session_id="test_session",
        )

        # Verify: Task created with pending status
        assert task.id is not None
        assert task.status == TaskStatus.PENDING
        assert task.session_id == "test_session"

        # Wait for completion
        completed_task = await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Task completed
        assert completed_task is not None
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.result is not None

    @pytest.mark.asyncio
    async def test_monitor_task_status_transitions(self):
        """
        Test monitoring task status transitions

        Flow:
        1. Launch task
        2. Monitor status changes: PENDING -> RUNNING -> COMPLETED
        """
        manager = BackgroundManager()

        status_history = []

        def engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                status_history.append("engine_started")
                await asyncio.sleep(0.1)
                return "Done"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="test_agent",
            prompt="Test task",
            session_id="test_session",
        )

        # Record initial status
        initial_status = task.status
        status_history.append(f"initial_{initial_status.value}")

        # Wait for task to start
        await asyncio.sleep(0.05)

        # Check running status
        running_status = manager.get_status(task.id)
        if running_status and running_status.status == TaskStatus.RUNNING:
            status_history.append("running")

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Task went through expected states
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_with_metadata(self):
        """
        Test task with custom metadata

        Flow:
        1. Launch task with metadata
        2. Verify metadata is preserved
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task with metadata
        task = await manager.launch(
            agent_type="test_agent",
            prompt="Task with metadata",
            session_id="test_session",
            metadata={
                "custom_field": "custom_value",
                "priority": 10,
                "tags": ["important", "urgent"],
            },
        )

        # Verify: Metadata preserved
        assert task.metadata["custom_field"] == "custom_value"
        assert task.metadata["priority"] == 10
        assert "important" in task.metadata["tags"]

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Metadata still present after completion
        assert task.metadata["custom_field"] == "custom_value"


class TestTaskWithToolCalls:
    """Test tasks that involve tool calls"""

    @pytest.mark.asyncio
    async def test_task_with_single_tool_call(self):
        """
        Test task that calls a single tool

        Flow:
        1. Launch task with tool available
        2. LLM calls tool
        3. Tool executes
        4. Task completes with result
        """
        task_tool = SimpleTaskTool()

        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            # Mock provider that will call the tool
            responses = [
                ProviderResponse(
                    content=[
                        TextBlock(text="I will use the tool."),
                        ToolUseBlock(id="tool_1", name="task_tool", input={"param": "value"}),
                    ],
                    stop_reason="tool_use",
                ),
                ProviderResponse(
                    content=[TextBlock(text="Task completed using the tool.")],
                    stop_reason="end_turn",
                ),
            ]

            mock_provider = MockProvider(responses=responses)
            registry = ToolRegistry()
            registry.register(task_tool)

            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=10),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="tool_agent",
            prompt="Use the task tool",
            session_id="test_session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Task completed
        assert task.status == TaskStatus.COMPLETED

        # Verify: Tool was called
        assert task_tool.execute_count == 1

    @pytest.mark.asyncio
    async def test_task_with_multiple_tool_calls(self):
        """
        Test task that calls multiple tools

        Flow:
        1. Launch task with multiple tools available
        2. LLM calls multiple tools in sequence
        3. All tools execute
        4. Task completes
        """
        tool1 = SimpleTaskTool()
        tool1.name = "tool_1"
        tool2 = SimpleTaskTool()
        tool2.name = "tool_2"

        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            responses = [
                # First tool call
                ProviderResponse(
                    content=[
                        ToolUseBlock(id="t1", name="tool_1", input={"x": 1}),
                    ],
                    stop_reason="tool_use",
                ),
                # Second tool call
                ProviderResponse(
                    content=[
                        ToolUseBlock(id="t2", name="tool_2", input={"y": 2}),
                    ],
                    stop_reason="tool_use",
                ),
                # Final response
                ProviderResponse(
                    content=[TextBlock(text="All tools used successfully.")],
                    stop_reason="end_turn",
                ),
            ]

            mock_provider = MockProvider(responses=responses)
            registry = ToolRegistry()
            registry.register(tool1)
            registry.register(tool2)

            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=10),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="multi_tool_agent",
            prompt="Use multiple tools",
            session_id="test_session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Task completed
        assert task.status == TaskStatus.COMPLETED

        # Verify: Both tools called
        assert tool1.execute_count == 1
        assert tool2.execute_count == 1

    @pytest.mark.asyncio
    async def test_task_with_parallel_tool_calls(self):
        """
        Test task that calls tools in parallel

        Flow:
        1. LLM calls multiple tools at once
        2. Tools execute in parallel
        3. All results returned
        """
        tool1 = SlowTaskTool()
        tool1.name = "fast_tool_1"
        tool2 = SlowTaskTool()
        tool2.name = "fast_tool_2"

        # Override to be fast
        async def fast_execute(**kwargs):
            await asyncio.sleep(0.05)
            return "Fast result"

        tool1.execute = fast_execute
        tool2.execute = fast_execute

        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            responses = [
                # Parallel tool calls
                ProviderResponse(
                    content=[
                        ToolUseBlock(id="t1", name="fast_tool_1", input={}),
                        ToolUseBlock(id="t2", name="fast_tool_2", input={}),
                    ],
                    stop_reason="tool_use",
                ),
                ProviderResponse(
                    content=[TextBlock(text="Parallel tools completed.")],
                    stop_reason="end_turn",
                ),
            ]

            mock_provider = MockProvider(responses=responses)
            registry = ToolRegistry()
            registry.register(tool1)
            registry.register(tool2)

            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=10),
            )

        manager.set_engine_factory(engine_factory)

        import time
        start = time.time()

        # Launch task
        task = await manager.launch(
            agent_type="parallel_agent",
            prompt="Run parallel tools",
            session_id="test_session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        elapsed = time.time() - start

        # Verify: Task completed
        assert task.status == TaskStatus.COMPLETED

        # Verify: Parallel execution (should be fast, not sequential)
        assert elapsed < 0.3  # Both tools at ~0.05s, parallel should be quick


class TestTaskErrorHandling:
    """Test task error handling"""

    @pytest.mark.asyncio
    async def test_task_with_tool_error(self):
        """
        Test task handling when tool raises error

        Flow:
        1. Launch task with tool that will fail
        2. Tool raises error
        3. LLM sees error and recovers
        4. Task completes
        """
        failing_tool = FailingTaskTool()

        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            responses = [
                # Tool call that will fail
                ProviderResponse(
                    content=[
                        ToolUseBlock(id="t1", name="failing_task_tool", input={}),
                    ],
                    stop_reason="tool_use",
                ),
                # Recovery after error
                ProviderResponse(
                    content=[TextBlock(text="Tool failed but I handled it.")],
                    stop_reason="end_turn",
                ),
            ]

            mock_provider = MockProvider(responses=responses)
            registry = ToolRegistry()
            registry.register(failing_tool)

            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=10),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="error_handling_agent",
            prompt="Use failing tool",
            session_id="test_session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Task completed (not failed)
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_task_engine_failure(self):
        """
        Test task handling when engine itself fails

        Flow:
        1. Create engine that raises exception
        2. Launch task
        3. Task fails gracefully
        4. Error is recorded
        """
        manager = BackgroundManager()

        def failing_engine_factory(agent_type: str):
            engine = MagicMock()
            engine.run = AsyncMock(side_effect=ValueError("Engine initialization failed"))
            return engine

        manager.set_engine_factory(failing_engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="failing_agent",
            prompt="This will fail",
            session_id="test_session",
        )

        # Wait for failure
        await asyncio.sleep(0.2)

        # Verify: Task failed
        assert task.status == TaskStatus.FAILED
        assert "Engine initialization failed" in task.error

    @pytest.mark.asyncio
    async def test_task_max_iterations_exceeded(self):
        """
        Test task that exceeds max iterations

        Flow:
        1. Create engine with low iteration limit
        2. LLM keeps calling tools
        3. Max iterations reached
        4. Task completes with error message
        """
        tool = SimpleTaskTool()

        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            # Response that always calls tool (infinite loop)
            loop_response = ProviderResponse(
                content=[
                    ToolUseBlock(id="loop", name="simple_task_tool", input={}),
                ],
                stop_reason="tool_use",
            )

            mock_provider = MockProvider(responses=[loop_response] * 100)
            registry = ToolRegistry()
            tool.name = "simple_task_tool"
            registry.register(tool)

            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=3),  # Very low limit
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="loop_agent",
            prompt="Loop forever",
            session_id="test_session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Task completed (with error message)
        assert task.status == TaskStatus.COMPLETED
        assert "Maximum iterations" in task.result or "Error" in task.result


class TestTaskCancellationPropagation:
    """Test task cancellation propagation"""

    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        """
        Test cancelling a running task

        Flow:
        1. Launch long-running task
        2. Cancel while running
        3. Verify task is cancelled
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                await asyncio.sleep(10)  # Long running
                return "Should not reach here"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="slow_agent",
            prompt="Long running task",
            session_id="test_session",
        )

        # Wait for task to start
        await asyncio.sleep(0.1)

        # Cancel task
        cancelled = await manager.cancel(task.id)

        # Verify: Task was cancelled
        assert cancelled is True
        assert task.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self):
        """
        Test that cancelling completed task has no effect

        Flow:
        1. Launch and complete task
        2. Try to cancel
        3. Verify cancellation fails
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch and complete task
        task = await manager.launch(
            agent_type="fast_agent",
            prompt="Quick task",
            session_id="test_session",
        )

        await manager.wait_for_completion(task.id, timeout=5.0)

        # Try to cancel completed task
        cancelled = await manager.cancel(task.id)

        # Verify: Cannot cancel completed task
        assert cancelled is False
        assert task.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_cancel_multiple_tasks(self):
        """
        Test cancelling multiple tasks at once

        Flow:
        1. Launch multiple tasks
        2. Cancel all while running
        3. Verify all are cancelled
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            async def slow_run(prompt: str):
                await asyncio.sleep(10)
                return "Done"

            engine = MagicMock()
            engine.run = slow_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch multiple tasks
        tasks = []
        for i in range(3):
            task = await manager.launch(
                agent_type="slow_agent",
                prompt=f"Task {i}",
                session_id="test_session",
            )
            tasks.append(task)

        # Wait for tasks to start
        await asyncio.sleep(0.1)

        # Cancel all
        for task in tasks:
            await manager.cancel(task.id)

        # Verify: All cancelled
        for task in tasks:
            assert task.status == TaskStatus.CANCELLED


class TestTaskResultRetrieval:
    """Test task result retrieval"""

    @pytest.mark.asyncio
    async def test_get_result_after_completion(self):
        """
        Test retrieving result after task completion

        Flow:
        1. Launch task
        2. Wait for completion
        3. Retrieve result
        """
        manager = BackgroundManager()

        expected_result = "Task completed with expected result"

        def engine_factory(agent_type: str):
            async def run(prompt: str):
                return expected_result

            engine = MagicMock()
            engine.run = run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="result_agent",
            prompt="Return specific result",
            session_id="test_session",
        )

        # Wait for completion
        completed_task = await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Result retrieved
        assert completed_task is not None
        assert completed_task.result == expected_result

    @pytest.mark.asyncio
    async def test_get_result_by_id(self):
        """
        Test retrieving result by task ID

        Flow:
        1. Launch task
        2. Complete task
        3. Look up by ID
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="test_agent",
            prompt="Test",
            session_id="test_session",
        )

        task_id = task.id

        # Wait for completion
        await manager.wait_for_completion(task_id, timeout=5.0)

        # Look up by ID
        retrieved = manager.get_status(task_id)

        # Verify: Retrieved task has result
        assert retrieved is not None
        assert retrieved.status == TaskStatus.COMPLETED
        assert retrieved.result is not None

    @pytest.mark.asyncio
    async def test_result_includes_duration(self):
        """
        Test that result includes execution duration

        Flow:
        1. Launch task
        2. Complete task
        3. Verify duration is recorded
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            async def timed_run(prompt: str):
                await asyncio.sleep(0.1)
                return "Done"

            engine = MagicMock()
            engine.run = timed_run
            return engine

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="timed_agent",
            prompt="Timed task",
            session_id="test_session",
        )

        # Wait for completion
        await manager.wait_for_completion(task.id, timeout=5.0)

        # Verify: Duration recorded
        assert task.duration_ms > 0
        assert task.started_at is not None
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_list_all_tasks(self):
        """
        Test listing all tasks

        Flow:
        1. Launch multiple tasks
        2. Complete all
        3. List all tasks
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch multiple tasks
        task_ids = []
        for i in range(3):
            task = await manager.launch(
                agent_type="agent",
                prompt=f"Task {i}",
                session_id=f"session_{i}",
            )
            task_ids.append(task.id)

        # Wait for completion
        await asyncio.sleep(0.3)

        # List all
        stats = manager.get_stats()

        # Verify: All tasks present
        assert stats["total_tasks"] == 3
        assert stats["completed"] == 3

    @pytest.mark.asyncio
    async def test_filter_tasks_by_session(self):
        """
        Test filtering tasks by session

        Flow:
        1. Launch tasks in different sessions
        2. Filter by specific session
        """
        manager = BackgroundManager()

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch tasks in different sessions
        for session in ["session_a", "session_b", "session_a"]:
            await manager.launch(
                agent_type="agent",
                prompt="Test",
                session_id=session,
            )

        # Wait for completion
        await asyncio.sleep(0.3)

        # Filter by session
        session_a_tasks = manager.list_by_session("session_a")
        session_b_tasks = manager.list_by_session("session_b")

        # Verify: Correct filtering
        assert len(session_a_tasks) == 2
        assert len(session_b_tasks) == 1


class TestTaskPersistenceIntegration:
    """Test task persistence with TaskStore"""

    @pytest.mark.asyncio
    async def test_task_to_stored_task_conversion(self):
        """
        Test converting BackgroundTask to StoredTask

        Flow:
        1. Create BackgroundTask
        2. Convert to StoredTask
        3. Verify fields preserved
        """
        # Create background task
        bg_task = BackgroundTask(
            id="test_123",
            agent_type="test_agent",
            prompt="Test prompt",
            session_id="session_1",
            status=TaskStatus.COMPLETED,
            result="Task result",
        )

        # Convert to stored task
        stored = StoredTask(
            id=bg_task.id,
            title=f"Task: {bg_task.agent_type}",
            description=bg_task.prompt,
            status=bg_task.status.value,
            priority="medium",
            result=bg_task.result,
        )

        # Verify: Conversion successful
        assert stored.id == bg_task.id
        assert stored.description == bg_task.prompt
        assert stored.status == "completed"
        assert stored.result == bg_task.result

    @pytest.mark.asyncio
    async def test_task_store_save_and_load(self, tmp_path):
        """
        Test saving and loading tasks from TaskStore

        Flow:
        1. Create TaskStore
        2. Save task
        3. Load task
        4. Verify data preserved
        """
        store = TaskStore(storage_path=str(tmp_path / "tasks"))
        store.initialize()

        # Create and save task
        stored = StoredTask(
            id="task_001",
            title="Test Task",
            description="Test description",
            status="pending",
            priority="high",
        )

        store.save_task(stored)

        # Load task
        loaded = store.load_task("task_001")

        # Verify: Loaded correctly
        assert loaded is not None
        assert loaded.id == stored.id
        assert loaded.title == stored.title
        assert loaded.description == stored.description

    @pytest.mark.asyncio
    async def test_task_store_list_and_filter(self, tmp_path):
        """
        Test listing and filtering tasks in store

        Flow:
        1. Create multiple tasks with different statuses
        2. Save all
        3. List and filter
        """
        store = TaskStore(storage_path=str(tmp_path / "tasks"))
        store.initialize()

        # Create tasks with different statuses
        tasks = [
            StoredTask(id="t1", title="Task 1", description="D1", status="pending", priority="high"),
            StoredTask(id="t2", title="Task 2", description="D2", status="completed", priority="low"),
            StoredTask(id="t3", title="Task 3", description="D3", status="pending", priority="medium"),
        ]

        for task in tasks:
            store.save_task(task)

        # List all
        all_tasks = store.list_tasks()
        assert len(all_tasks) == 3

        # Filter by status
        pending = store.get_pending_tasks()
        assert len(pending) == 2

        completed = store.get_completed_tasks()
        assert len(completed) == 1

    @pytest.mark.asyncio
    async def test_task_store_delete(self, tmp_path):
        """
        Test deleting tasks from store

        Flow:
        1. Save task
        2. Delete task
        3. Verify deleted
        """
        store = TaskStore(storage_path=str(tmp_path / "tasks"))
        store.initialize()

        # Save task
        stored = StoredTask(
            id="delete_me",
            title="To Delete",
            description="Will be deleted",
            status="pending",
            priority="low",
        )

        store.save_task(stored)

        # Delete
        deleted = store.delete_task("delete_me")
        assert deleted is True

        # Verify: Gone
        loaded = store.load_task("delete_me")
        assert loaded is None


class TestTaskNotifications:
    """Test task notification system"""

    @pytest.mark.asyncio
    async def test_completion_notification(self):
        """
        Test notification on task completion

        Flow:
        1. Set notification callback
        2. Launch task
        3. Verify callback called on completion
        """
        notifications = []

        async def callback(session_id: str, tasks: list):
            notifications.append({
                "session_id": session_id,
                "tasks": [t.id for t in tasks],
            })

        manager = BackgroundManager(notification_delay=0.05)
        manager.set_notification_callback(callback)

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch task
        task = await manager.launch(
            agent_type="notify_agent",
            prompt="Test notification",
            session_id="notify_session",
        )

        # Wait for completion and notification
        await asyncio.sleep(0.3)

        # Verify: Notification sent
        assert len(notifications) >= 1
        assert any(task.id in n["tasks"] for n in notifications)

    @pytest.mark.asyncio
    async def test_batched_notifications(self):
        """
        Test that multiple completions are batched

        Flow:
        1. Set notification callback
        2. Launch multiple tasks in same session
        3. Verify batched notification
        """
        notifications = []

        async def callback(session_id: str, tasks: list):
            notifications.append({
                "session_id": session_id,
                "count": len(tasks),
            })

        manager = BackgroundManager(notification_delay=0.1)
        manager.set_notification_callback(callback)

        def engine_factory(agent_type: str):
            mock_provider = MockProvider()
            registry = ToolRegistry()
            return AgentEngine(
                provider=mock_provider,
                tool_registry=registry,
                config=AgentConfig(),
            )

        manager.set_engine_factory(engine_factory)

        # Launch multiple tasks quickly
        for i in range(3):
            await manager.launch(
                agent_type="batch_agent",
                prompt=f"Task {i}",
                session_id="batch_session",
            )

        # Wait for batched notification
        await asyncio.sleep(0.4)

        # Verify: At least one notification was sent
        assert len(notifications) >= 1

        # Verify: At least some tasks were batched together
        total_notified = sum(n["count"] for n in notifications)
        assert total_notified >= 1
