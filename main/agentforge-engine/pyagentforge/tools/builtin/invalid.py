"""
Invalid 工具

处理无效的工具调用
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class InvalidTool(BaseTool):
    """Invalid 工具 - 处理无效调用"""

    name = "invalid"
    description = """处理无效的工具调用。

当 Agent 尝试调用不存在的工具时，
系统会自动返回此工具的结果。

提供有用的错误信息和可用工具列表。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "requested_tool": {
                "type": "string",
                "description": "请求的工具名称",
            },
            "reason": {
                "type": "string",
                "description": "无效原因",
            },
        },
    }
    timeout = 5
    risk_level = "low"

    def __init__(self, available_tools: list[str] | None = None) -> None:
        self.available_tools = available_tools or []

    async def execute(
        self,
        requested_tool: str = "unknown",
        reason: str = "Tool not found",
    ) -> str:
        """返回无效工具错误"""
        logger.warning(
            "Invalid tool requested",
            extra_data={"tool": requested_tool, "reason": reason},
        )

        error_msg = f"Error: Invalid tool '{requested_tool}'"
        error_msg += f"\nReason: {reason}"

        if self.available_tools:
            error_msg += "\n\nAvailable tools:"
            for tool in sorted(self.available_tools):
                error_msg += f"\n  - {tool}"
        else:
            error_msg += "\n\nPlease check the tool name and try again."

        return error_msg


class ToolSuggestionTool(BaseTool):
    """ToolSuggestion 工具 - 工具建议"""

    name = "suggest_tool"
    description = """根据任务描述建议合适的工具。

当不确定使用哪个工具时，
提供任务描述获取工具建议。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "任务描述",
            },
        },
        "required": ["task"],
    }
    timeout = 5
    risk_level = "low"

    # 工具用途映射
    TOOL_PURPOSES = {
        "bash": ["execute command", "run script", "shell", "terminal", "process"],
        "read": ["read file", "view file", "show file", "cat file", "file content"],
        "write": ["create file", "write file", "new file", "save file"],
        "edit": ["modify file", "change file", "update file", "replace text"],
        "glob": ["find files", "search files", "list files", "file pattern"],
        "grep": ["search text", "find text", "search content", "grep"],
        "ls": ["list directory", "show files", "dir", "folder contents"],
        "webfetch": ["fetch url", "get webpage", "download page", "http request"],
        "websearch": ["search web", "google", "search online", "find online"],
        "lsp": ["definition", "references", "rename", "code navigation"],
        "codesearch": ["search code", "find function", "find class", "code search"],
        "plan": ["create plan", "make plan", "planning", "strategy"],
        "task": ["subagent", "sub task", "delegate", "parallel"],
        "skill": ["load knowledge", "expert", "domain knowledge"],
        "todo": ["task list", "checklist", "todo", "track progress"],
        "question": ["ask user", "confirm", "user input", "question"],
        "diff": ["compare", "difference", "compare files", "diff"],
        "patch": ["apply patch", "git patch", "diff apply"],
    }

    async def execute(self, task: str) -> str:
        """建议工具"""
        task_lower = task.lower()

        suggestions = []

        for tool, keywords in self.TOOL_PURPOSES.items():
            for keyword in keywords:
                if keyword in task_lower:
                    suggestions.append((tool, keyword))
                    break

        if not suggestions:
            return f"No specific tool suggestions for: '{task}'\n\nTry describing your task more specifically."

        output = [f"Tool suggestions for: '{task}'", "=" * 40]

        for tool, matched_keyword in suggestions:
            output.append(f"\n• {tool}")
            output.append(f"  Matched: '{matched_keyword}'")

        if len(suggestions) > 1:
            output.append("\nMultiple tools may be applicable. Choose based on your specific needs.")

        return "\n".join(output)


class ToolErrorHandler:
    """工具错误处理器"""

    @staticmethod
    def handle_tool_error(
        tool_name: str,
        error: Exception,
        available_tools: list[str] | None = None,
    ) -> str:
        """处理工具执行错误"""
        error_str = str(error).lower()

        # 常见错误类型和建议
        suggestions = []

        if "timeout" in error_str:
            suggestions.append("The operation timed out. Try increasing the timeout or simplifying the task.")
        elif "permission" in error_str or "access" in error_str:
            suggestions.append("Permission denied. Check file/directory permissions.")
        elif "not found" in error_str:
            suggestions.append("File or resource not found. Check the path or name.")
        elif "syntax" in error_str or "parse" in error_str:
            suggestions.append("Syntax error. Check the input format.")
        elif "connection" in error_str or "network" in error_str:
            suggestions.append("Network error. Check your connection and try again.")

        error_msg = f"Error executing tool '{tool_name}':\n{str(error)}"

        if suggestions:
            error_msg += "\n\nSuggestions:"
            for s in suggestions:
                error_msg += f"\n  • {s}"

        # 提供替代工具
        alternatives = ToolErrorHandler._get_alternative_tools(tool_name, available_tools)
        if alternatives:
            error_msg += f"\n\nAlternative tools: {', '.join(alternatives)}"

        return error_msg

    @staticmethod
    def _get_alternative_tools(
        tool_name: str,
        available_tools: list[str] | None,
    ) -> list[str]:
        """获取替代工具"""
        alternatives_map = {
            "bash": ["glob", "grep"],
            "read": ["bash (cat)", "grep"],
            "write": ["edit", "bash (echo)"],
            "edit": ["write", "bash (sed)"],
            "webfetch": ["bash (curl)", "websearch"],
            "lsp": ["grep", "codesearch"],
        }

        alternatives = alternatives_map.get(tool_name, [])

        if available_tools:
            alternatives = [a for a in alternatives if a in available_tools or "bash" in a]

        return alternatives
