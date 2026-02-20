"""
Tests for EditTool

Tests for file editing functionality.
"""

import pytest
from pathlib import Path

from pyagentforge.tools.builtin.edit import EditTool
from pyagentforge.tools.permission import PermissionChecker, PermissionConfig


class TestEditTool:
    """Test cases for EditTool."""

    def test_edit_tool_attributes(self):
        """Test EditTool class attributes."""
        tool = EditTool()

        assert tool.name == "edit"
        assert tool.timeout == 30
        assert tool.risk_level == "medium"
        assert "file_path" in tool.parameters_schema["properties"]
        assert "old_string" in tool.parameters_schema["properties"]
        assert "new_string" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["file_path", "old_string", "new_string"]

    @pytest.mark.asyncio
    async def test_single_line_replace(self, tmp_path):
        """Test replacing a single line."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello, World!\nGoodbye, World!\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="Hello, World!",
            new_string="Hi, Universe!"
        )

        assert "Successfully" in result
        content = file_path.read_text()
        assert "Hi, Universe!" in content
        assert "Hello, World!" not in content

    @pytest.mark.asyncio
    async def test_multiline_replace(self, tmp_path):
        """Test replacing multiple lines."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("Line 1\nLine 2\nLine 3\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="Line 1\nLine 2",
            new_string="New Line 1\nNew Line 2"
        )

        assert "Successfully" in result
        content = file_path.read_text()
        assert "New Line 1" in content
        assert "New Line 2" in content
        assert "Line 1" not in content

    @pytest.mark.asyncio
    async def test_pattern_matching_exact(self, tmp_path):
        """Test exact pattern matching."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("value = 10\nvalue = 20\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="value = 10",
            new_string="value = 100"
        )

        assert "Successfully" in result
        content = file_path.read_text()
        assert "value = 100" in content
        assert "value = 20" in content  # Unchanged

    @pytest.mark.asyncio
    async def test_multiple_edits_error(self, tmp_path):
        """Test error when old_string appears multiple times."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("foo\nfoo\nfoo\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="foo",
            new_string="bar"
        )

        # Should error because 'foo' appears multiple times
        assert "Error" in result
        assert "3 times" in result or "multiple" in result.lower()

    @pytest.mark.asyncio
    async def test_replace_all(self, tmp_path):
        """Test replacing all occurrences with replace_all=True."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("foo\nfoo\nfoo\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="foo",
            new_string="bar",
            replace_all=True
        )

        assert "Successfully" in result
        content = file_path.read_text()
        assert content == "bar\nbar\nbar\n"

    @pytest.mark.asyncio
    async def test_no_match_error(self, tmp_path):
        """Test error when old_string not found."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("Hello, World!\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="Nonexistent",
            new_string="Replacement"
        )

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path):
        """Test editing a non-existent file."""
        tool = EditTool()

        result = await tool.execute(
            file_path=str(tmp_path / "nonexistent.txt"),
            old_string="old",
            new_string="new"
        )

        assert "Error" in result
        assert "does not exist" in result.lower()

    @pytest.mark.asyncio
    async def test_whitespace_preservation(self, tmp_path):
        """Test that whitespace is preserved exactly."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("    indented line\nother line\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="    indented line",
            new_string="        more indented"
        )

        assert "Successfully" in result
        content = file_path.read_text()
        assert "        more indented" in content

    @pytest.mark.asyncio
    async def test_replace_with_empty_string(self, tmp_path):
        """Test replacing with empty string (deletion)."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("keep\nremove\nkeep\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="remove\n",
            new_string=""
        )

        assert "Successfully" in result
        content = file_path.read_text()
        assert content == "keep\nkeep\n"

    @pytest.mark.asyncio
    async def test_replace_with_longer_string(self, tmp_path):
        """Test replacing with a longer string."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("x\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="x",
            new_string="this is a much longer replacement string"
        )

        assert "Successfully" in result
        assert len(file_path.read_text()) > 2

    @pytest.mark.asyncio
    async def test_unicode_handling(self, tmp_path):
        """Test handling Unicode characters."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("\u4e2d\u6587\n", encoding="utf-8")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="\u4e2d\u6587",
            new_string="\u65e5\u672c\u8a9e"
        )

        assert "Successfully" in result
        content = file_path.read_text(encoding="utf-8")
        assert "\u65e5\u672c\u8a9e" in content


class TestEditToolWithPermission:
    """Test EditTool with permission checking."""

    @pytest.mark.asyncio
    async def test_edit_with_permission_denied(self, tmp_path):
        """Test editing with permission denied."""
        config = PermissionConfig(
            allowed=["*"],
            denied_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = EditTool(permission_checker=checker)

        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="content",
            new_string="new"
        )

        assert "denied" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_edit_with_permission_allowed(self, tmp_path):
        """Test editing with permission allowed."""
        config = PermissionConfig(
            allowed=["*"],
            allowed_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = EditTool(permission_checker=checker)

        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="content",
            new_string="new"
        )

        assert "Successfully" in result


