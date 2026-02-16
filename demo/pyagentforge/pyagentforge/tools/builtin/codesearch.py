"""
CodeSearch 工具

语义代码搜索
"""

import re
from pathlib import Path
from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.permission import PermissionChecker
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CodeSearchTool(BaseTool):
    """CodeSearch 工具 - 语义代码搜索"""

    name = "codesearch"
    description = """语义代码搜索。

比 grep 更智能的代码搜索:
- 理解代码结构
- 匹配函数/类定义
- 支持模糊匹配
- 按上下文过滤

搜索模式:
- "function:xxx" - 搜索函数定义
- "class:xxx" - 搜索类定义
- "variable:xxx" - 搜索变量
- "import:xxx" - 搜索导入
- "xxx" - 通用搜索
"""
    parameters_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索查询",
            },
            "path": {
                "type": "string",
                "description": "搜索路径",
                "default": ".",
            },
            "file_pattern": {
                "type": "string",
                "description": "文件模式 (如 *.py)",
                "default": "*",
            },
            "context_lines": {
                "type": "integer",
                "description": "上下文行数",
                "default": 3,
            },
            "max_results": {
                "type": "integer",
                "description": "最大结果数",
                "default": 50,
            },
        },
        "required": ["query"],
    }
    timeout = 60
    risk_level = "low"

    # 语言特定的模式
    LANGUAGE_PATTERNS = {
        "python": {
            "function": r'(?:def|async\s+def)\s+{name}\s*\(',
            "class": r'class\s+{name}\s*[:\(]',
            "variable": r'{name}\s*=',
            "import": r'(?:import|from)\s+.*{name}',
        },
        "typescript": {
            "function": r'(?:function|const|let|var)\s+{name}\s*[=\(]',
            "class": r'class\s+{name}\s*(?:extends|implements|\{)',
            "variable": r'(?:const|let|var)\s+{name}\s*=',
            "import": r'(?:import|require)\s*.*{name}',
        },
        "go": {
            "function": r'func\s+(?:\([^)]+\)\s+)?{name}\s*\(',
            "struct": r'type\s+{name}\s+struct',
            "variable": r'{name}\s*:=',
            "import": r'import\s+.*{name}',
        },
        "rust": {
            "function": r'fn\s+{name}\s*[<(]',
            "struct": r'struct\s+{name}',
            "enum": r'enum\s+{name}',
            "variable": r'let\s+(?:mut\s+)?{name}\s*=',
        },
    }

    def __init__(
        self,
        permission_checker: PermissionChecker | None = None,
    ) -> None:
        self.permission_checker = permission_checker

    async def execute(
        self,
        query: str,
        path: str = ".",
        file_pattern: str = "*",
        context_lines: int = 3,
        max_results: int = 50,
    ) -> str:
        """执行代码搜索"""
        logger.info(
            "Executing code search",
            extra_data={"query": query, "path": path},
        )

        search_path = Path(path)

        # 检查权限
        if self.permission_checker:
            from pyagentforge.tools.permission import PermissionResult

            if self.permission_checker.check_path(str(search_path)) == PermissionResult.DENY:
                return f"Error: Access to path '{path}' is denied"

        # 解析查询
        search_type, search_term = self._parse_query(query)

        # 收集文件
        if search_path.is_file():
            files = [search_path]
        else:
            files = list(search_path.rglob(file_pattern))
            files = [f for f in files if f.is_file() and not self._should_ignore(f)]

        # 搜索
        results = []

        for file_path in files[:500]:  # 限制文件数量
            try:
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.split("\n")

                language = self._detect_language(file_path)

                for i, line in enumerate(lines):
                    if self._match_line(line, search_type, search_term, language):
                        context = self._get_context(lines, i, context_lines)
                        results.append({
                            "file": str(file_path),
                            "line_number": i + 1,
                            "line": line.strip(),
                            "context": context,
                        })

                        if len(results) >= max_results:
                            break

            except Exception:
                continue

            if len(results) >= max_results:
                break

        # 格式化输出
        if not results:
            return f"No results found for: {query}"

        output = [f"Code search results for '{query}':", "=" * 50]

        for r in results:
            output.append(f"\n📁 {r['file']}:{r['line_number']}")
            output.append(f"   {r['line']}")
            if r['context']:
                for ctx in r['context']:
                    prefix = "→" if ctx['is_match'] else " "
                    output.append(f"  {prefix} {ctx['line_number']:4}: {ctx['line']}")

        output.append(f"\n{'=' * 50}")
        output.append(f"Total: {len(results)} results")

        return "\n".join(output)

    def _parse_query(self, query: str) -> tuple[str | None, str]:
        """解析查询类型"""
        # 检查特殊前缀
        prefixes = ["function:", "class:", "variable:", "import:", "struct:", "enum:"]
        for prefix in prefixes:
            if query.startswith(prefix):
                return prefix[:-1], query[len(prefix):]

        # 通用搜索
        return None, query

    def _detect_language(self, file_path: Path) -> str:
        """检测文件语言"""
        ext = file_path.suffix.lower()
        mapping = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "typescript",
            ".jsx": "typescript",
            ".go": "go",
            ".rs": "rust",
        }
        return mapping.get(ext, "generic")

    def _match_line(
        self,
        line: str,
        search_type: str | None,
        search_term: str,
        language: str,
    ) -> bool:
        """检查行是否匹配"""
        if search_type is None:
            # 通用搜索
            return search_term.lower() in line.lower()

        # 获取语言特定模式
        patterns = self.LANGUAGE_PATTERNS.get(language, {})
        pattern_template = patterns.get(search_type)

        if pattern_template:
            # 使用精确模式
            pattern = pattern_template.format(name=re.escape(search_term))
            return bool(re.search(pattern, line))

        # 回退到简单匹配
        return search_term.lower() in line.lower()

    def _get_context(
        self,
        lines: list[str],
        match_idx: int,
        context_lines: int,
    ) -> list[dict]:
        """获取上下文"""
        context = []
        start = max(0, match_idx - context_lines)
        end = min(len(lines), match_idx + context_lines + 1)

        for i in range(start, end):
            context.append({
                "line_number": i + 1,
                "line": lines[i].rstrip(),
                "is_match": i == match_idx,
            })

        return context

    def _should_ignore(self, path: Path) -> bool:
        """检查是否应该忽略"""
        ignore_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            "venv",
            ".venv",
            "dist",
            "build",
            ".idea",
            ".vscode",
        }
        return any(part in ignore_dirs for part in path.parts)
