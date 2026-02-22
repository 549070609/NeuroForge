"""
Test Task System Enhancements

Quick verification script for all phases.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from pyagentforge.plugins.integration.task_system.PLUGIN import (
    TaskManager,
    TaskStatus,
    TaskPriority,
    TaskType,
    TaskComplexity,
)
from pyagentforge.plugins.integration.task_system.storage import (
    InMemoryStorage,
    FileStorage,
    create_storage,
)
from pyagentforge.plugins.integration.task_system.reporter import TaskReporter


def test_phase1_data_model():
    """Test Phase 1: Enhanced data model"""
    print("\n=== Phase 1: Data Model ===")

    manager = TaskManager()

    # Test 1: Create task with all new fields
    task = manager.create_task(
        title="Implement Feature X",
        description="Add new feature to system",
        priority=TaskPriority.HIGH,
        task_type=TaskType.IMPLEMENTATION,
        complexity=TaskComplexity.COMPLEX,
        estimated_hours=16.0,
    )

    assert task.progress == 0.0
    assert task.task_type == TaskType.IMPLEMENTATION
    assert task.complexity == TaskComplexity.COMPLEX
    assert task.estimated_hours == 16.0
    print("✓ Task created with new fields")

    # Test 2: Create subtask
    subtask = manager.create_subtask(
        parent_id=task.id,
        title="Design API",
        description="Design REST API endpoints",
    )

    assert subtask.parent_id == task.id
    assert subtask.level == 1
    assert task.id in manager.get_task(task.id).subtasks
    print("✓ Subtask created")

    # Test 3: Max nesting depth
    subtask2 = manager.create_subtask(
        parent_id=subtask.id,
        title="Write API Spec",
        description="Write OpenAPI specification",
    )
    assert subtask2.level == 2

    try:
        manager.create_subtask(
            parent_id=subtask2.id,
            title="Too Deep",
            description="Should fail",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Maximum nesting depth" in str(e)
        print("✓ Max nesting depth enforced (3 levels)")

    # Test 4: Update progress
    manager.update_progress(subtask.id, 0.5)
    assert manager.get_task(subtask.id).progress == 0.5
    print("✓ Progress updated")

    # Test 5: Get task tree
    tree = manager.get_task_tree(task.id)
    assert tree["task"].id == task.id
    assert len(tree["subtrees"]) == 1
    print("✓ Task tree structure correct")


def test_phase2_storage():
    """Test Phase 2: Persistence storage"""
    print("\n=== Phase 2: Storage ===")

    # Test 1: InMemoryStorage
    storage = InMemoryStorage()
    manager = TaskManager(storage=storage)

    task1 = manager.create_task(
        title="Test Task 1",
        description="Test description",
        task_type=TaskType.BUG_FIX,
    )

    # Load from storage
    loaded = storage.load(task1.id)
    assert loaded is not None
    assert loaded.title == task1.title
    print("✓ InMemoryStorage works")

    # Test 2: FileStorage
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        file_storage = create_storage("file", Path(tmpdir))
        manager2 = TaskManager(storage=file_storage)

        task2 = manager2.create_task(
            title="Persistent Task",
            description="This should persist",
            complexity=TaskComplexity.SIMPLE,
        )

        # Verify file exists
        task_file = Path(tmpdir) / f"{task2.id}.json"
        assert task_file.exists()
        print("✓ FileStorage creates files")

        # Create new manager to test loading
        manager3 = TaskManager(storage=file_storage)
        assert len(manager3._tasks) >= 1
        loaded_task = manager3.get_task(task2.id)
        assert loaded_task is not None
        assert loaded_task.title == "Persistent Task"
        print("✓ FileStorage loads on startup")


def test_phase3_reports():
    """Test Phase 3: Progress reports"""
    print("\n=== Phase 3: Reports ===")

    manager = TaskManager()

    # Create test tasks
    task1 = manager.create_task(
        title="Main Task",
        description="Main task with subtasks",
        task_type=TaskType.IMPLEMENTATION,
        complexity=TaskComplexity.COMPLEX,
    )

    task2 = manager.create_subtask(
        parent_id=task1.id,
        title="Subtask 1",
        description="First subtask",
        complexity=TaskComplexity.SIMPLE,
    )

    task3 = manager.create_subtask(
        parent_id=task1.id,
        title="Subtask 2",
        description="Second subtask",
        complexity=TaskComplexity.SIMPLE,
    )

    # Update progress
    manager.update_progress(task2.id, 0.8)
    manager.update_progress(task3.id, 0.6)

    reporter = TaskReporter(manager)

    # Test 1: Progress report
    report = reporter.generate_progress_report(task1.id)
    assert report is not None
    assert report.task.id == task1.id
    assert len(report.subtasks_progress) == 2
    assert report.progress_percentage >= 0
    print("✓ Progress report generated")

    # Test 2: Format report
    markdown = reporter.format_report(report, format="markdown")
    assert "Main Task" in markdown
    assert "Progress:" in markdown
    print("✓ Markdown formatting works")

    json_report = reporter.format_report(report, format="json")
    assert '"task_id"' in json_report
    print("✓ JSON formatting works")

    # Test 3: Summary report
    summary = reporter.generate_summary_report()
    assert summary.total_tasks == 3
    assert summary.by_type.get("implementation", 0) == 3
    print("✓ Summary report generated")

    # Test 4: Format summary
    summary_md = reporter.format_summary(summary, format="markdown")
    assert "Total Tasks" in summary_md
    assert "By Type" in summary_md
    print("✓ Summary formatting works")


def test_phase4_integration():
    """Test Phase 4: Agent integration"""
    print("\n=== Phase 4: Integration ===")

    manager = TaskManager()

    # Test 1: Parent progress auto-calculation
    parent = manager.create_task(
        title="Parent Task",
        description="Parent with auto-progress",
    )

    child1 = manager.create_subtask(
        parent_id=parent.id,
        title="Child 1",
        description="First child",
    )

    child2 = manager.create_subtask(
        parent_id=parent.id,
        title="Child 2",
        description="Second child",
    )

    # Update child progress
    manager.update_progress(child1.id, 1.0)  # 100%
    manager.update_progress(child2.id, 0.5)  # 50%

    # Check parent auto-updated
    parent_updated = manager.get_task(parent.id)
    # Average: (1.0 + 0.5) / 2 = 0.75
    assert abs(parent_updated.progress - 0.75) < 0.01
    print("✓ Parent progress auto-calculated (0.75)")

    # Test 2: Background correlation (mock)
    from dataclasses import dataclass

    @dataclass
    class MockBackgroundTask:
        id: str
        task_id: str | None = None

    bg_task = MockBackgroundTask(id="bg-123")
    task_from_bg = manager.create_from_background(
        background_task=bg_task,
        title="From Background",
        description="Created from background task",
    )

    assert task_from_bg.background_task_id == "bg-123"
    assert bg_task.task_id == task_from_bg.id
    print("✓ Background correlation works")

    print("\n=== All Tests Passed! ===\n")


if __name__ == "__main__":
    try:
        test_phase1_data_model()
        test_phase2_storage()
        test_phase3_reports()
        test_phase4_integration()

        print("\n✅ All phases implemented successfully!\n")

    except Exception as e:
        print(f"\n❌ Test failed: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
