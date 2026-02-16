"""
Interact Tools Plugin

Provides question, confirm, todo, and batch tools for user interaction
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, List

from pydantic import BaseModel, Field

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool


# ============ Todo Tools ============

class TodoItem(BaseModel):
    """Todo item"""
    id: int
    content: str
    status: str = "pending"  # pending, in_progress, completed
    priority: str = "medium"  # low, medium, high
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TodoWriteTool(BaseTool):
    """TodoWrite Tool - Write todo items"""

    name = "todowrite"
    description = """Manage todo list.

    Use scenarios:
    - Plan task steps
    - Track progress
    - Break down complex tasks

    Status:
    - pending: To be processed
    - in_progress: In progress
    - completed: Completed
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "Todo list",
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
        """Load todo items"""
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
        """Save todo items"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, "w") as f:
            json.dump(
                [t.model_dump() for t in self._todos.values()],
                f,
                indent=2,
            )

    async def execute(self, todos: list[dict[str, Any]]) -> str:
        """Update todo items"""
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

        self._save()
        return self._format_todos()

    def _format_todos(self) -> str:
        """Format todo items"""
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
            prio = priority_icons.get(todo.priority, "")
            lines.append(f"{icon} [{todo.id}] {prio} {todo.content}")

        return "\n".join(lines)


class TodoReadTool(BaseTool):
    """TodoRead Tool - Read todo items"""

    name = "todoread"
    description = """Read current todo list."""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
    }
    timeout = 10
    risk_level = "low"

    def __init__(self, todo_write_tool: TodoWriteTool) -> None:
        self.todo_tool = todo_write_tool

    async def execute(self) -> str:
        """Read todo items"""
        return self.todo_tool._format_todos()


# ============ Question Tools ============

class QuestionTool(BaseTool):
    """Question Tool - Ask user questions"""

    name = "question"
    description = """Ask user questions and wait for answers.

    Use scenarios:
    - Need user confirmation
    - Request information from user
    - Let user make choices

    Questions are displayed to user, execution continues after answer.
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Question to ask user",
            },
            "options": {
                "type": "array",
                "description": "Optional answer choices",
                "items": {"type": "string"},
            },
            "default": {
                "type": "string",
                "description": "Default answer",
            },
        },
        "required": ["question"],
    }
    timeout = 300  # 5 minutes wait for answer
    risk_level = "low"

    def __init__(
        self,
        ask_callback: Callable[[str, list[str] | None, str | None], str] | None = None,
    ) -> None:
        self.ask_callback = ask_callback

    async def execute(
        self,
        question: str,
        options: list[str] | None = None,
        default: str | None = None,
    ) -> str:
        """Ask user question"""
        if self.ask_callback:
            answer = self.ask_callback(question, options, default)
            return f"User answered: {answer}"

        # Return prompt for agent to handle
        result_parts = [f"[QUESTION]: {question}"]

        if options:
            result_parts.append("\nOptions:")
            for i, opt in enumerate(options, 1):
                marker = " (default)" if opt == default else ""
                result_parts.append(f"  {i}. {opt}{marker}")

        if default:
            result_parts.append(f"\nDefault: {default}")

        result_parts.append("\n[Waiting for user response...]")
        return "\n".join(result_parts)


class ConfirmTool(BaseTool):
    """Confirm Tool - Simple yes/no confirmation"""

    name = "confirm"
    description = """Request user yes/no confirmation."""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Confirmation message",
            },
            "default": {
                "type": "boolean",
                "description": "Default value",
                "default": False,
            },
        },
        "required": ["message"],
    }
    timeout = 120
    risk_level = "low"

    def __init__(
        self,
        confirm_callback: Callable[[str, bool], bool] | None = None,
    ) -> None:
        self.confirm_callback = confirm_callback

    async def execute(
        self,
        message: str,
        default: bool = False,
    ) -> str:
        """Request confirmation"""
        if self.confirm_callback:
            result = self.confirm_callback(message, default)
            return f"User confirmed: {result}"

        default_str = "Y/n" if default else "y/N"
        return f"[CONFIRM]: {message}\n[{default_str}]?\n[Waiting for user confirmation...]"


