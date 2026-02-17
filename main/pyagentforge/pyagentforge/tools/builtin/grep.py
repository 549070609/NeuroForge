"""
Grep 工具

文件内容搜索
"""

import asyncio
import re
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class GrepTool(BaseTool):
    """Grep 工具 - 文件内容搜索"""

    name = "grep"
    description = """在文件内容中搜索正则表达式模式。

搜索模式:
- 输出 "content" 显示匹配行 (带上下文)
- 输出 "files_with_matches" 只显示文件名
- 输出 "count" 显示匹配计数

支持完整正则表达式语法。
使用 glob 参数过滤文件类型。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "正则表达式搜索模式",
            },
            "path": {
                "type": "string",
                "description": "搜索路径 (文件或目录)",
                "default": ".",
            },
            "glob": {
                "type": "string",
                "description": "文件类型过滤 (如 *.py)",
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_with_matches", "count"],
                "default": "content",
                "description": "输出模式",
            },
            "-i": {
                "type": "boolean",
                "default": False,
                "description": "忽略大小写",
            },
            "-C": {
                "type": "integer",
                "description": "上下文行数",
            },
            "-n": {
                "type": "boolean",
                "default": True,
                "description": "显示行号",
            },
            "head_limit": {
                "type": "integer",
                "description": "最大输出数量",
            },
        },
        "required": ["pattern"],
    }
    timeout = 60
    risk_level = "low"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        glob: str | None = None,
        output_mode: str = "content",
        **kwargs: Any,
    ) -> str:
        """执行 grep 搜索"""
        ignore_case = kwargs.get("-i", False)
        context = kwargs.get("-C", 0)
        show_line_numbers = kwargs.get("-n", True)
        head_limit = kwargs.get("head_limit", 0)

        logger.info(
            "Executing grep",
            extra_data={
                "pattern": pattern,
                "path": path,
                "glob": glob,
                "output_mode": output_mode,
            },
        )

        search_path = Path(path)

        # 检查路径权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(search_path)) == PermissionResult.DENY:
                return f"Error: Access to path '{path}' is denied"

        try:
            # 编译正则表达式
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)

            # 收集文件
            if search_path.is_file():
                files = [search_path]
            else:
                if glob:
                    files = list(search_path.rglob(glob))
                else:
                    files = list(search_path.rglob("*"))
                files = [f for f in files if f.is_file() and not f.name.startswith(".")]

            # 执行搜索
            results: list[dict[str, Any]] = []

            for file_path in files[:1000]:  # 限制文件数量
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()

                    matches_in_file = []

                    for i, line in enumerate(lines):
                        if regex.search(line):
                            matches_in_file.append({
                                "line_number": i + 1,
                                "line": line.rstrip("\n"),
                            })

                    if matches_in_file:
                        if output_mode == "files_with_matches":
                            results.append({"file": str(file_path)})
                        elif output_mode == "count":
                            results.append({
                                "file": str(file_path),
                                "count": len(matches_in_file),
                            })
                        else:
                            for match in matches_in_file:
                                # 添加上下文
                                context_lines = []
                                if context > 0:
                                    start = max(0, match["line_number"] - context - 1)
                                    end = min(len(lines), match["line_number"] + context)
                                    for j in range(start, end):
                                        context_lines.append({
                                            "line_number": j + 1,
                                            "line": lines[j].rstrip("\n"),
                                            "is_match": j + 1 == match["line_number"],
                                        })

                                results.append({
                                    "file": str(file_path),
                                    "line_number": match["line_number"],
                                    "line": match["line"],
                                    "context": context_lines if context_lines else None,
                                })

                except Exception:
                    continue

            # 应用 head_limit
            if head_limit > 0:
                results = results[:head_limit]

            # 格式化输出
            if not results:
                return f"No matches found for pattern: {pattern}"

            if output_mode == "files_with_matches":
                lines = [r["file"] for r in results]
                return "\n".join(lines)

            elif output_mode == "count":
                lines = [f"{r['file']}: {r['count']}" for r in results]
                return "\n".join(lines)

            else:
                output_lines = []
                for r in results:
                    if r.get("context"):
                        for ctx in r["context"]:
                            prefix = ">" if ctx["is_match"] else " "
                            output_lines.append(
                                f"{prefix} {r['file']}:{ctx['line_number']}: {ctx['line']}"
                            )
                        output_lines.append("--")
                    else:
                        output_lines.append(
                            f"{r['file']}:{r['line_number']}: {r['line']}"
                        )

                return "\n".join(output_lines)

        except re.error as e:
            return f"Error: Invalid regex pattern: {str(e)}"
        except Exception as e:
            logger.error(
                "Grep error",
                extra_data={"pattern": pattern, "error": str(e)},
            )
            return f"Error: {str(e)}"
