"""
Python AST Analyzer

Provides AST-based code analysis for Python.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DefinitionInfo:
    """Information about a definition (function, class, method)"""

    name: str
    type: str  # function, class, method, async_function
    line: int
    end_line: int
    docstring: str | None = None
    args: list[str] = field(default_factory=list)
    returns: str | None = None
    decorators: list[str] = field(default_factory=list)
    is_async: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "type": self.type,
            "line": self.line,
            "end_line": self.end_line,
            "docstring": self.docstring,
            "args": self.args,
            "returns": self.returns,
            "decorators": self.decorators,
            "is_async": self.is_async,
        }


@dataclass
class ImportInfo:
    """Information about an import"""

    module: str
    names: list[str]  # For 'from X import a, b'
    alias: str | None = None  # For 'import X as Y'
    line: int = 0
    is_from: bool = False  # 'from X import ...'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "module": self.module,
            "names": self.names,
            "alias": self.alias,
            "line": self.line,
            "is_from": self.is_from,
        }


@dataclass
class CallInfo:
    """Information about a function call"""

    name: str
    line: int
    args_count: int = 0
    has_starargs: bool = False
    has_kwargs: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "line": self.line,
            "args_count": self.args_count,
            "has_starargs": self.has_starargs,
            "has_kwargs": self.has_kwargs,
        }


@dataclass
class ComplexityInfo:
    """Complexity metrics"""

    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    function_count: int = 0
    class_count: int = 0
    import_count: int = 0
    max_nesting: int = 0
    cyclomatic_complexity: int = 1  # Base complexity

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_lines": self.total_lines,
            "code_lines": self.code_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "function_count": self.function_count,
            "class_count": self.class_count,
            "import_count": self.import_count,
            "max_nesting": self.max_nesting,
            "cyclomatic_complexity": self.cyclomatic_complexity,
        }


class PythonASTAnalyzer:
    """
    Python AST Analyzer

    Provides code analysis using Python's ast module.
    """

    def __init__(self, source_code: str):
        """
        Initialize analyzer

        Args:
            source_code: Python source code to analyze
        """
        self.source_code = source_code
        self._tree: ast.AST | None = None
        self._parse_error: str | None = None

    def _parse(self) -> ast.AST | None:
        """Parse source code into AST"""
        if self._tree is not None:
            return self._tree

        try:
            self._tree = ast.parse(self.source_code)
            return self._tree
        except SyntaxError as e:
            self._parse_error = str(e)
            logger.warning(f"Failed to parse Python code: {e}")
            return None

    def find_definitions(self) -> list[DefinitionInfo]:
        """
        Find all definitions (functions, classes, methods)

        Returns:
            List of DefinitionInfo
        """
        tree = self._parse()
        if not tree:
            return []

        definitions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                info = self._extract_function_info(node)
                definitions.append(info)
            elif isinstance(node, ast.AsyncFunctionDef):
                info = self._extract_function_info(node, is_async=True)
                definitions.append(info)
            elif isinstance(node, ast.ClassDef):
                info = self._extract_class_info(node)
                definitions.append(info)

        return definitions

    def _extract_function_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool = False,
    ) -> DefinitionInfo:
        """Extract function information from AST node"""
        # Get docstring
        docstring = ast.get_docstring(node)

        # Get arguments
        args = []
        if node.args:
            for arg in node.args.args:
                args.append(arg.arg)
            if node.args.vararg:
                args.append(f"*{node.args.vararg.arg}")
            if node.args.kwarg:
                args.append(f"**{node.args.kwarg.arg}")

        # Get return annotation
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns) if hasattr(ast, "unparse") else None

        # Get decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)
            elif isinstance(decorator, ast.Attribute):
                decorators.append(ast.unparse(decorator) if hasattr(ast, "unparse") else str(decorator.attr))

        # Determine if method (inside a class)
        is_method = False
        # This requires context from parent traversal

        return DefinitionInfo(
            name=node.name,
            type="async_function" if is_async else "function",
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring,
            args=args,
            returns=returns,
            decorators=decorators,
            is_async=is_async,
        )

    def _extract_class_info(self, node: ast.ClassDef) -> DefinitionInfo:
        """Extract class information from AST node"""
        # Get docstring
        docstring = ast.get_docstring(node)

        # Get decorators
        decorators = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                decorators.append(decorator.id)

        # Get methods
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._extract_function_info(
                    item,
                    is_async=isinstance(item, ast.AsyncFunctionDef),
                )
                method_info.type = "method"
                methods.append(method_info)

        return DefinitionInfo(
            name=node.name,
            type="class",
            line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=docstring,
            decorators=decorators,
        )

    def find_imports(self) -> list[ImportInfo]:
        """
        Find all imports

        Returns:
            List of ImportInfo
        """
        tree = self._parse()
        if not tree:
            return []

        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        names=[alias.name],
                        alias=alias.asname,
                        line=node.lineno,
                        is_from=False,
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(ImportInfo(
                    module=module,
                    names=names,
                    line=node.lineno,
                    is_from=True,
                ))

        return imports

    def find_calls(self) -> list[CallInfo]:
        """
        Find all function calls

        Returns:
            List of CallInfo
        """
        tree = self._parse()
        if not tree:
            return []

        calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Get function name
                name = self._get_call_name(node.func)

                if name:
                    calls.append(CallInfo(
                        name=name,
                        line=node.lineno,
                        args_count=len(node.args),
                        has_starargs=any(isinstance(a, ast.Starred) for a in node.args),
                        has_kwargs=any(isinstance(k, ast.keyword) and k.arg is None for k in node.keywords),
                    ))

        return calls

    def _get_call_name(self, node: ast.expr) -> str | None:
        """Get call name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_call_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        return None

    def extract_classes(self) -> list[dict[str, Any]]:
        """
        Extract all classes with their methods

        Returns:
            List of class dictionaries
        """
        tree = self._parse()
        if not tree:
            return []

        classes = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                # Get class info
                class_info = self._extract_class_info(node)

                # Get methods
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_info = self._extract_function_info(
                            item,
                            is_async=isinstance(item, ast.AsyncFunctionDef),
                        )
                        method_info.type = "method"
                        methods.append(method_info.to_dict())

                classes.append({
                    **class_info.to_dict(),
                    "methods": methods,
                })

        return classes

    def analyze_complexity(self) -> ComplexityInfo:
        """
        Analyze code complexity

        Returns:
            ComplexityInfo
        """
        tree = self._parse()

        # Basic line counting
        lines = self.source_code.split("\n")
        total_lines = len(lines)
        code_lines = 0
        comment_lines = 0
        blank_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_lines += 1
            elif stripped.startswith("#"):
                comment_lines += 1
            else:
                code_lines += 1

        if not tree:
            return ComplexityInfo(
                total_lines=total_lines,
                code_lines=code_lines,
                comment_lines=comment_lines,
                blank_lines=blank_lines,
            )

        # Count definitions
        function_count = 0
        class_count = 0
        import_count = 0
        max_nesting = 0
        cyclomatic_complexity = 1  # Base

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_count += 1
                # Cyclomatic complexity contributions
                for child in ast.walk(node):
                    if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                        cyclomatic_complexity += 1
                    elif isinstance(child, ast.BoolOp):
                        # and/or operators
                        cyclomatic_complexity += len(child.values) - 1
            elif isinstance(node, ast.ClassDef):
                class_count += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_count += 1

        # Calculate max nesting
        max_nesting = self._calculate_max_nesting(tree)

        return ComplexityInfo(
            total_lines=total_lines,
            code_lines=code_lines,
            comment_lines=comment_lines,
            blank_lines=blank_lines,
            function_count=function_count,
            class_count=class_count,
            import_count=import_count,
            max_nesting=max_nesting,
            cyclomatic_complexity=cyclomatic_complexity,
        )

    def _calculate_max_nesting(self, tree: ast.AST) -> int:
        """Calculate maximum nesting depth"""
        max_depth = 0

        def visit(node, depth):
            nonlocal max_depth
            max_depth = max(max_depth, depth)

            nesting_nodes = (ast.If, ast.For, ast.While, ast.With, ast.Try)

            for child in ast.iter_child_nodes(node):
                if isinstance(child, nesting_nodes):
                    visit(child, depth + 1)
                else:
                    visit(child, depth)

        visit(tree, 0)
        return max_depth

    def get_parse_error(self) -> str | None:
        """Get parse error if any"""
        return self._parse_error

    def is_valid_python(self) -> bool:
        """Check if source is valid Python"""
        return self._parse() is not None
