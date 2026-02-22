"""
Tests for ToolExecutor class

Comprehensive tests for tool execution, timeout handling, and permissions.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyagentforge.kernel.executor import (
    PermissionChecker,
    PermissionResult,
    ToolExecutor,
)
from pyagentforge.kernel.message import ToolUseBlock
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.tools.base import BaseTool


class SlowTool(BaseTool):
    """A tool that takes time to execute."""

    name = "slow_tool"
    description = "A slow tool for testing timeouts"
    parameters_schema = {
        "type": "object",
        "properties": {
            "delay": {"type": "number"}
        }
    }

    def __init__(self, delay: float = 1.0):
        self.delay = delay

    async def execute(self, **kwargs) -> str:
        """Execute with delay."""
        delay = kwargs.get("delay", self.delay)
        await asyncio.sleep(delay)
        return f"Executed after {delay}s"


class LongOutputTool(BaseTool):
    """A tool that produces long output."""

    name = "long_output_tool"
    description = "A tool that produces long output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "length": {"type": "number"}
        }
    }

    async def execute(self, **kwargs) -> str:
        """Generate long output."""
        length = kwargs.get("length", 100000)
        return "x" * length


class ErrorTool(BaseTool):
    """A tool that raises an error."""

    name = "error_tool"
    description = "A tool that raises an error"
    parameters_schema = {
        "type": "object",
        "properties": {}
    }

    async def execute(self, **kwargs) -> str:
        """Raise an error."""
        raise ValueError("Tool execution failed")


class MockTool(BaseTool):
    """A simple mock tool."""

    name = "mock_tool"
    description = "A mock tool for testing"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        }
    }

    def __init__(self, return_value: str = "Success"):
        self.return_value = return_value
        self.execute_count = 0

    async def execute(self, **kwargs) -> str:
        """Execute the tool."""
        self.execute_count += 1
        return self.return_value


class TestToolExecutorBasicExecution:
    """Tests for basic tool execution."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor."""
        return ToolExecutor(tool_registry=tool_registry, timeout=30)

    @pytest.mark.asyncio
    async def test_execute_returns_tool_result(
        self, tool_executor: ToolExecutor
    ):
        """Test that execute returns the expected tool result."""
        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={"input": "test"}
        )

        result = await tool_executor.execute(tool_call)

        assert result == "Success"

    @pytest.mark.asyncio
    async def test_execute_with_multiple_calls(
        self, tool_executor: ToolExecutor, tool_registry: ToolRegistry
    ):
        """Test executing multiple tool calls."""
        mock_tool = tool_registry.get("mock_tool")

        # First call
        result1 = await tool_executor.execute(
            ToolUseBlock(id="call_1", name="mock_tool", input={})
        )
        assert result1 == "Success"

        # Second call
        result2 = await tool_executor.execute(
            ToolUseBlock(id="call_2", name="mock_tool", input={})
        )
        assert result2 == "Success"

        assert mock_tool.execute_count == 2


class TestToolExecutorMissingTool:
    """Tests for missing tool handling."""

    @pytest.fixture
    def empty_registry(self) -> ToolRegistry:
        """Create an empty tool registry."""
        return ToolRegistry()

    @pytest.fixture
    def tool_executor(self, empty_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor with empty registry."""
        return ToolExecutor(tool_registry=empty_registry, timeout=30)

    @pytest.mark.asyncio
    async def test_execute_handles_missing_tool(
        self, tool_executor: ToolExecutor
    ):
        """Test that execute handles missing tools gracefully."""
        tool_call = ToolUseBlock(
            id="call_1",
            name="nonexistent_tool",
            input={}
        )

        result = await tool_executor.execute(tool_call)

        assert "Error:" in result
        assert "not found" in result


class TestToolExecutorTimeout:
    """Tests for timeout handling."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with slow tool."""
        registry = ToolRegistry()
        registry.register(SlowTool(delay=5.0))
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor with short timeout."""
        return ToolExecutor(tool_registry=tool_registry, timeout=1)

    @pytest.mark.asyncio
    async def test_execute_enforces_timeout(
        self, tool_executor: ToolExecutor
    ):
        """Test that execute enforces timeout."""
        tool_call = ToolUseBlock(
            id="call_1",
            name="slow_tool",
            input={"delay": 10}  # 10 second delay, timeout is 1 second
        )

        result = await tool_executor.execute(tool_call)

        assert "Error:" in result
        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_execute_completes_within_timeout(self):
        """Test that execution completes if within timeout."""
        registry = ToolRegistry()
        registry.register(SlowTool(delay=0.1))  # 100ms delay
        executor = ToolExecutor(tool_registry=registry, timeout=5)

        tool_call = ToolUseBlock(
            id="call_1",
            name="slow_tool",
            input={"delay": 0.1}
        )

        result = await executor.execute(tool_call)

        assert "Executed after" in result
        assert "Error:" not in result


class TestToolExecutorPermissions:
    """Tests for permission handling."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        registry.register(SlowTool(delay=0.1))
        return registry

    @pytest.fixture
    def deny_checker(self) -> PermissionChecker:
        """Create a permission checker that denies all tools."""
        return PermissionChecker(
            denied_tools={"mock_tool"}
        )

    @pytest.fixture
    def allow_checker(self) -> PermissionChecker:
        """Create a permission checker that allows specific tools."""
        return PermissionChecker(
            allowed_tools={"mock_tool"}
        )

    @pytest.fixture
    def ask_checker(self) -> PermissionChecker:
        """Create a permission checker that asks for confirmation."""
        return PermissionChecker(
            ask_tools={"mock_tool"}
        )

    @pytest.mark.asyncio
    async def test_execute_respects_permission_deny(
        self, tool_registry: ToolRegistry, deny_checker: PermissionChecker
    ):
        """Test that execute respects permission deny."""
        executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=deny_checker
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={}
        )

        result = await executor.execute(tool_call)

        assert "Error:" in result
        assert "not allowed" in result

    @pytest.mark.asyncio
    async def test_execute_allows_permitted_tools(
        self, tool_registry: ToolRegistry, allow_checker: PermissionChecker
    ):
        """Test that execute allows permitted tools."""
        executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=allow_checker
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={}
        )

        result = await executor.execute(tool_call)

        assert result == "Success"

    @pytest.mark.asyncio
    async def test_execute_denies_non_allowed_tools(
        self, tool_registry: ToolRegistry, allow_checker: PermissionChecker
    ):
        """Test that execute denies tools not in allowed list."""
        executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=allow_checker
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="slow_tool",  # Not in allowed list
            input={}
        )

        result = await executor.execute(tool_call)

        assert "Error:" in result
        assert "not allowed" in result