# ============ Batch Tool ============

class BatchTool(BaseTool):
    """Batch Tool - Execute multiple tool calls in batch"""

    name = "batch"
    description = """Execute multiple tool calls in batch.

    Use scenarios:
    - Read multiple files in parallel
    - Execute commands in batch
    - Improve efficiency

    All operations execute in parallel, results summarized.
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "invocations": {
                "type": "array",
                "description": "Tool call list",
                "items": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"},
                        "arguments": {"type": "object"},
                    },
                    "required": ["tool_name", "arguments"],
                },
            },
            "parallel": {
                "type": "boolean",
                "description": "Whether to execute in parallel",
                "default": True,
            },
        },
        "required": ["invocations"],
    }
    timeout = 120
    risk_level = "medium"

    def __init__(self, tool_registry: Any = None) -> None:
        self.registry = tool_registry

    async def execute(
        self,
        invocations: list[dict[str, Any]],
        parallel: bool = True,
    ) -> str:
        """Execute batch tool calls"""
        results = []

        if parallel:
            tasks = []
            for i, inv in enumerate(invocations):
                tool_name = inv.get("tool_name")
                args = inv.get("arguments", {})
                tasks.append(self._execute_single(i, tool_name, args))

            results = await asyncio.gather(*tasks)
        else:
            for i, inv in enumerate(invocations):
                tool_name = inv.get("tool_name")
                args = inv.get("arguments", {})
                result = await self._execute_single(i, tool_name, args)
                results.append(result)

        # Format results
        lines = [f"Batch execution: {len(invocations)} invocations\n"]

        success = 0
        failed = 0

        for i, result in enumerate(results):
            tool_name = invocations[i].get("tool_name", "unknown")
            if result.startswith("Error"):
                failed += 1
                lines.append(f"## [{i+1}] {tool_name} - FAILED")
            else:
                success += 1
                lines.append(f"## [{i+1}] {tool_name} - SUCCESS")

            # Truncate long results
            display_result = result[:2000] if len(result) > 2000 else result
            lines.append(f"```\n{display_result}\n```\n")

        lines.append(f"Summary: {success} succeeded, {failed} failed")
        return "\n".join(lines)

    async def _execute_single(
        self,
        index: int,
        tool_name: str,
        args: dict[str, Any],
    ) -> str:
        """Execute single tool call"""
        try:
            if self.registry is None:
                return f"Error: No tool registry available"

            tool = self.registry.get(tool_name)
            if tool is None:
                return f"Error: Tool '{tool_name}' not found"

            result = await tool.execute(**args)
            return result

        except Exception as e:
            return f"Error: {str(e)}"


# ============ Plugin ============

class InteractToolsPlugin(Plugin):
    """Interactive tools plugin"""

    metadata = PluginMetadata(
        id="tool.interact_tools",
        name="Interact Tools",
        version="1.0.0",
        type=PluginType.TOOL,
        description="Provides question, confirm, todo, and batch tools for user interaction",
        author="PyAgentForge",
        provides=["tools.interact"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._todo_write_tool: TodoWriteTool | None = None
        self._todo_read_tool: TodoReadTool | None = None
        self._question_tool: QuestionTool | None = None
        self._confirm_tool: ConfirmTool | None = None
        self._batch_tool: BatchTool | None = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        config = self.context.config or {}

        # Create tools
        self._todo_write_tool = TodoWriteTool(
            storage_path=Path(config.get("todo_storage_path", "./data/todos.json"))
        )
        self._todo_read_tool = TodoReadTool(self._todo_write_tool)
        self._question_tool = QuestionTool()
        self._confirm_tool = ConfirmTool()
        self._batch_tool = BatchTool(
            tool_registry=self.context.get_tool_registry() if self.context else None
        )

        self.context.logger.info("Interact tools plugin initialized")

    def get_tools(self) -> List[BaseTool]:
        """Return plugin provided tools"""
        return [
            self._todo_write_tool,
            self._todo_read_tool,
            self._question_tool,
            self._confirm_tool,
            self._batch_tool,
        ]
