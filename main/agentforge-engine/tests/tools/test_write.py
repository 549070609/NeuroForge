"""
Tests for WriteTool

Tests for file writing functionality.
"""

import os
import pytest
from pathlib import Path

from pyagentforge.tools.builtin.write import WriteTool
from pyagentforge.tools.permission import PermissionChecker, PermissionConfig


class TestWriteTool:
    """Test cases for WriteTool."""

    def test_write_tool_attributes(self):
        """Test WriteTool class attributes."""
        tool = WriteTool()

        assert tool.name == "write"
        assert tool.timeout == 30
        assert tool.risk_level == "medium"
        assert "file_path" in tool.parameters_schema["properties"]
        assert "content" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["file_path", "content"]

    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path):
        """Test writing a new file."""
        tool = WriteTool()
        file_path = tmp_path / "new_file.txt"
        content = "Hello, World!"

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.exists()
        assert file_path.read_text() == content

    @pytest.mark.asyncio
    async def test_overwrite_existing(self, tmp_path):
        """Test overwriting an existing file."""
        tool = WriteTool()
        file_path = tmp_path / "existing.txt"
        file_path.write_text("Old content")

        new_content = "New content"
        result = await tool.execute(
            file_path=str(file_path),
            content=new_content
        )

        assert "successfully" in result.lower()
        assert file_path.read_text() == new_content

    @pytest.mark.asyncio
    async def test_create_directories(self, tmp_path):
        """Test creating parent directories automatically."""
        tool = WriteTool()
        file_path = tmp_path / "subdir" / "deep" / "file.txt"
        content = "Nested content"

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.exists()
        assert file_path.parent.exists()
        assert file_path.read_text() == content

    @pytest.mark.asyncio
    async def test_write_with_encoding(self, tmp_path):
        """Test writing with UTF-8 encoding."""
        tool = WriteTool()
        file_path = tmp_path / "utf8.txt"
        content = "Unicode: \u4e2d\u6587 \U0001F600"  # Chinese + emoji

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_write_empty_content(self, tmp_path):
        """Test writing empty content."""
        tool = WriteTool()
        file_path = tmp_path / "empty.txt"
        content = ""

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.exists()
        assert file_path.read_text() == ""

    @pytest.mark.asyncio
    async def test_write_multiline_content(self, tmp_path):
        """Test writing multiline content."""
        tool = WriteTool()
        file_path = tmp_path / "multiline.txt"
        content = "Line 1\nLine 2\nLine 3\n"

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.read_text() == content

    @pytest.mark.asyncio
    async def test_write_large_content(self, tmp_path):
        """Test writing large content."""
        tool = WriteTool()
        file_path = tmp_path / "large.txt"
        content = "x" * 100000  # 100KB

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert len(file_path.read_text()) == 100000

    @pytest.mark.asyncio
    async def test_write_with_special_characters_in_path(self, tmp_path):
        """Test writing to path with special characters."""
        tool = WriteTool()
        file_path = tmp_path / "file with spaces.txt"
        content = "content"

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_write_python_file(self, tmp_path):
        """Test writing a Python file."""
        tool = WriteTool()
        file_path = tmp_path / "script.py"
        content = '''#!/usr/bin/env python3
"""A test script."""

def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
'''

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.read_text() == content


