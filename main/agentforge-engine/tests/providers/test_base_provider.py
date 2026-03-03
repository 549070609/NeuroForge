"""
Tests for BaseProvider Abstract Class

Tests the abstract interface and common functionality for all LLM providers.
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pyagentforge.providers.base import BaseProvider
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock


class ConcreteProvider(BaseProvider):
    """Concrete implementation of BaseProvider for testing."""

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """Test implementation of create_message."""
        # Simple implementation that returns a text response
        return ProviderResponse(
            content=[TextBlock(text="Test response")],
            stop_reason="end_turn",
            usage={"input_tokens": 10, "output_tokens": 5},
        )

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Test implementation of count_tokens."""
        # Simple implementation that counts characters
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total += len(block.get("text", ""))
        return total


class TestBaseProvider:
    """Test suite for BaseProvider abstract class."""

    def test_base_provider_initialization(self):
        """Test that BaseProvider initializes with correct default values."""
        provider = ConcreteProvider(model="test-model")

        assert provider.model == "test-model"
        assert provider.max_tokens == 4096
        assert provider.temperature == 1.0
        assert provider.extra_params == {}

    def test_base_provider_custom_parameters(self):
        """Test that BaseProvider accepts custom parameters."""
        provider = ConcreteProvider(
            model="custom-model",
            max_tokens=2048,
            temperature=0.7,
            custom_param="value",
        )

        assert provider.model == "custom-model"
        assert provider.max_tokens == 2048
        assert provider.temperature == 0.7
        assert provider.extra_params == {"custom_param": "value"}

    @pytest.mark.asyncio
    async def test_create_message_abstract_method(self):
        """Test that concrete implementation of create_message works."""
        provider = ConcreteProvider(model="test-model")

        response = await provider.create_message(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello!"}],
            tools=[],
        )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) == 1
        assert isinstance(response.content[0], TextBlock)
        assert response.content[0].text == "Test response"
        assert response.stop_reason == "end_turn"
        assert response.usage["input_tokens"] == 10

    @pytest.mark.asyncio
    async def test_count_tokens_abstract_method(self):
        """Test that concrete implementation of count_tokens works."""
        provider = ConcreteProvider(model="test-model")

        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well!"},
        ]

        token_count = await provider.count_tokens(messages)

        # Based on our simple implementation (character count)
        assert token_count == len("Hello, how are you?") + len("I'm doing well!")

    @pytest.mark.asyncio
    async def test_count_tokens_with_complex_messages(self):
        """Test count_tokens with messages containing content blocks."""
        provider = ConcreteProvider(model="test-model")

        messages = [
            {
                "role": "user",
                "content": "First message",
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Second message"},
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "test_tool",
                        "input": {"arg": "value"},
                    },
                ],
            },
        ]

        token_count = await provider.count_tokens(messages)

        # Should count text content only
        assert token_count == len("First message") + len("Second message")

    @pytest.mark.asyncio
    async def test_stream_message_default_implementation(self):
        """Test that stream_message has a default implementation that yields once."""
        provider = ConcreteProvider(model="test-model")

        chunks = []
        async for chunk in provider.stream_message(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello!"}],
            tools=[],
        ):
            chunks.append(chunk)

        # Default implementation should yield the non-streaming response once
        assert len(chunks) == 1
        assert isinstance(chunks[0], ProviderResponse)
        assert chunks[0].stop_reason == "end_turn"

    def test_base_provider_cannot_be_instantiated_directly(self):
        """Test that BaseProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            # Should raise TypeError because BaseProvider has abstract methods
            BaseProvider(model="test-model")

    @pytest.mark.asyncio
    async def test_create_message_with_tools(self):
        """Test that create_message can handle tool definitions."""
        provider = ConcreteProvider(model="test-model")

        tools = [
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                    },
                    "required": ["file_path"],
                },
            }
        ]

        response = await provider.create_message(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Read the file"}],
            tools=tools,
        )

        assert isinstance(response, ProviderResponse)

    @pytest.mark.asyncio
    async def test_create_message_with_extra_kwargs(self):
        """Test that create_message accepts extra keyword arguments."""
        provider = ConcreteProvider(model="test-model")

        response = await provider.create_message(
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Hello!"}],
            tools=[],
            custom_param="value",
            another_param=42,
        )

        assert isinstance(response, ProviderResponse)

    def test_provider_with_temperature_zero(self):
        """Test that provider can have temperature of 0."""
        provider = ConcreteProvider(model="test-model", temperature=0.0)

        assert provider.temperature == 0.0

    def test_provider_with_high_max_tokens(self):
        """Test that provider can have high max_tokens value."""
        provider = ConcreteProvider(model="test-model", max_tokens=128000)

        assert provider.max_tokens == 128000

    @pytest.mark.asyncio
    async def test_count_tokens_empty_messages(self):
        """Test count_tokens with empty message list."""
        provider = ConcreteProvider(model="test-model")

        token_count = await provider.count_tokens([])

        assert token_count == 0

    @pytest.mark.asyncio
    async def test_count_tokens_message_without_content(self):
        """Test count_tokens with message lacking content field."""
        provider = ConcreteProvider(model="test-model")

        messages = [{"role": "user"}]

        token_count = await provider.count_tokens(messages)

        # Should handle missing content gracefully
        assert token_count == 0

    @pytest.mark.asyncio
    async def test_stream_message_with_tools(self):
        """Test stream_message with tool definitions."""
        provider = ConcreteProvider(model="test-model")

        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        chunks = []
        async for chunk in provider.stream_message(
            system="Test",
            messages=[{"role": "user", "content": "Test"}],
            tools=tools,
        ):
            chunks.append(chunk)

        assert len(chunks) == 1
        assert isinstance(chunks[0], ProviderResponse)

    @pytest.mark.asyncio
    async def test_create_message_returns_correct_usage(self):
        """Test that create_message returns usage information."""
        provider = ConcreteProvider(model="test-model")

        response = await provider.create_message(
            system="System prompt",
            messages=[{"role": "user", "content": "User message"}],
            tools=[],
        )

        assert "input_tokens" in response.usage
        assert "output_tokens" in response.usage
        assert isinstance(response.usage["input_tokens"], int)
        assert isinstance(response.usage["output_tokens"], int)


class TestProviderResponse:
    """Test suite for ProviderResponse properties and methods."""

    def test_response_text_property(self):
        """Test that text property extracts text from content blocks."""
        response = ProviderResponse(
            content=[
                TextBlock(text="First paragraph."),
                TextBlock(text="Second paragraph."),
            ],
            stop_reason="end_turn",
        )

        assert response.text == "First paragraph.\nSecond paragraph."

    def test_response_text_property_empty(self):
        """Test text property with no text blocks."""
        response = ProviderResponse(
            content=[
                ToolUseBlock(id="tool_1", name="test", input={}),
            ],
            stop_reason="tool_use",
        )

        assert response.text == ""

    def test_response_tool_calls_property(self):
        """Test that tool_calls property extracts tool use blocks."""
        response = ProviderResponse(
            content=[
                TextBlock(text="Using tool..."),
                ToolUseBlock(id="tool_1", name="read", input={"file": "test.txt"}),
                ToolUseBlock(id="tool_2", name="write", input={"file": "out.txt"}),
            ],
            stop_reason="tool_use",
        )

        assert len(response.tool_calls) == 2
        assert response.tool_calls[0].name == "read"
        assert response.tool_calls[1].name == "write"

    def test_response_tool_calls_property_empty(self):
        """Test tool_calls property with no tool use blocks."""
        response = ProviderResponse(
            content=[TextBlock(text="Just text")],
            stop_reason="end_turn",
        )

        assert len(response.tool_calls) == 0

    def test_response_has_tool_calls_true(self):
        """Test has_tool_calls property returns True when tools present."""
        response = ProviderResponse(
            content=[
                ToolUseBlock(id="tool_1", name="test", input={}),
            ],
            stop_reason="tool_use",
        )

        assert response.has_tool_calls is True

    def test_response_has_tool_calls_false(self):
        """Test has_tool_calls property returns False when no tools."""
        response = ProviderResponse(
            content=[TextBlock(text="Text only")],
            stop_reason="end_turn",
        )

        assert response.has_tool_calls is False

    def test_response_with_usage(self):
        """Test ProviderResponse with usage information."""
        response = ProviderResponse(
            content=[TextBlock(text="Response")],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 50},
        )

        assert response.usage["input_tokens"] == 100
        assert response.usage["output_tokens"] == 50

    def test_response_default_usage(self):
        """Test ProviderResponse with default usage."""
        response = ProviderResponse(
            content=[TextBlock(text="Response")],
            stop_reason="end_turn",
        )

        assert response.usage == {}

    def test_response_mixed_content(self):
        """Test ProviderResponse with mixed content blocks."""
        response = ProviderResponse(
            content=[
                TextBlock(text="Let me help you."),
                ToolUseBlock(id="tool_1", name="search", input={"query": "test"}),
                TextBlock(text="I found some results."),
                ToolUseBlock(id="tool_2", name="read", input={"file": "result.txt"}),
            ],
            stop_reason="tool_use",
        )

        # Text property should extract both text blocks
        assert "Let me help you." in response.text
        assert "I found some results." in response.text

        # tool_calls should extract both tool blocks
        assert len(response.tool_calls) == 2
        assert response.has_tool_calls is True


class TestProviderEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_system_prompt(self):
        """Test create_message with empty system prompt."""
        provider = ConcreteProvider(model="test-model")

        response = await provider.create_message(
            system="",
            messages=[{"role": "user", "content": "Hello"}],
            tools=[],
        )

        assert isinstance(response, ProviderResponse)

    @pytest.mark.asyncio
    async def test_empty_messages_list(self):
        """Test create_message with empty messages list."""
        provider = ConcreteProvider(model="test-model")

        response = await provider.create_message(
            system="You are helpful.",
            messages=[],
            tools=[],
        )

        assert isinstance(response, ProviderResponse)

    @pytest.mark.asyncio
    async def test_large_number_of_messages(self):
        """Test create_message with large number of messages."""
        provider = ConcreteProvider(model="test-model")

        messages = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"}
            for i in range(100)
        ]

        response = await provider.create_message(
            system="You are helpful.",
            messages=messages,
            tools=[],
        )

        assert isinstance(response, ProviderResponse)

    @pytest.mark.asyncio
    async def test_large_tool_definitions(self):
        """Test create_message with large number of tools."""
        provider = ConcreteProvider(model="test-model")

        tools = [
            {
                "name": f"tool_{i}",
                "description": f"Tool number {i}",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        f"param_{j}": {"type": "string"} for j in range(10)
                    },
                },
            }
            for i in range(50)
        ]

        response = await provider.create_message(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Use tools"}],
            tools=tools,
        )

        assert isinstance(response, ProviderResponse)
