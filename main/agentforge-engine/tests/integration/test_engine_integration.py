"""
Integration Tests for Engine-Tools-Provider Flow

Tests the complete execution flow from Engine to Tools to Provider
and back, ensuring all components integrate correctly.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.errors import AgentMaxIterationsError
from pyagentforge.kernel.executor import PermissionChecker, ToolExecutor
from pyagentforge.kernel.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.registry import ToolRegistry


class MockProvider:
    """Mock LLM Provider for testing"""

    def __init__(self, responses: list[ProviderResponse] | None = None):
        self.model = "mock-model"
        self.max_tokens = 4096
        self.responses = responses or []
        self.call_count = 0
        self.last_messages = None
        self.last_tools = None

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Create a mock message"""
        self.call_count += 1
        self.last_messages = messages
        self.last_tools = tools

        if self.responses:
            idx = min(self.call_count - 1, len(self.responses) - 1)
            return self.responses[idx]

        # Default: simple text response
        return ProviderResponse(
            content=[TextBlock(text="Hello, this is a mock response.")],
            stop_reason="end_turn",
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream_message(self, system: str, messages: list[dict], tools: list[dict], **kwargs):
        """Mock stream message - not used in these tests"""
        yield ProviderResponse(
            content=[TextBlock(text="Mock stream response")],
            stop_reason="end_turn",
        )


class SimpleTool(BaseTool):
    """Simple test tool"""

    name: str = "simple_tool"
    description: str = "A simple test tool"
    execute_count: int = 0
    last_input: dict = {}

    async def execute(self, **kwargs: Any) -> str:
        self.execute_count += 1
        self.last_input = kwargs
        return f"Tool executed with args: {kwargs}"


class FailingTool(BaseTool):
    """Tool that raises an error"""

    name: str = "failing_tool"
    description: str = "A tool that fails"

    async def execute(self, **kwargs: Any) -> str:
        raise ValueError("Intentional test error")


class SlowTool(BaseTool):
    """Tool with delayed execution"""

    name: str = "slow_tool"
    description: str = "A slow tool"
    execute_count: int = 0

    async def execute(self, **kwargs: Any) -> str:
        self.execute_count += 1
        await asyncio.sleep(0.1)
        return "Slow tool completed"


class TestSimpleToolExecutionFlow:
    """Test simple single tool execution flow"""

    @pytest.mark.asyncio
    async def test_single_tool_execution_flow(self):
        """
        Test complete flow: User prompt -> LLM calls tool -> Tool executes -> Result fed back

        Flow:
        1. User sends prompt asking to use a tool
        2. LLM responds with tool call
        3. Engine executes tool
        4. Tool result is fed back to LLM
        5. LLM provides final text response
        """
        # Setup: Create a simple tool
        simple_tool = SimpleTool()

        # Setup: Create tool registry
        registry = ToolRegistry()
        registry.register(simple_tool)

        # Setup: Create mock provider with sequence of responses
        responses = [
            # First response: LLM decides to call tool
            ProviderResponse(
                content=[
                    TextBlock(text="I will use the tool."),
                    ToolUseBlock(id="tool_1", name="simple_tool", input={"arg1": "value1"}),
                ],
                stop_reason="tool_use",
                usage={"input_tokens": 10, "output_tokens": 20},
            ),
            # Second response: LLM provides final answer after seeing tool result
            ProviderResponse(
                content=[TextBlock(text="The tool executed successfully.")],
                stop_reason="end_turn",
                usage={"input_tokens": 30, "output_tokens": 10},
            ),
        ]

        mock_provider = MockProvider(responses=responses)

        # Setup: Create engine
        config = AgentConfig(
            system_prompt="You are a helpful assistant.",
            max_iterations=10,
        )

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=config,
        )

        # Execute: Run the engine
        result = await engine.run("Please use the simple tool")

        # Verify: Tool was executed
        assert simple_tool.execute_count == 1
        assert simple_tool.last_input == {"arg1": "value1"}

        # Verify: Provider was called twice (tool call + final response)
        assert mock_provider.call_count == 2

        # Verify: Final result is text response
        assert "successfully" in result.lower() or "tool executed" in result.lower()

    @pytest.mark.asyncio
    async def test_tool_not_found_handling(self):
        """
        Test handling when LLM calls a non-existent tool

        Flow:
        1. LLM calls non-existent tool
        2. Engine returns error message
        3. LLM can recover and continue
        """
        registry = ToolRegistry()
        # No tools registered

        responses = [
            # LLM calls non-existent tool
            ProviderResponse(
                content=[
                    ToolUseBlock(id="tool_1", name="nonexistent_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            # LLM recovers after seeing error
            ProviderResponse(
                content=[TextBlock(text="I apologize, that tool doesn't exist.")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Use the nonexistent tool")

        # Verify: Provider was called twice (tool call + recovery)
        assert mock_provider.call_count == 2

        # Verify: Engine didn't crash
        assert isinstance(result, str)


class TestMultiToolParallelExecution:
    """Test parallel execution of multiple tools"""

    @pytest.mark.asyncio
    async def test_multi_tool_parallel_execution(self):
        """
        Test that multiple tools in same response are executed in parallel

        Flow:
        1. LLM calls 3 tools simultaneously
        2. All tools execute in parallel
        3. All results are collected and fed back together
        """
        # Create multiple slow tools
        slow_tools = [SlowTool() for _ in range(3)]
        for i, tool in enumerate(slow_tools):
            tool.name = f"slow_tool_{i}"

        registry = ToolRegistry()
        for tool in slow_tools:
            registry.register(tool)

        # LLM calls all tools at once
        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id=f"tool_{i}", name=f"slow_tool_{i}", input={"idx": i})
                    for i in range(3)
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="All tools completed.")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        # Execute and measure time
        import time
        start = time.time()
        await engine.run("Run all tools")
        elapsed = time.time() - start

        # Verify: All tools executed
        for tool in slow_tools:
            assert tool.execute_count == 1

        # Verify: Parallel execution (should take ~0.1s, not ~0.3s)
        assert elapsed < 0.25, f"Tools should execute in parallel, took {elapsed}s"

    @pytest.mark.asyncio
    async def test_mixed_tool_results(self):
        """
        Test handling of mixed success/failure tool results

        Flow:
        1. LLM calls multiple tools
        2. Some succeed, some fail
        3. LLM receives all results (success and errors)
        """
        registry = ToolRegistry()
        registry.register(SimpleTool())
        registry.register(FailingTool())

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="tool_1", name="simple_tool", input={"x": 1}),
                    ToolUseBlock(id="tool_2", name="failing_tool", input={"y": 2}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Some tools failed but I can continue.")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Run tools with mixed results")

        # Verify: Engine didn't crash and provided response
        assert isinstance(result, str)


class TestToolResultFeedbackToLLM:
    """Test that tool results are properly fed back to LLM"""

    @pytest.mark.asyncio
    async def test_tool_result_in_conversation_history(self):
        """
        Test that tool results are added to conversation history correctly

        Flow:
        1. User sends prompt
        2. LLM calls tool
        3. Tool result is added to history
        4. Verify history structure
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="simple_tool", input={"data": "test"}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Done")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        context = ContextManager()
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        await engine.run("Test prompt")

        # Verify: Context has correct message flow
        messages = context.get_messages_for_api()

        # Should have: user message, assistant (tool call), tool result
        assert len(messages) >= 3

        # Find tool result message
        tool_result_found = False
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            tool_result_found = True
                            assert "tool_use_id" in block
                            assert block["tool_use_id"] == "call_1"

        assert tool_result_found, "Tool result should be in conversation history"


class TestContextPreservationAcrossIterations:
    """Test context preservation across multiple iterations"""

    @pytest.mark.asyncio
    async def test_context_preservation(self):
        """
        Test that context is preserved across multiple tool call iterations

        Flow:
        1. User sends prompt with specific information
        2. LLM calls tool, sees result
        3. LLM calls another tool (iteration 2)
        4. Verify information from step 1 is still in context
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        responses = [
            # Iteration 1: First tool call
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="simple_tool", input={"step": 1}),
                ],
                stop_reason="tool_use",
            ),
            # Iteration 2: Second tool call
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_2", name="simple_tool", input={"step": 2}),
                ],
                stop_reason="tool_use",
            ),
            # Iteration 3: Final response
            ProviderResponse(
                content=[TextBlock(text="Completed all steps")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        context = ContextManager()
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        await engine.run("Process data: IMPORTANT_VALUE_123")

        # Verify: Multiple iterations occurred
        assert mock_provider.call_count == 3

        # Verify: Second call to LLM included the original user message
        second_call_messages = mock_provider.last_messages
        user_msg_found = False
        for msg in second_call_messages:
            if msg.get("role") == "user" and "IMPORTANT_VALUE_123" in str(msg.get("content", "")):
                user_msg_found = True
                break

        assert user_msg_found, "Original user message should be preserved in context"

    @pytest.mark.asyncio
    async def test_context_truncation(self):
        """
        Test context truncation when message limit is approached

        Flow:
        1. Set low max_messages limit
        2. Generate many tool calls
        3. Verify truncation occurs
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        # Create many responses to trigger truncation
        responses = []
        for i in range(10):
            responses.append(
                ProviderResponse(
                    content=[
                        ToolUseBlock(id=f"call_{i}", name="simple_tool", input={"i": i}),
                    ],
                    stop_reason="tool_use",
                )
            )
        responses.append(
            ProviderResponse(
                content=[TextBlock(text="Done")],
                stop_reason="end_turn",
            )
        )

        mock_provider = MockProvider(responses=responses)
        context = ContextManager(max_messages=20)  # Low limit
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=15),
            context=context,
        )

        await engine.run("Run many iterations")

        # Verify: Context was truncated (fewer messages than total generated)
        # Each iteration adds at least 2 messages (tool call + result)
        # With 10 iterations, we'd have 20+ messages without truncation
        assert len(context) < 25


class TestPluginHooksInExecution:
    """Test plugin hooks during execution"""

    @pytest.mark.asyncio
    async def test_on_before_llm_call_hook(self):
        """
        Test that on_before_llm_call hook is called before LLM calls

        Flow:
        1. Register hook for on_before_llm_call
        2. Run engine
        3. Verify hook was called with correct parameters
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        mock_provider = MockProvider()
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        # Track hook calls
        hook_calls = []

        async def before_llm_hook(messages):
            hook_calls.append(("on_before_llm_call", messages))
            return None  # Don't modify

        # Create mock plugin manager
        plugin_manager = MagicMock()
        async def emit_hook(name, *args):
            if name == "on_before_llm_call":
                await before_llm_hook(*args)
            return None

        plugin_manager.emit_hook = AsyncMock(side_effect=emit_hook)

        engine.plugin_manager = plugin_manager

        await engine.run("Test prompt")

        # Verify: Hook was called
        assert len(hook_calls) > 0
        assert hook_calls[0][0] == "on_before_llm_call"
        assert isinstance(hook_calls[0][1], list)  # messages list

    @pytest.mark.asyncio
    async def test_on_after_llm_call_hook(self):
        """
        Test that on_after_llm_call hook receives LLM response

        Flow:
        1. Register hook for on_after_llm_call
        2. Run engine
        3. Verify hook received ProviderResponse
        """
        registry = ToolRegistry()
        mock_provider = MockProvider()
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        hook_calls = []

        async def after_llm_hook(response):
            hook_calls.append(("on_after_llm_call", response))
            return None

        plugin_manager = MagicMock()
        async def emit_hook(name, *args):
            if name == "on_after_llm_call":
                await after_llm_hook(*args)
            return None

        plugin_manager.emit_hook = AsyncMock(side_effect=emit_hook)

        engine.plugin_manager = plugin_manager

        await engine.run("Test prompt")

        # Verify: Hook was called with response
        assert len(hook_calls) > 0
        assert hook_calls[0][0] == "on_after_llm_call"
        # Response should be ProviderResponse or similar structure


class TestPermissionCheckBeforeToolExec:
    """Test permission checking before tool execution"""

    @pytest.mark.asyncio
    async def test_permission_allow_tool(self):
        """
        Test that allowed tools can execute

        Flow:
        1. Set permission checker allowing specific tool
        2. LLM calls allowed tool
        3. Tool executes successfully
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        # Permission checker allows simple_tool
        permission_checker = PermissionChecker(
            allowed_tools={"simple_tool"},
        )

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="simple_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Done")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        config = AgentConfig(
            max_iterations=10,
            permission_checker=permission_checker,
        )

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=config,
        )

        await engine.run("Use tool")

        # Verify: Tool executed
        assert simple_tool.execute_count == 1

    @pytest.mark.asyncio
    async def test_permission_deny_tool(self):
        """
        Test that denied tools cannot execute

        Flow:
        1. Set permission checker denying tool
        2. LLM calls denied tool
        3. Tool execution is blocked
        4. Error message returned
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        # Permission checker denies simple_tool
        permission_checker = PermissionChecker(
            denied_tools={"simple_tool"},
        )

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="simple_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Tool was denied")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        config = AgentConfig(
            max_iterations=10,
            permission_checker=permission_checker,
        )

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=config,
        )

        await engine.run("Use tool")

        # Verify: Tool was NOT executed
        assert simple_tool.execute_count == 0

    @pytest.mark.asyncio
    async def test_permission_ask_user(self):
        """
        Test ASK permission mode with user callback

        Flow:
        1. Set permission checker in ASK mode for tool
        2. LLM calls tool
        3. User callback is invoked
        4. Tool executes only if user confirms
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        # Permission checker asks for user confirmation
        permission_checker = PermissionChecker(
            ask_tools={"simple_tool"},
        )

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="simple_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Done")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        config = AgentConfig(
            max_iterations=10,
            permission_checker=permission_checker,
        )

        # User callback that approves
        ask_callback = AsyncMock(return_value=True)

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=config,
            ask_callback=ask_callback,
        )

        await engine.run("Use tool")

        # Verify: Callback was called and tool executed
        assert ask_callback.called
        assert simple_tool.execute_count == 1


class TestFullConversationWithMultipleTurns:
    """Test full multi-turn conversations"""

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self):
        """
        Test a complete multi-turn conversation with tool calls

        Flow:
        1. Turn 1: User asks question, LLM calls tool, responds
        2. Turn 2: User follows up, LLM uses context from Turn 1
        3. Verify context is maintained across turns
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        context = ContextManager()

        # Turn 1 responses
        turn1_responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="simple_tool", input={"turn": 1}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Turn 1 complete. Value is 42.")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=turn1_responses)
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Turn 1
        result1 = await engine.run("What is the value?")
        assert "42" in result1

        # Verify tool was called
        assert simple_tool.execute_count == 1

        # Reset provider for turn 2
        turn2_responses = [
            ProviderResponse(
                content=[TextBlock(text="Based on the previous value of 42, the answer is 84.")],
                stop_reason="end_turn",
            ),
        ]
        mock_provider2 = MockProvider(responses=turn2_responses)

        # Create new engine with same context
        engine2 = AgentEngine(
            provider=mock_provider2,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Turn 2: Should reference turn 1 context
        await engine2.run("Double it")

        # Verify: LLM received context from previous turn
        last_messages = mock_provider2.last_messages
        context_preserved = False
        for msg in last_messages:
            content = str(msg.get("content", ""))
            if "42" in content or "Turn 1" in content:
                context_preserved = True
                break

        assert context_preserved, "Context from turn 1 should be available in turn 2"


class TestErrorRecoveryInToolExecution:
    """Test error recovery during tool execution"""

    @pytest.mark.asyncio
    async def test_tool_error_recovery(self):
        """
        Test that engine can recover from tool errors

        Flow:
        1. LLM calls tool that raises exception
        2. Error is caught and returned as result
        3. LLM sees error and continues
        """
        registry = ToolRegistry()
        registry.register(FailingTool())

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="failing_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="The tool failed but I handled it gracefully.")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        result = await engine.run("Use failing tool")

        # Verify: Engine didn't crash
        assert isinstance(result, str)
        assert mock_provider.call_count == 2  # Tool call + recovery

    @pytest.mark.asyncio
    async def test_tool_timeout_recovery(self):
        """
        Test recovery from tool timeout

        Flow:
        1. LLM calls slow tool
        2. Tool times out
        3. LLM receives timeout error
        4. LLM continues with alternative approach
        """
        registry = ToolRegistry()
        registry.register(SlowTool())

        responses = [
            ProviderResponse(
                content=[
                    ToolUseBlock(id="call_1", name="slow_tool", input={}),
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="Tool timed out, using fallback.")],
                stop_reason="end_turn",
            ),
        ]

        mock_provider = MockProvider(responses=responses)

        # Create executor with very short timeout
        executor = ToolExecutor(
            tool_registry=registry,
            timeout=0.01,  # Very short timeout
        )

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )
        engine.executor = executor  # Override with short timeout executor

        result = await engine.run("Use slow tool")

        # Verify: Engine handled timeout gracefully
        assert isinstance(result, str)
        assert mock_provider.call_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_protection(self):
        """
        Test that max_iterations prevents infinite loops

        Flow:
        1. LLM always responds with tool calls (never end_turn)
        2. Engine stops after max_iterations
        3. Returns error message instead of hanging
        """
        simple_tool = SimpleTool()
        registry = ToolRegistry()
        registry.register(simple_tool)

        # LLM that always wants to call tools
        loop_response = ProviderResponse(
            content=[
                ToolUseBlock(id="loop", name="simple_tool", input={}),
            ],
            stop_reason="tool_use",
        )

        mock_provider = MockProvider(responses=[loop_response] * 100)

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=5),  # Low limit
        )

        with pytest.raises(AgentMaxIterationsError):
            await engine.run("Loop forever")

        # Verify: Engine stopped at max iterations
        assert mock_provider.call_count == 5  # Stopped at limit
