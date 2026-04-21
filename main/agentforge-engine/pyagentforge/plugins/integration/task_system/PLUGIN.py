"""
Task Management System Plugin

v4.0: 任务管理系统

提供任务创建、查询、列表和更新功能。
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pyagentforge.plugin.base import Plugin as BasePlugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(StrEnum):
    """任务状态"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    """任务优先级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskType(StrEnum):
    """任务类型"""

    EXPLORATION = "exploration"
    IMPLEMENTATION = "implementation"
    BUG_FIX = "bug_fix"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    REVIEW = "review"
    RESEARCH = "research"


class TaskComplexity(StrEnum):
    """任务复杂度"""

    TRIVIAL = "trivial"  # < 30 min
    SIMPLE = "simple"  # 30 min - 2 hours
    MODERATE = "moderate"  # 2-8 hours
    COMPLEX = "complex"  # 1-3 days
    EPIC = "epic"  # > 3 days


@dataclass
class Task:
    """任务定义"""

    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    progress: float = 0.0  # 0.0 to 1.0
    progress_updated_at: str | None = None
    parent_id: str | None = None
    subtasks: list[str] = field(default_factory=list)
    level: int = 0  # 0 = top-level, max 2 for 3 levels total
    task_type: TaskType = TaskType.IMPLEMENTATION
    complexity: TaskComplexity = TaskComplexity.MODERATE
    estimated_hours: float | None = None
    actual_hours: float | None = None
    background_task_id: str | None = None
    blockedBy: list[str] = field(default_factory=list)  # 依赖任务
    blocks: list[str] = field(default_factory=list)  # 被依赖任务
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress": self.progress,
            "progress_updated_at": self.progress_updated_at,
            "parent_id": self.parent_id,
            "subtasks": self.subtasks,
            "level": self.level,
            "task_type": self.task_type.value,
            "complexity": self.complexity.value,
            "estimated_hours": self.estimated_hours,
            "actual_hours": self.actual_hours,
            "background_task_id": self.background_task_id,
            "blockedBy": self.blockedBy,
            "blocks": self.blocks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """从字典重构 Task"""
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", "medium")),
            progress=data.get("progress", 0.0),
            progress_updated_at=data.get("progress_updated_at"),
            parent_id=data.get("parent_id"),
            subtasks=data.get("subtasks", []),
            level=data.get("level", 0),
            task_type=TaskType(data.get("task_type", "implementation")),
            complexity=TaskComplexity(data.get("complexity", "moderate")),
            estimated_hours=data.get("estimated_hours"),
            actual_hours=data.get("actual_hours"),
            background_task_id=data.get("background_task_id"),
            blockedBy=data.get("blockedBy", []),
            blocks=data.get("blocks", []),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            updated_at=data.get("updated_at", datetime.now(UTC).isoformat()),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
        )


