"""
LSP 桥接器

连接 CodeSearch 和 LSP 服务
"""

from pathlib import Path
from typing import Any
from uuid import uuid4

from pyagentforge.codesearch.storage.models import Symbol, SymbolKind
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class LSPBridge:
    """LSP 服务桥接器"""

    # LSP SymbolKind 到内部 SymbolKind 的映射
    KIND_MAPPING = {
        1: SymbolKind.FILE,
        2: SymbolKind.MODULE,
        3: SymbolKind.NAMESPACE,
        4: SymbolKind.PACKAGE,
        5: SymbolKind.CLASS,
        6: SymbolKind.METHOD,
        7: SymbolKind.PROPERTY,
        8: SymbolKind.FIELD,
        9: SymbolKind.CONSTRUCTOR,
        10: SymbolKind.ENUM,
        11: SymbolKind.INTERFACE,
        12: SymbolKind.FUNCTION,
        13: SymbolKind.VARIABLE,
        14: SymbolKind.CONSTANT,
        15: SymbolKind.STRUCT,
        16: SymbolKind.ENUM,
        17: SymbolKind.FIELD,
        18: SymbolKind.INTERFACE,
        19: SymbolKind.FUNCTION,
        20: SymbolKind.VARIABLE,
        21: SymbolKind.CLASS,
        22: SymbolKind.METHOD,
        23: SymbolKind.PROPERTY,
        24: SymbolKind.FIELD,
        25: SymbolKind.CONSTANT,
        26: SymbolKind.STRUCT,
    }

    def __init__(self, lsp_manager: Any = None) -> None:
        """
        初始化 LSP 桥接器

        Args:
            lsp_manager: LSP 管理器实例
        """
        self.lsp_manager = lsp_manager

    @property
    def is_available(self) -> bool:
        """检查 LSP 服务是否可用"""
        return self.lsp_manager is not None

    async def search_symbols(
        self,
        query: str,
        language: str | None = None,
    ) -> list[Symbol]:
        """
        使用 LSP workspace/symbol 搜索符号

        Args:
            query: 搜索查询
            language: 语言过滤（可选）

        Returns:
            符号列表
        """
        if not self.is_available:
            return []

        try:
            # 调用 LSP 管理器的 workspace_symbols 方法
            lsp_symbols = await self.lsp_manager.workspace_symbols(query)

            if not lsp_symbols:
                return []

            symbols = []
            for lsp_symbol in lsp_symbols:
                symbol = self._convert_symbol(lsp_symbol, language)
                if symbol:
                    symbols.append(symbol)

            return symbols

        except Exception as e:
            logger.warning(
                "LSP workspace_symbols failed",
                extra_data={"error": str(e)},
            )
            return []

    async def get_document_symbols(
        self,
        file_path: Path,
    ) -> list[Symbol]:
        """
        获取文档符号

        Args:
            file_path: 文件路径

        Returns:
            符号列表
        """
        if not self.is_available:
            return []

        try:
            symbols = await self.lsp_manager.document_symbols(file_path)

            if not symbols:
                return []

            result = []
            for lsp_symbol in symbols:
                symbol = self._convert_document_symbol(lsp_symbol, str(file_path))
                if symbol:
                    result.append(symbol)

            return result

        except Exception as e:
            logger.warning(
                "LSP document_symbols failed",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

    def _convert_symbol(
        self,
        lsp_symbol: Any,
        language: str | None = None,
    ) -> Symbol | None:
        """将 LSP SymbolInformation 转换为内部 Symbol"""
        try:
            kind = self.KIND_MAPPING.get(lsp_symbol.kind, SymbolKind.VARIABLE)

            # 获取文件路径
            file_path = lsp_symbol.location.uri
            if file_path.startswith("file://"):
                file_path = file_path[7:]

            return Symbol(
                id=str(uuid4()),
                name=lsp_symbol.name,
                kind=kind,
                file_path=file_path,
                line_start=lsp_symbol.location.range.start.line + 1,
                line_end=lsp_symbol.location.range.end.line + 1,
                column_start=lsp_symbol.location.range.start.character,
                column_end=lsp_symbol.location.range.end.character,
                language=language or self._detect_language(file_path),
                file_hash="",
                parent_scope=lsp_symbol.containerName if hasattr(lsp_symbol, "containerName") else None,
            )
        except Exception as e:
            logger.debug(f"Failed to convert LSP symbol: {e}")
            return None

    def _convert_document_symbol(
        self,
        lsp_symbol: Any,
        file_path: str,
    ) -> Symbol | None:
        """将 LSP DocumentSymbol 转换为内部 Symbol"""
        try:
            kind = self.KIND_MAPPING.get(lsp_symbol.kind, SymbolKind.VARIABLE)

            return Symbol(
                id=str(uuid4()),
                name=lsp_symbol.name,
                kind=kind,
                file_path=file_path,
                line_start=lsp_symbol.range.start.line + 1,
                line_end=lsp_symbol.range.end.line + 1,
                column_start=lsp_symbol.range.start.character,
                column_end=lsp_symbol.range.end.character,
                language=self._detect_language(file_path),
                file_hash="",
                parent_scope=None,
                docstring=lsp_symbol.detail if hasattr(lsp_symbol, "detail") else None,
            )
        except Exception as e:
            logger.debug(f"Failed to convert document symbol: {e}")
            return None

    def _detect_language(self, file_path: str) -> str:
        """根据文件扩展名检测语言"""
        ext_map = {
            ".py": "python",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".js": "javascript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
        }
        ext = Path(file_path).suffix.lower()
        return ext_map.get(ext, "")
