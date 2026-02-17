"""
CodeSearch 数据模型

定义符号和文件哈希的数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SymbolKind(str, Enum):
    """符号类型"""
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    MODULE = "module"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    PROPERTY = "property"
    FIELD = "field"


@dataclass
class Symbol:
    """代码符号"""
    id: str                              # UUID
    name: str                            # 符号名称
    kind: SymbolKind                     # 符号类型
    file_path: str                       # 文件路径
    line_start: int                      # 起始行 (1-indexed)
    line_end: int                        # 结束行
    column_start: int                    # 起始列 (0-indexed)
    column_end: int                      # 结束列
    language: str                        # 语言
    file_hash: str                       # 文件内容哈希
    parent_scope: str | None = None      # 父作用域 (类名/模块名)
    docstring: str | None = None         # 文档字符串
    signature: str | None = None         # 函数签名
    metadata: dict[str, Any] = field(default_factory=dict)  # 额外元数据
    indexed_at: datetime = field(default_factory=lambda: datetime.utcnow())


@dataclass
class FileHash:
    """文件哈希记录（用于增量索引）"""
    file_path: str                       # 文件路径
    content_hash: str                    # 内容哈希 (MD5)
    file_size: int                       # 文件大小
    modified_time: float                 # 修改时间戳
    symbol_count: int = 0                # 符号数量
    indexed_at: datetime = field(default_factory=lambda: datetime.utcnow())
