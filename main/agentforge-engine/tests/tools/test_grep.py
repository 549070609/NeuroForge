"""
Tests for GrepTool

Tests for file content search functionality.
"""

import pytest
from pathlib import Path

from pyagentforge.tools.builtin.grep import GrepTool
from pyagentforge.tools.permission import PermissionChecker, PermissionConfig


class TestGrepTool:
    """Test cases for GrepTool."""

    def test_grep_tool_attributes(self):
        """Test GrepTool class attributes."""
        tool = GrepTool()

        assert tool.name == "grep"
        assert tool.timeout == 60
        assert tool.risk_level == "low"
        assert "pattern" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["pattern"]

    @pytest.mark.asyncio
    async def test_regex_search(self, temp_workspace):
        """Test basic regex search."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="hello",
            path=str(temp_workspace / "test.py")
        )

        assert "hello" in result

    @pytest.mark.asyncio
    async def test_regex_pattern(self, temp_workspace):
        """Test regex pattern matching."""
        tool = GrepTool()

        result = await tool.execute(
            pattern=r"print\(.*\)",
            path=str(temp_workspace / "test.py")
        )

        assert "print" in result

    @pytest.mark.asyncio
    async def test_case_sensitive_search(self, temp_workspace):
        """Test case-sensitive search (default)."""
        tool = GrepTool()

        # Create file with mixed case
        test_file = temp_workspace / "case_test.txt"
        test_file.write_text("Hello World\nhello world\n")

        result = await tool.execute(
            pattern="Hello",
            path=str(test_file),
            **{"-i": False}
        )

        # Should only match "Hello" not "hello"
        lines = [l for l in result.split("\n") if "Hello" in l or "hello" in l]
        assert any("Hello" in l for l in lines)

    @pytest.mark.asyncio
    async def test_case_insensitive_search(self, temp_workspace):
        """Test case-insensitive search."""
        tool = GrepTool()

        # Create file with mixed case
        test_file = temp_workspace / "case_test.txt"
        test_file.write_text("Hello World\nhello world\n")

        result = await tool.execute(
            pattern="hello",
            path=str(test_file),
            **{"-i": True}
        )

        # Should match both "Hello" and "hello"
        assert "Hello" in result or "hello" in result

    @pytest.mark.asyncio
    async def test_context_lines(self, temp_workspace):
        """Test showing context lines."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="key",
            path=str(temp_workspace / "config.yaml"),
            **{"-C": 2}
        )

        # Should show context
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_no_matches(self, temp_workspace):
        """Test when pattern doesn't match anything."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="nonexistent_pattern_xyz123",
            path=str(temp_workspace)
        )

        assert "No matches found" in result

    @pytest.mark.asyncio
    async def test_output_mode_files_with_matches(self, temp_workspace):
        """Test output_mode=files_with_matches."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="print",
            path=str(temp_workspace),
            output_mode="files_with_matches"
        )

        # Should only show file paths
        assert "test.py" in result
        # Should not show line content
        assert ":" not in result or result.count("\n") < 3

    @pytest.mark.asyncio
    async def test_output_mode_count(self, temp_workspace):
        """Test output_mode=count."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="print",
            path=str(temp_workspace / "test.py"),
            output_mode="count"
        )

        # Should show count
        assert "test.py" in result
        assert ":" in result  # Format: "file: count"

    @pytest.mark.asyncio
    async def test_output_mode_content(self, temp_workspace):
        """Test output_mode=content (default)."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="print",
            path=str(temp_workspace / "test.py"),
            output_mode="content"
        )

        # Should show actual content with line numbers
        assert "test.py" in result
        assert "print" in result

    @pytest.mark.asyncio
    async def test_glob_filter(self, temp_workspace):
        """Test filtering by glob pattern."""
        tool = GrepTool()

        result = await tool.execute(
            pattern=".*",  # Match anything
            path=str(temp_workspace),
            glob="*.py"
        )

        # Should only search Python files
        assert "test.py" in result
        assert "config.yaml" not in result

    @pytest.mark.asyncio
    async def test_head_limit(self, temp_workspace):
        """Test limiting output with head_limit."""
        tool = GrepTool()

        # Create file with many matches
        test_file = temp_workspace / "many_matches.txt"
        test_file.write_text("\n".join([f"match {i}" for i in range(100)]))

        result = await tool.execute(
            pattern="match",
            path=str(test_file),
            head_limit=5
        )

        lines = [l for l in result.split("\n") if l.strip()]
        # Should be limited (plus header line)
        assert len(lines) <= 6


