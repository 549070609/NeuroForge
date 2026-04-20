"""
CodeSearch 模块

增强版代码搜索, 支持 AST 解析、增量索引、高级查询语法
"""

from pyagentforge.codesearch.config import CodeSearchConfig
from pyagentforge.codesearch.indexers.symbol_indexer import SymbolIndexer
from pyagentforge.codesearch.parsers.base import BaseParser, ParserRegistry
from pyagentforge.codesearch.parsers.python_parser import PythonParser
from pyagentforge.codesearch.parsers.regex_parser import RegexParser
from pyagentforge.codesearch.query.executor import QueryExecutor
from pyagentforge.codesearch.query.parser import QueryParser
from pyagentforge.codesearch.storage.database import CodeSearchDatabase
from pyagentforge.codesearch.storage.models import FileHash, Symbol, SymbolKind
from pyagentforge.codesearch.tool import CodeSearchTool, create_codesearch_tool

__all__ = [
    # 核心类
    "CodeSearchTool",
    "CodeSearchDatabase",
    "SymbolIndexer",
    "ParserRegistry",
    "BaseParser",
    # 配置
    "CodeSearchConfig",
    # 查询
    "QueryParser",
    "QueryExecutor",
    # 数据模型
    "Symbol",
    "SymbolKind",
    "FileHash",
    # 工厂函数
    "create_codesearch_tool",
    # 解析器
    "PythonParser",
    "RegexParser",
]
