"""
Python AST Tools

Provides AST-based code analysis tools for Python.
"""

from typing import Any

from pyagentforge.tools.base import BaseTool
from pyagentforge.plugins.tools.python_ast.analyzer import (
    PythonASTAnalyzer,
)
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class PythonASTFindDefinitionsTool(BaseTool):
    """Find all definitions in Python code"""

    name = "python_find_definitions"
    description = "Find all function, class, and method definitions in Python code"
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to analyze",
            },
            "type_filter": {
                "type": "string",
                "enum": ["all", "function", "class", "method", "async_function"],
                "description": "Filter by definition type (default: all)",
                "default": "all",
            },
        },
        "required": ["code"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(
        self,
        code: str,
        type_filter: str = "all",
        **kwargs: Any,
    ) -> str:
        """Execute the tool"""
        analyzer = PythonASTAnalyzer(code)

        # Check for parse errors
        if not analyzer.is_valid_python():
            error = analyzer.get_parse_error()
            return f"Error: Invalid Python code - {error}"

        # Find definitions
        definitions = analyzer.find_definitions()

        # Filter by type
        if type_filter != "all":
            definitions = [d for d in definitions if d.type == type_filter]

        if not definitions:
            return "No definitions found"

        # Format output
        lines = [f"Found {len(definitions)} definition(s):\n"]

        for defn in definitions:
            type_icon = {
                "function": "𝑓",
                "class": "ℂ",
                "method": "𝑚",
                "async_function": "⏳",
            }.get(defn.type, "•")

            lines.append(f"{type_icon} {defn.name} (line {defn.line})")
            lines.append(f"   Type: {defn.type}")

            if defn.args:
                lines.append(f"   Args: {', '.join(defn.args)}")

            if defn.docstring:
                doc_preview = defn.docstring[:60]
                if len(defn.docstring) > 60:
                    doc_preview += "..."
                lines.append(f"   Doc: {doc_preview}")

            if defn.decorators:
                lines.append(f"   Decorators: {', '.join(defn.decorators)}")

            lines.append("")

        return "\n".join(lines)


class PythonASTFindImportsTool(BaseTool):
    """Find all imports in Python code"""

    name = "python_find_imports"
    description = "Find all import statements in Python code"
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to analyze",
            },
        },
        "required": ["code"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(self, code: str, **kwargs: Any) -> str:
        """Execute the tool"""
        analyzer = PythonASTAnalyzer(code)

        # Check for parse errors
        if not analyzer.is_valid_python():
            error = analyzer.get_parse_error()
            return f"Error: Invalid Python code - {error}"

        # Find imports
        imports = analyzer.find_imports()

        if not imports:
            return "No imports found"

        # Format output
        lines = [f"Found {len(imports)} import(s):\n"]

        for imp in imports:
            if imp.is_from:
                names_str = ", ".join(imp.names)
                lines.append(f"from {imp.module} import {names_str}")
            else:
                alias = f" as {imp.alias}" if imp.alias else ""
                lines.append(f"import {imp.module}{alias}")
            lines.append(f"   Line: {imp.line}")

        return "\n".join(lines)


class PythonASTFindCallsTool(BaseTool):
    """Find all function calls in Python code"""

    name = "python_find_calls"
    description = "Find all function and method calls in Python code"
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to analyze",
            },
            "name_filter": {
                "type": "string",
                "description": "Filter calls by name (partial match)",
            },
        },
        "required": ["code"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(
        self,
        code: str,
        name_filter: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute the tool"""
        analyzer = PythonASTAnalyzer(code)

        # Check for parse errors
        if not analyzer.is_valid_python():
            error = analyzer.get_parse_error()
            return f"Error: Invalid Python code - {error}"

        # Find calls
        calls = analyzer.find_calls()

        # Filter by name
        if name_filter:
            calls = [c for c in calls if name_filter.lower() in c.name.lower()]

        if not calls:
            return "No calls found"

        # Format output
        lines = [f"Found {len(calls)} call(s):\n"]

        # Group by name
        call_counts: dict[str, int] = {}
        for call in calls:
            call_counts[call.name] = call_counts.get(call.name, 0) + 1

        # Show summary
        lines.append("Call Summary:")
        for name, count in sorted(call_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {name}: {count}x")
        lines.append("")

        # Show details
        lines.append("Call Details:")
        for call in calls[:50]:  # Limit to first 50
            lines.append(f"  {call.name}() at line {call.name}")
            if call.args_count > 0:
                lines.append(f"    Args: {call.args_count}")

        if len(calls) > 50:
            lines.append(f"\n... and {len(calls) - 50} more calls")

        return "\n".join(lines)


class PythonASTExtractClassesTool(BaseTool):
    """Extract class definitions with methods"""

    name = "python_extract_classes"
    description = "Extract all class definitions with their methods and attributes"
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to analyze",
            },
            "class_name": {
                "type": "string",
                "description": "Filter by class name (optional)",
            },
        },
        "required": ["code"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(
        self,
        code: str,
        class_name: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Execute the tool"""
        analyzer = PythonASTAnalyzer(code)

        # Check for parse errors
        if not analyzer.is_valid_python():
            error = analyzer.get_parse_error()
            return f"Error: Invalid Python code - {error}"

        # Extract classes
        classes = analyzer.extract_classes()

        # Filter by name
        if class_name:
            classes = [c for c in classes if class_name.lower() in c["name"].lower()]

        if not classes:
            return "No classes found"

        # Format output
        lines = [f"Found {len(classes)} class(es):\n"]

        for cls in classes:
            lines.append(f"ℂ Class: {cls['name']} (line {cls['line']})")

            if cls.get("docstring"):
                doc_preview = cls["docstring"][:80]
                if len(cls["docstring"]) > 80:
                    doc_preview += "..."
                lines.append(f"   Doc: {doc_preview}")

            if cls.get("decorators"):
                lines.append(f"   Decorators: {', '.join(cls['decorators'])}")

            methods = cls.get("methods", [])
            if methods:
                lines.append(f"   Methods ({len(methods)}):")
                for method in methods:
                    async_marker = "⏳ " if method.get("is_async") else ""
                    args_str = ", ".join(method.get("args", []))
                    lines.append(f"     {async_marker}{method['name']}({args_str})")
            else:
                lines.append("   Methods: (none)")

            lines.append("")

        return "\n".join(lines)


class PythonASTAnalyzeComplexityTool(BaseTool):
    """Analyze code complexity"""

    name = "python_analyze_complexity"
    description = "Analyze Python code complexity metrics (lines, nesting, cyclomatic complexity)"
    parameters_schema = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python source code to analyze",
            },
        },
        "required": ["code"],
    }
    timeout = 30
    risk_level = "low"

    async def execute(self, code: str, **kwargs: Any) -> str:
        """Execute the tool"""
        analyzer = PythonASTAnalyzer(code)

        # Analyze complexity
        complexity = analyzer.analyze_complexity()

        # Check for parse errors
        if not analyzer.is_valid_python():
            error = analyzer.get_parse_error()
            return f"Warning: Code has syntax errors - {error}\n\nFalling back to line counting..."

        # Format output
        lines = ["# Code Complexity Analysis\n"]

        # Line counts
        lines.append("## Line Counts")
        lines.append(f"- Total lines: {complexity.total_lines}")
        lines.append(f"- Code lines: {complexity.code_lines}")
        lines.append(f"- Comment lines: {complexity.comment_lines}")
        lines.append(f"- Blank lines: {complexity.blank_lines}")
        lines.append("")

        # Structure
        lines.append("## Structure")
        lines.append(f"- Functions: {complexity.function_count}")
        lines.append(f"- Classes: {complexity.class_count}")
        lines.append(f"- Imports: {complexity.import_count}")
        lines.append("")

        # Complexity
        lines.append("## Complexity Metrics")
        lines.append(f"- Max nesting depth: {complexity.max_nesting}")
        lines.append(f"- Cyclomatic complexity: {complexity.cyclomatic_complexity}")

        # Rating
        if complexity.cyclomatic_complexity <= 10:
            rating = "✅ Low (good)"
        elif complexity.cyclomatic_complexity <= 20:
            rating = "⚠️ Moderate"
        elif complexity.cyclomatic_complexity <= 50:
            rating = "🔶 High (consider refactoring)"
        else:
            rating = "🔴 Very high (needs refactoring)"

        lines.append(f"- Complexity rating: {rating}")

        # Nesting rating
        if complexity.max_nesting <= 3:
            nest_rating = "✅ Good"
        elif complexity.max_nesting <= 5:
            nest_rating = "⚠️ Moderate"
        else:
            nest_rating = "🔴 Deep nesting (consider flattening)"

        lines.append(f"- Nesting rating: {nest_rating}")

        return "\n".join(lines)


# Export tools
__all__ = [
    "PythonASTFindDefinitionsTool",
    "PythonASTFindImportsTool",
    "PythonASTFindCallsTool",
    "PythonASTExtractClassesTool",
    "PythonASTAnalyzeComplexityTool",
]
