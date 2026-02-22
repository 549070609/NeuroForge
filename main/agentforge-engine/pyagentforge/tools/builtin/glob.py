"""
Glob 工具

文件模式匹配搜索
"""

import fnmatch
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class GlobTool(BaseTool):
    """Glob 工具 - 文件模式匹配搜索"""

    name = "glob"
    description = """使用 glob 模式搜索文件。

快速查找匹配特定模式的文件:
- "**/*.js" - 所有 JS 文件
- "src/**/*.ts" - src 目录下的 TS 文件
- "*.py" - 当前目录的 Python 文件

支持 glob 模式如 **, *, ?。
结果按修改时间排序。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob 模式 (如 **/*.py)",
            },
            "path": {
                "type": "string",
                "description": "搜索目录，默认当前目录",
                "default": ".",
            },
        },
        "required": ["pattern"],
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
        pattern: str,
        path: str = ".",
    ) -> str:
        """执行 glob 搜索"""
        logger.info(
            "Executing glob",
            extra_data={"pattern": pattern, "path": path},
        )

        search_path = Path(path)

        # 检查路径权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(search_path)) == PermissionResult.DENY:
                return f"Error: Access to path '{path}' is denied"

        try:
            # 使用 rglob 处理递归模式
            if "**" in pattern:
                matches = list(search_path.rglob(pattern.replace("**/", "").replace("**", "*")))
            else:
                matches = list(search_path.glob(pattern))

            # 过滤掉目录，只保留文件
            matches = [m for m in matches if m.is_file()]

            # 按修改时间排序
            matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            if not matches:
                return f"No files matching pattern: {pattern}"

            # 格式化输出
            lines = [f"Found {len(matches)} files matching '{pattern}':"]
            for match in matches[:100]:  # 限制输出数量
                rel_path = match.relative_to(search_path) if search_path != Path(".") else match
                lines.append(f"  {rel_path}")

            if len(matches) > 100:
                lines.append(f"  ... and {len(matches) - 100} more")

            return "\n".join(lines)

        except Exception as e:
            logger.error(
                "Glob error",
                extra_data={"pattern": pattern, "error": str(e)},
            )
            return f"Error: {str(e)}"
