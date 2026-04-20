"""
鏌ヨ鎵ц鍣?

鎵ц鏌ヨ AST 骞惰繑鍥炵粨鏋?
"""

from pathlib import Path

from pyagentforge.codesearch.query.nodes import (
    AndExpr,
    FileFilter,
    KindFilter,
    LanguageFilter,
    NameMatch,
    NotExpr,
    OrExpr,
    QueryNode,
)
from pyagentforge.codesearch.storage.database import CodeSearchDatabase
from pyagentforge.codesearch.storage.models import Symbol, SymbolKind
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class QueryExecutor:
    """查询执行器"""

    def __init__(self, db: CodeSearchDatabase) -> None:
        self.db = db

    async def execute(
        self,
        node: QueryNode,
        path: str = ".",
        file_pattern: str = "*",
        limit: int = 100,
    ) -> list[Symbol]:
        """
        鎵ц鏌ヨ AST

        Args:
            node: 鏌ヨ AST 鏍硅妭鐐?
            path: 鎼滅储璺緞
            file_pattern: 鏂囦欢妯紡
            limit: 鏈€澶х粨鏋滄暟

        Returns:
            鍖归厤鐨勭鍙峰垪琛?
        """
        #
        candidates = await self._get_candidates(node, path, file_pattern, limit * 2)

        # 鍦ㄥ唴瀛樹腑杩囨护
        results = []
        for symbol in candidates:
            if self._matches(symbol, node):
                results.append(symbol)
                if len(results) >= limit:
                    break

        return results

    async def _get_candidates(
        self,
        node: QueryNode,
        path: str,
        file_pattern: str,
        limit: int,
    ) -> list[Symbol]:
        """获取候选符号"""
        #
        name = self._extract_name_pattern(node)
        kind = self._extract_kind(node)
        effective_pattern = file_pattern
        if path != ".":
            effective_pattern = str(Path(path) / file_pattern)

        return await self.db.search_symbols(
            name=name,
            kind=kind,
            file_pattern=effective_pattern if effective_pattern != "*" else None,
            limit=limit,
        )

    def _extract_name_pattern(self, node: QueryNode) -> str | None:
        """"""
        if isinstance(node, NameMatch):
            if node.is_wildcard:
                return node.pattern.rstrip("*")
            return node.pattern
        elif isinstance(node, KindFilter):
            return node.pattern if node.pattern != "*" else None
        elif isinstance(node, AndExpr):
            return self._extract_name_pattern(node.left) or self._extract_name_pattern(node.right)
        elif isinstance(node, OrExpr):
            return self._extract_name_pattern(node.left)
        return None

    def _extract_kind(self, node: QueryNode) -> SymbolKind | None:
        """浠庢煡璇?AST 鎻愬彇绗﹀彿绫诲瀷"""
        if isinstance(node, KindFilter):
            return node.kind
        elif isinstance(node, AndExpr):
            return self._extract_kind(node.left) or self._extract_kind(node.right)
        elif isinstance(node, OrExpr):
            return self._extract_kind(node.left)
        return None

    def _matches(self, symbol: Symbol, node: QueryNode) -> bool:
        """检查符号是否匹配查询节点"""
        if isinstance(node, NameMatch):
            return self._match_name(symbol.name, node)
        elif isinstance(node, KindFilter):
            return self._match_kind(symbol, node)
        elif isinstance(node, AndExpr):
            return self._matches(symbol, node.left) and self._matches(symbol, node.right)
        elif isinstance(node, OrExpr):
            return self._matches(symbol, node.left) or self._matches(symbol, node.right)
        elif isinstance(node, NotExpr):
            return not self._matches(symbol, node.operand)
        elif isinstance(node, LanguageFilter):
            return symbol.language.lower() == node.language.lower() and self._matches(symbol, node.operand)
        elif isinstance(node, FileFilter):
            return node.pattern.lower() in symbol.file_path.lower() and self._matches(symbol, node.operand)
        return True

    def _match_name(self, name: str, node: NameMatch) -> bool:
        """鍖归厤鍚嶇О"""
        import fnmatch

        pattern = node.pattern
        target = name if not node.is_exact else name.lower()
        search_pattern = pattern if not node.is_exact else pattern.lower()

        if node.is_wildcard:
            return fnmatch.fnmatch(target, search_pattern)
        elif node.is_exact:
            return target == search_pattern
        else:
            return search_pattern.lower() in target.lower()

    def _match_kind(self, symbol: Symbol, node: KindFilter) -> bool:
        """鍖归厤绗﹀彿绫诲瀷"""
        if symbol.kind != node.kind:
            return False

        if node.pattern == "*":
            return True

        import fnmatch
        return fnmatch.fnmatch(symbol.name.lower(), node.pattern.lower())