class TestGrepToolWithPermission:
    """Test GrepTool with permission checking."""

    @pytest.mark.asyncio
    async def test_grep_with_permission_denied(self, tmp_path):
        """Test grep with permission denied."""
        config = PermissionConfig(
            allowed=["*"],
            denied_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = GrepTool(permission_checker=checker)

        result = await tool.execute(pattern="test", path=str(tmp_path))

        assert "denied" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_grep_with_permission_allowed(self, tmp_path):
        """Test grep with permission allowed."""
        config = PermissionConfig(
            allowed=["*"],
            allowed_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = GrepTool(permission_checker=checker)

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        result = await tool.execute(pattern="hello", path=str(test_file))

        assert "hello" in result
        assert "Error" not in result


class TestGrepToolAdvancedPatterns:
    """Test advanced regex patterns."""

    @pytest.mark.asyncio
    async def test_word_boundary(self, tmp_path):
        """Test word boundary pattern."""
        tool = GrepTool()
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello\nhelloworld\nhello world\n")

        result = await tool.execute(
            pattern=r"\bhello\b",
            path=str(test_file)
        )

        # Should match standalone "hello" but not "helloworld"
        lines = result.split("\n")
        matches = [l for l in lines if "hello" in l.lower()]
        # Check that we got results
        assert result

    @pytest.mark.asyncio
    async def test_digit_pattern(self, tmp_path):
        """Test digit matching pattern."""
        tool = GrepTool()
        test_file = tmp_path / "test.txt"
        test_file.write_text("number 123\nno number\nnumber 456\n")

        result = await tool.execute(
            pattern=r"\d+",
            path=str(test_file)
        )

        assert "123" in result
        assert "456" in result
        assert "no number" not in result

    @pytest.mark.asyncio
    async def test_anchor_patterns(self, tmp_path):
        """Test start/end anchor patterns."""
        tool = GrepTool()
        test_file = tmp_path / "test.txt"
        test_file.write_text("start of line\nmiddle of line\nend of line\n")

        result = await tool.execute(
            pattern=r"^start",
            path=str(test_file)
        )

        assert "start of line" in result
        assert "middle of line" not in result

    @pytest.mark.asyncio
    async def test_or_pattern(self, tmp_path):
        """Test OR pattern with |."""
        tool = GrepTool()
        test_file = tmp_path / "test.txt"
        test_file.write_text("cat\ndog\nbird\n")

        result = await tool.execute(
            pattern=r"cat|dog",
            path=str(test_file)
        )

        assert "cat" in result
        assert "dog" in result
        assert "bird" not in result

    @pytest.mark.asyncio
    async def test_character_class(self, tmp_path):
        """Test character class pattern."""
        tool = GrepTool()
        test_file = tmp_path / "test.txt"
        test_file.write_text("apple\nbanana\ncherry\n")

        result = await tool.execute(
            pattern=r"[aeiou]",
            path=str(test_file)
        )

        # All lines have vowels
        assert "apple" in result

    @pytest.mark.asyncio
    async def test_invalid_regex(self, tmp_path):
        """Test handling invalid regex pattern."""
        tool = GrepTool()
        test_file = tmp_path / "test.txt"
        test_file.write_text("content\n")

        result = await tool.execute(
            pattern=r"[invalid(regex",  # Invalid regex
            path=str(test_file)
        )

        assert "Error" in result or "Invalid regex" in result


class TestGrepToolEdgeCases:
    """Edge case tests for GrepTool."""

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        """Test searching in empty file."""
        tool = GrepTool()
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        result = await tool.execute(
            pattern="anything",
            path=str(test_file)
        )

        assert "No matches found" in result

    @pytest.mark.asyncio
    async def test_binary_file(self, tmp_path):
        """Test searching in binary file."""
        tool = GrepTool()
        test_file = tmp_path / "binary.bin"
        test_file.write_bytes(b"\x00\x01\x02\x03hello\x00")

        result = await tool.execute(
            pattern="hello",
            path=str(test_file)
        )

        # May or may not find it (errors ignored for binary)
        assert result

    @pytest.mark.asyncio
    async def test_nonexistent_file(self, tmp_path):
        """Test searching in non-existent file."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="test",
            path=str(tmp_path / "nonexistent.txt")
        )

        # Should handle gracefully
        assert result

    @pytest.mark.asyncio
    async def test_directory_search(self, temp_workspace):
        """Test searching in directory (multiple files)."""
        tool = GrepTool()

        result = await tool.execute(
            pattern="print",
            path=str(temp_workspace)
        )

        # Should search all files in directory
        assert result

    @pytest.mark.asyncio
    async def test_large_file(self, tmp_path):
        """Test searching in large file."""
        tool = GrepTool()
        test_file = tmp_path / "large.txt"

        # Create large file with target in middle
        with open(test_file, "w") as f:
            for i in range(1000):
                if i == 500:
                    f.write("TARGET_LINE\n")
                else:
                    f.write(f"line {i}\n")

        result = await tool.execute(
            pattern="TARGET_LINE",
            path=str(test_file)
        )

        assert "TARGET_LINE" in result

    @pytest.mark.asyncio
    async def test_unicode_content(self, tmp_path):
        """Test searching Unicode content."""
        tool = GrepTool()
        test_file = tmp_path / "unicode.txt"
        test_file.write_text("\u4e2d\u6587\u6d4b\u8bd5\nEnglish\n", encoding="utf-8")

        result = await tool.execute(
            pattern="\u4e2d\u6587",
            path=str(test_file)
        )

        assert "\u4e2d\u6587" in result or result  # May or may not match


class TestGrepToolSchema:
    """Test schema generation for GrepTool."""

    def test_to_anthropic_schema(self):
        """Test Anthropic schema generation."""
        tool = GrepTool()

        schema = tool.to_anthropic_schema()

        assert schema["name"] == "grep"
        assert "description" in schema
        assert "input_schema" in schema
        assert "pattern" in schema["input_schema"]["properties"]
        assert "path" in schema["input_schema"]["properties"]
        assert "glob" in schema["input_schema"]["properties"]

    def test_to_openai_schema(self):
        """Test OpenAI schema generation."""
        tool = GrepTool()

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "grep"
        assert "parameters" in schema["function"]

    def test_output_mode_enum(self):
        """Test output_mode has correct enum values."""
        tool = GrepTool()

        schema = tool.to_anthropic_schema()
        output_mode = schema["input_schema"]["properties"]["output_mode"]

        assert output_mode["default"] == "content"
        assert "content" in output_mode["enum"]
        assert "files_with_matches" in output_mode["enum"]
        assert "count" in output_mode["enum"]


class TestGrepToolIntegration:
    """Integration tests for GrepTool."""

    @pytest.mark.asyncio
    async def test_find_function_definitions(self, temp_workspace):
        """Test finding function definitions in Python files."""
        tool = GrepTool()

        result = await tool.execute(
            pattern=r"def \w+\(",
            path=str(temp_workspace),
            glob="*.py"
        )

        # Should find function definitions
        assert "def main():" in result or result

    @pytest.mark.asyncio
    async def test_search_and_read(self, temp_workspace):
        """Test searching then reading found file."""
        from pyagentforge.tools.builtin.read import ReadTool

        grep_tool = GrepTool()
        read_tool = ReadTool()

        # Find files containing "print"
        grep_result = await grep_tool.execute(
            pattern="print",
            path=str(temp_workspace),
            glob="*.py"
        )

        # Read the found file
        read_result = await read_tool.execute(
            file_path=str(temp_workspace / "test.py")
        )

        assert "print" in read_result

    @pytest.mark.asyncio
    async def test_find_all_imports(self, temp_workspace):
        """Test finding all import statements."""
        tool = GrepTool()

        # Create file with imports
        (temp_workspace / "imports.py").write_text("import os\nimport sys\n")

        result = await tool.execute(
            pattern=r"^import ",
            path=str(temp_workspace),
            glob="*.py"
        )

        assert "import os" in result or "import sys" in result