class TaskManager:
    """任务管理器"""

    def __init__(self, storage: Any | None = None):
        """
        初始化任务管理器

        Args:
            storage: 存储后端（None 使用内存存储）
        """
        from .storage import InMemoryStorage

        self._storage = storage or InMemoryStorage()
        self._tasks: dict[str, Task] = {}
        self.hook_registry: Any = None  # Will be set by Phase 4

        # Load existing tasks from storage
        for task in self._storage.load_all():
            self._tasks[task.id] = task

        logger.info(f"TaskManager initialized with {len(self._tasks)} existing tasks")

    def create_task(
        self,
        title: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        task_type: TaskType = TaskType.IMPLEMENTATION,
        complexity: TaskComplexity = TaskComplexity.MODERATE,
        estimated_hours: float | None = None,
        parent_id: str | None = None,
        background_task_id: str | None = None,
        blocked_by: list[str] | None = None,
    ) -> Task:
        """
        创建任务

        Args:
            title: 任务标题
            description: 任务描述
            priority: 优先级
            task_type: 任务类型
            complexity: 复杂度
            estimated_hours: 预估时间（小时）
            parent_id: 父任务 ID（用于子任务）
            background_task_id: 关联的后台任务 ID
            blocked_by: 依赖任务 ID 列表

        Returns:
            创建的任务
        """
        task_id = str(uuid.uuid4())[:8]

        # 确定层级
        level = 0
        if parent_id:
            parent = self._tasks.get(parent_id)
            if parent:
                level = parent.level + 1
                if level > 2:
                    raise ValueError("Maximum nesting depth reached (max 3 levels)")

        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            task_type=task_type,
            complexity=complexity,
            estimated_hours=estimated_hours,
            parent_id=parent_id,
            level=level,
            background_task_id=background_task_id,
            blockedBy=blocked_by or [],
        )

        self._tasks[task_id] = task

        # 更新父任务的子任务列表
        if parent_id:
            parent = self._tasks.get(parent_id)
            if parent and task_id not in parent.subtasks:
                parent.subtasks.append(task_id)

        # 更新依赖关系
        for dep_id in task.blockedBy:
            dep_task = self._tasks.get(dep_id)
            if dep_task and task_id not in dep_task.blocks:
                dep_task.blocks.append(task_id)

        # 持久化（Phase 2 会实现）
        if self._storage:
            self._storage.save(task)

        logger.info(f"Created task {task_id}: {title}")

        # Phase 4: 发送钩子
        if self.hook_registry:
            try:
                import asyncio

                # 尝试获取事件循环
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 在运行中的事件循环中，创建任务
                        asyncio.create_task(
                            self.hook_registry.emit(
                                HookType.ON_TASK_CREATED, task=task
                            )
                        )
                    else:
                        # 事件循环未运行，直接运行
                        loop.run_until_complete(
                            self.hook_registry.emit(HookType.ON_TASK_CREATED, task=task)
                        )
                except RuntimeError:
                    # 没有事件循环，同步调用
                    pass
            except Exception as e:
                logger.warning(f"Failed to emit ON_TASK_CREATED hook: {e}")

        return task

    def create_subtask(
        self,
        parent_id: str,
        title: str,
        description: str,
        priority: TaskPriority | None = None,
        task_type: TaskType | None = None,
        complexity: TaskComplexity | None = None,
        **kwargs: Any,
    ) -> Task | None:
        """
        创建子任务

        Args:
            parent_id: 父任务 ID
            title: 任务标题
            description: 任务描述
            priority: 优先级（默认继承父任务）
            task_type: 任务类型（默认继承父任务）
            complexity: 复杂度（默认继承父任务）
            **kwargs: 其他参数

        Returns:
            创建的子任务，如果父任务不存在则返回 None
        """
        parent = self.get_task(parent_id)
        if not parent:
            return None

        # 继承父任务属性
        if priority is None:
            priority = parent.priority
        if task_type is None:
            task_type = parent.task_type
        if complexity is None:
            complexity = parent.complexity

        return self.create_task(
            title=title,
            description=description,
            priority=priority,
            task_type=task_type,
            complexity=complexity,
            parent_id=parent_id,
            **kwargs,
        )

    def get_subtasks(self, task_id: str) -> list[Task]:
        """获取所有直接子任务"""
        task = self.get_task(task_id)
        if not task:
            return []
        return [self.get_task(sid) for sid in task.subtasks if self.get_task(sid)]

    def get_task_tree(self, task_id: str) -> dict[str, Any]:
        """获取完整任务树"""
        task = self.get_task(task_id)
        if not task:
            return {}

        return {
            "task": task,
            "subtrees": [self.get_task_tree(sid) for sid in task.subtasks],
        }

    def update_progress(self, task_id: str, progress: float) -> Task | None:
        """
        更新任务进度

        Args:
            task_id: 任务 ID
            progress: 进度值（0.0 到 1.0）

        Returns:
            更新后的任务
        """
        task = self.get_task(task_id)
        if not task:
            return None

        old_progress = task.progress
        task.progress = max(0.0, min(1.0, progress))
        task.progress_updated_at = datetime.now(UTC).isoformat()
        task.updated_at = task.progress_updated_at

        # 持久化
        if self._storage:
            self._storage.save(task)

        logger.info(f"Updated task {task_id} progress: {old_progress:.2f} -> {task.progress:.2f}")

        # Phase 4: 发送钩子
        if self.hook_registry:
            try:
                import asyncio

                # 尝试获取事件循环
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(
                            self.hook_registry.emit(
                                HookType.ON_TASK_PROGRESS,
                                task=task,
                                progress_delta=progress - old_progress,
                            )
                        )
                    else:
                        loop.run_until_complete(
                            self.hook_registry.emit(
                                HookType.ON_TASK_PROGRESS,
                                task=task,
                                progress_delta=progress - old_progress,
                            )
                        )
                except RuntimeError:
                    pass
            except Exception as e:
                logger.warning(f"Failed to emit ON_TASK_PROGRESS hook: {e}")

        # 自动更新父任务进度
        if task.parent_id:
            self._update_parent_progress(task.parent_id)

        return task

    def _update_parent_progress(self, parent_id: str) -> None:
        """
        递归更新父任务进度（基于子任务平均值）

        Args:
            parent_id: 父任务 ID
        """
        parent = self.get_task(parent_id)
        if not parent:
            return

        subtasks = self.get_subtasks(parent_id)
        if not subtasks:
            return

        # 计算平均进度
        avg_progress = sum(s.progress for s in subtasks) / len(subtasks)

        # 更新父任务（避免无限递归）
        if abs(parent.progress - avg_progress) > 0.001:
            parent.progress = avg_progress
            parent.progress_updated_at = datetime.now(UTC).isoformat()

            if self._storage:
                self._storage.save(parent)

            logger.debug(
                f"Auto-updated parent task {parent_id} progress: {avg_progress:.2f}"
            )

            # 发送钩子
            if self.hook_registry:
                try:
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(
                                self.hook_registry.emit(
                                    HookType.ON_TASK_PROGRESS,
                                    task=parent,
                                    progress_delta=avg_progress - parent.progress,
                                    auto_calculated=True,
                                )
                            )
                    except RuntimeError:
                        pass
                except Exception as e:
                    logger.warning(f"Failed to emit ON_TASK_PROGRESS hook for parent: {e}")

            # 递归更新祖父任务
            if parent.parent_id:
                self._update_parent_progress(parent.parent_id)

    def create_from_background(
        self,
        background_task: Any,
        title: str,
        description: str,
        **kwargs: Any,
    ) -> Task:
        """
        从 BackgroundTask 创建 Task

        Args:
            background_task: BackgroundTask 实例
            title: 任务标题
            description: 任务描述
            **kwargs: 其他参数

        Returns:
            创建的 Task
        """
        task = self.create_task(
            title=title,
            description=description,
            background_task_id=background_task.id,
            **kwargs,
        )

        # 双向关联
        background_task.task_id = task.id

        logger.info(f"Created task {task.id} from background task {background_task.id}")

        return task

    def sync_with_background(self, task_id: str, background_manager: Any) -> None:
        """
        同步 Task 状态与 BackgroundTask

        Args:
            task_id: Task ID
            background_manager: BackgroundManager 实例
        """
        task = self.get_task(task_id)
        if not task or not task.background_task_id:
            return

        # 获取 BackgroundTask
        bg_task = background_manager.get_task(task.background_task_id)
        if not bg_task:
            logger.warning(f"BackgroundTask {task.background_task_id} not found")
            return

        # 同步状态
        from pyagentforge.kernel.background_manager import TaskStatus as BGTaskStatus

        status_mapping = {
            BGTaskStatus.PENDING: TaskStatus.PENDING,
            BGTaskStatus.RUNNING: TaskStatus.IN_PROGRESS,
            BGTaskStatus.COMPLETED: TaskStatus.COMPLETED,
            BGTaskStatus.FAILED: TaskStatus.CANCELLED,  # 或自定义失败状态
            BGTaskStatus.CANCELLED: TaskStatus.CANCELLED,
        }

        new_status = status_mapping.get(bg_task.status)
        if new_status and task.status != new_status:
            task.status = new_status
            task.updated_at = datetime.now(UTC).isoformat()

            if new_status == TaskStatus.COMPLETED:
                task.completed_at = bg_task.completed_at
                task.progress = 1.0

            if self._storage:
                self._storage.save(task)

            logger.info(
                f"Synced task {task_id} status with background task: {new_status.value}"
            )

    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(
        self,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
    ) -> list[Task]:
        """
        列出任务

        Args:
            status: 状态过滤
            priority: 优先级过滤

        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        if priority:
            tasks = [t for t in tasks if t.priority == priority]

        # 按优先级和创建时间排序
        priority_order = {
            TaskPriority.URGENT: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
        }

        tasks.sort(key=lambda t: (priority_order[t.priority], t.created_at))

        return tasks

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        progress: float | None = None,
    ) -> Task | None:
        """
        更新任务

        Args:
            task_id: 任务 ID
            status: 新状态
            priority: 新优先级
            progress: 新进度（0.0 到 1.0）

        Returns:
            更新后的任务
        """
        task = self._tasks.get(task_id)

        if not task:
            return None

        if status:
            task.status = status

            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.now(UTC).isoformat()
                if task.progress < 1.0:
                    task.progress = 1.0

        if priority:
            task.priority = priority

        if progress is not None:
            task.progress = max(0.0, min(1.0, progress))
            task.progress_updated_at = datetime.now(UTC).isoformat()

        task.updated_at = datetime.now(UTC).isoformat()

        # 持久化
        if self._storage:
            self._storage.save(task)

        logger.info(f"Updated task {task_id}: status={status}, priority={priority}, progress={progress}")

        return task

    def get_ready_tasks(self) -> list[Task]:
        """
        获取准备执行的任务（依赖已完成）

        Returns:
            可执行的任务列表
        """
        ready = []

        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            # 检查依赖
            all_deps_complete = all(
                self._tasks.get(dep_id, Task(id="", title="", description="")).status
                == TaskStatus.COMPLETED
                for dep_id in task.blockedBy
            )

            if all_deps_complete:
                ready.append(task)

        return ready


class TaskCreateTool(BaseTool):
    """创建任务工具"""

    name = "task_create"
    description = "Create a new task with title, description, and optional priority/type/complexity"
    parameters_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Task title",
            },
            "description": {
                "type": "string",
                "description": "Task description",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Task priority (default: medium)",
                "default": "medium",
            },
            "task_type": {
                "type": "string",
                "enum": [
                    "exploration",
                    "implementation",
                    "bug_fix",
                    "refactoring",
                    "documentation",
                    "testing",
                    "review",
                    "research",
                ],
                "description": "Task type (default: implementation)",
                "default": "implementation",
            },
            "complexity": {
                "type": "string",
                "enum": ["trivial", "simple", "moderate", "complex", "epic"],
                "description": "Task complexity (default: moderate)",
                "default": "moderate",
            },
            "estimated_hours": {
                "type": "number",
                "description": "Estimated time in hours",
            },
            "parent_id": {
                "type": "string",
                "description": "Parent task ID for subtasks",
            },
            "blocked_by": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of task IDs that must complete first",
            },
        },
        "required": ["title", "description"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        task_type: str = "implementation",
        complexity: str = "moderate",
        estimated_hours: float | None = None,
        parent_id: str | None = None,
        blocked_by: list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        task_manager = kwargs.get("task_manager")

        if not task_manager:
            return "Error: Task manager not available"

        try:
            task = task_manager.create_task(
                title=title,
                description=description,
                priority=TaskPriority(priority),
                task_type=TaskType(task_type),
                complexity=TaskComplexity(complexity),
                estimated_hours=estimated_hours,
                parent_id=parent_id,
                blocked_by=blocked_by,
            )

            result = f"Created task {task.id}: {task.title}\n"
            result += f"Priority: {task.priority.value}\n"
            result += f"Type: {task.task_type.value}\n"
            result += f"Complexity: {task.complexity.value}\n"
            result += f"Status: {task.status.value}"

            if task.parent_id:
                result += f"\nParent: {task.parent_id}"

            return result
        except ValueError as e:
            return f"Error: {str(e)}"


class TaskGetTool(BaseTool):
    """获取任务工具"""

    name = "task_get"
    description = "Get detailed information about a specific task including progress and hierarchy"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The task ID to retrieve",
            },
        },
        "required": ["task_id"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(self, task_id: str, **kwargs: Any) -> str:
        """执行工具"""
        task_manager = kwargs.get("task_manager")

        if not task_manager:
            return "Error: Task manager not available"

        task = task_manager.get_task(task_id)

        if not task:
            return f"Error: Task {task_id} not found"

        output = f"""Task ID: {task.id}
