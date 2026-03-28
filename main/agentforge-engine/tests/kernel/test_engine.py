"""
Tests for AgentEngine class

Comprehensive tests for the core Agent execution engine.
"""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.executor import ToolExecutor, PermissionChecker, PermissionResult
from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.tools.registry import ToolRegistry
from pyagentforge.tools.base import BaseTool


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    def __init__(self, responses: list[ProviderResponse] | None = None, model: str = "test-model"):
        super().__init__(model=model)
        self.responses = responses or []
        self.call_count = 0
        self.call_history: list[dict[str, Any]] = []

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> ProviderResponse:
        """Return pre-configured responses."""
        self.call_history.append({
            "system": system,
            "messages": messages,
            "tools": tools,
            "kwargs": kwargs
        })

        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
        else:
            # Default response
            response = ProviderResponse(
                content=[TextBlock(text="Default mock response")],
                stop_reason="end_turn"
            )

        self.call_count += 1
        return response

    async def count_tokens(self, messages: list[dict]) -> int:
        """Simple token counting for tests."""
        return sum(len(str(m)) // 4 for m in messages)

    async def stream_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ):
        """Stream mock responses."""
        response = await self.create_message(system, messages, tools, **kwargs)
        yield response


class MockTool(BaseTool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        },
        "required": ["input"]
    }

    def __init__(self, return_value: str = "Tool executed successfully"):
        self.return_value = return_value
        self.execute_count = 0
        self.last_input = None

    async def execute(self, **kwargs) -> str:
        """Execute the mock tool."""
        self.execute_count += 1
        self.last_input = kwargs
        return self.return_value


class TestAgentEngineSimpleRun:
    """Tests for simple run scenarios."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider with text response."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[TextBlock(text="Hello! I'm here to help.")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.mark.asyncio
    async def test_simple_run_returns_text_response(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that a simple run returns the expected text response."""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
        )

        result = await engine.run("Hello")

        assert result == "Hello! I'm here to help."
        assert mock_provider.call_count == 1
        assert len(engine.context) == 2  # user message + assistant message


class TestAgentEngineToolCalls:
    """Tests for tool call execution."""

    @pytest.fixture
    def mock_provider_with_tools(self) -> MockProvider:
        """Create a mock provider that returns tool calls."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[
                    TextBlock(text="I'll use the mock tool."),
                    ToolUseBlock(
                        id="tool_1",
                        name="mock_tool",
                        input={"input": "test"}
                    )
                ],
                stop_reason="tool_use"
            ),
            ProviderResponse(
                content=[TextBlock(text="Tool executed successfully!")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.mark.asyncio
    async def test_run_with_tool_calls_executes_tools(
        self, mock_provider_with_tools: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that tool calls are properly executed."""
        engine = AgentEngine(
            provider=mock_provider_with_tools,
            tool_registry=tool_registry,
        )

        mock_tool = tool_registry.get("mock_tool")
        assert mock_tool is not None

        result = await engine.run("Use the mock tool")

        assert "Tool executed successfully!" in result
        assert mock_tool.execute_count == 1
        assert mock_tool.last_input == {"input": "test"}
        assert mock_provider_with_tools.call_count == 2  # tool call + final response


class TestAgentEngineStreaming:
    """Tests for streaming execution."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider for streaming."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[TextBlock(text="Streaming response")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        registry = ToolRegistry()
        return registry

    @pytest.mark.asyncio
    async def test_run_stream_yields_events(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that run_stream yields proper events with phase info."""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
        )

        events = []
        async for event in engine.run_stream("Hello"):
            events.append(event)

        assert len(events) == 2
        assert events[0]["type"] == "phase_start"
        assert events[0]["phase"] == 1
        assert events[0]["phase_label"] == "快速响应"
        assert events[1]["type"] == "complete"
        assert events[1]["text"] == "Streaming response"
        assert events[1]["phase"] == 1


