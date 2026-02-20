"""
Simple verification of Task System enhancements
"""

print("Testing Task System...")

# Test imports
try:
    from pyagentforge.plugins.integration.task_system import PLUGIN
    print("✓ PLUGIN module imported")
except Exception as e:
    print(f"✗ Failed to import PLUGIN: {e}")
    exit(1)

try:
    from pyagentforge.plugins.integration.task_system import storage
    print("✓ Storage module imported")
except Exception as e:
    print(f"✗ Failed to import storage: {e}")
    exit(1)

try:
    from pyagentforge.plugins.integration.task_system import reporter
    print("✓ Reporter module imported")
except Exception as e:
    print(f"✗ Failed to import reporter: {e}")
    exit(1)

# Test basic functionality
try:
    manager = PLUGIN.TaskManager()
    print("✓ TaskManager created")
except Exception as e:
    print(f"✗ Failed to create TaskManager: {e}")
    exit(1)

try:
    task = manager.create_task(
        title="Test Task",
        description="Testing new features",
        task_type=PLUGIN.TaskType.IMPLEMENTATION,
        complexity=PLUGIN.TaskComplexity.MODERATE,
    )
    print(f"✓ Task created with ID: {task.id}")
    print(f"  - Type: {task.task_type.value}")
    print(f"  - Complexity: {task.complexity.value}")
    print(f"  - Progress: {task.progress}")
except Exception as e:
    print(f"✗ Failed to create task: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

try:
    subtask = manager.create_subtask(
        parent_id=task.id,
        title="Subtask",
        description="Testing subtasks"
    )
    print(f"✓ Subtask created with ID: {subtask.id}")
    print(f"  - Parent: {subtask.parent_id}")
    print(f"  - Level: {subtask.level}")
except Exception as e:
    print(f"✗ Failed to create subtask: {e}")
    exit(1)

try:
    manager.update_progress(subtask.id, 0.5)
    updated = manager.get_task(subtask.id)
    print(f"✓ Progress updated to {updated.progress}")
except Exception as e:
    print(f"✗ Failed to update progress: {e}")
    exit(1)

print("\n✅ All basic tests passed!")
