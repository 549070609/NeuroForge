"""
Output Truncator

Intelligently truncates tool output while preserving code blocks.
"""

import re
from dataclasses import dataclass, field

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TruncationConfig:
    """Configuration for output truncation"""

    max_total_lines: int = 500  # Max total output lines
    max_non_code_lines: int = 200  # Max lines outside code blocks
    preserve_code_blocks: bool = True  # Preserve code blocks entirely
    truncation_message: str = "... [truncated] ..."
    show_line_count: bool = True  # Show removed line count


@dataclass
class TruncationResult:
    """Result of truncation"""

    content: str
    was_truncated: bool
    removed_lines: int
    original_lines: int
    preserved_code_blocks: int
    truncation_points: list[int] = field(default_factory=list)


class OutputTruncator:
    """
    Output Truncator

    Intelligently truncates tool output while preserving code blocks
    and important content.
    """

    # Code block pattern
    CODE_BLOCK_PATTERN = re.compile(r"```[\w]*\n([\s\S]*?)```", re.MULTILINE)

    def __init__(self, config: TruncationConfig | None = None):
        """
        Initialize output truncator

        Args:
            config: Truncation configuration
        """
        self.config = config or TruncationConfig()

    def truncate(self, content: str) -> TruncationResult:
        """
        Truncate content if necessary

        Args:
            content: Content to truncate

        Returns:
            TruncationResult
        """
        lines = content.split("\n")
        original_lines = len(lines)

        # Check if truncation is needed
        if original_lines <= self.config.max_total_lines:
            return TruncationResult(
                content=content,
                was_truncated=False,
                removed_lines=0,
                original_lines=original_lines,
                preserved_code_blocks=0,
            )

        # Find code blocks
        code_blocks = self._find_code_blocks(content)

        if self.config.preserve_code_blocks and code_blocks:
            return self._truncate_preserving_code(content, lines, code_blocks)
        else:
            return self._truncate_simple(content, lines)

    def _find_code_blocks(self, content: str) -> list[tuple[int, int, str]]:
        """
        Find all code blocks in content

        Args:
            content: Content to search

        Returns:
            List of (start_line, end_line, content) tuples
        """
        blocks = []
        lines = content.split("\n")

        in_block = False
        block_start = 0
        block_content = []
        block_lines = 0

        for i, line in enumerate(lines):
            if line.strip().startswith("```"):
                if in_block:
                    # End of block
                    block_lines += 1
                    blocks.append((
                        block_start,
                        i,
                        "\n".join(block_content),
                    ))
                    in_block = False
                    block_content = []
                else:
                    # Start of block
                    block_start = i
                    in_block = True
                    block_lines = 1
            elif in_block:
                block_content.append(line)
                block_lines += 1

        # Handle unclosed blocks
        if in_block:
            blocks.append((
                block_start,
                len(lines) - 1,
                "\n".join(block_content),
            ))

        return blocks

    def _truncate_preserving_code(
        self,
        content: str,
        lines: list[str],
        code_blocks: list[tuple[int, int, str]],
    ) -> TruncationResult:
        """
        Truncate while preserving code blocks

        Args:
            content: Original content
            lines: All lines
            code_blocks: Found code blocks

        Returns:
            TruncationResult
        """
        # Calculate lines to preserve from code blocks
        code_block_lines = set()
        for start, end, _ in code_blocks:
            for i in range(start, end + 1):
                code_block_lines.add(i)

        # Build result
        result_lines = []
        non_code_count = 0
        truncation_points = []
        removed_lines = 0

        i = 0
        while i < len(lines):
            if i in code_block_lines:
                # Preserve code block line
                result_lines.append(lines[i])
            else:
                # Non-code line
                if non_code_count < self.config.max_non_code_lines:
                    result_lines.append(lines[i])
                    non_code_count += 1
                else:
                    # Truncate
                    if not truncation_points:
                        # Add truncation message
                        msg = self.config.truncation_message
                        if self.config.show_line_count:
                            remaining = len(lines) - i
                            msg = f"... [{remaining} lines truncated] ..."
                        result_lines.append(msg)
                    removed_lines += 1
                    truncation_points.append(i)

            i += 1

        result_content = "\n".join(result_lines)

        return TruncationResult(
            content=result_content,
            was_truncated=removed_lines > 0,
            removed_lines=removed_lines,
            original_lines=len(lines),
            preserved_code_blocks=len(code_blocks),
            truncation_points=truncation_points[:5],  # Limit points
        )

    def _truncate_simple(
        self,
        content: str,
        lines: list[str],
    ) -> TruncationResult:
        """
        Simple truncation at max lines

        Args:
            content: Original content
            lines: All lines

        Returns:
            TruncationResult
        """
        max_lines = self.config.max_total_lines

        if len(lines) <= max_lines:
            return TruncationResult(
                content=content,
                was_truncated=False,
                removed_lines=0,
                original_lines=len(lines),
                preserved_code_blocks=0,
            )

        # Truncate
        result_lines = lines[:max_lines]

        # Add truncation message
        msg = self.config.truncation_message
        if self.config.show_line_count:
            remaining = len(lines) - max_lines
            msg = f"\n\n... [{remaining} more lines truncated] ..."
        result_lines.append(msg)

        return TruncationResult(
            content="\n".join(result_lines),
            was_truncated=True,
            removed_lines=len(lines) - max_lines,
            original_lines=len(lines),
            preserved_code_blocks=0,
            truncation_points=[max_lines],
        )

    def truncate_with_context(
        self,
        content: str,
        context_lines: int = 10,
    ) -> TruncationResult:
        """
        Truncate keeping context at start and end

        Args:
            content: Content to truncate
            context_lines: Lines to keep at start and end

        Returns:
            TruncationResult
        """
        lines = content.split("\n")
        original_lines = len(lines)

        if original_lines <= self.config.max_total_lines:
            return TruncationResult(
                content=content,
                was_truncated=False,
                removed_lines=0,
                original_lines=original_lines,
                preserved_code_blocks=0,
            )

        # Keep context at start and end
        start_lines = lines[:context_lines]
        end_lines = lines[-context_lines:]

        # Build result
        removed = original_lines - (2 * context_lines)
        msg = f"\n\n... [{removed} lines truncated] ...\n\n"

        result_content = "\n".join(start_lines) + msg + "\n".join(end_lines)

        return TruncationResult(
            content=result_content,
            was_truncated=True,
            removed_lines=removed,
            original_lines=original_lines,
            preserved_code_blocks=0,
        )