class TestAgentEngineMaxIterations:
    """Tests for max iteration handling."""

    @pytest.fixture
    def infinite_tool_provider(self) -> MockProvider:
        """Create a provider that always returns tool calls."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[
                    ToolUseBlock(
                        id=f"tool_{i}",
                        name="mock_tool",
                        input={"input": f"iteration_{i}"}
                    )
                ],
                stop_reason="tool_use"
            )
            for i in range(100)
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.mark.asyncio
    async def test_max_iterations_prevents_infinite_loop(
        self, infinite_tool_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that max_iterations prevents infinite tool call loops."""
        config = AgentConfig(max_iterations=5)
        engine = AgentEngine(
            provider=infinite_tool_provider,
            tool_registry=tool_registry,
            config=config,
        )

        result = await engine.run("Start infinite loop")

        assert "Maximum iterations reached" in result
        assert infinite_tool_provider.call_count == 5


class TestAgentEngineContextTruncation:
    """Tests for context truncation."""

    @pytest.fixture
    def multi_response_provider(self) -> MockProvider:
        """Create a provider with multiple responses."""
        responses = []
        for i in range(10):
            responses.append(
                ProviderResponse(
                    content=[
                        TextBlock(text=f"Response {i}"),
                        ToolUseBlock(
                            id=f"tool_{i}",
                            name="mock_tool",
                            input={"input": f"call_{i}"}
                        )
                    ],
                    stop_reason="tool_use"
                )
            )
        # Final response
        responses.append(
            ProviderResponse(
                content=[TextBlock(text="All done!")],
                stop_reason="end_turn"
            )
        )
        return MockProvider(responses=responses)

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.mark.asyncio
    async def test_context_truncation_when_exceeds_limit(
        self, multi_response_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that context is truncated when it exceeds limit."""
        # Create context manager with small limit
        context = ContextManager(max_messages=10)

        config = AgentConfig(max_iterations=50)
        engine = AgentEngine(
            provider=multi_response_provider,
            tool_registry=tool_registry,
            config=config,
            context=context,
        )

        await engine.run("Start")

        # Context should have been truncated at some point
        # Final count should be within max_messages
        assert len(engine.context) <= 20  # Allow some margin for truncation threshold


class TestAgentEngineReset:
    """Tests for engine reset."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[TextBlock(text="Response")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_reset_clears_context(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that reset clears the context."""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
        )

        await engine.run("First message")
        assert len(engine.context) > 0

        engine.reset()
        assert len(engine.context) == 0
        assert len(engine.context.get_loaded_skills()) == 0


class TestAgentEngineContextSummary:
    """Tests for context summary."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[TextBlock(text="Response")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_get_context_summary_returns_valid_data(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that get_context_summary returns valid data."""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
        )

        await engine.run("Hello")

        summary = engine.get_context_summary()

        assert "session_id" in summary
        assert summary["session_id"] == engine.session_id
        assert "message_count" in summary
        assert summary["message_count"] == 2  # user + assistant
        assert "loaded_skills" in summary
        assert "config" in summary
        assert summary["config"]["model"] == "test-model"


class TestAgentEngineSessionId:
    """Tests for session ID."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider()

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    def test_session_id_is_unique_per_instance(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that each engine instance has a unique session ID."""
        engine1 = AgentEngine(provider=mock_provider, tool_registry=tool_registry)
        engine2 = AgentEngine(provider=mock_provider, tool_registry=tool_registry)

        assert engine1.session_id != engine2.session_id
        assert engine1.session_id is not None
        assert engine2.session_id is not None

        # Verify it's a valid UUID format
        uuid.UUID(engine1.session_id)  # Will raise if invalid
        uuid.UUID(engine2.session_id)


