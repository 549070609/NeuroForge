"""
MultiEdit 工具

同时编辑多个文件
"""

from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class MultiEditTool(BaseTool):
    """MultiEdit 工具 - 同时编辑多个文件"""

    name = "multiedit"
    description = """同时编辑多个文件。

使用场景:
- 批量重命名
- 跨文件重构
- 批量更新配置

每个编辑操作独立验证，失败不影响其他操作。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "edits": {
                "type": "array",
                "description": "编辑操作列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                        "replace_all": {"type": "boolean"},
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            },
        },
        "required": ["edits"],
    }
    timeout = 60
    risk_level = "medium"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.permission_checker = permission_checker

    async def execute(self, edits: list[dict[str, Any]]) -> str:
        """执行多文件编辑"""
        logger.info(
            "Executing multi-edit",
            extra_data={"num_edits": len(edits)},
        )

        results = []

        for i, edit in enumerate(edits):
            file_path = edit.get("file_path")
            old_string = edit.get("old_string")
            new_string = edit.get("new_string")
            replace_all = edit.get("replace_all", False)

            if not all([file_path, old_string is not None, new_string is not None]):
                results.append(f"[{i+1}] Error: Missing required fields")
                continue

            result = await self._edit_file(
                file_path, old_string, new_string, replace_all
            )
            results.append(f"[{i+1}] {file_path}: {result}")

        success = sum(1 for r in results if "Error" not in r)
        failed = len(results) - success

        summary = f"\nMulti-edit complete: {success} succeeded, {failed} failed"
        return "\n".join(results) + summary

    async def _edit_file(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool,
    ) -> str:
        """编辑单个文件"""
        path = Path(file_path)

        # 检查权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(path)) == PermissionResult.DENY:
                return f"Error: Access denied to '{file_path}'"

        if not path.exists():
            return f"Error: File not found '{file_path}'"

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            if old_string not in content:
                return f"Error: old_string not found"

            count = content.count(old_string)
            if count > 1 and not replace_all:
                return f"Error: Found {count} matches, use replace_all=true"

            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Success ({count} replacement{'s' if count > 1 else ''})"

        except Exception as e:
            return f"Error: {str(e)}"
