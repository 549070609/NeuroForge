"""
Todo 工具

管理待办事项列表，支持任务完成监控和强制继续
"""

import json
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ============ 常量 ============

DEFAULT_COUNTDOWN_SECONDS = 5
DEFAULT_MAX_RECOVERY_ATTEMPTS = 3

# 可跳过强制继续的 Agent 类型
SKIP_AGENTS = {"explore", "librarian", "oracle"}

# 续接消息模板
CONTINUATION_PROMPT = """
[Task Continuation]

You have {pending_count} incomplete task(s):
{pending_tasks}

Please continue working on these tasks. Start with the first incomplete task.
"""


# ============ 类型定义 ============

class TodoStatus(str, Enum):
    """Todo 状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TodoItem(BaseModel):
    """待办事项"""
    id: int
    content: str
    status: str = "pending"
    priority: str = "medium"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TodoEnforcerConfig(BaseModel):
    """强制继续配置"""
    enabled: bool = True
    countdown_seconds: int = DEFAULT_COUNTDOWN_SECONDS
    max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS
    skip_agents: List[str] = []
    auto_continue: bool = True


# ============ Todo 状态管理器 ============

class TodoStateManager:
    """
    Todo 状态管理器

    负责管理 Todo 状态和强制继续逻辑
    """

    def __init__(
        self,
        config: Optional[TodoEnforcerConfig] = None,
        continuation_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        初始化状态管理器

        Args:
            config: 强制继续配置
            continuation_callback: 继续回调函数，接收续接消息
        """
        self.config = config or TodoEnforcerConfig()
        self.continuation_callback = continuation_callback

        # 会话状态
        self._recovery_count: int = 0
        self._is_recovering: bool = False
        self._countdown_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def should_skip_agent(self, agent_name: Optional[str]) -> bool:
        """检查是否应该跳过此 Agent"""
        if not agent_name:
            return False
        skip_set = set(self.config.skip_agents) | SKIP_AGENTS
        return agent_name.lower() in skip_set

    def has_pending_todos(self, todos: Dict[int, TodoItem]) -> bool:
        """检查是否有未完成的 Todo"""
        for todo in todos.values():
            if todo.status in [TodoStatus.PENDING.value, TodoStatus.IN_PROGRESS.value]:
                return True
        return False

    def get_pending_todos(self, todos: Dict[int, TodoItem]) -> List[TodoItem]:
        """获取未完成的 Todo 列表"""
        pending = []
        for todo in todos.values():
            if todo.status in [TodoStatus.PENDING.value, TodoStatus.IN_PROGRESS.value]:
                pending.append(todo)
        return pending

    def get_status_summary(self, todos: Dict[int, TodoItem]) -> Dict[str, Any]:
        """获取状态摘要"""
        total = len(todos)
        pending = sum(
            1 for t in todos.values()
            if t.status in [TodoStatus.PENDING.value, TodoStatus.IN_PROGRESS.value]
        )
        completed = sum(
            1 for t in todos.values()
            if t.status == TodoStatus.COMPLETED.value
        )

        return {
            "total": total,
            "pending": pending,
            "completed": completed,
            "is_recovering": self._is_recovering,
            "recovery_count": self._recovery_count,
        }

    def generate_continuation_prompt(self, pending_todos: List[TodoItem]) -> str:
        """生成续接消息"""
        task_lines = []
        for i, todo in enumerate(pending_todos, 1):
            status_marker = "[IN PROGRESS]" if todo.status == TodoStatus.IN_PROGRESS.value else "[PENDING]"
            task_lines.append(f"  {i}. {status_marker} {todo.content}")

        return CONTINUATION_PROMPT.format(
            pending_count=len(pending_todos),
            pending_tasks="\n".join(task_lines),
        )

    def can_recover(self) -> bool:
        """检查是否可以恢复"""
        return self._recovery_count < self.config.max_recovery_attempts

    def mark_recovering(self) -> None:
        """标记为恢复中"""
        with self._lock:
            self._is_recovering = True
            self._cancel_countdown()
            logger.debug("Marked as recovering")

    def mark_recovery_complete(self) -> None:
        """标记恢复完成"""
        with self._lock:
            self._is_recovering = False
            self._recovery_count += 1
            logger.debug(f"Recovery complete (count: {self._recovery_count})")

    def on_agent_stop(
        self,
        todos: Dict[int, TodoItem],
        agent_name: Optional[str] = None,
    ) -> Optional[str]:
        """
        Agent 停止时检查是否需要继续

        Args:
            todos: Todo 字典
            agent_name: Agent 名称

        Returns:
            Optional[str]: 如果需要继续，返回续接消息；否则返回 None
        """
        if not self.config.enabled:
            return None

        # 检查是否跳过
        if self.should_skip_agent(agent_name):
            logger.debug(f"Skipping enforcer for agent: {agent_name}")
            return None

        # 检查是否正在恢复
        if self._is_recovering:
            logger.debug("Already recovering")
            return None

        # 检查是否有未完成的任务
        pending = self.get_pending_todos(todos)
        if not pending:
            logger.debug("No pending todos")
            return None

        # 检查是否可以恢复
        if not self.can_recover():
            logger.warning("Max recovery attempts reached")
            return None

        # 生成续接消息
        prompt = self.generate_continuation_prompt(pending)

        logger.info(f"Agent stopped with {len(pending)} pending todos")

        # 如果配置了自动继续
        if self.config.auto_continue and self.continuation_callback:
            self.mark_recovering()
            self.continuation_callback(prompt)

        return prompt

    def _cancel_countdown(self) -> None:
        """取消倒计时"""
        if self._countdown_timer:
            self._countdown_timer.cancel()
            self._countdown_timer = None


