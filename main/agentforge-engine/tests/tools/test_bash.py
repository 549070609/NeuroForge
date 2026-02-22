"""
Tests for BashTool

Tests for shell command execution.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pyagentforge.tools.builtin.bash import BashTool


class TestBashTool:
    """Test cases for BashTool."""

    def test_bash_tool_attributes(self):
        """Test BashTool class attributes."""
        tool = BashTool()

        assert tool.name == "bash"
        assert tool.timeout == 120
        assert tool.risk_level == "high"
        assert "command" in tool.parameters_schema["properties"]
        assert tool.parameters_schema["required"] == ["command"]

    def test_bash_tool_with_working_dir(self):
        """Test BashTool with custom working directory."""
        tool = BashTool(working_dir="/tmp")

        assert tool.working_dir == "/tmp"

    @pytest.mark.asyncio
    async def test_simple_command_execution(self):
        """Test executing a simple command."""
        tool = BashTool()

        result = await tool.execute(command="echo 'Hello, World!'")

        assert "Hello, World!" in result
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_command_with_output(self):
        """Test command that produces output."""
        tool = BashTool()

        result = await tool.execute(command="echo 'test output'")

        assert "test output" in result

    @pytest.mark.asyncio
    async def test_command_exit_code_handling(self):
        """Test handling of non-zero exit codes."""
        tool = BashTool()

        # Command that exits with non-zero code
        result = await tool.execute(command="exit 1")

        assert "Exit code: 1" in result

    @pytest.mark.asyncio
    async def test_command_stderr_capture(self):
        """Test capturing stderr output."""
        tool = BashTool()

        # Write to stderr
        result = await tool.execute(command="echo 'error message' >&2")

        assert "[stderr]" in result or "error message" in result

    @pytest.mark.asyncio
    async def test_command_timeout(self):
        """Test command timeout handling."""
        tool = BashTool()

        # Command that sleeps longer than timeout
        result = await tool.execute(command="sleep 10", timeout=500)  # 500ms timeout

        assert "timed out" in result.lower() or "timeout" in result.lower()

    @pytest.mark.asyncio
    async def test_command_no_output(self):
        """Test command with no output."""
        tool = BashTool()

        result = await tool.execute(command="true")  # Command that succeeds with no output

        assert "(no output)" in result or "Exit code: 0" in result

    @pytest.mark.asyncio
    async def test_command_with_pipes(self):
        """Test command with pipes."""
        tool = BashTool()

        result = await tool.execute(command="echo 'hello world' | grep hello")

        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_environment_variables(self):
        """Test command with environment variables."""
        tool = BashTool()

        result = await tool.execute(command="echo $HOME")

        # Should output the home directory path
        assert result  # Should have some output
        assert "Error" not in result

    @pytest.mark.asyncio
    async def test_description_parameter(self):
        """Test that description parameter is accepted."""
        tool = BashTool()

        result = await tool.execute(
            command="echo 'test'",
            description="A test command"
        )

        assert "test" in result

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Test custom timeout parameter."""
        tool = BashTool()

        # Fast command with long timeout
        result = await tool.execute(
            command="echo 'quick'",
            timeout=60000  # 60 seconds
        )

        assert "quick" in result
        assert "timeout" not in result.lower()

    @pytest.mark.asyncio
    async def test_command_with_special_characters(self):
        """Test command with special characters."""
        tool = BashTool()

        result = await tool.execute(command='echo "Special: $HOME"')

        # Should handle special characters
        assert "Special:" in result

    @pytest.mark.asyncio
    async def test_working_directory(self):
        """Test command execution in specific directory."""
        tool = BashTool(working_dir="/tmp")

        result = await tool.execute(command="pwd")

        assert "/tmp" in result

    @pytest.mark.asyncio
    async def test_nonexistent_working_directory(self):
        """Test command execution with non-existent working directory."""
        tool = BashTool(working_dir="/nonexistent/directory")

        result = await tool.execute(command="pwd")

        # Should handle gracefully (may error)
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_command_not_found(self):
        """Test handling of non-existent commands."""
        tool = BashTool()

        result = await tool.execute(command="nonexistent_command_xyz")

        # Should have error or non-zero exit code
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_multiline_command(self):
        """Test multiline command with semicolons."""
        tool = BashTool()

        result = await tool.execute(command="echo 'line1'; echo 'line2'")

        assert "line1" in result
        assert "line2" in result

    @pytest.mark.asyncio
    async def test_command_with_quotes(self):
        """Test command with various quote styles."""
        tool = BashTool()

        result = await tool.execute(command='echo "double quotes"')

        assert "double quotes" in result

    @pytest.mark.asyncio
    async def test_to_anthropic_schema(self):
        """Test Anthropic schema generation."""
        tool = BashTool()

        schema = tool.to_anthropic_schema()

        assert schema["name"] == "bash"
        assert "description" in schema
        assert "input_schema" in schema

    @pytest.mark.asyncio
    async def test_to_openai_schema(self):
        """Test OpenAI schema generation."""
        tool = BashTool()

        schema = tool.to_openai_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "bash"
        assert "parameters" in schema["function"]

    @pytest.mark.asyncio
    async def test_concurrent_commands(self):
        """Test running multiple commands concurrently."""
        tool = BashTool()

        # Run multiple commands concurrently
        results = await asyncio.gather(
            tool.execute(command="echo 'cmd1'"),
            tool.execute(command="echo 'cmd2'"),
            tool.execute(command="echo 'cmd3'"),
        )

        assert len(results) == 3
        assert all("Error" not in r for r in results)


class TestBashToolErrorHandling:
    """Test error handling for BashTool."""

    @pytest.mark.asyncio
    async def test_permission_denied_command(self):
        """Test handling permission denied errors."""
        tool = BashTool()

        # Try to access a file that likely requires elevated permissions
        result = await tool.execute(command="cat /root/.ssh/id_rsa 2>&1 || true")

        # Should complete without crashing
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_invalid_syntax_command(self):
        """Test handling commands with invalid syntax."""
        tool = BashTool()

        result = await tool.execute(command="if then else")  # Invalid bash syntax

        # Should have error in output
        assert result  # Should return something

    @pytest.mark.asyncio
    async def test_killed_process(self):
        """Test handling of killed processes."""
        tool = BashTool()

        # Start a command and send SIGTERM
        result = await tool.execute(command="sleep 100 & kill $! 2>/dev/null; echo 'killed'")

        # Should complete
        assert result


class TestBashToolIntegration:
    """Integration tests for BashTool."""

    @pytest.mark.asyncio
    async def test_git_command(self, temp_workspace):
        """Test running git commands."""
        tool = BashTool(working_dir=str(temp_workspace))

        # Initialize a git repo
        result = await tool.execute(command="git init")

        assert "Initialized" in result or "Reinitialized" in result

    @pytest.mark.asyncio
    async def test_file_operations(self, temp_workspace):
        """Test file operations via bash."""
        tool = BashTool(working_dir=str(temp_workspace))

        # Create a file
        await tool.execute(command="echo 'test content' > bash_test.txt")

        # Read the file
        result = await tool.execute(command="cat bash_test.txt")

        assert "test content" in result

    @pytest.mark.asyncio
    async def test_directory_listing(self, temp_workspace):
        """Test directory listing."""
        tool = BashTool(working_dir=str(temp_workspace))

        result = await tool.execute(command="ls -la")

        assert "test.py" in result
        assert "config.yaml" in result
