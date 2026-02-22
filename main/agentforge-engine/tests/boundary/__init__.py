"""
Boundary Tests for PyAgentForge

This module contains edge case and boundary condition tests to verify
the system handles extreme inputs and edge cases correctly.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.message import (
    TextBlock,
    ToolUseBlock,
    ProviderResponse,
)
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.tools.base import BaseTool
from tests.test_config import generate_large_text, calculate_expected_tokens


# ============================================================================
# Mock Provider for Boundary Testing
# ============================================================================

class BoundaryMockProvider:
    """Mock provider for boundary condition testing."""

    def __init__(self):
        self.model = "boundary-test-model"
        self.max_tokens = 4096
        self.call_count = 0

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Standard response for boundary tests."""
        self.call_count += 1
        return ProviderResponse(
            content=[TextBlock(text="Response")],
            stop_reason="end_turn",
        )

    async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
        """Mock streaming."""
        response = await self.create_message(system, messages, tools, **kwargs)
        yield response


# ============================================================================
# Boundary Tests: Input Validation
# ============================================================================

class TestInputBoundaries:
    """Tests for input boundary conditions."""

    @pytest.fixture
    def boundary_setup(self):
        """Set up boundary test environment."""
        provider = BoundaryMockProvider()
        registry = ToolRegistry()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        return {"provider": provider, "registry": registry, "engine": engine}

    @pytest.mark.asyncio
    async def test_empty_input(self, boundary_setup):
        """
        Boundary Test: Empty input string

        Expected: Should handle gracefully without crash
        """
        engine = boundary_setup["engine"]

        result = await engine.run("")

        # Should return something, not crash
        assert result is not None

    @pytest.mark.asyncio
    async def test_whitespace_only_input(self, boundary_setup):
        """
        Boundary Test: Whitespace-only input

        Expected: Should handle gracefully
        """
        engine = boundary_setup["engine"]

        result = await engine.run("   \n\t   ")

        assert result is not None

    @pytest.mark.asyncio
    async def test_extremely_long_input(self, boundary_setup):
        """
        Boundary Test: Extremely long input (100KB)

        Expected: Should handle without memory issues
        """
        engine = boundary_setup["engine"]

        # Generate 100KB of text
        long_input = generate_large_text(size_kb=100)

        result = await engine.run(long_input)

        assert result is not None

    @pytest.mark.asyncio
    async def test_unicode_input(self, boundary_setup):
        """
        Boundary Test: Unicode characters in input

        Expected: Should handle all Unicode correctly
        """
        engine = boundary_setup["engine"]

        # Various Unicode characters
        unicode_inputs = [
            "Hello 世界",  # Chinese
            "Привет мир",  # Russian
            "مرحبا بالعالم",  # Arabic
            "🎉🎊🎈",  # Emoji
            "日本語テスト",  # Japanese
        ]

        for input_text in unicode_inputs:
            result = await engine.run(input_text)
            assert result is not None

    @pytest.mark.asyncio
    async def test_special_characters_input(self, boundary_setup):
        """
        Boundary Test: Special characters in input

        Expected: Should handle special chars without issues
        """
        engine = boundary_setup["engine"]

        special_inputs = [
            "Test<script>alert('xss')</script>",
            "Test'; DROP TABLE users; --",
            "Test\n\r\n\rLine breaks",
            "Test\x00\x01\x02",  # Control characters
            "Test with <>&\"' special HTML chars",
        ]

        for input_text in special_inputs:
            result = await engine.run(input_text)
            assert result is not None


# ============================================================================
# Boundary Tests: Context Limits
# ============================================================================