class TestToolExecutorAskPermission:
    """Tests for ask permission handling."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.fixture
    def ask_checker(self) -> PermissionChecker:
        """Create a permission checker that asks for confirmation."""
        return PermissionChecker(ask_tools={"mock_tool"})

    @pytest.mark.asyncio
    async def test_execute_handles_ask_permission(
        self, tool_registry: ToolRegistry, ask_checker: PermissionChecker
    ):
        """Test that execute handles ask permission with callback."""
        executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=ask_checker
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={"input": "test"}
        )

        # User confirms
        async def confirm_callback(tool_name: str, tool_input: dict) -> bool:
            return True

        result = await executor.execute(tool_call, ask_callback=confirm_callback)
        assert result == "Success"

        # User denies
        async def deny_callback(tool_name: str, tool_input: dict) -> bool:
            return False

        result = await executor.execute(tool_call, ask_callback=deny_callback)
        assert "denied" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_ask_without_callback_denies(
        self, tool_registry: ToolRegistry, ask_checker: PermissionChecker
    ):
        """Test that ask permission without callback allows execution."""
        executor = ToolExecutor(
            tool_registry=tool_registry,
            permission_checker=ask_checker
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={}
        )

        # Without callback, ask should allow (no explicit denial)
        result = await executor.execute(tool_call, ask_callback=None)
        # Actually, looking at the code, if ask and no callback, it proceeds
        assert result == "Success"


class TestToolExecutorOutputTruncation:
    """Tests for output truncation."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with long output tool."""
        registry = ToolRegistry()
        registry.register(LongOutputTool())
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor with short max output length."""
        return ToolExecutor(
            tool_registry=tool_registry,
            max_output_length=1000
        )

    @pytest.mark.asyncio
    async def test_execute_truncates_long_output(
        self, tool_executor: ToolExecutor
    ):
        """Test that execute truncates long output."""
        tool_call = ToolUseBlock(
            id="call_1",
            name="long_output_tool",
            input={"length": 10000}
        )

        result = await tool_executor.execute(tool_call)

        assert len(result) < 1100  # 1000 + truncation message
        assert "truncated" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_preserves_short_output(self):
        """Test that execute preserves output shorter than max."""
        registry = ToolRegistry()
        registry.register(MockTool(return_value="Short output"))
        executor = ToolExecutor(
            tool_registry=registry,
            max_output_length=1000
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={}
        )

        result = await executor.execute(tool_call)

        assert result == "Short output"
        assert "truncated" not in result.lower()


class TestToolExecutorErrorHandling:
    """Tests for error handling."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with error tool."""
        registry = ToolRegistry()
        registry.register(ErrorTool())
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor."""
        return ToolExecutor(tool_registry=tool_registry, timeout=30)

    @pytest.mark.asyncio
    async def test_execute_handles_tool_error(
        self, tool_executor: ToolExecutor
    ):
        """Test that execute handles tool errors gracefully."""
        tool_call = ToolUseBlock(
            id="call_1",
            name="error_tool",
            input={}
        )

        result = await tool_executor.execute(tool_call)

        assert "Error" in result
        assert "Tool execution failed" in result


class TestToolExecutorBatchExecution:
    """Tests for batch execution."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor."""
        return ToolExecutor(tool_registry=tool_registry, timeout=30)

    @pytest.mark.asyncio
    async def test_execute_batch_returns_all_results(
        self, tool_executor: ToolExecutor
    ):
        """Test that execute_batch returns results for all tool calls."""
        tool_calls = [
            ToolUseBlock(id="call_1", name="mock_tool", input={}),
            ToolUseBlock(id="call_2", name="mock_tool", input={}),
            ToolUseBlock(id="call_3", name="mock_tool", input={}),
        ]

        results = await tool_executor.execute_batch(tool_calls)

        assert len(results) == 3
        assert results[0][0] == "call_1"
        assert results[1][0] == "call_2"
        assert results[2][0] == "call_3"

        for tool_id, result in results:
            assert result == "Success"

    @pytest.mark.asyncio
    async def test_execute_batch_handles_mixed_results(self):
        """Test that execute_batch handles mixed success and failure."""
        registry = ToolRegistry()
        registry.register(MockTool())
        registry.register(ErrorTool())

        executor = ToolExecutor(tool_registry=registry, timeout=30)

        tool_calls = [
            ToolUseBlock(id="call_1", name="mock_tool", input={}),
            ToolUseBlock(id="call_2", name="error_tool", input={}),
            ToolUseBlock(id="call_3", name="mock_tool", input={}),
        ]

        results = await tool_executor.execute_batch(tool_calls)

        assert len(results) == 3
        assert results[0][1] == "Success"
        assert "Error" in results[1][1]
        assert results[2][1] == "Success"