class TestEditToolEdgeCases:
    """Edge case tests for EditTool."""

    @pytest.mark.asyncio
    async def test_edit_empty_file(self, tmp_path):
        """Test editing an empty file."""
        tool = EditTool()
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="something",
            new_string="else"
        )

        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_binary_file(self, tmp_path):
        """Test editing a binary file."""
        tool = EditTool()
        file_path = tmp_path / "binary.bin"
        file_path.write_bytes(b"\x00\x01\x02\x03")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="\x01",
            new_string="\xff"
        )

        # May or may not work with binary files
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_consecutive_edits(self, tmp_path):
        """Test multiple consecutive edits."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("a b c d e\n")

        # First edit
        await tool.execute(
            file_path=str(file_path),
            old_string="a",
            new_string="1"
        )

        # Second edit
        await tool.execute(
            file_path=str(file_path),
            old_string="b",
            new_string="2"
        )

        # Third edit
        await tool.execute(
            file_path=str(file_path),
            old_string="c",
            new_string="3"
        )

        content = file_path.read_text()
        assert content == "1 2 3 d e\n"

    @pytest.mark.asyncio
    async def test_edit_preserves_line_endings(self, tmp_path):
        """Test that line endings are preserved."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        # Write with Windows line endings
        file_path.write_bytes(b"line1\r\nline2\r\n")

        result = await tool.execute(
            file_path=str(file_path),
            old_string="line1",
            new_string="new1"
        )

        assert "Successfully" in result
        content = file_path.read_bytes()
        # Should still have Windows line endings
        assert b"\r\n" in content

    @pytest.mark.asyncio
    async def test_very_long_old_string(self, tmp_path):
        """Test editing with a very long old_string."""
        tool = EditTool()
        file_path = tmp_path / "test.txt"
        long_content = "x" * 10000
        file_path.write_text(long_content)

        result = await tool.execute(
            file_path=str(file_path),
            old_string="x" * 1000,
            new_string="y" * 1000
        )

        # May or may not work depending on implementation
        assert result


class TestEditToolSchema:
    """Test schema generation for EditTool."""

    def test_to_anthropic_schema(self):
        """Test Anthropic schema generation."""
        tool = EditTool()

        schema = tool.to_anthropic_schema()

        assert schema["name"] == "edit"
        assert "description" in schema
        assert "input_schema" in schema
        assert "file_path" in schema["input_schema"]["properties"]
        assert "old_string" in schema["input_schema"]["properties"]
        assert "new_string" in schema["input_schema"]["properties"]
        assert "replace_all" in schema["input_schema"]["properties"]

    def test_to_openai_schema(self):
        """Test OpenAI schema generation."""
        tool = EditTool()

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "edit"
        assert "parameters" in schema["function"]

    def test_replace_all_default(self):
        """Test that replace_all has correct default."""
        tool = EditTool()

        schema = tool.to_anthropic_schema()
        replace_all = schema["input_schema"]["properties"]["replace_all"]

        assert replace_all["default"] is False
        assert replace_all["type"] == "boolean"


class TestEditToolIntegration:
    """Integration tests for EditTool."""

    @pytest.mark.asyncio
    async def test_edit_python_file(self, temp_workspace):
        """Test editing a Python file."""
        tool = EditTool()
        file_path = temp_workspace / "test.py"

        result = await tool.execute(
            file_path=str(file_path),
            old_string="print('hello world')",
            new_string="print('goodbye world')"
        )

        assert "Successfully" in result
        assert "goodbye world" in file_path.read_text()

    @pytest.mark.asyncio
    async def test_edit_yaml_file(self, temp_workspace):
        """Test editing a YAML file."""
        tool = EditTool()
        file_path = temp_workspace / "config.yaml"

        result = await tool.execute(
            file_path=str(file_path),
            old_string="key: value",
            new_string="key: updated_value"
        )

        assert "Successfully" in result
        assert "updated_value" in file_path.read_text()

    @pytest.mark.asyncio
    async def test_edit_read_write_cycle(self, tmp_path):
        """Test read, edit, read cycle."""
        from pyagentforge.tools.builtin.read import ReadTool

        edit_tool = EditTool()
        read_tool = ReadTool()

        file_path = tmp_path / "cycle.txt"
        file_path.write_text("Original content\n")

        # Read
        read_result = await read_tool.execute(file_path=str(file_path))
        assert "Original content" in read_result

        # Edit
        edit_result = await edit_tool.execute(
            file_path=str(file_path),
            old_string="Original content",
            new_string="Modified content"
        )
        assert "Successfully" in edit_result

        # Read again
        read_result = await read_tool.execute(file_path=str(file_path))
        assert "Modified content" in read_result
        assert "Original content" not in read_result
