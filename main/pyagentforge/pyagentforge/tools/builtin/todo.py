"""
Todo 工具

管理待办事项列表
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TodoItem(BaseModel):
    """待办事项"""

    id: int
    content: str
    status: str = "pending"  # pending, in_progress, completed
    priority: str = "medium"  # low, medium, high
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


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

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or Path("./data/todos.json")
        self._todos: dict[int, TodoItem] = {}
        self._load()

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
            "pending": "○",
            "in_progress": "◐",
            "completed": "●",
        }
        priority_icons = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
        }

        for todo in sorted(self._todos.values(), key=lambda x: x.id):
            icon = status_icons.get(todo.status, "○")
            prio = priority_icons.get(todo.priority, "")
            lines.append(f"{icon} [{todo.id}] {prio} {todo.content}")
            if todo.status == "in_progress":
                lines.append(f"   Status: {todo.status}")

        return "\n".join(lines)


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
