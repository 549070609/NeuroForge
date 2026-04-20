"""
Task Store

Persistent storage for tasks.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class StoredTask:
    """Stored task data"""

    id: str
    title: str
    description: str
    status: str  # pending, in_progress, completed, cancelled
    priority: str  # low, medium, high, urgent
    blocked_by: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    result: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoredTask":
        """Create from dictionary"""
        return cls(**data)

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "StoredTask":
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)


class TaskStore:
    """
    Task Store

    Provides persistent storage for tasks using JSON files.
    """

    def __init__(self, storage_path: str = ".agent/tasks"):
        """
        Initialize task store

        Args:
            storage_path: Directory to store task files
        """
        self.storage_path = Path(storage_path)
        self._initialized = False

    def initialize(self) -> None:
        """Initialize storage directory"""
        if self._initialized:
            return

        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._initialized = True
            logger.info(f"Task store initialized at {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to initialize task store: {e}")
            raise

    def _ensure_initialized(self) -> None:
        """Ensure store is initialized"""
        if not self._initialized:
            self.initialize()

    def _get_task_path(self, task_id: str) -> Path:
        """Get path to task file"""
        return self.storage_path / f"{task_id}.json"

    def save_task(self, task: StoredTask) -> str:
        """
        Save a task to storage

        Args:
            task: Task to save

        Returns:
            Task ID
        """
        self._ensure_initialized()

        task_path = self._get_task_path(task.id)

        try:
            with open(task_path, "w", encoding="utf-8") as f:
                f.write(task.to_json())

            logger.debug(f"Saved task {task.id} to {task_path}")
            return task.id

        except Exception as e:
            logger.error(f"Failed to save task {task.id}: {e}")
            raise

    def load_task(self, task_id: str) -> StoredTask | None:
        """
        Load a task from storage

        Args:
            task_id: Task ID to load

        Returns:
            StoredTask or None if not found
        """
        self._ensure_initialized()

        task_path = self._get_task_path(task_id)

        if not task_path.exists():
            logger.debug(f"Task {task_id} not found")
            return None

        try:
            with open(task_path, encoding="utf-8") as f:
                content = f.read()

            return StoredTask.from_json(content)

        except Exception as e:
            logger.error(f"Failed to load task {task_id}: {e}")
            return None

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task from storage

        Args:
            task_id: Task ID to delete

        Returns:
            True if deleted, False if not found
        """
        self._ensure_initialized()

        task_path = self._get_task_path(task_id)

        if not task_path.exists():
            return False

        try:
            task_path.unlink()
            logger.debug(f"Deleted task {task_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete task {task_id}: {e}")
            return False

    def list_tasks(self) -> list[StoredTask]:
        """
        List all stored tasks

        Returns:
            List of all tasks
        """
        self._ensure_initialized()

        tasks = []

        try:
            for task_file in self.storage_path.glob("*.json"):
                try:
                    with open(task_file, encoding="utf-8") as f:
                        task = StoredTask.from_json(f.read())
                    tasks.append(task)
                except Exception as e:
                    logger.warning(f"Failed to load task from {task_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")

        return tasks

    def get_tasks_by_status(self, status: str) -> list[StoredTask]:
        """
        Get tasks by status

        Args:
            status: Status to filter by

        Returns:
            List of matching tasks
        """
        tasks = self.list_tasks()
        return [t for t in tasks if t.status == status]

    def get_pending_tasks(self) -> list[StoredTask]:
        """Get all pending tasks"""
        return self.get_tasks_by_status("pending")

    def get_in_progress_tasks(self) -> list[StoredTask]:
        """Get all in-progress tasks"""
        return self.get_tasks_by_status("in_progress")

    def get_completed_tasks(self) -> list[StoredTask]:
        """Get all completed tasks"""
        return self.get_tasks_by_status("completed")

    def cleanup_completed(self, days_old: int = 7) -> int:
        """
        Clean up completed tasks older than specified days

        Args:
            days_old: Delete tasks completed more than this many days ago

        Returns:
            Number of tasks deleted
        """
        self._ensure_initialized()

        deleted = 0
        cutoff = datetime.now(UTC)

        # Load all completed tasks
        for task in self.get_completed_tasks():
            if not task.completed_at:
                continue

            try:
                completed_date = datetime.fromisoformat(task.completed_at.replace("Z", "+00:00"))
                age_days = (cutoff - completed_date).days

                if age_days > days_old and self.delete_task(task.id):
                    deleted += 1

            except Exception as e:
                logger.warning(f"Failed to check age of task {task.id}: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} completed tasks older than {days_old} days")

        return deleted

    def get_stats(self) -> dict[str, Any]:
        """
        Get storage statistics

        Returns:
            Statistics dictionary
        """
        tasks = self.list_tasks()

        status_counts = {}
        priority_counts = {}

        for task in tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1
            priority_counts[task.priority] = priority_counts.get(task.priority, 0) + 1

        return {
            "total_tasks": len(tasks),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "storage_path": str(self.storage_path),
        }

    def export_all(self) -> str:
        """
        Export all tasks as JSON

        Returns:
            JSON string of all tasks
        """
        tasks = self.list_tasks()
        return json.dumps([t.to_dict() for t in tasks], indent=2)

    def import_tasks(self, json_data: str) -> int:
        """
        Import tasks from JSON

        Args:
            json_data: JSON string of tasks

        Returns:
            Number of tasks imported
        """
        try:
            tasks_data = json.loads(json_data)
            imported = 0

            for task_data in tasks_data:
                task = StoredTask.from_dict(task_data)
                self.save_task(task)
                imported += 1

            logger.info(f"Imported {imported} tasks")
            return imported

        except Exception as e:
            logger.error(f"Failed to import tasks: {e}")
            return 0
