"""
Passive Agent Handler — Tool Definitions

Declares the tool capabilities that are registered with the passive AgentEngine.
Tools are backed by pyagentforge built-ins; the LLM can actually call them.
"""

from __future__ import annotations

from typing import Any

# These reflect the built-in tools registered in EngineManager._create_passive_engine().
# The LLM decides when to call each tool based on the user's request.
TOOL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "bash": {
        "name": "bash",
        "description": "执行 shell 命令（代码验证、构建、测试等）",
        "parameters": {"command": "string"},
        "category": "execution",
    },
    "read": {
        "name": "read",
        "description": "读取文件内容",
        "parameters": {"file_path": "string", "offset": "integer", "limit": "integer"},
        "category": "file",
    },
    "write": {
        "name": "write",
        "description": "写入文件内容（创建或覆盖）",
        "parameters": {"file_path": "string", "content": "string"},
        "category": "file",
    },
    "edit": {
        "name": "edit",
        "description": "编辑文件的指定行范围",
        "parameters": {"file_path": "string", "old_string": "string", "new_string": "string"},
        "category": "file",
    },
    "glob": {
        "name": "glob",
        "description": "按 glob 模式查找文件",
        "parameters": {"pattern": "string", "path": "string"},
        "category": "search",
    },
    "grep": {
        "name": "grep",
        "description": "在文件中搜索文本（正则表达式）",
        "parameters": {"pattern": "string", "path": "string"},
        "category": "search",
    },
    "ls": {
        "name": "ls",
        "description": "列出目录内容",
        "parameters": {"path": "string"},
        "category": "file",
    },
    "webfetch": {
        "name": "webfetch",
        "description": "获取网页内容（读取文档、参考资料）",
        "parameters": {"url": "string"},
        "category": "web",
    },
    "websearch": {
        "name": "websearch",
        "description": "搜索网络获取最新信息",
        "parameters": {"query": "string"},
        "category": "web",
    },
    "multiedit": {
        "name": "multiedit",
        "description": "批量编辑多个文件",
        "parameters": {"edits": "array"},
        "category": "file",
    },
    "todo_write": {
        "name": "todo_write",
        "description": "记录和管理任务列表",
        "parameters": {"todos": "array"},
        "category": "productivity",
    },
    "plan": {
        "name": "plan",
        "description": "制定结构化执行计划",
        "parameters": {"title": "string", "steps": "array"},
        "category": "productivity",
    },
}


def get_tool_list() -> list[dict[str, Any]]:
    return list(TOOL_DEFINITIONS.values())
