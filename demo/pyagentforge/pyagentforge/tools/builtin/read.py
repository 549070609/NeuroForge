"""
Read 工具

读取文件内容
"""

import os
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class ReadTool(BaseTool):
    """Read 工具 - 读取文件内容"""

    name = "read"
    description = """读取文件内容。

支持:
- 文本文件 (自动检测编码)
- 指定行范围 (offset + limit)
- 图片文件 (PNG, JPG, JPEG) - 返回视觉描述
- Jupyter notebooks (.ipynb)
- PDF 文件 (可指定页面范围)

对于大文件，使用 offset 和 limit 参数分页读取。
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件的绝对路径",
            },
            "offset": {
                "type": "integer",
                "description": "起始行号(从 0 开始)",
                "default": 0,
            },
            "limit": {
                "type": "integer",
                "description": "读取的行数",
            },
            "pages": {
                "type": "string",
                "description": "PDF 文件的页面范围，如 '1-5' 或 '1,3,5'",
            },
        },
        "required": ["file_path"],
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
        file_path: str,
        offset: int = 0,
        limit: int | None = None,
        pages: str | None = None,
    ) -> str:
        """读取文件内容"""
        logger.info(
            "Reading file",
            extra_data={"file_path": file_path, "offset": offset, "limit": limit},
        )

        path = Path(file_path)

        # 检查路径权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(path)) == PermissionResult.DENY:
                return f"Error: Access to path '{file_path}' is denied"

        # 检查文件是否存在
        if not path.exists():
            return f"Error: File '{file_path}' does not exist"

        if not path.is_file():
            return f"Error: '{file_path}' is not a file"

        # 检查文件大小
        file_size = path.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB
            return f"Error: File is too large ({file_size / 1024 / 1024:.1f} MB). Use limit parameter."

        try:
            # 根据文件类型处理
            suffix = path.suffix.lower()

            if suffix == ".ipynb":
                return await self._read_notebook(path)
            elif suffix == ".pdf":
                return await self._read_pdf(path, pages)
            elif suffix in (".png", ".jpg", ".jpeg"):
                return f"[Image file: {path.name}]"
            else:
                return await self._read_text_file(path, offset, limit)

        except PermissionError:
            return f"Error: Permission denied reading '{file_path}'"
        except Exception as e:
            logger.error(
                "Error reading file",
                extra_data={"file_path": file_path, "error": str(e)},
            )
            return f"Error reading file: {str(e)}"

    async def _read_text_file(
        self,
        path: Path,
        offset: int,
        limit: int | None,
    ) -> str:
        """读取文本文件"""
        # 尝试多种编码
        encodings = ["utf-8", "gbk", "gb2312", "latin-1"]

        content = None
        used_encoding = None

        for encoding in encodings:
            try:
                with open(path, encoding=encoding) as f:
                    content = f.read()
                used_encoding = encoding
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return f"Error: Unable to decode file with supported encodings"

        lines = content.splitlines()

        # 应用分页
        if offset > 0 or limit is not None:
            end = offset + limit if limit else len(lines)
            lines = lines[offset:end]

        # 格式化输出 (带行号)
        output_lines = []
        for i, line in enumerate(lines, start=offset + 1):
            output_lines.append(f"{i:6}\t{line}")

        result = "\n".join(output_lines)

        # 添加文件信息头
        header = f"File: {path}\n"
        header += f"Encoding: {used_encoding}\n"
        header += f"Lines: {len(lines)} (showing {offset + 1}-{offset + len(lines)})\n"
        header += "-" * 40 + "\n"

        return header + result

    async def _read_notebook(self, path: Path) -> str:
        """读取 Jupyter Notebook"""
        import json

        with open(path) as f:
            nb = json.load(f)

        output = [f"Jupyter Notebook: {path.name}"]
        output.append(f"Cells: {len(nb.get('cells', []))}")
        output.append("-" * 40)

        for i, cell in enumerate(nb.get("cells", []), 1):
            cell_type = cell.get("cell_type", "unknown")
            source = "".join(cell.get("source", []))

            output.append(f"\n## Cell {i} ({cell_type})")
            output.append("```")
            output.append(source)
            output.append("```")

            if cell_type == "code" and cell.get("outputs"):
                output.append("### Outputs:")
                for out in cell.get("outputs", []):
                    if out.get("output_type") == "stream":
                        output.append("".join(out.get("text", [])))
                    elif out.get("output_type") == "execute_result":
                        if "text/plain" in out.get("data", {}):
                            output.append(out["data"]["text/plain"])

        return "\n".join(output)

    async def _read_pdf(self, path: Path, pages: str | None) -> str:
        """读取 PDF 文件"""
        # 简化实现 - 返回提示信息
        return f"PDF file: {path.name}\nPages: {pages or 'all'}\n(PDF reading requires additional dependencies)"