class TestContextBoundaries:
    """Tests for context boundary conditions."""

    @pytest.mark.asyncio
    async def test_context_at_max_messages(self):
        """
        Boundary Test: Context at maximum message limit

        Expected: Should truncate properly
        """
        provider = BoundaryMockProvider()
        registry = ToolRegistry()
        context = ContextManager(max_messages=10)

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Add many messages
        for i in range(20):
            await engine.run(f"Message {i}")

        # Context should be truncated
        assert len(context) <= 20  # Some margin for truncation threshold

    @pytest.mark.asyncio
    async def test_context_with_single_message(self):
        """
        Boundary Test: Context with minimal messages

        Expected: Should work with just one message
        """
        provider = BoundaryMockProvider()
        registry = ToolRegistry()
        context = ContextManager()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        result = await engine.run("Single message")

        assert result is not None
        assert len(context) >= 2  # At least user + assistant message

    @pytest.mark.asyncio
    async def test_context_reset_after_large_history(self):
        """
        Boundary Test: Reset after building large history

        Expected: Should clean up properly
        """
        provider = BoundaryMockProvider()
        registry = ToolRegistry()
        context = ContextManager()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Build large history
        for i in range(50):
            await engine.run(f"Message {i}")

        # Reset
        engine.reset()

        # Context should be empty
        assert len(context) == 0


# ============================================================================
# Boundary Tests: Tool Execution
# ============================================================================

class TestToolBoundaries:
    """Tests for tool execution boundary conditions."""

    @pytest.fixture
    def tool_boundary_setup(self):
        """Set up tool boundary test environment."""
        class BoundaryTool(BaseTool):
            name: str = "boundary_tool"
            description: str = "Tool for boundary testing"

            async def execute(self, **kwargs) -> str:
                # Return info about what was received
                return f"Received {len(kwargs)} arguments"

        provider = BoundaryMockProvider()
        registry = ToolRegistry()
        registry.register(BoundaryTool())

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        return {"provider": provider, "registry": registry, "engine": engine}

    @pytest.mark.asyncio
    async def test_tool_with_no_arguments(self, tool_boundary_setup):
        """
        Boundary Test: Tool called with no arguments

        Expected: Should execute without error
        """
        tool = tool_boundary_setup["registry"].get("boundary_tool")

        result = await tool.execute()

        assert result is not None

    @pytest.mark.asyncio
    async def test_tool_with_many_arguments(self, tool_boundary_setup):
        """
        Boundary Test: Tool called with many arguments

        Expected: Should handle gracefully
        """
        tool = tool_boundary_setup["registry"].get("boundary_tool")

        # Create many arguments
        many_args = {f"arg_{i}": f"value_{i}" for i in range(100)}

        result = await tool.execute(**many_args)

        assert "100 arguments" in result

    @pytest.mark.asyncio
    async def test_tool_with_large_argument_value(self, tool_boundary_setup):
        """
        Boundary Test: Tool with large argument value

        Expected: Should handle large data
        """
        tool = tool_boundary_setup["registry"].get("boundary_tool")

        # Create large argument value (1MB)
        large_value = "x" * (1024 * 1024)

        result = await tool.execute(data=large_value)

        assert result is not None

    @pytest.mark.asyncio
    async def test_tool_with_special_argument_names(self, tool_boundary_setup):
        """
        Boundary Test: Tool with special argument names

        Expected: Should handle various argument names
        """
        tool = tool_boundary_setup["registry"].get("boundary_tool")

        special_names = {
            "__init__": "value",
            "class": "value",
            "def": "value",
            "return": "value",
            "with spaces": "value",
        }

        result = await tool.execute(**special_names)

        assert result is not None


# ============================================================================
# Boundary Tests: Provider Responses
# ============================================================================

