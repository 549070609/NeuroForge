"""
File Tools Plugin

Provides ls and truncation tools
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.kernel.base_tool import BaseTool
from pyagentforge.tools.permission import PermissionChecker


class LsTool(BaseTool):
    """Ls Tool - List directory contents"""

    name = "ls"
    description = """List directory contents.

    Returns files and subdirectories in the directory, including:
    - File/directory names
    - Type (file/directory)
    - Size (files)
    - Modification time
    - Permissions

    Supports recursive listing of subdirectories.
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path, defaults to current directory",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to recursively list subdirectories",
                "default": False,
            },
            "show_hidden": {
                "type": "boolean",
                "description": "Whether to show hidden files",
                "default": False,
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum recursion depth",
                "default": 3,
            },
        },
        "required": [],
    }
    timeout = 30
    risk_level = "low"

    def __init__(self, permission_checker: PermissionChecker | None = None) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        path: str = ".",
        recursive: bool = False,
        show_hidden: bool = False,
        max_depth: int = 3,
    ) -> str:
        """List directory contents"""
        dir_path = Path(path)

        # Check if directory exists
        if not dir_path.exists():
            return f"Error: Path '{path}' does not exist"

        if not dir_path.is_dir():
            return f"Error: '{path}' is not a directory"

        try:
            if recursive:
                lines = self._list_recursive(dir_path, show_hidden, max_depth, 0)
            else:
                lines = self._list_single(dir_path, show_hidden)

            if not lines:
                return f"Directory '{path}' is empty"

            return "\n".join(lines)

        except PermissionError:
            return f"Error: Permission denied accessing '{path}'"
        except Exception as e:
            return f"Error: {str(e)}"

    def _list_single(self, dir_path: Path, show_hidden: bool) -> list[str]:
        """List single directory"""
        lines = [f"Directory: {dir_path.absolute()}", "-" * 60]

        entries = list(dir_path.iterdir())

        # Filter hidden files
        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]

        # Sort: directories first, then by name
        entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        for entry in entries:
            try:
                stat = entry.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

                if entry.is_dir():
                    size_str = "<DIR>"
                    type_str = "DIR"
                else:
                    size = stat.st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f}KB"
                    else:
                        size_str = f"{size/1024/1024:.1f}MB"
                    type_str = "FILE"

                lines.append(f"{type_str:5} {size_str:>10} {mtime} {entry.name}")

            except PermissionError:
                lines.append(f"????  ?????????? ???????????? {entry.name}")

        lines.append(f"\nTotal: {len(entries)} items")
        return lines

    def _list_recursive(
        self,
        dir_path: Path,
        show_hidden: bool,
        max_depth: int,
        current_depth: int,
    ) -> list[str]:
        """Recursively list directory"""
        if current_depth > max_depth:
            return [f"{'  ' * current_depth}[max depth reached]"]

        lines = []

        if current_depth == 0:
            lines.append(f"Directory: {dir_path.absolute()}")
            lines.append("-" * 60)

        try:
            entries = list(dir_path.iterdir())

            # Filter hidden files
            if not show_hidden:
                entries = [e for e in entries if not e.name.startswith(".")]

            # Sort
            entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            prefix = "  " * current_depth

            for entry in entries:
                try:
                    stat = entry.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")

                    if entry.is_dir():
                        lines.append(f"{prefix}[D] {entry.name}/")
                        # Recurse
                        sub_lines = self._list_recursive(
                            entry, show_hidden, max_depth, current_depth + 1
                        )
                        lines.extend(sub_lines)
                    else:
                        size = stat.st_size
                        if size < 1024:
                            size_str = f"{size}B"
                        elif size < 1024 * 1024:
                            size_str = f"{size/1024:.1f}KB"
                        else:
                            size_str = f"{size/1024/1024:.1f}MB"
                        lines.append(f"{prefix}[F] {entry.name} ({size_str}, {mtime})")

                except PermissionError:
                    lines.append(f"{prefix}[?] {entry.name}")

        except PermissionError:
            lines.append(f"{prefix}[permission denied]")

        return lines