Title: {task.title}
Description: {task.description}
Status: {task.status.value}
Priority: {task.priority.value}
Type: {task.task_type.value}
Complexity: {task.complexity.value}
Progress: {task.progress * 100:.0f}%
Level: {task.level}
Created: {task.created_at}
Updated: {task.updated_at}
"""

        if task.estimated_hours:
            output += f"Estimated: {task.estimated_hours} hours\n"

        if task.actual_hours:
            output += f"Actual: {task.actual_hours} hours\n"

        if task.completed_at:
            output += f"Completed: {task.completed_at}\n"

        if task.parent_id:
            parent = task_manager.get_task(task.parent_id)
            parent_info = f"{task.parent_id}" if not parent else f"{task.parent_id} ({parent.title})"
            output += f"\nParent: {parent_info}\n"

        if task.subtasks:
            output += f"\nSubtasks ({len(task.subtasks)}):\n"
            for subtask_id in task.subtasks:
                subtask = task_manager.get_task(subtask_id)
                if subtask:
                    status_icon = "✅" if subtask.progress >= 1.0 else "🔄" if subtask.progress > 0 else "⏳"
                    output += f"  {status_icon} [{subtask_id}] {subtask.title} ({subtask.progress * 100:.0f}%)\n"

        if task.blockedBy:
            output += f"\nBlocked by: {', '.join(task.blockedBy)}\n"

        if task.blocks:
            output += f"Blocks: {', '.join(task.blocks)}\n"

        return output


class TaskListTool(BaseTool):
    """列出任务工具"""

    name = "task_list"
    description = "List all tasks, optionally filtered by status, priority, or type"
    parameters_schema = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "cancelled", "all"],
                "description": "Filter by status (default: all)",
                "default": "all",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent", "all"],
                "description": "Filter by priority (default: all)",
                "default": "all",
            },
            "task_type": {
                "type": "string",
                "enum": [
                    "exploration",
                    "implementation",
                    "bug_fix",
                    "refactoring",
                    "documentation",
                    "testing",
                    "review",
                    "research",
                    "all",
                ],
                "description": "Filter by task type (default: all)",
                "default": "all",
            },
        },
        "required": [],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        status: str = "all",
        priority: str = "all",
        task_type: str = "all",
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        task_manager = kwargs.get("task_manager")

        if not task_manager:
            return "Error: Task manager not available"

        status_filter = TaskStatus(status) if status != "all" else None
        priority_filter = TaskPriority(priority) if priority != "all" else None

        tasks = task_manager.list_tasks(status=status_filter, priority=priority_filter)

        # Filter by task_type if specified
        if task_type != "all":
            type_enum = TaskType(task_type)
            tasks = [t for t in tasks if t.task_type == type_enum]

        if not tasks:
            return "No tasks found"

        output = f"Found {len(tasks)} task(s):\n\n"

        for i, task in enumerate(tasks, 1):
            progress_bar = self._get_progress_bar(task.progress)
            output += f"{i}. [{task.id}] {task.title}\n"
            output += f"   Status: {task.status.value} | Priority: {task.priority.value} | Type: {task.task_type.value}\n"
            output += f"   Progress: {progress_bar} {task.progress * 100:.0f}%\n"

            if task.blockedBy:
                deps_status = []
                for dep_id in task.blockedBy:
                    dep = task_manager.get_task(dep_id)
                    if dep:
                        deps_status.append(f"{dep_id}({dep.status.value})")
                output += f"   Blocked by: {', '.join(deps_status)}\n"

            output += "\n"

        return output

    def _get_progress_bar(self, progress: float, width: int = 20) -> str:
        """生成进度条"""
        filled = int(progress * width)
        return "█" * filled + "░" * (width - filled)


class TaskUpdateTool(BaseTool):
    """更新任务工具"""

    name = "task_update"
    description = "Update a task's status, priority, or progress"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The task ID to update",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "cancelled"],
                "description": "New status",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "New priority",
            },
            "progress": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "New progress value (0.0 to 1.0)",
            },
        },
        "required": ["task_id"],
    }
    timeout = 10
    risk_level = "medium"

    async def execute(
        self,
        task_id: str,
        status: str | None = None,
        priority: str | None = None,
        progress: float | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        task_manager = kwargs.get("task_manager")

        if not task_manager:
            return "Error: Task manager not available"

        status_enum = TaskStatus(status) if status else None
        priority_enum = TaskPriority(priority) if priority else None

        task = task_manager.update_task(
            task_id=task_id,
            status=status_enum,
            priority=priority_enum,
            progress=progress,
        )

        if not task:
            return f"Error: Task {task_id} not found"

        result = f"Updated task {task_id}\n"
        result += f"New status: {task.status.value}\n"
        result += f"New priority: {task.priority.value}\n"
        result += f"New progress: {task.progress * 100:.0f}%"

        return result


class TaskProgressTool(BaseTool):
    """更新任务进度工具"""

    name = "task_progress"
    description = "Update task progress with optional note"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The task ID",
            },
            "progress": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Progress value (0.0 to 1.0)",
            },
            "note": {
                "type": "string",
                "description": "Optional progress note",
            },
        },
        "required": ["task_id", "progress"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        task_id: str,
        progress: float,
        note: str | None = None,
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        task_manager = kwargs.get("task_manager")

        if not task_manager:
            return "Error: Task manager not available"

        task = task_manager.update_progress(task_id, progress)

        if not task:
            return f"Error: Task {task_id} not found"

        result = f"Updated progress for task {task_id}\n"
        result += f"Progress: {task.progress * 100:.0f}%\n"
        result += f"Status: {task.status.value}"

        if note:
            result += f"\nNote: {note}"

        return result


class TaskReportTool(BaseTool):
    """任务报告工具"""

    name = "task_report"
    description = "Generate task progress report or summary"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID for individual report (omit for summary)",
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "json", "text"],
                "description": "Report format (default: markdown)",
                "default": "markdown",
            },
            "status_filter": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "cancelled", "all"],
                "description": "Filter by status for summary (default: all)",
                "default": "all",
            },
        },
        "required": [],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        task_id: str | None = None,
        format: str = "markdown",
        status_filter: str = "all",
        **kwargs: Any,
    ) -> str:
        """执行工具"""
        task_manager = kwargs.get("task_manager")

        if not task_manager:
            return "Error: Task manager not available"

        from .reporter import TaskReporter

        reporter = TaskReporter(task_manager)

        if task_id:
            # Generate individual task report
            report = reporter.generate_progress_report(task_id)
            if not report:
                return f"Error: Task {task_id} not found"
            return reporter.format_report(report, format)
        else:
            # Generate summary report
            filter_status = status_filter if status_filter != "all" else None
            summary = reporter.generate_summary_report(filter_status)
            return reporter.format_summary(summary, format)


class TaskManagementPlugin(BasePlugin):
    """任务管理插件"""

    def __init__(self):
        super().__init__()

        self.metadata = PluginMetadata(
            id="task_system",
            name="Task Management System",
            version="4.0.0",
            type=PluginType.INTEGRATION,
            description="Task creation and management tools",
            author="PyAgentForge Team",
        )

        self.task_manager = TaskManager()

    async def on_activate(self) -> None:
        """激活插件"""
        # 注册工具
        tools = [
            TaskCreateTool(),
            TaskGetTool(),
            TaskListTool(),
            TaskUpdateTool(),
            TaskProgressTool(),
            TaskReportTool(),
        ]

        for tool in tools:
            self.register_tool(tool)

        logger.info("Task Management System activated")

    async def on_deactivate(self) -> None:
        """停用插件"""
        logger.info("Task Management System deactivated")

    def get_context(self) -> dict[str, Any]:
        """获取插件上下文"""
        return {
            "task_manager": self.task_manager,
        }


# 导出
__all__ = [
    "TaskManagementPlugin",
    "TaskManager",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
    "TaskComplexity",
    "TaskCreateTool",
    "TaskGetTool",
    "TaskListTool",
    "TaskUpdateTool",
    "TaskProgressTool",
    "TaskReportTool",
]
