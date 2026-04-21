"""
Tests for Task Management System
"""


import pytest

from pyagentforge.plugins.integration.task_system import (
    Task,
    TaskManagementPlugin,
    TaskManager,
    TaskPriority,
    TaskStatus,
)


class TestTask:
    """Tests for Task dataclass"""

    def test_task_creation(self):
        """Test basic task creation"""
        task = Task(
            id="test-1",
            title="Test Task",
            description="A test task",
        )

        assert task.id == "test-1"
        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM
        assert task.blockedBy == []
        assert task.blocks == []

    def test_task_to_dict(self):
        """Test task serialization"""
        task = Task(
            id="test-1",
            title="Test Task",
            description="A test task",
            priority=TaskPriority.HIGH,
        )

        data = task.to_dict()

        assert data["id"] == "test-1"
        assert data["title"] == "Test Task"
        assert data["status"] == "pending"
        assert data["priority"] == "high"


class TestTaskManager:
    """Tests for TaskManager"""

    def test_create_task(self):
        """Test task creation"""
        manager = TaskManager()

        task = manager.create_task(
            title="Test Task",
            description="A test task",
        )

        assert task.id is not None
        assert task.title == "Test Task"
        assert task.status == TaskStatus.PENDING

    def test_create_task_with_priority(self):
        """Test task creation with priority"""
        manager = TaskManager()

        task = manager.create_task(
            title="Urgent Task",
            description="An urgent task",
            priority=TaskPriority.URGENT,
        )

        assert task.priority == TaskPriority.URGENT

    def test_create_task_with_dependencies(self):
        """Test task creation with dependencies"""
        manager = TaskManager()

        # Create dependency task
        dep_task = manager.create_task(
            title="Dependency",
            description="A dependency",
        )

        # Create task with dependency
        task = manager.create_task(
            title="Main Task",
            description="Main task",
            blocked_by=[dep_task.id],
        )

        assert task.blockedBy == [dep_task.id]
        assert dep_task.blocks == [task.id]

    def test_get_task(self):
        """Test task retrieval"""
        manager = TaskManager()

        created = manager.create_task(
            title="Test Task",
            description="A test task",
        )

        retrieved = manager.get_task(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id

    def test_list_tasks(self):
        """Test task listing"""
        manager = TaskManager()

        manager.create_task("Task 1", "First task")
        manager.create_task("Task 2", "Second task", priority=TaskPriority.HIGH)

        tasks = manager.list_tasks()

        assert len(tasks) == 2

        # High priority should come first
        assert tasks[0].priority == TaskPriority.HIGH

    def test_list_tasks_with_filter(self):
        """Test task listing with status filter"""
        manager = TaskManager()

        task1 = manager.create_task("Task 1", "First task")
        task2 = manager.create_task("Task 2", "Second task")

        manager.update_task(task1.id, status=TaskStatus.COMPLETED)

        pending = manager.list_tasks(status=TaskStatus.PENDING)

        assert len(pending) == 1
        assert pending[0].id == task2.id

    def test_update_task_status(self):
        """Test task status update"""
        manager = TaskManager()

        task = manager.create_task("Test Task", "A test task")

        updated = manager.update_task(task.id, status=TaskStatus.IN_PROGRESS)

        assert updated is not None
        assert updated.status == TaskStatus.IN_PROGRESS

    def test_update_task_priority(self):
        """Test task priority update"""
        manager = TaskManager()

        task = manager.create_task("Test Task", "A test task")

        updated = manager.update_task(task.id, priority=TaskPriority.URGENT)

        assert updated is not None
        assert updated.priority == TaskPriority.URGENT

    def test_complete_task_sets_timestamp(self):
        """Test that completing task sets completed_at"""
        manager = TaskManager()

        task = manager.create_task("Test Task", "A test task")

        updated = manager.update_task(task.id, status=TaskStatus.COMPLETED)

        assert updated is not None
        assert updated.completed_at is not None

    def test_get_ready_tasks(self):
        """Test getting ready tasks (dependencies complete)"""
        manager = TaskManager()

        # Create dependency chain: task1 -> task2 -> task3
        task1 = manager.create_task("Task 1", "First")
        task2 = manager.create_task("Task 2", "Second", blocked_by=[task1.id])
        task3 = manager.create_task("Task 3", "Third", blocked_by=[task2.id])

        # Initially only task1 is ready
        ready = manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == task1.id

        # Complete task1
        manager.update_task(task1.id, status=TaskStatus.COMPLETED)

        # Now task2 is ready
        ready = manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == task2.id

        # Complete task2
        manager.update_task(task2.id, status=TaskStatus.COMPLETED)

        # Now task3 is ready
        ready = manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == task3.id


class TestTaskManagementPlugin:
    """Tests for TaskManagementPlugin"""

    @pytest.mark.asyncio
    async def test_plugin_activation(self):
        """Test plugin activation"""
        plugin = TaskManagementPlugin()

        await plugin.on_activate()

        # Should have registered 6 tools
        tools = plugin.get_tools()
        assert len(tools) == 6

    @pytest.mark.asyncio
    async def test_plugin_context(self):
        """Test plugin context"""
        plugin = TaskManagementPlugin()

        context = plugin.get_context()

        assert "task_manager" in context
        assert isinstance(context["task_manager"], TaskManager)
