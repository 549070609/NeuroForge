"""
Task Storage Abstraction Layer

Provides storage backends for task persistence.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import json

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TaskStorage(ABC):
    """Abstract storage interface"""

    @abstractmethod
    def save(self, task: Any) -> None:
        """Save a task"""
        pass

    @abstractmethod
    def load(self, task_id: str) -> Any | None:
        """Load a task by ID"""
        pass

    @abstractmethod
    def load_all(self) -> list[Any]:
        """Load all tasks"""
        pass

    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Delete a task"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all tasks"""
        pass


class InMemoryStorage(TaskStorage):
    """In-memory storage implementation"""

    def __init__(self):
        self._tasks: dict[str, Any] = {}

    def save(self, task: Any) -> None:
        """Save task to memory"""
        self._tasks[task.id] = task
        logger.debug(f"Saved task {task.id} to memory")

    def load(self, task_id: str) -> Any | None:
        """Load task from memory"""
        return self._tasks.get(task_id)

    def load_all(self) -> list[Any]:
        """Load all tasks from memory"""
        return list(self._tasks.values())

    def delete(self, task_id: str) -> bool:
        """Delete task from memory"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.debug(f"Deleted task {task_id} from memory")
            return True
        return False

    def clear(self) -> None:
        """Clear all tasks from memory"""
        self._tasks.clear()
        logger.debug("Cleared all tasks from memory")


class FileStorage(TaskStorage):
    """File-based storage with atomic writes"""

    def __init__(self, storage_path: Path):
        """
        Initialize file storage

        Args:
            storage_path: Directory path for storing task files
        """
        self._storage_path = storage_path
        self._storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized FileStorage at {storage_path}")

    def _get_task_file(self, task_id: str) -> Path:
        """Get the file path for a task"""
        return self._storage_path / f"{task_id}.json"

    def save(self, task: Any) -> None:
        """
        Save task to file with atomic write

        Args:
            task: Task object with to_dict() method
        """
        file_path = self._get_task_file(task.id)
        temp_path = file_path.with_suffix(".tmp")

        try:
            # Atomic write: write to temp, then rename
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(task.to_dict(), f, indent=2, ensure_ascii=False)

            # Rename is atomic on most filesystems
            temp_path.rename(file_path)
            logger.debug(f"Saved task {task.id} to {file_path}")

        except Exception as e:
            logger.error(f"Failed to save task {task.id}: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise

    def load(self, task_id: str) -> Any | None:
        """
        Load task from file

        Args:
            task_id: Task ID to load

        Returns:
            Task object or None if not found
        """
        file_path = self._get_task_file(task_id)

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Import here to avoid circular dependency
            from .PLUGIN import Task

            task = Task.from_dict(data)
            logger.debug(f"Loaded task {task_id} from {file_path}")
            return task

        except Exception as e:
            logger.error(f"Failed to load task {task_id}: {e}")
            return None

    def load_all(self) -> list[Any]:
        """
        Load all tasks from storage

        Returns:
            List of Task objects
        """
        tasks = []

        for file_path in self._storage_path.glob("*.json"):
            if file_path.stem == "index":
                continue

            task = self.load(file_path.stem)
            if task:
                tasks.append(task)

        logger.debug(f"Loaded {len(tasks)} tasks from storage")
        return tasks

    def delete(self, task_id: str) -> bool:
        """
        Delete task file

        Args:
            task_id: Task ID to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self._get_task_file(task_id)

        if file_path.exists():
            try:
                file_path.unlink()
                logger.debug(f"Deleted task file {file_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete task {task_id}: {e}")
                return False

        return False

    def clear(self) -> None:
        """Clear all task files"""
        count = 0
        for file_path in self._storage_path.glob("*.json"):
            try:
                file_path.unlink()
                count += 1
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

        logger.debug(f"Cleared {count} task files from storage")


# Convenience factory function
def create_storage(storage_type: str = "memory", storage_path: Path | None = None) -> TaskStorage:
    """
    Create storage instance

    Args:
        storage_type: "memory" or "file"
        storage_path: Path for file storage (required if storage_type="file")

    Returns:
        TaskStorage instance

    Raises:
        ValueError: If storage_type is invalid or storage_path missing for file storage
    """
    if storage_type == "memory":
        return InMemoryStorage()
    elif storage_type == "file":
        if not storage_path:
            raise ValueError("storage_path required for file storage")
        return FileStorage(storage_path)
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
