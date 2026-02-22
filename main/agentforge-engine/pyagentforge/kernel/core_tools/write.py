"""
Write 工具

创建或覆盖文件
"""

import logging
from pathlib import Path
from typing import Any

from pyagentforge.kernel.base_tool import BaseTool

logger = logging.getLogger(__name__)


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

    async def execute(
        self,
        file_path: str,
        content: str,
    ) -> str:
        """写入文件"""
        logger.info(f"Writing file: {file_path}, content_len={len(content)}")

        path = Path(file_path)

        try:
            # 创建父目录
            path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"File written successfully: {file_path}")

            return f"File written successfully: {file_path}"

        except PermissionError:
            return f"Error: Permission denied writing to '{file_path}'"
        except Exception as e:
            logger.error(f"Error writing file: {file_path}, error={str(e)}")
            return f"Error writing file: {str(e)}"
