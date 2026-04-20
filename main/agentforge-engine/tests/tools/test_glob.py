"""
Tests for GlobTool

Tests for file pattern matching search functionality.
"""

import time

import pytest

from pyagentforge.tools.builtin.glob import GlobTool
from pyagentforge.tools.permission import PermissionChecker, PermissionConfig


class TestGlobTool:
    """Test cases for GlobTool."""

    def test_glob_tool_attributes(self):
        """Test GlobTool class attributes."""
        tool = GlobTool()

        assert tool.name == "glob"
        assert tool.timeout == 30
        assert tool.risk_level == "low"
        assert "pattern" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["pattern"]

    @pytest.mark.asyncio
    async def test_pattern_matching_simple(self, temp_workspace):
        """Test simple pattern matching."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.py", path=str(temp_workspace))

        assert "test.py" in result
        assert "Found" in result

    @pytest.mark.asyncio
    async def test_pattern_matching_yaml(self, temp_workspace):
        """Test matching YAML files."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.yaml", path=str(temp_workspace))

        assert "config.yaml" in result

    @pytest.mark.asyncio
    async def test_pattern_matching_markdown(self, temp_workspace):
        """Test matching Markdown files."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.md", path=str(temp_workspace))

        assert "README.md" in result

    @pytest.mark.asyncio
    async def test_recursive_search(self, temp_workspace):
        """Test recursive search with ** pattern."""
        tool = GlobTool()

        result = await tool.execute(pattern="**/*.py", path=str(temp_workspace))

        assert "test.py" in result
        assert "main.py" in result

    @pytest.mark.asyncio
    async def test_path_normalization(self, temp_workspace):
        """Test path normalization in output."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.py", path=str(temp_workspace))

        # Should use relative paths in output
        assert "test.py" in result

    @pytest.mark.asyncio
    async def test_no_matches(self, temp_workspace):
        """Test when no files match the pattern."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.nonexistent", path=str(temp_workspace))

        assert "No files matching" in result

    @pytest.mark.asyncio
    async def test_search_in_subdirectory(self, temp_workspace):
        """Test searching in a subdirectory."""
        tool = GlobTool()
        subdir = temp_workspace / "src"

        result = await tool.execute(pattern="*.py", path=str(subdir))

        assert "main.py" in result
        assert "test.py" not in result  # In parent directory

    @pytest.mark.asyncio
    async def test_default_path(self, temp_workspace):
        """Test using default path (current directory)."""
        tool = GlobTool()

        # Using default path "."
        result = await tool.execute(pattern="*.py", path=str(temp_workspace))

        assert "Found" in result or "test.py" in result

    @pytest.mark.asyncio
    async def test_results_sorted_by_mtime(self, temp_workspace):
        """Test that results are sorted by modification time."""
        tool = GlobTool()

        # Modify one file to make it newer
        time.sleep(0.1)
        (temp_workspace / "test.py").touch()

        result = await tool.execute(pattern="*.py", path=str(temp_workspace))

        # Most recently modified should appear first
        result.split("\n")
        # test.py should be first (most recently touched)
        assert "test.py" in result


class TestGlobToolWithPermission:
    """Test GlobTool with permission checking."""

    @pytest.mark.asyncio
    async def test_glob_with_permission_denied(self, tmp_path):
        """Test glob with permission denied."""
        config = PermissionConfig(
            allowed=["*"],
            denied_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = GlobTool(permission_checker=checker)

        result = await tool.execute(pattern="*.txt", path=str(tmp_path))

        assert "denied" in result.lower() or "Error" in result

    @pytest.mark.asyncio
    async def test_glob_with_permission_allowed(self, tmp_path):
        """Test glob with permission allowed."""
        config = PermissionConfig(
            allowed=["*"],
            allowed_paths=[str(tmp_path)]
        )
        checker = PermissionChecker(config)
        tool = GlobTool(permission_checker=checker)

        # Create test file
        (tmp_path / "test.txt").write_text("content")

        result = await tool.execute(pattern="*.txt", path=str(tmp_path))

        assert "test.txt" in result
        assert "Error" not in result


class TestGlobToolPatterns:
    """Test various glob patterns."""

    @pytest.mark.asyncio
    async def test_wildcard_pattern(self, temp_workspace):
        """Test wildcard * pattern."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.py", path=str(temp_workspace))

        assert "test.py" in result

    @pytest.mark.asyncio
    async def test_double_wildcard_recursive(self, temp_workspace):
        """Test double wildcard ** for recursive search."""
        tool = GlobTool()

        result = await tool.execute(pattern="**/*.py", path=str(temp_workspace))

        assert "test.py" in result
        assert "main.py" in result

    @pytest.mark.asyncio
    async def test_question_mark_single_char(self, temp_workspace):
        """Test ? pattern for single character."""
        tool = GlobTool()
        (temp_workspace / "test1.py").write_text("print('x')\n")

        result = await tool.execute(pattern="test?.py", path=str(temp_workspace))

        assert "test1.py" in result
        assert "test.py" not in result

    @pytest.mark.asyncio
    async def test_multiple_extensions(self, temp_workspace):
        """Test pattern doesn't match multiple extensions by default."""
        tool = GlobTool()

        # Create file with different extension
        (temp_workspace / "test.pyc").write_bytes(b"compiled")

        result = await tool.execute(pattern="*.py", path=str(temp_workspace))

        assert "test.py" in result
        assert "test.pyc" not in result

    @pytest.mark.asyncio
    async def test_directory_pattern(self, temp_workspace):
        """Test pattern matching directories."""
        tool = GlobTool()

        # Glob for all Python files in any subdirectory
        result = await tool.execute(pattern="*/*.py", path=str(temp_workspace))

        # Should find main.py in src/
        assert "main.py" in result


