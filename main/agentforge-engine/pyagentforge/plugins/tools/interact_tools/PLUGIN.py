"""
Interact Tools Plugin

Provides question, confirm, and batch tools for user interaction

Note: Todo tools are provided by builtin tools (pyagentforge.tools.builtin.todo)
"""

import asyncio
import logging
from typing import Any, Callable, List

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool


# ============ Question Tool ============

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


# ============ Confirm Tool ============

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
    """Interactive tools plugin (question, confirm, batch)

    Note: Todo tools are provided by builtin tools, not this plugin.
    """

    metadata = PluginMetadata(
        id="tool.interact_tools",
        name="Interact Tools",
        version="2.0.0",
        type=PluginType.TOOL,
        description="Provides question, confirm, and batch tools for user interaction",
        author="PyAgentForge",
        provides=["tools.interact"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._question_tool: QuestionTool | None = None
        self._confirm_tool: ConfirmTool | None = None
        self._batch_tool: BatchTool | None = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Create tools
        self._question_tool = QuestionTool()
        self._confirm_tool = ConfirmTool()
        self._batch_tool = BatchTool(
            tool_registry=self.context.get_tool_registry() if self.context else None
        )

        self.context.logger.info("Interact tools plugin initialized (v2.0 - no todo)")

    def get_tools(self) -> List[BaseTool]:
        """Return plugin provided tools"""
        return [
            self._question_tool,
            self._confirm_tool,
            self._batch_tool,
        ]
