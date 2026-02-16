"""
Write 工具

创建或覆盖文件
"""

from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class WriteTool(BaseTool):
    """Write 工具 - 创建或覆盖文件"""

    name = "write"
    description = """创建或覆盖文件。

重要:
- 对于已存在的文件，必须先读取
- 总是优先编辑现有文件而非创建新文件
- 不要主动创建文档文件(.md, README)
- 不要使用表情符号除非用户明确要求

文件会被自动创建必要的父目录。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要写入的文件的绝对路径",
            },
            "content": {
                "type": "string",
                "description": "要写入文件的内容",
            },
        },
        "required": ["file_path", "content"],
    }
    timeout = 30
    risk_level = "medium"

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        file_path: str,
        content: str,
    ) -> str:
        """写入文件"""
        logger.info(
            "Writing file",
            extra_data={"file_path": file_path, "content_length": len(content)},
        )

        path = Path(file_path)

        # 检查路径权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(path)) == PermissionResult.DENY:
                return f"Error: Access to path '{file_path}' is denied"

        try:
            # 创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(
                "File written successfully",
                extra_data={"file_path": file_path},
            )

            return f"File written successfully: {file_path}"

        except PermissionError:
            return f"Error: Permission denied writing to '{file_path}'"
        except Exception as e:
            logger.error(
                "Error writing file",
                extra_data={"file_path": file_path, "error": str(e)},
            )
            return f"Error writing file: {str(e)}"