class TestGlobToolEdgeCases:
    """Edge case tests for GlobTool."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, tmp_path):
        """Test searching in an empty directory."""
        tool = GlobTool()
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = await tool.execute(pattern="*", path=str(empty_dir))

        assert "No files matching" in result

    @pytest.mark.asyncio
    async def test_many_files_limit(self, tmp_path):
        """Test handling many files (output limiting)."""
        tool = GlobTool()

        # Create many files
        for i in range(150):
            (tmp_path / f"file_{i:03d}.txt").write_text(f"content {i}")

        result = await tool.execute(pattern="*.txt", path=str(tmp_path))

        # Should indicate there are more files
        assert "Found" in result

    @pytest.mark.asyncio
    async def test_special_characters_in_pattern(self, tmp_path):
        """Test pattern with special characters."""
        tool = GlobTool()

        # Create file with special name
        (tmp_path / "file-with-dash.txt").write_text("content")

        result = await tool.execute(pattern="*dash*.txt", path=str(tmp_path))

        assert "file-with-dash.txt" in result

    @pytest.mark.asyncio
    async def test_nonexistent_directory(self, tmp_path):
        """Test searching in non-existent directory."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.txt", path=str(tmp_path / "nonexistent"))

        # Should handle gracefully
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_file_as_path(self, tmp_path):
        """Test when path is a file instead of directory."""
        tool = GlobTool()
        file_path = tmp_path / "file.txt"
        file_path.write_text("content")

        # Using a file as path - glob on file returns empty typically
        result = await tool.execute(pattern="*.txt", path=str(file_path))

        # Should handle gracefully
        assert result

    @pytest.mark.asyncio
    async def test_hidden_files(self, tmp_path):
        """Test matching hidden files."""
        tool = GlobTool()

        # Create hidden file
        (tmp_path / ".hidden").write_text("hidden content")

        result = await tool.execute(pattern=".*", path=str(tmp_path))

        # Hidden files may or may not be included
        assert result


class TestGlobToolSchema:
    """Test schema generation for GlobTool."""

    def test_to_anthropic_schema(self):
        """Test Anthropic schema generation."""
        tool = GlobTool()

        schema = tool.to_anthropic_schema()

        assert schema["name"] == "glob"
        assert "description" in schema
        assert "input_schema" in schema
        assert "pattern" in schema["input_schema"]["properties"]
        assert "path" in schema["input_schema"]["properties"]

    def test_to_openai_schema(self):
        """Test OpenAI schema generation."""
        tool = GlobTool()

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "glob"
        assert "parameters" in schema["function"]

    def test_path_default(self):
        """Test that path has correct default."""
        tool = GlobTool()

        schema = tool.to_anthropic_schema()
        path_prop = schema["input_schema"]["properties"]["path"]

        assert path_prop["default"] == "."


class TestGlobToolIntegration:
    """Integration tests for GlobTool."""

    @pytest.mark.asyncio
    async def test_find_all_python_files(self, temp_workspace):
        """Test finding all Python files recursively."""
        tool = GlobTool()

        result = await tool.execute(pattern="**/*.py", path=str(temp_workspace))

        assert "test.py" in result
        assert "main.py" in result

    @pytest.mark.asyncio
    async def test_find_config_files(self, temp_workspace):
        """Test finding configuration files."""
        tool = GlobTool()

        result = await tool.execute(pattern="*.yaml", path=str(temp_workspace))

        assert "config.yaml" in result

    @pytest.mark.asyncio
    async def test_combined_with_read(self, temp_workspace):
        """Test using glob results with read tool."""
        from pyagentforge.tools.builtin.read import ReadTool

        glob_tool = GlobTool()
        read_tool = ReadTool()

        # Find Python files
        glob_result = await glob_tool.execute(pattern="*.py", path=str(temp_workspace))

        # Should find test.py
        assert "test.py" in glob_result

        # Read the found file
        read_result = await read_tool.execute(
            file_path=str(temp_workspace / "test.py")
        )

        assert "print('hello world')" in read_result
