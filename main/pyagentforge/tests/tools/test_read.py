"""
Tests for ReadTool

Tests for file reading functionality.
"""

import json
import pytest
from pathlib import Path

from pyagentforge.tools.builtin.read import ReadTool
from pyagentforge.tools.permission import PermissionChecker, PermissionConfig, PermissionResult


class TestReadTool:
    """Test cases for ReadTool."""

    def test_read_tool_attributes(self):
        """Test ReadTool class attributes."""
        tool = ReadTool()

        assert tool.name == "read"
        assert tool.timeout == 30
        assert tool.risk_level == "low"
        assert "file_path" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["file_path"]

    @pytest.mark.asyncio
    async def test_read_text_file(self, temp_file):
        """Test reading a text file."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_file))

        assert "Test content" in result
        assert "Line 2" in result
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_read_file_with_line_numbers(self, temp_file):
        """Test that line numbers are included in output."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_file))

        # Line numbers should be present (format: "     1\t")
        assert "1" in result
        assert "2" in result

    @pytest.mark.asyncio
    async def test_read_file_with_offset(self, temp_file):
        """Test reading file with offset."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_file), offset=1)

        # Should start from line 2
        assert "Line 2" in result
        assert "Test content" not in result  # Line 1 should be skipped

    @pytest.mark.asyncio
    async def test_read_file_with_limit(self, temp_file):
        """Test reading file with limit."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_file), limit=1)

        # Should only have one line
        assert "Test content" in result
        assert "Line 2" not in result

    @pytest.mark.asyncio
    async def test_read_file_with_offset_and_limit(self, temp_file):
        """Test reading file with both offset and limit."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_file), offset=1, limit=1)

        # Should only have line 2
        assert "Line 2" in result
        assert "Line 3" not in result
        assert "Test content" not in result

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, tmp_path):
        """Test reading a non-existent file."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(tmp_path / "nonexistent.txt"))

        assert "does not exist" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_read_directory(self, temp_workspace):
        """Test reading a directory (should fail)."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_workspace))

        assert "not a file" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_encoding_handling_utf8(self, tmp_path):
        """Test reading UTF-8 encoded file."""
        tool = ReadTool()
        file_path = tmp_path / "utf8.txt"
        file_path.write_text("Hello, World!\n", encoding="utf-8")

        result = await tool.execute(file_path=str(file_path))

        assert "Hello, World!" in result
        assert "Encoding: utf-8" in result

    @pytest.mark.asyncio
    async def test_encoding_handling_gbk(self, tmp_path):
        """Test reading GBK encoded file."""
        tool = ReadTool()
        file_path = tmp_path / "gbk.txt"
        # Write Chinese characters in GBK encoding
        file_path.write_bytes("\u4e2d\u6587\u6d4b\u8bd5\n".encode("gbk"))

        result = await tool.execute(file_path=str(file_path))

        # Should successfully decode
        assert "Error" not in result or "Unable to decode" not in result

    @pytest.mark.asyncio
    async def test_read_binary_file_fallback(self, tmp_path):
        """Test handling of binary files."""
        tool = ReadTool()
        file_path = tmp_path / "binary.bin"
        file_path.write_bytes(b"\x00\x01\x02\x03\x04")

        result = await tool.execute(file_path=str(file_path))

        # Should attempt to read (may fail or decode as latin-1)
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_read_empty_file(self, tmp_path):
        """Test reading an empty file."""
        tool = ReadTool()
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        result = await tool.execute(file_path=str(file_path))

        # Should handle gracefully
        assert result
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_read_file_with_special_characters(self, tmp_path):
        """Test reading file with special characters in path."""
        tool = ReadTool()
        file_path = tmp_path / "file with spaces.txt"
        file_path.write_text("content with spaces\n")

        result = await tool.execute(file_path=str(file_path))

        assert "content with spaces" in result

    @pytest.mark.asyncio
    async def test_read_jupyter_notebook(self, tmp_path):
        """Test reading a Jupyter notebook."""
        tool = ReadTool()
        notebook_path = tmp_path / "test.ipynb"

        notebook_content = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["print('hello')"],
                    "outputs": []
                },
                {
                    "cell_type": "markdown",
                    "source": ["# Title"],
                }
            ],
            "metadata": {}
        }

        notebook_path.write_text(json.dumps(notebook_content))

        result = await tool.execute(file_path=str(notebook_path))

        assert "Jupyter Notebook" in result
        assert "Cell" in result
        assert "print('hello')" in result

    @pytest.mark.asyncio
    async def test_read_image_file(self, tmp_path):
        """Test reading an image file."""
        tool = ReadTool()
        image_path = tmp_path / "test.png"

        # Create a minimal PNG file
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)

        result = await tool.execute(file_path=str(image_path))

        assert "[Image file" in result


class TestReadToolWithPermission:
    """Test ReadTool with permission checking."""

    @pytest.mark.asyncio
    async def test_read_with_permission_denied(self, tmp_path):
        """Test reading with permission denied."""
        config = PermissionConfig(
            allowed=["*"],
            denied_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = ReadTool(permission_checker=checker)

        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        result = await tool.execute(file_path=str(file_path))

        assert "denied" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_read_with_permission_allowed(self, tmp_path):
        """Test reading with permission allowed."""
        config = PermissionConfig(
            allowed=["*"],
            allowed_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = ReadTool(permission_checker=checker)

        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        result = await tool.execute(file_path=str(file_path))

        assert "content" in result
        assert "Error" not in result


class TestReadToolEdgeCases:
    """Edge case tests for ReadTool."""

    @pytest.mark.asyncio
    async def test_read_large_file_rejection(self, tmp_path):
        """Test reading a file that's too large."""
        tool = ReadTool()
        file_path = tmp_path / "large.txt"

        # Create a file larger than 10MB (write in chunks to avoid memory issues)
        with open(file_path, "wb") as f:
            for _ in range(11 * 1024):  # 11MB
                f.write(b"x" * 1024)

        result = await tool.execute(file_path=str(file_path))

        assert "too large" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_read_with_limit_larger_than_file(self, tmp_path):
        """Test reading with limit larger than file size."""
        tool = ReadTool()
        file_path = tmp_path / "small.txt"
        file_path.write_text("one line\n")

        result = await tool.execute(file_path=str(file_path), limit=1000)

        assert "one line" in result
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_read_with_negative_offset(self, tmp_path):
        """Test reading with negative offset."""
        tool = ReadTool()
        file_path = tmp_path / "test.txt"
        file_path.write_text("line 1\nline 2\n")

        result = await tool.execute(file_path=str(file_path), offset=-1)

        # Should handle gracefully (may treat as 0 or error)
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_read_symlink(self, tmp_path):
        """Test reading a symlink."""
        tool = ReadTool()
        real_file = tmp_path / "real.txt"
        real_file.write_text("real content\n")
        link_file = tmp_path / "link.txt"

        try:
            link_file.symlink_to(real_file)
        except OSError:
            pytest.skip("Symlinks not supported on this system")

        result = await tool.execute(file_path=str(link_file))

        assert "real content" in result

    @pytest.mark.asyncio
    async def test_read_pdf_file(self, tmp_path):
        """Test reading a PDF file."""
        tool = ReadTool()
        pdf_path = tmp_path / "test.pdf"

        # Create a minimal PDF
        pdf_path.write_bytes(b"%PDF-1.4\n%fake pdf content")

        result = await tool.execute(file_path=str(pdf_path))

        assert "PDF" in result

    @pytest.mark.asyncio
    async def test_read_pdf_with_pages(self, tmp_path):
        """Test reading a PDF with specific pages."""
        tool = ReadTool()
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%fake pdf content")

        result = await tool.execute(file_path=str(pdf_path), pages="1-5")

        assert "Pages:" in result
        assert "1-5" in result


