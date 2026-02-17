"""
Edit 工具

精确修改文件内容
"""

import logging
from pathlib import Path
from typing import Any

from pyagentforge.kernel.base_tool import BaseTool

logger = logging.getLogger(__name__)


class EditTool(BaseTool):
    """Edit 工具 - 精确修改文件内容"""

    name = "edit"
    description = """精确替换文件中的文本。

关键要求:
- 必须先读取文件
- old_string 必须与文件内容完全匹配 (包括空白)
- old_string 必须唯一 - 提供足够上下文确保匹配
- 使用 replace_all 进行全局替换

适用于: 重命名变量、更新特定代码块、修复 bug。
避免: 大范围重写 (创建新文件更清晰)。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要编辑的文件的绝对路径",
            },
            "old_string": {
                "type": "string",
                "description": "要替换的文本 (必须精确匹配)",
            },
            "new_string": {
                "type": "string",
                "description": "替换后的文本",
            },
            "replace_all": {
                "type": "boolean",
                "description": "是否替换所有出现",
                "default": False,
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }
    timeout = 30
    risk_level = "medium"

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """编辑文件"""
        logger.info(
            f"Editing file: {file_path}, old_len={len(old_string)}, "
            f"new_len={len(new_string)}, replace_all={replace_all}"
        )

        path = Path(file_path)

        # 检查文件存在
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"

        try:
            # 读取文件
            with open(path, encoding="utf-8") as f:
                content = f.read()

            # 检查 old_string 是否存在
            if old_string not in content:
                return f"Error: old_string not found in file. Make sure it matches exactly (including whitespace)."

            # 检查唯一性 (如果不是 replace_all)
            if not replace_all:
                count = content.count(old_string)
                if count > 1:
                    return f"Error: old_string found {count} times. Provide more context for a unique match, or use replace_all=true."

            # 执行替换
            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            # 写回文件
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"File edited successfully: {file_path}")

            return f"Successfully edited {file_path}"

        except PermissionError:
            return f"Error: Permission denied editing '{file_path}'"
        except Exception as e:
            logger.error(f"Error editing file: {file_path}, error={str(e)}")
            return f"Error editing file: {str(e)}"