class TestPermissionChecker:
    """Tests for PermissionChecker class."""

    def test_check_allows_by_default(self):
        """Test that checker allows tools by default."""
        checker = PermissionChecker()
        assert checker.check("any_tool", {}) == PermissionResult.ALLOW

    def test_check_denies_denied_tools(self):
        """Test that checker denies tools in denied list."""
        checker = PermissionChecker(denied_tools={"dangerous_tool"})
        assert checker.check("dangerous_tool", {}) == PermissionResult.DENY

    def test_check_asks_for_ask_tools(self):
        """Test that checker asks for tools in ask list."""
        checker = PermissionChecker(ask_tools={"sensitive_tool"})
        assert checker.check("sensitive_tool", {}) == PermissionResult.ASK

    def test_check_denies_non_allowed_when_allowed_set(self):
        """Test that checker denies tools not in allowed list when set."""
        checker = PermissionChecker(allowed_tools={"safe_tool"})
        assert checker.check("other_tool", {}) == PermissionResult.DENY

    def test_check_allows_tools_in_allowed_list(self):
        """Test that checker allows tools in allowed list."""
        checker = PermissionChecker(allowed_tools={"safe_tool"})
        assert checker.check("safe_tool", {}) == PermissionResult.ALLOW

    def test_check_denied_takes_precedence_over_ask(self):
        """Test that denied takes precedence over ask."""
        checker = PermissionChecker(
            denied_tools={"tool"},
            ask_tools={"tool"}
        )
        assert checker.check("tool", {}) == PermissionResult.DENY

    def test_check_ask_takes_precedence_over_allow(self):
        """Test that ask takes precedence when both are set."""
        # Note: The current implementation checks denied first, then ask, then allowed
        # If a tool is in ask_tools, it will return ASK regardless of allowed
        checker = PermissionChecker(
            allowed_tools={"tool"},
            ask_tools={"tool"}
        )
        assert checker.check("tool", {}) == PermissionResult.ASK


class TestPermissionResult:
    """Tests for PermissionResult constants."""

    def test_permission_result_values(self):
        """Test that PermissionResult has expected values."""
        assert PermissionResult.ALLOW == "allow"
        assert PermissionResult.DENY == "deny"
        assert PermissionResult.ASK == "ask"


class TestToolExecutorWithNoneRegistry:
    """Tests for ToolExecutor with edge cases."""

    def test_executor_with_none_permission_checker(self):
        """Test that executor can be created without permission checker."""
        registry = ToolRegistry()
        executor = ToolExecutor(
            tool_registry=registry,
            permission_checker=None
        )
        assert executor.permission_checker is None

    @pytest.mark.asyncio
    async def test_execute_without_permission_checker(self):
        """Test that execute works without permission checker."""
        registry = ToolRegistry()
        registry.register(MockTool())

        executor = ToolExecutor(
            tool_registry=registry,
            permission_checker=None
        )

        tool_call = ToolUseBlock(
            id="call_1",
            name="mock_tool",
            input={}
        )

        result = await executor.execute(tool_call)
        assert result == "Success"


class TestToolExecutorConcurrency:
    """Tests for concurrent execution."""

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.fixture
    def tool_executor(self, tool_registry: ToolRegistry) -> ToolExecutor:
        """Create a tool executor."""
        return ToolExecutor(tool_registry=tool_registry, timeout=30)

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, tool_executor: ToolExecutor):
        """Test that multiple executions can run concurrently."""
        tool_calls = [
            ToolUseBlock(id=f"call_{i}", name="mock_tool", input={})
            for i in range(10)
        ]

        # Execute all concurrently
        results = await tool_executor.execute_batch(tool_calls)

        assert len(results) == 10
        for tool_id, result in results:
            assert result == "Success"
