"""
Background Task Tools

v4.0: 后台任务管理工具

提供后台任务的状态检查、取消和列表功能。
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class BackgroundOutputTool(BaseTool):
    """
    后台任务输出工具

    检查后台任务的状态和结果。
    """

    name = "background_output"
    description = "Check the status and output of a background task"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the background task to check",
            },
            "wait": {
                "type": "boolean",
                "description": "Wait for task completion if still running (default: false)",
                "default": False,
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds to wait (default: 60)",
                "default": 60,
            },
        },
        "required": ["task_id"],
    }
    timeout = 120
    risk_level = "low"

    async def execute(
        self,
        task_id: str,
        wait: bool = False,
        timeout: int = 60,
        **kwargs: Any,
    ) -> str:
        """
        执行工具

        Args:
            task_id: 任务 ID
            wait: 是否等待任务完成
            timeout: 超时秒数

        Returns:
            任务状态和结果
        """
        # 获取 background_manager
        background_manager = kwargs.get("background_manager")

        if not background_manager:
            return "Error: Background manager not available"

        # 获取任务
        task = background_manager.get_status(task_id)

        if not task:
            return f"Error: Task {task_id} not found"

        # 如果需要等待
        if wait and task.status in ("pending", "running"):
            task = await background_manager.wait_for_completion(
                task_id, timeout=timeout
            )

        # 构建输出
        output = f"""Task ID: {task.id}
Status: {task.status.value}
Agent: {task.agent_type}
Created: {task.created_at}
"""

        if task.started_at:
            output += f"Started: {task.started_at}\n"

        if task.completed_at:
            output += f"Completed: {task.completed_at}\n"
            output += f"Duration: {task.duration_ms}ms\n"

        if task.result:
            output += f"\nResult:\n{task.result}\n"

        if task.error:
            output += f"\nError:\n{task.error}\n"

        return output


class BackgroundCancelTool(BaseTool):
    """
    后台任务取消工具

    取消运行中的后台任务。
    """

    name = "background_cancel"
    description = "Cancel a running background task"
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "The ID of the background task to cancel",
            },
        },
        "required": ["task_id"],
    }
    timeout = 10
    risk_level = "medium"

    async def execute(self, task_id: str, **kwargs: Any) -> str:
        """
        执行工具

        Args:
            task_id: 任务 ID

        Returns:
            取消结果
        """
        # 获取 background_manager
        background_manager = kwargs.get("background_manager")

        if not background_manager:
            return "Error: Background manager not available"

        # 取消任务
        success = await background_manager.cancel(task_id)

        if success:
            return f"Successfully cancelled task {task_id}"
        else:
            return f"Failed to cancel task {task_id} (task may not exist or already completed)"


class BackgroundListTool(BaseTool):
    """
    后台任务列表工具

    列出所有后台任务。
    """

    name = "background_list"
    description = "List all background tasks, optionally filtered by session"
    parameters_schema = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Filter by session ID (optional)",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "running", "completed", "failed", "cancelled", "all"],
                "description": "Filter by status (default: all)",
                "default": "all",
            },
        },
        "required": [],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        session_id: str | None = None,
        status: str = "all",
        **kwargs: Any,
    ) -> str:
        """
        执行工具

        Args:
            session_id: 会话 ID (可选)
            status: 状态过滤

        Returns:
            任务列表
        """
        # 获取 background_manager
        background_manager = kwargs.get("background_manager")

        if not background_manager:
            return "Error: Background manager not available"

        # 获取任务列表
        if session_id:
            tasks = background_manager.list_by_session(session_id)
        elif status == "running":
            tasks = background_manager.list_active()
        else:
            tasks = list(background_manager._tasks.values())

        # 过滤状态
        if status != "all":
            tasks = [t for t in tasks if t.status.value == status]

        # 排序（按创建时间倒序）
        tasks.sort(key=lambda t: t.created_at, reverse=True)

        # 构建输出
        if not tasks:
            return "No background tasks found"

        output = f"Found {len(tasks)} background task(s):\n\n"

        for i, task in enumerate(tasks, 1):
            output += f"{i}. {task.id} - {task.agent_type}\n"
            output += f"   Status: {task.status.value}\n"
            output += f"   Created: {task.created_at}\n"

            if task.duration_ms > 0:
                output += f"   Duration: {task.duration_ms}ms\n"

            output += "\n"

        return output


# 导出
__all__ = ["BackgroundOutputTool", "BackgroundCancelTool", "BackgroundListTool"]