class TestProviderResponseBoundaries:
    """Tests for provider response boundary conditions."""

    @pytest.fixture
    def provider_boundary_setup(self):
        """Set up provider boundary test environment."""
        class VariableResponseProvider:
            def __init__(self, responses: list[ProviderResponse]):
                self.model = "variable-test-model"
                self.max_tokens = 4096
                self.responses = responses
                self.response_index = 0

            async def create_message(
                self,
                system: str,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]] | None = None,
                **kwargs: Any,
            ) -> ProviderResponse:
                if self.response_index < len(self.responses):
                    response = self.responses[self.response_index]
                    self.response_index += 1
                    return response
                return ProviderResponse(
                    content=[TextBlock(text="Default")],
                    stop_reason="end_turn",
                )

            async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
                response = await self.create_message(system, messages, tools, **kwargs)
                yield response

        return VariableResponseProvider

    @pytest.mark.asyncio
    async def test_empty_content_response(self, provider_boundary_setup):
        """
        Boundary Test: Empty content in response

        Expected: Should handle gracefully
        """
        provider = provider_boundary_setup([
            ProviderResponse(
                content=[],
                stop_reason="end_turn",
            )
        ])

        registry = ToolRegistry()
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Hello")

        # Should handle empty content
        assert result is not None

    @pytest.mark.asyncio
    async def test_many_content_blocks(self, provider_boundary_setup):
        """
        Boundary Test: Response with many content blocks

        Expected: Should handle large number of blocks
        """
        # Create response with 100 content blocks
        many_blocks = [TextBlock(text=f"Block {i}") for i in range(100)]

        provider = provider_boundary_setup([
            ProviderResponse(
                content=many_blocks,
                stop_reason="end_turn",
            )
        ])

        registry = ToolRegistry()
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Hello")

        assert result is not None

    @pytest.mark.asyncio
    async def test_very_long_single_response(self, provider_boundary_setup):
        """
        Boundary Test: Very long single text response

        Expected: Should handle large response
        """
        # Create response with 100KB of text
        long_text = generate_large_text(size_kb=100)

        provider = provider_boundary_setup([
            ProviderResponse(
                content=[TextBlock(text=long_text)],
                stop_reason="end_turn",
            )
        ])

        registry = ToolRegistry()
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Hello")

        assert result is not None
        assert len(result) > 1000


# ============================================================================
# Boundary Tests: Iteration Limits
# ============================================================================

class TestIterationBoundaries:
    """Tests for iteration limit boundary conditions."""

    @pytest.fixture
    def infinite_loop_provider(self):
        """Provider that always returns tool use (potential infinite loop)."""
        class InfiniteToolUseProvider:
            def __init__(self):
                self.model = "infinite-test-model"
                self.max_tokens = 4096
                self.call_count = 0

            async def create_message(
                self,
                system: str,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]] | None = None,
                **kwargs: Any,
            ) -> ProviderResponse:
                self.call_count += 1
                return ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id=f"tool_{self.call_count}",
                            name="nonexistent_tool",
                            input={}
                        )
                    ],
                    stop_reason="tool_use",
                )

            async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
                response = await self.create_message(system, messages, tools, **kwargs)
                yield response

        return InfiniteToolUseProvider()

    @pytest.mark.asyncio
    async def test_max_iterations_one(self, infinite_loop_provider):
        """
        Boundary Test: Max iterations set to 1

        Expected: Should stop after exactly 1 iteration
        """
        registry = ToolRegistry()

        engine = AgentEngine(
            provider=infinite_loop_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=1),
        )

        result = await engine.run("Test")

        assert infinite_loop_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_max_iterations_boundary(self, infinite_loop_provider):
        """
        Boundary Test: Max iterations at boundary values

        Expected: Should respect exact iteration limits
        """
        registry = ToolRegistry()

        for max_iter in [1, 5, 10, 50]:
            provider = infinite_loop_provider.__class__()
            engine = AgentEngine(
                provider=provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=max_iter),
            )

            await engine.run("Test")

            assert provider.call_count == max_iter, \
                f"Expected {max_iter} iterations, got {provider.call_count}"


# ============================================================================
# Boundary Tests: Concurrency Limits
# ============================================================================

