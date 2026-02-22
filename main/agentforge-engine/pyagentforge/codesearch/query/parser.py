"""
查询语法解析器

支持高级查询语法:
- "function:xxx" - 搜索函数定义
- "class:xxx" - 搜索类定义
- "xxx AND yyy" - 逻辑 AND
- "xxx OR yyy" - 逻辑 OR
- "NOT xxx" - 排除
- "xxx*" - 通配符
- "(xxx OR yyy) AND zzz" - 分组
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

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
from pyagentforge.codesearch.storage.models import SymbolKind
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class TokenType(Enum):
    """词法分析 token 类型"""
    KIND_FILTER = auto()    # function:, class:, etc.
    LANG_FILTER = auto()    # lang:
    FILE_FILTER = auto()    # file:
    IDENTIFIER = auto()     # 标识符
    STRING = auto()         # 引号字符串
    AND = auto()
    OR = auto()
    NOT = auto()
    LPAREN = auto()
    RPAREN = auto()
    STAR = auto()
    COLON = auto()
    EOF = auto()


@dataclass
class Token:
    """词法分析 token"""
    type: TokenType
    value: str


class Lexer:
    """词法分析器"""

    KEYWORDS = {
        "AND": TokenType.AND,
        "OR": TokenType.OR,
        "NOT": TokenType.NOT,
        "lang": TokenType.LANG_FILTER,
        "file": TokenType.FILE_FILTER,
    }

    KIND_FILTERS: dict[str, Callable[[], SymbolKind]] = {
        "function": lambda: SymbolKind.FUNCTION,
        "func": lambda: SymbolKind.FUNCTION,
        "async_function": lambda: SymbolKind.ASYNC_FUNCTION,
        "class": lambda: SymbolKind.CLASS,
        "method": lambda: SymbolKind.METHOD,
        "variable": lambda: SymbolKind.VARIABLE,
        "var": lambda: SymbolKind.VARIABLE,
        "constant": lambda: SymbolKind.CONSTANT,
        "const": lambda: SymbolKind.CONSTANT,
        "import": lambda: SymbolKind.IMPORT,
        "interface": lambda: SymbolKind.INTERFACE,
        "struct": lambda: SymbolKind.STRUCT,
        "enum": lambda: SymbolKind.ENUM,
        "property": lambda: SymbolKind.PROPERTY,
        "field": lambda: SymbolKind.FIELD,
    }

    def __init__(self, query: str):
        self.query = query
        self.pos = 0
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        """将查询字符串转换为 token 列表"""
        while self.pos < len(self.query):
            self._skip_whitespace()
            if self.pos >= len(self.query):
                break

            char = self.query[self.pos]

            if char == "(":
                self.tokens.append(Token(TokenType.LPAREN, "("))
                self.pos += 1
            elif char == ")":
                self.tokens.append(Token(TokenType.RPAREN, ")"))
                self.pos += 1
            elif char == "*":
                self.tokens.append(Token(TokenType.STAR, "*"))
                self.pos += 1
            elif char == '"':
                self._read_string()
            elif char == ":":
                self.tokens.append(Token(TokenType.COLON, ":"))
                self.pos += 1
            elif char.isalpha() or char == "_" or char == ".":
                self._read_identifier()
            else:
                self.pos += 1  # 跳过未知字符

        self.tokens.append(Token(TokenType.EOF, ""))
        return self.tokens

    def _skip_whitespace(self) -> None:
        while self.pos < len(self.query) and self.query[self.pos].isspace():
            self.pos += 1

    def _read_string(self) -> None:
        self.pos += 1  # 跳过起始引号
        start = self.pos
        while self.pos < len(self.query) and self.query[self.pos] != '"':
            if self.query[self.pos] == "\\":
                self.pos += 1  # 跳过转义字符
            self.pos += 1
        value = self.query[start:self.pos]
        self.tokens.append(Token(TokenType.STRING, value))
        self.pos += 1  # 跳过结束引号

    def _read_identifier(self) -> None:
        start = self.pos
        while self.pos < len(self.query) and (
            self.query[self.pos].isalnum() or
            self.query[self.pos] in "_-./\\*"
        ):
            self.pos += 1
        value = self.query[start:self.pos]

        # 检查是否是 kind 过滤器 (当前标识符后跟冒号)
        if self.pos < len(self.query) and self.query[self.pos] == ":":
            if value in self.KIND_FILTERS:
                self.pos += 1  # 跳过冒号
                self.tokens.append(Token(TokenType.KIND_FILTER, value))
                return
            elif value == "lang":
                self.pos += 1  # 跳过冒号
                self.tokens.append(Token(TokenType.LANG_FILTER, value))
                return
            elif value == "file":
                self.pos += 1  # 跳过冒号
                self.tokens.append(Token(TokenType.FILE_FILTER, value))
                return

        # 检查是否是关键字
        upper_value = value.upper()
        if upper_value in self.KEYWORDS:
            self.tokens.append(Token(self.KEYWORDS[upper_value], value))
        else:
            self.tokens.append(Token(TokenType.IDENTIFIER, value))


class QueryParser:
    """查询语法解析器"""

    def __init__(self, query: str):
        self.lexer = Lexer(query)
        self.tokens = self.lexer.tokenize()
        self.pos = 0

    def parse(self) -> QueryNode | None:
        """解析查询字符串为 AST"""
        if self._current().type == TokenType.EOF:
            return None

        # 检查是否是简单查询（没有高级语法）
        if self._is_simple_query():
            return self._parse_simple()

        return self._parse_or_expr()

    def _is_simple_query(self) -> bool:
        """检查是否是简单查询（只有标识符或带前缀的标识符）"""
        has_advanced_syntax = False
        for token in self.tokens:
            if token.type in (TokenType.AND, TokenType.OR, TokenType.NOT,
                            TokenType.LPAREN, TokenType.RPAREN):
                has_advanced_syntax = True
                break
        return not has_advanced_syntax

    def _parse_simple(self) -> QueryNode:
        """解析简单查询"""
        # 收集所有 token
        parts: list[str] = []
        current_kind: SymbolKind | None = None

        while self._current().type not in (TokenType.EOF,):
            token = self._current()

            if token.type == TokenType.KIND_FILTER:
                current_kind = Lexer.KIND_FILTERS[token.value]()
                self._consume()

                # 下一个应该是标识符
                if self._current().type == TokenType.IDENTIFIER:
                    pattern = self._consume().value
                    parts.append(KindFilter(kind=current_kind, pattern=pattern))
                    current_kind = None
            elif token.type == TokenType.IDENTIFIER:
                pattern = self._consume().value
                if current_kind:
                    parts.append(KindFilter(kind=current_kind, pattern=pattern))
                    current_kind = None
                else:
                    parts.append(NameMatch(pattern=pattern))
            elif token.type == TokenType.STRING:
                parts.append(NameMatch(pattern=self._consume().value, is_exact=True))
            else:
                self._consume()

        # 如果只有一个部分，直接返回
        if len(parts) == 1:
            return parts[0]

        # 多个部分用 AND 连接
        result = parts[0]
        for part in parts[1:]:
            result = AndExpr(left=result, right=part)

        return result

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _consume(self, expected: TokenType | None = None) -> Token:
        token = self._current()
        if expected and token.type != expected:
            raise ValueError(f"Expected {expected}, got {token.type}")
        self.pos += 1
        return token

    def _parse_or_expr(self) -> QueryNode:
        left = self._parse_and_expr()
        while self._current().type == TokenType.OR:
            self._consume(TokenType.OR)
            right = self._parse_and_expr()
            left = OrExpr(left, right)
        return left

    def _parse_and_expr(self) -> QueryNode:
        left = self._parse_unary_expr()
        while self._current().type in (TokenType.AND, TokenType.IDENTIFIER,
                                       TokenType.KIND_FILTER, TokenType.LANG_FILTER):
            if self._current().type == TokenType.AND:
                self._consume(TokenType.AND)
            right = self._parse_unary_expr()
            left = AndExpr(left, right)
        return left

    def _parse_unary_expr(self) -> QueryNode:
        if self._current().type == TokenType.NOT:
            self._consume(TokenType.NOT)
            operand = self._parse_primary()
            return NotExpr(operand)
        return self._parse_primary()

    def _parse_primary(self) -> QueryNode:
        token = self._current()

        if token.type == TokenType.LPAREN:
            self._consume(TokenType.LPAREN)
            node = self._parse_or_expr()
            self._consume(TokenType.RPAREN)
            return node

        if token.type == TokenType.KIND_FILTER:
            kind = Lexer.KIND_FILTERS[token.value]()
            self._consume()

            # 下一个 token 应该是标识符或字符串
            if self._current().type == TokenType.IDENTIFIER:
                pattern = self._consume().value
                # 检查通配符
                if self._current().type == TokenType.STAR:
                    self._consume(TokenType.STAR)
                    pattern += "*"
                return KindFilter(kind=kind, pattern=pattern)
            elif self._current().type == TokenType.STRING:
                return KindFilter(kind=kind, pattern=self._consume().value)
            else:
                # 只有 kind 过滤器，匹配所有
                return KindFilter(kind=kind, pattern="*")

        if token.type == TokenType.LANG_FILTER:
            self._consume()
            lang = self._consume(TokenType.IDENTIFIER).value
            # 后面应该有内容
            if self._current().type in (TokenType.AND, TokenType.OR, TokenType.EOF, TokenType.RPAREN):
                # 语言过滤器单独使用，返回一个匹配所有的节点
                return LanguageFilter(language=lang, operand=NameMatch(pattern="*"))
            operand = self._parse_primary()
            return LanguageFilter(language=lang, operand=operand)

        if token.type == TokenType.FILE_FILTER:
            self._consume()
            pattern = self._consume(TokenType.IDENTIFIER).value
            if self._current().type in (TokenType.AND, TokenType.OR, TokenType.EOF, TokenType.RPAREN):
                return FileFilter(pattern=pattern, operand=NameMatch(pattern="*"))
            operand = self._parse_primary()
            return FileFilter(pattern=pattern, operand=operand)

        if token.type == TokenType.IDENTIFIER:
            pattern = self._consume().value
            # 检查后跟 *
            if self._current().type == TokenType.STAR:
                self._consume(TokenType.STAR)
                return NameMatch(pattern=pattern + "*", is_wildcard=True)
            return NameMatch(pattern=pattern)

        if token.type == TokenType.STRING:
            return NameMatch(pattern=self._consume().value, is_exact=True)

        # 默认返回一个匹配所有的节点
        return NameMatch(pattern="*")
