"""
正则表达式解析器

通用回退解析器，支持多种语言
"""

import hashlib
import re
import uuid
from pathlib import Path

from pyagentforge.codesearch.parsers.base import BaseParser
from pyagentforge.codesearch.storage.models import Symbol, SymbolKind
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class RegexParser(BaseParser):
    """正则表达式解析器 - 通用回退方案"""

    # 语言特定的正则模式
    LANGUAGE_PATTERNS = {
        "python": {
            "function": r'(?:def|async\s+def)\s+(\w+)\s*\(',
            "class": r'class\s+(\w+)\s*[:\(]',
            "import": r'(?:import|from)\s+([\w.]+)',
        },
        "typescript": {
            "function": r'(?:function|const|let|var)\s+(\w+)\s*[=\(]',
            "class": r'class\s+(\w+)\s*(?:extends|implements|\{)',
            "interface": r'interface\s+(\w+)\s*\{',
            "import": r'(?:import|require)\s*.*?[\'"]([^\'"]+)[\'"]',
        },
        "javascript": {
            "function": r'(?:function|const|let|var)\s+(\w+)\s*[=\(]',
            "class": r'class\s+(\w+)\s*(?:extends|\{)',
            "import": r'(?:import|require)\s*.*?[\'"]([^\'"]+)[\'"]',
        },
        "go": {
            "function": r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(',
            "struct": r'type\s+(\w+)\s+struct',
            "interface": r'type\s+(\w+)\s+interface',
        },
        "rust": {
            "function": r'(?:pub\s+)?fn\s+(\w+)\s*[<(]',
            "struct": r'(?:pub\s+)?struct\s+(\w+)',
            "enum": r'(?:pub\s+)?enum\s+(\w+)',
            "trait": r'(?:pub\s+)?trait\s+(\w+)',
        },
        "java": {
            "class": r'(?:public|private|protected)?\s*class\s+(\w+)',
            "interface": r'(?:public|private|protected)?\s*interface\s+(\w+)',
            "method": r'(?:public|private|protected)?\s*(?:static\s+)?\w+\s+(\w+)\s*\(',
        },
    }

    # 文件扩展名到语言的映射
    EXTENSION_MAP = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
    }

    @property
    def priority(self) -> int:
        return 10  # 最低优先级，作为回退方案

    def supports_language(self, language: str) -> bool:
        # 支持所有已知语言
        return language.lower() in self.LANGUAGE_PATTERNS

    def detect_language(self, file_path: Path) -> str:
        """根据文件扩展名检测语言"""
        ext = file_path.suffix.lower()
        return self.EXTENSION_MAP.get(ext, "unknown")

    async def parse_file(self, content: str, file_path: Path) -> list[Symbol]:
        """使用正则表达式解析文件"""
        language = self.detect_language(file_path)

        if language not in self.LANGUAGE_PATTERNS:
            return []

        file_hash = hashlib.md5(content.encode()).hexdigest()
        content.split("\n")
        symbols: list[Symbol] = []

        patterns = self.LANGUAGE_PATTERNS[language]

        for kind_name, pattern in patterns.items():
            kind = self._get_symbol_kind(kind_name)
            if not kind:
                continue

            for match in re.finditer(pattern, content, re.MULTILINE):
                # 计算行号
                line_start = content[:match.start()].count("\n") + 1
                line_end = content[:match.end()].count("\n") + 1

                symbol = Symbol(
                    id=str(uuid.uuid4()),
                    name=match.group(1),
                    kind=kind,
                    file_path=str(file_path),
                    line_start=line_start,
                    line_end=line_end,
                    column_start=match.start() - content.rfind("\n", 0, match.start()),
                    column_end=match.end() - content.rfind("\n", 0, match.end()),
                    language=language,
                    file_hash=file_hash,
                )
                symbols.append(symbol)

        return symbols

    def _get_symbol_kind(self, kind_name: str) -> SymbolKind | None:
        """获取符号类型"""
        mapping = {
            "function": SymbolKind.FUNCTION,
            "class": SymbolKind.CLASS,
            "method": SymbolKind.METHOD,
            "interface": SymbolKind.INTERFACE,
            "struct": SymbolKind.STRUCT,
            "enum": SymbolKind.ENUM,
            "import": SymbolKind.IMPORT,
            "trait": SymbolKind.INTERFACE,
        }
        return mapping.get(kind_name)