class TestConcurrencyBoundaries:
    """Tests for concurrency boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_concurrent_operations(self):
        """
        Boundary Test: Zero concurrent operations

        Expected: Should handle gracefully (no deadlock)
        """
        # Just verify no crash with zero operations
        results = await asyncio.gather()
        assert results == []

    @pytest.mark.asyncio
    async def test_single_concurrent_operation(self):
        """
        Boundary Test: Single concurrent operation

        Expected: Should work normally
        """
        provider = BoundaryMockProvider()
        registry = ToolRegistry()

        async def run_one():
            engine = AgentEngine(
                provider=provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=5),
            )
            return await engine.run("Hello")

        results = await asyncio.gather(run_one())
        assert len(results) == 1
        assert results[0] is not None

    @pytest.mark.asyncio
    async def test_many_concurrent_operations(self):
        """
        Boundary Test: Many concurrent operations

        Expected: Should handle without resource exhaustion
        """
        provider = BoundaryMockProvider()
        registry = ToolRegistry()

        async def run_one(idx: int):
            engine = AgentEngine(
                provider=provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=5),
            )
            return await engine.run(f"Hello {idx}")

        # Run 100 concurrent operations
        results = await asyncio.gather(*[run_one(i) for i in range(100)])

        assert len(results) == 100
        assert all(r is not None for r in results)


# ============================================================================
# Boundary Tests: Error Conditions
# ============================================================================

class TestErrorBoundaries:
    """Tests for error condition boundaries."""

    @pytest.fixture
    def error_setup(self):
        """Set up error boundary test environment."""
        class ErrorProvider:
            def __init__(self, raise_error: bool = False):
                self.model = "error-test-model"
                self.max_tokens = 4096
                self.raise_error = raise_error

            async def create_message(
                self,
                system: str,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]] | None = None,
                **kwargs: Any,
            ) -> ProviderResponse:
                if self.raise_error:
                    raise RuntimeError("Provider error")
                return ProviderResponse(
                    content=[TextBlock(text="Response")],
                    stop_reason="end_turn",
                )

            async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
                response = await self.create_message(system, messages, tools, **kwargs)
                yield response

        return ErrorProvider

    @pytest.mark.asyncio
    async def test_provider_error_handling(self, error_setup):
        """
        Boundary Test: Provider raises error

        Expected: Should handle provider errors gracefully
        """
        provider = error_setup(raise_error=True)
        registry = ToolRegistry()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=5),
        )

        # Should not crash, but may raise or return error message
        try:
            result = await engine.run("Hello")
            # If it doesn't raise, result should indicate error
            assert result is not None
        except RuntimeError as e:
            # If it raises, should be the provider error
            assert "Provider error" in str(e)

    @pytest.mark.asyncio
    async def test_tool_error_recovery(self):
        """
        Boundary Test: Tool execution error

        Expected: Should handle tool errors and continue
        """
        class ErrorTool(BaseTool):
            name: str = "error_tool"
            description: str = "Tool that errors"

            async def execute(self, **kwargs) -> str:
                raise ValueError("Tool execution failed")

        class ToolUseProvider:
            def __init__(self):
                self.model = "tool-use-test-model"
                self.max_tokens = 4096
                self.call_count = 0

            async def create_message(
                self,
                system: str,
                messages: list[dict[str, Any]],
                tools: list[dict[str, Any]] | None = None,
                **kwargs: Any,
            ) -> ProviderResponse:
                self.call_count += 1
                if self.call_count == 1:
                    return ProviderResponse(
                        content=[
                            ToolUseBlock(
                                id="tool_1",
                                name="error_tool",
                                input={}
                            )
                        ],
                        stop_reason="tool_use",
                    )
                return ProviderResponse(
                    content=[TextBlock(text="Recovered from error")],
                    stop_reason="end_turn",
                )

            async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
                response = await self.create_message(system, messages, tools, **kwargs)
                yield response

        provider = ToolUseProvider()
        registry = ToolRegistry()
        registry.register(ErrorTool())

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Use the error tool")

        # Should have recovered and returned a result
        assert result is not None
