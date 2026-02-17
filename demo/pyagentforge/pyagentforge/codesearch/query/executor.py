"""
查询执行器

执行查询 AST 并返回结果
"""

from pathlib import Path
from typing import Any

from pyagentforge.codesearch.query.nodes import (
    QueryNode,
    KindFilter,
    NameMatch,
    AndExpr,
    OrExpr,
    NotExpr,
    LanguageFilter,
    FileFilter,
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
        执行查询 AST

        Args:
            node: 查询 AST 根节点
            path: 搜索路径
            file_pattern: 文件模式
            limit: 最大结果数

        Returns:
            匹配的符号列表
        """
        # 先从数据库获取候选符号
        candidates = await self._get_candidates(node, path, file_pattern, limit * 2)

        # 在内存中过滤
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
        """从数据库获取候选符号"""
        # 提取查询中的名称模式
        name = self._extract_name_pattern(node)
        kind = self._extract_kind(node)

        return await self.db.search_symbols(
            name=name,
            kind=kind,
            file_pattern=path if path != "." else None,
            limit=limit,
        )

    def _extract_name_pattern(self, node: QueryNode) -> str | None:
        """从查询 AST 提取名称模式"""
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
        """从查询 AST 提取符号类型"""
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
        """匹配名称"""
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
        """匹配符号类型"""
        if symbol.kind != node.kind:
            return False

        if node.pattern == "*":
            return True

        import fnmatch
        return fnmatch.fnmatch(symbol.name.lower(), node.pattern.lower())