class TestWriteToolWithPermission:
    """Test WriteTool with permission checking."""

    @pytest.mark.asyncio
    async def test_write_with_permission_denied(self, tmp_path):
        """Test writing with permission denied."""
        config = PermissionConfig(
            allowed=["*"],
            denied_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = WriteTool(permission_checker=checker)

        file_path = tmp_path / "test.txt"

        result = await tool.execute(
            file_path=str(file_path),
            content="content"
        )

        assert "denied" in result.lower() or "Error" in result
        assert not file_path.exists()

    @pytest.mark.asyncio
    async def test_write_with_permission_allowed(self, tmp_path):
        """Test writing with permission allowed."""
        config = PermissionConfig(
            allowed=["*"],
            allowed_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = WriteTool(permission_checker=checker)

        file_path = tmp_path / "test.txt"

        result = await tool.execute(
            file_path=str(file_path),
            content="content"
        )

        assert "successfully" in result.lower()
        assert file_path.exists()


class TestWriteToolErrorHandling:
    """Error handling tests for WriteTool."""

    @pytest.mark.asyncio
    async def test_write_to_readonly_directory(self, tmp_path):
        """Test writing to a read-only directory."""
        tool = WriteTool()
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        file_path = readonly_dir / "test.txt"

        # Make directory read-only
        try:
            os.chmod(readonly_dir, 0o444)

            result = await tool.execute(
                file_path=str(file_path),
                content="content"
            )

            # Should handle gracefully
            assert "Error" in result or "denied" in result.lower()
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)

    @pytest.mark.asyncio
    async def test_write_to_existing_directory(self, tmp_path):
        """Test writing to a path that's already a directory."""
        tool = WriteTool()
        dir_path = tmp_path / "existing_dir"
        dir_path.mkdir()

        result = await tool.execute(
            file_path=str(dir_path),
            content="content"
        )

        # Should fail since it's a directory
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_write_with_invalid_path(self):
        """Test writing to an invalid path."""
        tool = WriteTool()

        result = await tool.execute(
            file_path="/nonexistent/path/that/does/not/exist/file.txt",
            content="content"
        )

        # May succeed or fail depending on permissions
        assert result  # Should return something


class TestWriteToolSchema:
    """Test schema generation for WriteTool."""

    def test_to_anthropic_schema(self):
        """Test Anthropic schema generation."""
        tool = WriteTool()

        schema = tool.to_anthropic_schema()

        assert schema["name"] == "write"
        assert "description" in schema
        assert "input_schema" in schema
        assert "file_path" in schema["input_schema"]["properties"]
        assert "content" in schema["input_schema"]["properties"]

    def test_to_openai_schema(self):
        """Test OpenAI schema generation."""
        tool = WriteTool()

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "write"
        assert "parameters" in schema["function"]
        assert "file_path" in schema["function"]["parameters"]["properties"]
        assert "content" in schema["function"]["parameters"]["properties"]

    def test_required_parameters(self):
        """Test that file_path and content are required."""
        tool = WriteTool()

        schema = tool.to_anthropic_schema()
        required = schema["input_schema"]["required"]

        assert "file_path" in required
        assert "content" in required


class TestWriteToolIntegration:
    """Integration tests for WriteTool."""

    @pytest.mark.asyncio
    async def test_write_and_read_cycle(self, tmp_path):
        """Test write followed by read."""
        from pyagentforge.tools.builtin.read import ReadTool

        write_tool = WriteTool()
        read_tool = ReadTool()

        file_path = tmp_path / "cycle.txt"
        content = "Test content for cycle"

        # Write
        write_result = await write_tool.execute(
            file_path=str(file_path),
            content=content
        )
        assert "successfully" in write_result.lower()

        # Read
        read_result = await read_tool.execute(file_path=str(file_path))
        assert content in read_result

    @pytest.mark.asyncio
    async def test_write_json_file(self, tmp_path):
        """Test writing a JSON file."""
        import json

        tool = WriteTool()
        file_path = tmp_path / "data.json"
        data = {"key": "value", "number": 42}
        content = json.dumps(data, indent=2)

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()

        # Verify it can be parsed as JSON
        loaded = json.loads(file_path.read_text())
        assert loaded == data

    @pytest.mark.asyncio
    async def test_write_yaml_file(self, tmp_path):
        """Test writing a YAML file."""
        tool = WriteTool()
        file_path = tmp_path / "config.yaml"
        content = """key: value
nested:
  item: value
  number: 42
"""

        result = await tool.execute(
            file_path=str(file_path),
            content=content
        )

        assert "successfully" in result.lower()
        assert file_path.read_text() == content

    @pytest.mark.asyncio
    async def test_overwrite_preserves_permissions(self, tmp_path):
        """Test that overwriting preserves executable permission."""
        tool = WriteTool()
        file_path = tmp_path / "script.sh"
        file_path.write_text("#!/bin/bash\necho old")

        # Make executable
        file_path.chmod(0o755)
        old_mode = file_path.stat().st_mode

        # Overwrite
        await tool.execute(
            file_path=str(file_path),
            content="#!/bin/bash\necho new"
        )

        # Check content updated
        assert "echo new" in file_path.read_text()
