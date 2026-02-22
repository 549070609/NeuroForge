"""
Comment Checker

Detects excessive comments in code output.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CommentThresholds:
    """Thresholds for comment detection"""

    max_comment_ratio: float = 0.4  # Max ratio of comments to code
    max_consecutive_comments: int = 5  # Max consecutive comment lines
    max_inline_comment_density: float = 0.5  # Max inline comment density


@dataclass
class CommentCheckResult:
    """Result of comment check"""

    is_excessive: bool
    comment_ratio: float
    issues: list[str] = field(default_factory=list)
    comment_lines: int = 0
    code_lines: int = 0
    suggestions: list[str] = field(default_factory=list)


class CommentChecker:
    """
    Comment Checker

    Analyzes code output for excessive comments and provides suggestions.
    """

    # Comment patterns by language
    COMMENT_PATTERNS = {
        "python": {
            "single": r"#.*$",
            "multi_start": r"'''|\"\"\"",
            "docstring": r'^\s*("""|\'\'\')\s*$',
        },
        "javascript": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "typescript": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "java": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "c": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "cpp": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "go": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "rust": {
            "single": r"//.*$",
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "html": {
            "single": None,
            "multi_start": r"<!--",
            "multi_end": r"-->",
        },
        "css": {
            "single": None,
            "multi_start": r"/\*",
            "multi_end": r"\*/",
        },
        "shell": {
            "single": r"#.*$",
            "multi_start": None,
            "multi_end": None,
        },
        "yaml": {
            "single": r"#.*$",
            "multi_start": None,
            "multi_end": None,
        },
    }

    def __init__(
        self,
        thresholds: CommentThresholds | None = None,
        min_lines: int = 10,
    ):
        """
        Initialize comment checker

        Args:
            thresholds: Thresholds for detection
            min_lines: Minimum lines to check (skip short outputs)
        """
        self.thresholds = thresholds or CommentThresholds()
        self.min_lines = min_lines

    def check(self, code: str, language: str = "python") -> CommentCheckResult:
        """
        Check code for excessive comments

        Args:
            code: Code to check
            language: Programming language

        Returns:
            CommentCheckResult
        """
        lines = code.strip().split("\n")

        # Skip short outputs
        if len(lines) < self.min_lines:
            return CommentCheckResult(
                is_excessive=False,
                comment_ratio=0.0,
                comment_lines=0,
                code_lines=len(lines),
            )

        # Get patterns for language
        patterns = self.COMMENT_PATTERNS.get(language, self.COMMENT_PATTERNS["python"])

        # Count comment and code lines
        comment_lines = 0
        code_lines = 0
        consecutive_comments = 0
        max_consecutive = 0
        in_multiline_comment = False
        issues: list[str] = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines
            if not stripped:
                continue

            # Check for multiline comments
            if patterns.get("multi_start"):
                if re.search(patterns["multi_start"], stripped):
                    in_multiline_comment = True
                    comment_lines += 1
                    consecutive_comments += 1
                    continue

                if in_multiline_comment:
                    if re.search(patterns["multi_end"], stripped):
                        in_multiline_comment = False
                    comment_lines += 1
                    consecutive_comments += 1
                    continue

            # Check for single-line comments
            is_comment = False
            if patterns.get("single"):
                # Check if line is entirely a comment
                if re.match(r"^\s*" + patterns["single"], stripped):
                    is_comment = True

            # Check for docstrings (Python)
            if language == "python" and patterns.get("docstring"):
                if re.match(patterns["docstring"], stripped):
                    is_comment = True

            if is_comment:
                comment_lines += 1
                consecutive_comments += 1
                max_consecutive = max(max_consecutive, consecutive_comments)
            else:
                code_lines += 1
                consecutive_comments = 0

                # Check for inline comments
                if patterns.get("single"):
                    if re.search(patterns["single"], stripped):
                        # Line has both code and comment
                        pass

        # Calculate ratio
        total_lines = comment_lines + code_lines
        comment_ratio = comment_lines / total_lines if total_lines > 0 else 0.0

        # Check for issues
        is_excessive = False

        if comment_ratio > self.thresholds.max_comment_ratio:
            is_excessive = True
            issues.append(
                f"Comment ratio ({comment_ratio:.1%}) exceeds threshold "
                f"({self.thresholds.max_comment_ratio:.1%})"
            )

        if max_consecutive > self.thresholds.max_consecutive_comments:
            is_excessive = True
            issues.append(
                f"Found {max_consecutive} consecutive comment lines "
                f"(max: {self.thresholds.max_consecutive_comments})"
            )

        # Generate suggestions
        suggestions = []
        if is_excessive:
            suggestions = self._generate_suggestions(issues, comment_ratio)

        return CommentCheckResult(
            is_excessive=is_excessive,
            comment_ratio=comment_ratio,
            issues=issues,
            comment_lines=comment_lines,
            code_lines=code_lines,
            suggestions=suggestions,
        )

    def _generate_suggestions(
        self,
        issues: list[str],
        comment_ratio: float,
    ) -> list[str]:
        """Generate improvement suggestions"""
        suggestions = []

        if comment_ratio > 0.5:
            suggestions.append(
                "Consider removing most comments and using descriptive "
                "variable/function names instead"
            )
        elif comment_ratio > 0.3:
            suggestions.append(
                "Consider reducing comments to only explain complex logic "
                "or non-obvious decisions"
            )

        suggestions.append(
            "Good code should be self-documenting. Use comments only for:"
        )
        suggestions.append("  - Explaining why (not what) code does something")
        suggestions.append("  - Documenting public APIs and interfaces")
        suggestions.append("  - Adding TODOs or FIXMEs for future work")

        return suggestions

    def suggest_improvements(self, result: CommentCheckResult) -> str:
        """
        Generate improvement suggestions as a formatted string

        Args:
            result: Check result

        Returns:
            Formatted suggestions
        """
        if not result.is_excessive:
            return "No excessive comments detected."

        lines = ["## Comment Analysis Results\n"]
        lines.append(f"**Comment ratio:** {result.comment_ratio:.1%}")
        lines.append(f"**Comment lines:** {result.comment_lines}")
        lines.append(f"**Code lines:** {result.code_lines}\n")

        if result.issues:
            lines.append("### Issues Found:")
            for issue in result.issues:
                lines.append(f"- {issue}")
            lines.append("")

        if result.suggestions:
            lines.append("### Suggestions:")
            for suggestion in result.suggestions:
                lines.append(f"- {suggestion}")

        return "\n".join(lines)
