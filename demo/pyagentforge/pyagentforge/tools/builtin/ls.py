"""
Ls 工具

列出目录内容
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LsTool(BaseTool):
    """Ls 工具 - 列出目录内容"""

    name = "ls"
    description = """列出目录内容。

返回目录中的文件和子目录列表，包含:
- 文件/目录名称
- 类型 (文件/目录)
- 大小 (文件)
- 修改时间
- 权限

支持递归列出子目录。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "目录路径，默认当前目录",
                "default": ".",
            },
            "recursive": {
                "type": "boolean",
                "description": "是否递归列出子目录",
                "default": False,
            },
            "show_hidden": {
                "type": "boolean",
                "description": "是否显示隐藏文件",
                "default": False,
            },
            "max_depth": {
                "type": "integer",
                "description": "递归最大深度",
                "default": 3,
            },
        },
        "required": [],
    }
    timeout = 30
    risk_level = "low"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        path: str = ".",
        recursive: bool = False,
        show_hidden: bool = False,
        max_depth: int = 3,
    ) -> str:
        """列出目录内容"""
        logger.info(
            "Listing directory",
            extra_data={"path": path, "recursive": recursive},
        )

        dir_path = Path(path)

        # 检查路径权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(dir_path)) == PermissionResult.DENY:
                return f"Error: Access to path '{path}' is denied"

        # 检查目录是否存在
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
            logger.error(
                "Ls error",
                extra_data={"path": path, "error": str(e)},
            )
            return f"Error: {str(e)}"

    def _list_single(
        self,
        dir_path: Path,
        show_hidden: bool,
    ) -> list[str]:
        """列出单个目录"""
        lines = [f"Directory: {dir_path.absolute()}", "-" * 60]

        entries = list(dir_path.iterdir())

        # 过滤隐藏文件
        if not show_hidden:
            entries = [e for e in entries if not e.name.startswith(".")]

        # 排序: 目录在前，然后按名称
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
        """递归列出目录"""
        if current_depth > max_depth:
            return [f"{'  ' * current_depth}[max depth reached]"]

        lines = []

        if current_depth == 0:
            lines.append(f"Directory: {dir_path.absolute()}")
            lines.append("-" * 60)

        try:
            entries = list(dir_path.iterdir())

            # 过滤隐藏文件
            if not show_hidden:
                entries = [e for e in entries if not e.name.startswith(".")]

            # 排序
            entries.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            prefix = "  " * current_depth

            for entry in entries:
                try:
                    stat = entry.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")

                    if entry.is_dir():
                        lines.append(f"{prefix}📁 {entry.name}/")
                        # 递归
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
                        lines.append(f"{prefix}📄 {entry.name} ({size_str}, {mtime})")

                except PermissionError:
                    lines.append(f"{prefix}❓ {entry.name}")

        except PermissionError:
            lines.append(f"{prefix}[permission denied]")

        return lines
