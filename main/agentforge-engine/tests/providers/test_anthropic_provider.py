"""
Tests for Anthropic Provider

Tests the Anthropic provider implementation with mocked API responses.
"""

import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pyagentforge.providers.anthropic_provider import AnthropicProvider
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock


class TestAnthropicProvider:
    """Test suite for Anthropic Provider."""

    def test_anthropic_provider_initialization(self):
        """Test Anthropic provider initializes correctly."""
        provider = AnthropicProvider(
            api_key="test-api-key",
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.7,
        )

        assert provider.model == "claude-sonnet-4-20250514"
        assert provider.max_tokens == 4096
        assert provider.temperature == 0.7
        assert provider.client is not None

    def test_anthropic_provider_default_model(self):
        """Test Anthropic provider with default model."""
        provider = AnthropicProvider(api_key="test-key")

        assert provider.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_create_message_success(self):
        """Test successful message creation."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        # Mock Anthropic response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].type = "text"
        mock_response.content[0].text = "Hello! I'm Claude."
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Hello, Claude!"}],
                tools=[],
            )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) == 1
        assert isinstance(response.content[0], TextBlock)
        assert response.content[0].text == "Hello! I'm Claude."
        assert response.stop_reason == "end_turn"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_create_message_with_tools(self):
        """Test message creation with tool calls."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        # Mock response with tool use
        mock_response = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Let me help you with that."

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "toolu_123"
        tool_block.name = "read_file"
        tool_block.input = {"file_path": "/tmp/test.txt"}

        mock_response.content = [text_block, tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 25

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Read the file"}],
                tools=[
                    {
                        "name": "read_file",
                        "description": "Read a file",
                        "input_schema": {
                            "type": "object",
                            "properties": {"file_path": {"type": "string"}},
                        },
                    }
                ],
            )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) == 2
        assert isinstance(response.content[0], TextBlock)
        assert isinstance(response.content[1], ToolUseBlock)
        assert response.content[1].id == "toolu_123"
        assert response.content[1].name == "read_file"
        assert response.content[1].input == {"file_path": "/tmp/test.txt"}
        assert response.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_create_message_with_multiple_tool_calls(self):
        """Test message creation with multiple tool calls."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        tool1 = MagicMock()
        tool1.type = "tool_use"
        tool1.id = "toolu_1"
        tool1.name = "search"
        tool1.input = {"query": "test"}

        tool2 = MagicMock()
        tool2.type = "tool_use"
        tool2.id = "toolu_2"
        tool2.name = "read"
        tool2.input = {"file": "result.txt"}

        mock_response.content = [tool1, tool2]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 20
        mock_response.usage.output_tokens = 30

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Search and read"}],
                tools=[],
            )

        assert len(response.content) == 2
        assert all(isinstance(block, ToolUseBlock) for block in response.content)
        assert response.content[0].name == "search"
        assert response.content[1].name == "read"
        assert len(response.tool_calls) == 2

    @pytest.mark.asyncio
    async def test_create_message_with_custom_temperature(self):
        """Test message creation with custom temperature."""
        provider = AnthropicProvider(
            api_key="test-key",
            model="claude-sonnet-4-20250514",
            temperature=0.5,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

            # Check that temperature was passed
            call_args = mock_create.call_args[1]
            assert call_args["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_create_message_temperature_override(self):
        """Test that kwargs can override temperature."""
        provider = AnthropicProvider(
            api_key="test-key",
            model="claude-sonnet-4-20250514",
            temperature=0.5,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
                temperature=0.9,
            )

            call_args = mock_create.call_args[1]
            assert call_args["temperature"] == 0.9

    @pytest.mark.asyncio
    async def test_create_message_with_extra_params(self):
        """Test message creation with extra Anthropic parameters."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
                top_p=0.9,
                top_k=50,
                stop_sequences=["END"],
            )

            call_args = mock_create.call_args[1]
            assert call_args["top_p"] == 0.9
            assert call_args["top_k"] == 50
            assert call_args["stop_sequences"] == ["END"]

    @pytest.mark.asyncio
    async def test_create_message_max_tokens_stop(self):
        """Test response with max_tokens stop reason."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Partial response...")]
        mock_response.stop_reason = "max_tokens"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 100

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Write a long story"}],
                tools=[],
            )

        assert response.stop_reason == "max_tokens"

    @pytest.mark.asyncio
    async def test_count_tokens_simple(self):
        """Test simple token counting estimation."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well!"},
        ]

        token_count = await provider.count_tokens(messages)

        # Should return a reasonable estimate (length / 4)
        assert isinstance(token_count, int)
        assert token_count > 0

    @pytest.mark.asyncio
    async def test_count_tokens_with_content_blocks(self):
        """Test token counting with content blocks."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First part"},
                    {"type": "tool_use", "id": "tool_1", "name": "test", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool_1", "content": "Result"}
                ],
            },
        ]

        token_count = await provider.count_tokens(messages)

        assert isinstance(token_count, int)
        assert token_count > 0

    @pytest.mark.asyncio
    async def test_count_tokens_empty_messages(self):
        """Test token counting with empty messages."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        token_count = await provider.count_tokens([])

        assert token_count == 0

    @pytest.mark.asyncio
    async def test_stream_message_yields_events(self):
        """Test that stream_message yields streaming events."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_final = MagicMock()
        final_text_block = MagicMock()
        final_text_block.type = "text"
        final_text_block.text = "Complete response"
        mock_final.content = [final_text_block]
        mock_final.stop_reason = "end_turn"
        mock_final.usage = MagicMock()
        mock_final.usage.input_tokens = 10
        mock_final.usage.output_tokens = 20

        class MockStream:
            """Mock that supports both async iteration and get_final_message."""

            def __init__(self):
                self._events = [
                    MagicMock(type="content_block_start"),
                    MagicMock(type="content_block_delta"),
                    MagicMock(type="content_block_stop"),
                ]

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return self._iter_events()

            async def _iter_events(self):
                for event in self._events:
                    yield event

            async def get_final_message(self):
                return mock_final

        with patch.object(
            provider.client.messages,
            "stream",
            return_value=MockStream(),
        ):
            chunks = []
            async for chunk in provider.stream_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
            ):
                chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_create_message_api_error(self):
        """Test handling of API errors."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            with pytest.raises(Exception, match="API Error"):
                await provider.create_message(
                    system="System",
                    messages=[{"role": "user", "content": "Test"}],
                    tools=[],
                )

    @pytest.mark.asyncio
    async def test_create_message_with_tools_parameter(self):
        """Test that tools are properly passed to API."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        tools = [
            {
                "name": "test_tool",
                "description": "A test tool",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=tools,
            )

            call_args = mock_create.call_args[1]
            assert call_args["tools"] == tools

    @pytest.mark.asyncio
    async def test_create_message_without_tools(self):
        """Test that tools parameter is not passed when empty."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

            call_args = mock_create.call_args[1]
            assert "tools" not in call_args

    def test_provider_with_different_models(self):
        """Test provider with different Claude models."""
        models = [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-sonnet-20241022",
        ]

        for model in models:
            provider = AnthropicProvider(api_key="test-key", model=model)
            assert provider.model == model

    @pytest.mark.asyncio
    async def test_create_message_preserves_message_format(self):
        """Test that messages are passed through without modification."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        messages = [
            {"role": "user", "content": "First message"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Response"},
                    {"type": "tool_use", "id": "tool_1", "name": "test", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool_1", "content": "Result"}
                ],
            },
        ]

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=messages,
                tools=[],
            )

            # Messages should be passed as-is
            call_args = mock_create.call_args[1]
            assert call_args["messages"] == messages

    @pytest.mark.asyncio
    async def test_response_text_property(self):
        """Test ProviderResponse text property with Anthropic response."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="First paragraph."),
            MagicMock(type="text", text="Second paragraph."),
        ]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 20
        mock_response.usage.output_tokens = 30

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Tell me a story"}],
                tools=[],
            )

        assert "First paragraph." in response.text
        assert "Second paragraph." in response.text

    @pytest.mark.asyncio
    async def test_response_tool_calls_property(self):
        """Test ProviderResponse tool_calls property."""
        provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_response = MagicMock()
        read_block = MagicMock()
        read_block.type = "tool_use"
        read_block.id = "tool_1"
        read_block.name = "read"
        read_block.input = {"file": "test.txt"}

        write_block = MagicMock()
        write_block.type = "tool_use"
        write_block.id = "tool_2"
        write_block.name = "write"
        write_block.input = {"file": "out.txt"}

        mock_response.content = [read_block, write_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 25

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Process files"}],
                tools=[],
            )

        assert len(response.tool_calls) == 2
        assert response.tool_calls[0].name == "read"
        assert response.tool_calls[1].name == "write"
        assert response.has_tool_calls is True

    @pytest.mark.asyncio
    async def test_temperature_not_sent_when_default(self):
        """Test that temperature is not sent when it's the default (1.0)."""
        provider = AnthropicProvider(
            api_key="test-key",
            model="claude-sonnet-4-20250514",
            temperature=1.0,  # Default value
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.stop_reason = "end_turn"
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20

        with patch.object(
            provider.client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

            call_args = mock_create.call_args[1]
            # Temperature should not be in params when it's default
            assert "temperature" not in call_args


class TestAnthropicProviderIntegration:
    """Integration tests that require actual API calls (skip in CI)."""

    @pytest.mark.skip(reason="Requires actual API key")
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """Test with real Anthropic API (requires API key in environment)."""
        import os

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        provider = AnthropicProvider(api_key=api_key, model="claude-sonnet-4-20250514")

        response = await provider.create_message(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Say 'test'"}],
            tools=[],
        )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) > 0
        assert response.stop_reason in ["end_turn", "max_tokens"]