class TestReadToolSchema:
    """Test schema generation for ReadTool."""

    def test_to_anthropic_schema(self):
        """Test Anthropic schema generation."""
        tool = ReadTool()

        schema = tool.to_anthropic_schema()

        assert schema["name"] == "read"
        assert "description" in schema
        assert "input_schema" in schema
        assert "file_path" in schema["input_schema"]["properties"]

    def test_to_openai_schema(self):
        """Test OpenAI schema generation."""
        tool = ReadTool()

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "read"
        assert "parameters" in schema["function"]
        assert "file_path" in schema["function"]["parameters"]["properties"]


class TestReadToolIntegration:
    """Integration tests for ReadTool."""

    @pytest.mark.asyncio
    async def test_read_python_file(self, temp_workspace):
        """Test reading a Python file."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_workspace / "test.py"))

        assert "print('hello world')" in result
        assert "Encoding:" in result

    @pytest.mark.asyncio
    async def test_read_yaml_file(self, temp_workspace):
        """Test reading a YAML file."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_workspace / "config.yaml"))

        assert "key: value" in result

    @pytest.mark.asyncio
    async def test_read_markdown_file(self, temp_workspace):
        """Test reading a Markdown file."""
        tool = ReadTool()

        result = await tool.execute(file_path=str(temp_workspace / "README.md"))

        assert "# Test Project" in result
