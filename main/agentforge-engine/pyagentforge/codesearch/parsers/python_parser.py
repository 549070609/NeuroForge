"""
Python AST 解析器

使用 Python 标准 ast 模块进行精确解析（零依赖）
"""

import ast
import hashlib
import uuid
from pathlib import Path
from typing import Any

from pyagentforge.codesearch.parsers.base import BaseParser
from pyagentforge.codesearch.storage.models import Symbol, SymbolKind
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PythonParser(BaseParser):
    """Python AST 解析器 - 使用内置 ast 模块"""

    # AST 节点类型到 SymbolKind 的映射
    NODE_KIND_MAP = {
        ast.FunctionDef: SymbolKind.FUNCTION,
        ast.AsyncFunctionDef: SymbolKind.ASYNC_FUNCTION,
        ast.ClassDef: SymbolKind.CLASS,
        ast.Import: SymbolKind.IMPORT,
        ast.ImportFrom: SymbolKind.IMPORT,
    }

    @property
    def priority(self) -> int:
        return 100  # 最高优先级

    def supports_language(self, language: str) -> bool:
        return language.lower() in ("python", "py")

    async def parse_file(self, content: str, file_path: Path) -> list[Symbol]:
        """使用 ast 模块解析 Python 文件"""
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            logger.debug(
                "Python syntax error, skipping file",
                extra_data={"file": str(file_path), "error": str(e)},
            )
            return []

        file_hash = hashlib.md5(content.encode()).hexdigest()
        symbols: list[Symbol] = []

        # 使用 ScopeTracker 遍历 AST
        tracker = ScopeTracker(str(file_path), file_hash)
        for node in ast.iter_child_nodes(tree):
            self._process_node(node, tracker, symbols)

        return symbols

    def _process_node(
        self,
        node: ast.AST,
        tracker: "ScopeTracker",
        symbols: list[Symbol],
    ) -> None:
        """处理 AST 节点"""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbol = self._function_to_symbol(node, tracker)
            if symbol:
                symbols.append(symbol)

            # 处理嵌套函数
            tracker.push_scope(node.name)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._process_node(child, tracker, symbols)
            tracker.pop_scope()

        elif isinstance(node, ast.ClassDef):
            symbol = self._class_to_symbol(node, tracker)
            if symbol:
                symbols.append(symbol)

            # 处理类方法
            tracker.push_scope(node.name)
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_symbol = self._method_to_symbol(child, tracker)
                    if method_symbol:
                        symbols.append(method_symbol)
            tracker.pop_scope()

        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            symbol = self._import_to_symbol(node, tracker)
            if symbol:
                symbols.append(symbol)

    def _function_to_symbol(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        tracker: "ScopeTracker",
    ) -> Symbol | None:
        """将函数节点转换为 Symbol"""
        return Symbol(
            id=str(uuid.uuid4()),
            name=node.name,
            kind=SymbolKind.ASYNC_FUNCTION if isinstance(node, ast.AsyncFunctionDef) else SymbolKind.FUNCTION,
            file_path=tracker.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            column_start=node.col_offset,
            column_end=node.end_col_offset or node.col_offset,
            language="python",
            file_hash=tracker.file_hash,
            parent_scope=tracker.current_scope,
            docstring=ast.get_docstring(node),
            signature=self._get_signature(node),
        )

    def _class_to_symbol(
        self,
        node: ast.ClassDef,
        tracker: "ScopeTracker",
    ) -> Symbol | None:
        """将类节点转换为 Symbol"""
        # 获取基类信息
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(ast.unparse(base))

        metadata: dict[str, Any] = {}
        if bases:
            metadata["bases"] = bases

        return Symbol(
            id=str(uuid.uuid4()),
            name=node.name,
            kind=SymbolKind.CLASS,
            file_path=tracker.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            column_start=node.col_offset,
            column_end=node.end_col_offset or node.col_offset,
            language="python",
            file_hash=tracker.file_hash,
            parent_scope=tracker.current_scope,
            docstring=ast.get_docstring(node),
            metadata=metadata,
        )

    def _method_to_symbol(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        tracker: "ScopeTracker",
    ) -> Symbol | None:
        """将方法节点转换为 Symbol"""
        return Symbol(
            id=str(uuid.uuid4()),
            name=node.name,
            kind=SymbolKind.METHOD,
            file_path=tracker.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            column_start=node.col_offset,
            column_end=node.end_col_offset or node.col_offset,
            language="python",
            file_hash=tracker.file_hash,
            parent_scope=tracker.current_scope,  # 类名
            docstring=ast.get_docstring(node),
            signature=self._get_signature(node),
        )

    def _import_to_symbol(
        self,
        node: ast.Import | ast.ImportFrom,
        tracker: "ScopeTracker",
    ) -> Symbol | None:
        """将导入节点转换为 Symbol"""
        if isinstance(node, ast.Import):
            names = [n.name for n in node.names]
        else:
            module = node.module or ""
            names = [f"{module}.{n.name}" if module else n.name for n in node.names]

        return Symbol(
            id=str(uuid.uuid4()),
            name=", ".join(names),
            kind=SymbolKind.IMPORT,
            file_path=tracker.file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            column_start=node.col_offset,
            column_end=node.end_col_offset or node.col_offset,
            language="python",
            file_hash=tracker.file_hash,
            parent_scope=tracker.current_scope,
        )

    def _get_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """获取函数签名"""
        args = []

        # 位置参数
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        # 默认值参数
        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                arg_idx = len(node.args.args) - len(defaults) + i
                if arg_idx < len(args):
                    args[arg_idx] += f" = {ast.unparse(default)}"

        # *args
        if node.args.vararg:
            arg_str = f"*{node.args.vararg.arg}"
            if node.args.vararg.annotation:
                arg_str += f": {ast.unparse(node.args.vararg.annotation)}"
            args.append(arg_str)

        # **kwargs
        if node.args.kwarg:
            arg_str = f"**{node.args.kwarg.arg}"
            if node.args.kwarg.annotation:
                arg_str += f": {ast.unparse(node.args.kwarg.annotation)}"
            args.append(arg_str)

        # 返回类型
        returns = ""
        if node.returns:
            returns = f" -> {ast.unparse(node.returns)}"

        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)}){returns}"


class ScopeTracker:
    """作用域跟踪器"""

    def __init__(self, file_path: str, file_hash: str) -> None:
        self.file_path = file_path
        self.file_hash = file_hash
        self._scope_stack: list[str] = []

    @property
    def current_scope(self) -> str | None:
        """获取当前作用域"""
        return ".".join(self._scope_stack) if self._scope_stack else None

    def push_scope(self, name: str) -> None:
        """进入新作用域"""
        self._scope_stack.append(name)

    def pop_scope(self) -> str | None:
        """退出当前作用域"""
        return self._scope_stack.pop() if self._scope_stack else None