# ============ Todo 工具 ============

class TodoWriteTool(BaseTool):
    """TodoWrite 工具 - 写入待办事项"""

    name = "todowrite"
    description = """管理待办事项列表。

使用场景:
- 规划任务步骤
- 跟踪进度
- 分解复杂任务

状态:
- pending: 待处理
- in_progress: 进行中
- completed: 已完成
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "待办事项列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["id", "content"],
                },
            },
        },
        "required": ["todos"],
    }
    timeout = 10
    risk_level = "low"

    def __init__(
        self,
        storage_path: Path | None = None,
        enforcer_config: Optional[TodoEnforcerConfig] = None,
        continuation_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.storage_path = storage_path or Path("./data/todos.json")
        self._todos: Dict[int, TodoItem] = {}
        self._load()

        # 初始化状态管理器
        self._state_manager = TodoStateManager(
            config=enforcer_config,
            continuation_callback=continuation_callback,
        )

    def _load(self) -> None:
        """加载待办事项"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for item in data:
                        todo = TodoItem(**item)
                        self._todos[todo.id] = todo
            except Exception:
                pass

    def _save(self) -> None:
        """保存待办事项"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(
                [t.model_dump() for t in self._todos.values()],
                f,
                indent=2,
            )

    async def execute(self, todos: list[dict[str, Any]]) -> str:
        """更新待办事项"""
        updated = []
        for item in todos:
            todo_id = item.get("id")
            content = item.get("content", "")
            status = item.get("status", "pending")
            priority = item.get("priority", "medium")

            todo = TodoItem(
                id=todo_id,
                content=content,
                status=status,
                priority=priority,
            )
            self._todos[todo_id] = todo
            updated.append(todo_id)

        self._save()

        logger.info(
            "Updated todos",
            extra_data={"count": len(updated), "ids": updated},
        )

        return self._format_todos()

    def _format_todos(self) -> str:
        """格式化待办事项"""
        if not self._todos:
            return "No todos."

        lines = ["# Todo List\n"]
        status_icons = {
            "pending": "[ ]",
            "in_progress": "[>]",
            "completed": "[x]",
        }
        priority_icons = {
            "high": "(!)",
            "medium": "( )",
            "low": "(-)",
        }

        for todo in sorted(self._todos.values(), key=lambda x: x.id):
            icon = status_icons.get(todo.status, "[ ]")
            prio = priority_icons.get(todo.priority, "( )")
            lines.append(f"{icon} [{todo.id}] {prio} {todo.content}")

        # 添加摘要
        summary = self.get_status_summary()
        lines.append(f"\n---\nTotal: {summary['total']} | Pending: {summary['pending']} | Completed: {summary['completed']}")

        return "\n".join(lines)

    # ============ 新增：强制继续相关方法 ============

    def has_pending_todos(self) -> bool:
        """检查是否有未完成的 Todo"""
        return self._state_manager.has_pending_todos(self._todos)

    def get_pending_todos(self) -> List[TodoItem]:
        """获取未完成的 Todo 列表"""
        return self._state_manager.get_pending_todos(self._todos)

    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        return self._state_manager.get_status_summary(self._todos)

    def on_agent_stop(self, agent_name: Optional[str] = None) -> Optional[str]:
        """
        Agent 停止时检查是否需要继续

        Args:
            agent_name: Agent 名称

        Returns:
            Optional[str]: 如果需要继续，返回续接消息；否则返回 None
        """
        return self._state_manager.on_agent_stop(self._todos, agent_name)

    def mark_recovery_complete(self) -> None:
        """标记恢复完成"""
        self._state_manager.mark_recovery_complete()

    def is_recovering(self) -> bool:
        """是否正在恢复"""
        return self._state_manager._is_recovering

    def get_state_manager(self) -> TodoStateManager:
        """获取状态管理器"""
        return self._state_manager


class TodoReadTool(BaseTool):
    """TodoRead 工具 - 读取待办事项"""

    name = "todoread"
    description = """读取当前待办事项列表。"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
    }
    timeout = 10
    risk_level = "low"

    def __init__(self, todo_write_tool: TodoWriteTool) -> None:
        self.todo_tool = todo_write_tool

    async def execute(self) -> str:
        """读取待办事项"""
        return self.todo_tool._format_todos()
