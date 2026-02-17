"""
查询 AST 节点定义
"""

from dataclasses import dataclass

from pyagentforge.codesearch.storage.models import SymbolKind


@dataclass
class QueryNode:
    """查询 AST 节点基类"""
    pass


@dataclass
class KindFilter(QueryNode):
    """类型过滤"""
    kind: SymbolKind
    pattern: str


@dataclass
class NameMatch(QueryNode):
    """名称匹配"""
    pattern: str
    is_wildcard: bool = False
    is_exact: bool = False


@dataclass
class AndExpr(QueryNode):
    """AND 表达式"""
    left: QueryNode
    right: QueryNode


@dataclass
class OrExpr(QueryNode):
    """OR 表达式"""
    left: QueryNode
    right: QueryNode


@dataclass
class NotExpr(QueryNode):
    """NOT 表达式"""
    operand: QueryNode


@dataclass
class LanguageFilter(QueryNode):
    """语言过滤"""
    language: str
    operand: QueryNode


@dataclass
class FileFilter(QueryNode):
    """文件路径过滤"""
    pattern: str
    operand: QueryNode
