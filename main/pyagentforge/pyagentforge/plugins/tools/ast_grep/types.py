"""
AST-Grep 插件类型定义
"""

from dataclasses import dataclass
from typing import List, Optional

from .constants import CLI_LANGUAGES


# 语言类型
CliLanguage = str  # CLI_LANGUAGES 中的值


@dataclass
class Position:
    """位置信息"""
    line: int
    column: int


@dataclass
class Range:
    """范围信息"""
    start: Position
    end: Position


@dataclass
class SgMatch:
    """单条匹配结果"""
    text: str
    file: str
    line: int
    column: int
    range_start_line: int
    range_end_line: int
    replacement: Optional[str] = None  # 替换模式下的替换后文本


@dataclass
class SgResult:
    """搜索/替换结果"""
    matches: List[SgMatch]
    total_matches: int
    truncated: bool = False
    truncated_reason: Optional[str] = None
    error: Optional[str] = None