class TruncationTool(BaseTool):
    """Truncation Tool - Smart text truncation"""

    name = "truncation"
    description = """Smart truncation of long text.

    Truncation strategies:
    - middle: Keep start and end, truncate middle
    - end: Keep start, truncate end
    - smart: Intelligently preserve important content

    Suitable for:
    - Truncating long tool outputs
    - Compressing context
    - Preserving key information
    """
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Content to truncate",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum length",
                "default": 10000,
            },
            "strategy": {
                "type": "string",
                "enum": ["middle", "end", "smart"],
                "description": "Truncation strategy",
                "default": "smart",
            },
        },
        "required": ["content"],
    }
    timeout = 10
    risk_level = "low"

    async def execute(
        self,
        content: str,
        max_length: int = 10000,
        strategy: str = "smart",
    ) -> str:
        """Truncate content"""
        if len(content) <= max_length:
            return content

        if strategy == "middle":
            return self._truncate_middle(content, max_length)
        elif strategy == "end":
            return self._truncate_end(content, max_length)
        else:
            return self._truncate_smart(content, max_length)

    def _truncate_middle(self, content: str, max_length: int) -> str:
        """Truncate middle"""
        lines = content.split("\n")
        if len(lines) <= 2:
            return content[:max_length]

        # Keep half at start and half at end
        keep_lines = (max_length // 80) // 2
        keep_lines = max(keep_lines, 5)

        head = "\n".join(lines[:keep_lines])
        tail = "\n".join(lines[-keep_lines:])
        omitted = len(lines) - 2 * keep_lines

        return f"{head}\n\n... ({omitted} lines omitted) ...\n\n{tail}"

    def _truncate_end(self, content: str, max_length: int) -> str:
        """Truncate end"""
        lines = content.split("\n")
        result_lines = []
        current_length = 0

        for line in lines:
            if current_length + len(line) + 1 > max_length - 50:
                break
            result_lines.append(line)
            current_length += len(line) + 1

        omitted = len(lines) - len(result_lines)
        return "\n".join(result_lines) + f"\n\n... ({omitted} more lines truncated)"

    def _truncate_smart(self, content: str, max_length: int) -> str:
        """Smart truncation - preserve important content"""
        lines = content.split("\n")

        # Score each line for importance
        scored_lines = []
        for i, line in enumerate(lines):
            score = self._score_line(line, i, len(lines))
            scored_lines.append((i, line, score))

        # Sort by importance
        scored_lines.sort(key=lambda x: x[2], reverse=True)

        # Select lines to keep
        selected_indices = set()
        current_length = 0

        for idx, line, score in scored_lines:
            if current_length + len(line) > max_length - 100:
                break
            selected_indices.add(idx)
            current_length += len(line) + 1

        # Rebuild in original order
        result_lines = []
        last_idx = -1

        for idx in sorted(selected_indices):
            if idx > last_idx + 1:
                result_lines.append(f"... ({idx - last_idx - 1} lines skipped) ...")
            result_lines.append(lines[idx])
            last_idx = idx

        if last_idx < len(lines) - 1:
            result_lines.append(f"... ({len(lines) - last_idx - 1} more lines) ...")

        return "\n".join(result_lines)

    def _score_line(self, line: str, index: int, total: int) -> float:
        """Calculate line importance score"""
        score = 0.0

        # Lines at start and end are more important
        if index < 10:
            score += 10 - index
        elif index > total - 10:
            score += 10 - (total - index)

        # Lines with keywords are more important
        important_keywords = [
            "error", "exception", "def ", "class ", "function ",
            "import ", "return", "async ", "await ", "TODO",
            "FIXME", "NOTE", "###", "##",
        ]
        for kw in important_keywords:
            if kw.lower() in line.lower():
                score += 5

        # Non-empty lines are more important
        if line.strip():
            score += 2

        return score


class FileToolsPlugin(Plugin):
    """File tools plugin"""

    metadata = PluginMetadata(
        id="tool.file_tools",
        name="File Tools",
        version="1.0.0",
        type=PluginType.TOOL,
        description="Provides ls and truncation tools for file operations",
        author="PyAgentForge",
        provides=["tools.file"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._ls_tool: LsTool | None = None
        self._truncation_tool: TruncationTool | None = None

    async def on_plugin_activate(self) -> None:
        """Activate plugin"""
        await super().on_plugin_activate()

        # Create tools
        self._ls_tool = LsTool()
        self._truncation_tool = TruncationTool()

        self.context.logger.info("File tools plugin initialized")

    def get_tools(self) -> List[BaseTool]:
        """Return plugin provided tools"""
        return [self._ls_tool, self._truncation_tool]