class TestAgentEnginePluginHooks:
    """Tests for plugin hooks."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[TextBlock(text="Response")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_on_engine_start_hook_called(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that on_engine_start hook is called."""
        plugin_manager = AsyncMock()
        plugin_manager.emit_hook = AsyncMock(return_value=None)

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            plugin_manager=plugin_manager,
        )

        await engine.run("Hello")

        plugin_manager.emit_hook.assert_any_call("on_engine_start", engine)

    @pytest.mark.asyncio
    async def test_on_before_llm_call_hook_receives_messages(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that on_before_llm_call hook receives messages."""
        plugin_manager = AsyncMock()

        # Track what messages were passed to the hook
        captured_messages = []

        async def capture_hook(hook_name, data):
            if hook_name == "on_before_llm_call":
                captured_messages.append(data)
            return None

        plugin_manager.emit_hook = AsyncMock(side_effect=capture_hook)

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            plugin_manager=plugin_manager,
        )

        await engine.run("Hello")

        # Verify hook was called with messages
        assert len(captured_messages) > 0
        messages = captured_messages[0]
        assert isinstance(messages, list)
        assert len(messages) >= 1
        assert messages[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_on_after_llm_call_hook_receives_response(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that on_after_llm_call hook receives response."""
        plugin_manager = AsyncMock()

        captured_responses = []

        async def capture_hook(hook_name, data):
            if hook_name == "on_after_llm_call":
                captured_responses.append(data)
            return None

        plugin_manager.emit_hook = AsyncMock(side_effect=capture_hook)

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            plugin_manager=plugin_manager,
        )

        await engine.run("Hello")

        assert len(captured_responses) > 0
        response = captured_responses[0]
        assert isinstance(response, ProviderResponse)

    @pytest.mark.asyncio
    async def test_on_task_complete_hook_called(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that on_task_complete hook is called with final text."""
        plugin_manager = AsyncMock()

        captured_text = []

        async def capture_hook(hook_name, data):
            if hook_name == "on_task_complete":
                captured_text.append(data)
            return None

        plugin_manager.emit_hook = AsyncMock(side_effect=capture_hook)

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            plugin_manager=plugin_manager,
        )

        await engine.run("Hello")

        assert len(captured_text) > 0
        assert captured_text[0] == "Response"


class TestAgentEngineHookModification:
    """Tests for hook modification of data."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[TextBlock(text="Original response")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_on_before_llm_call_can_modify_messages(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that on_before_llm_call can modify messages."""
        modified_messages = [{"role": "user", "content": "Modified message"}]

        plugin_manager = AsyncMock()
        plugin_manager.emit_hook = AsyncMock(return_value=[modified_messages])

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            plugin_manager=plugin_manager,
        )

        await engine.run("Original message")

        # Verify the modified messages were used
        assert mock_provider.call_history[0]["messages"] == modified_messages

    @pytest.mark.asyncio
    async def test_on_after_llm_call_can_modify_response(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that on_after_llm_call can modify response."""
        modified_response = ProviderResponse(
            content=[TextBlock(text="Modified response")],
            stop_reason="end_turn"
        )

        plugin_manager = AsyncMock()
        plugin_manager.emit_hook = AsyncMock(return_value=[modified_response])

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            plugin_manager=plugin_manager,
        )

        result = await engine.run("Hello")

        assert result == "Modified response"


class TestAgentEngineStreamingWithTools:
    """Tests for streaming with tool calls."""

    @pytest.fixture
    def mock_provider_with_tools(self) -> MockProvider:
        """Create a provider that returns tool calls."""
        return MockProvider(responses=[
            ProviderResponse(
                content=[
                    ToolUseBlock(
                        id="tool_1",
                        name="mock_tool",
                        input={"input": "test"}
                    )
                ],
                stop_reason="tool_use"
            ),
            ProviderResponse(
                content=[TextBlock(text="Final result")],
                stop_reason="end_turn"
            )
        ])

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry with mock tool."""
        registry = ToolRegistry()
        registry.register(MockTool())
        return registry

    @pytest.mark.asyncio
    async def test_run_stream_with_tool_calls(
        self, mock_provider_with_tools: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that run_stream handles tool calls with phased output."""
        engine = AgentEngine(
            provider=mock_provider_with_tools,
            tool_registry=tool_registry,
        )

        events = []
        async for event in engine.run_stream("Use tool"):
            events.append(event)

        event_types = [e["type"] for e in events]
        assert "phase_start" in event_types
        assert "tool_start" in event_types
        assert "tool_result" in event_types
        assert "complete" in event_types

        # Phase 1: tool calls
        phase_starts = [e for e in events if e["type"] == "phase_start"]
        assert len(phase_starts) >= 2
        assert phase_starts[0]["phase"] == 1
        assert phase_starts[0]["phase_label"] == "快速响应"
        assert phase_starts[1]["phase"] == 2
        assert phase_starts[1]["phase_label"] == "深度分析"

        # Check tool_start event has phase info
        tool_start_events = [e for e in events if e["type"] == "tool_start"]
        assert len(tool_start_events) == 1
        assert tool_start_events[0]["tool_name"] == "mock_tool"
        assert tool_start_events[0]["phase"] == 1

        # Check complete event has phase info
        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["text"] == "Final result"
        assert complete_events[0]["phase"] == 2


class TestAgentEngineAutoClassify:
    """Tests for auto task classification."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider()

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    @pytest.mark.asyncio
    async def test_auto_classify_task_without_registry(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test auto_classify_task returns fallback without registry."""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            category_registry=None,
        )

        result = await engine.auto_classify_task("Write a Python function")

        assert result["category"] == "coding"
        assert result["method"] == "fallback"
        assert result["confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_auto_classify_task_with_registry(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test auto_classify_task with registry."""
        # Create a mock category registry
        from dataclasses import dataclass
        from enum import Enum

        class Complexity(Enum):
            SIMPLE = "simple"
            STANDARD = "standard"
            COMPLEX = "complex"

        @dataclass
        class MockCategory:
            name: str = "coding"
            model: str = "claude-3-opus"
            agents: list = None
            complexity: Complexity = Complexity.STANDARD

            def __post_init__(self):
                if self.agents is None:
                    self.agents = ["code", "test"]

        @dataclass
        class MockClassificationResult:
            category: MockCategory
            confidence: float
            method: str
            matched_keywords: list = None

            def __post_init__(self):
                if self.matched_keywords is None:
                    self.matched_keywords = []

        mock_registry = AsyncMock()
        mock_registry.classify_async = AsyncMock(return_value=MockClassificationResult(
            category=MockCategory(),
            confidence=0.9,
            method="semantic"
        ))

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            category_registry=mock_registry,
        )

        result = await engine.auto_classify_task("Debug my code")

        assert result["category"] == "coding"
        assert result["confidence"] == 0.9
        assert result["method"] == "semantic"
        assert result["recommended_model"] == "claude-3-opus"

    @pytest.mark.asyncio
    async def test_auto_classify_task_handles_exception(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test auto_classify_task handles exceptions gracefully."""
        mock_registry = AsyncMock()
        mock_registry.classify_async = AsyncMock(side_effect=Exception("Classification failed"))

        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            category_registry=mock_registry,
        )

        result = await engine.auto_classify_task("Any task")

        # Should return fallback on exception
        assert result["category"] == "coding"
        assert result["method"] == "fallback"
        assert result["confidence"] == 0.5


class TestAgentEngineConfig:
    """Tests for AgentConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AgentConfig()
        assert config.system_prompt == "You are a helpful AI assistant."
        assert config.max_tokens == 4096
        assert config.temperature == 1.0
        assert config.max_iterations == 100
        assert config.permission_checker is None

    def test_custom_config(self):
        """Test custom configuration values."""
        config = AgentConfig(
            system_prompt="Custom prompt",
            max_tokens=8192,
            temperature=0.7,
            max_iterations=50,
        )
        assert config.system_prompt == "Custom prompt"
        assert config.max_tokens == 8192
        assert config.temperature == 0.7
        assert config.max_iterations == 50


class TestAgentEngineGetCategoryRegistry:
    """Tests for get_category_registry method."""

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider()

    @pytest.fixture
    def tool_registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    def test_get_category_registry_returns_none_when_not_set(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that get_category_registry returns None when not set."""
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            category_registry=None,
        )

        assert engine.get_category_registry() is None

    def test_get_category_registry_returns_registry(
        self, mock_provider: MockProvider, tool_registry: ToolRegistry
    ):
        """Test that get_category_registry returns the registry when set."""
        mock_registry = MagicMock()
        engine = AgentEngine(
            provider=mock_provider,
            tool_registry=tool_registry,
            category_registry=mock_registry,
        )

        assert engine.get_category_registry() is mock_registry


class TestAgentEngineConstructorContract:
    """Compatibility contract tests for engine constructor."""

    def test_old_model_id_signature_is_rejected(self):
        """The legacy model_id/llm_client constructor path should fail fast."""
        with pytest.raises(TypeError):
            AgentEngine(
                model_id="legacy-model",  # type: ignore[call-arg]
                tool_registry=ToolRegistry(),
            )
