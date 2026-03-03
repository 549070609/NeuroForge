"""
Tests for OpenAI Provider

Tests the OpenAI provider implementation with mocked API responses.
"""

import json
import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from pyagentforge.providers.openai_provider import OpenAIProvider
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock


class TestOpenAIProvider:
    """Test suite for OpenAI Provider."""

    def test_openai_provider_initialization(self):
        """Test OpenAI provider initializes correctly."""
        provider = OpenAIProvider(
            api_key="test-api-key",
            model="gpt-4-turbo-preview",
            max_tokens=4096,
            temperature=0.7,
        )

        assert provider.model == "gpt-4-turbo-preview"
        assert provider.max_tokens == 4096
        assert provider.temperature == 0.7
        assert provider.client is not None

    def test_openai_provider_with_custom_base_url(self):
        """Test OpenAI provider with custom base URL."""
        provider = OpenAIProvider(
            api_key="test-api-key",
            model="gpt-4",
            base_url="https://custom.api.com/v1",
        )

        assert str(provider.client.base_url).rstrip("/") == "https://custom.api.com/v1"

    def test_convert_tools_to_openai(self):
        """Test tool format conversion to OpenAI format."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        tools = [
            {
                "name": "read_file",
                "description": "Read a file from disk",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"},
                    },
                    "required": ["file_path"],
                },
            }
        ]

        openai_tools = provider._convert_tools_to_openai(tools)

        assert len(openai_tools) == 1
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "read_file"
        assert openai_tools[0]["function"]["description"] == "Read a file from disk"
        assert "properties" in openai_tools[0]["function"]["parameters"]

    def test_convert_messages_to_openai_simple(self):
        """Test simple message format conversion."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        openai_messages = provider._convert_messages_to_openai(
            system="You are helpful.",
            messages=messages,
        )

        assert len(openai_messages) == 3
        assert openai_messages[0] == {"role": "system", "content": "You are helpful."}
        assert openai_messages[1] == {"role": "user", "content": "Hello!"}
        assert openai_messages[2] == {"role": "assistant", "content": "Hi there!"}

    def test_convert_messages_with_tool_use(self):
        """Test message conversion with tool use blocks."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me read that file."},
                    {
                        "type": "tool_use",
                        "id": "call_123",
                        "name": "read_file",
                        "input": {"file_path": "/tmp/test.txt"},
                    },
                ],
            }
        ]

        openai_messages = provider._convert_messages_to_openai(
            system="You are helpful.",
            messages=messages,
        )

        assert len(openai_messages) == 2
        assert openai_messages[1]["role"] == "assistant"
        assert "tool_calls" in openai_messages[1]
        assert len(openai_messages[1]["tool_calls"]) == 1
        assert openai_messages[1]["tool_calls"][0]["function"]["name"] == "read_file"

    def test_convert_messages_with_tool_result(self):
        """Test message conversion with tool result blocks."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call_123",
                        "content": "File content here",
                    }
                ],
            }
        ]

        openai_messages = provider._convert_messages_to_openai(
            system="You are helpful.",
            messages=messages,
        )

        assert len(openai_messages) == 2
        assert openai_messages[1]["role"] == "tool"
        assert openai_messages[1]["tool_call_id"] == "call_123"
        assert openai_messages[1]["content"] == "File content here"

    @pytest.mark.asyncio
    async def test_create_message_success(self):
        """Test successful message creation."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        # Mock the OpenAI client response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello! I'm doing well."
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Hello, how are you?"}],
                tools=[],
            )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) == 1
        assert isinstance(response.content[0], TextBlock)
        assert response.content[0].text == "Hello! I'm doing well."
        assert response.stop_reason == "end_turn"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20

    @pytest.mark.asyncio
    async def test_create_message_with_tools(self):
        """Test message creation with tool calls."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        # Mock response with tool calls
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_123"
        mock_response.choices[0].message.tool_calls[0].function.name = "read_file"
        mock_response.choices[
            0
        ].message.tool_calls[0].function.arguments = '{"file_path": "/tmp/test.txt"}'
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 15
        mock_response.usage.completion_tokens = 10

        with patch.object(
            provider.client.chat.completions,
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
        assert len(response.content) == 1
        assert isinstance(response.content[0], ToolUseBlock)
        assert response.content[0].id == "call_123"
        assert response.content[0].name == "read_file"
        assert response.content[0].input == {"file_path": "/tmp/test.txt"}
        assert response.stop_reason == "tool_use"

    @pytest.mark.asyncio
    async def test_json_arguments_parsing_string(self):
        """Test parsing JSON arguments when returned as string."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_1"
        mock_response.choices[0].message.tool_calls[0].function.name = "search"
        mock_response.choices[
            0
        ].message.tool_calls[0].function.arguments = '{"query": "test", "limit": 10}'
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Search"}],
                tools=[],
            )

        # Should parse JSON string correctly
        assert response.content[0].input == {"query": "test", "limit": 10}

    @pytest.mark.asyncio
    async def test_json_arguments_parsing_dict(self):
        """Test parsing arguments when already a dict."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_1"
        mock_response.choices[0].message.tool_calls[0].function.name = "test"
        mock_response.choices[0].message.tool_calls[0].function.arguments = {
            "key": "value"
        }
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

        assert response.content[0].input == {"key": "value"}

    @pytest.mark.asyncio
    async def test_handle_json_parse_error(self):
        """Test handling of invalid JSON in tool arguments."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_1"
        mock_response.choices[0].message.tool_calls[0].function.name = "test_tool"
        mock_response.choices[
            0
        ].message.tool_calls[0].function.arguments = "invalid json{{{"
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

        # Should fallback to empty dict on parse error
        assert response.content[0].input == {}

    @pytest.mark.asyncio
    async def test_count_tokens_with_tiktoken(self):
        """Test token counting with tiktoken."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing well!"},
        ]

        token_count = await provider.count_tokens(messages)

        # Should return a reasonable token count (not just length/4)
        assert isinstance(token_count, int)
        assert token_count > 0

    @pytest.mark.asyncio
    async def test_count_tokens_fallback(self):
        """Test token counting fallback when tiktoken fails."""
        provider = OpenAIProvider(api_key="test-key", model="unknown-model")

        messages = [
            {"role": "user", "content": "Test message"},
        ]

        # Should fallback to simple estimation
        token_count = await provider.count_tokens(messages)

        assert isinstance(token_count, int)
        assert token_count > 0

    @pytest.mark.asyncio
    async def test_stream_message_yields_chunks(self):
        """Test that stream_message yields text deltas and a final ProviderResponse."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        def _make_chunk(content=None, finish_reason=None, usage=None):
            delta = MagicMock()
            delta.content = content
            delta.tool_calls = None
            choice = MagicMock()
            choice.delta = delta
            choice.finish_reason = finish_reason
            chunk = MagicMock()
            chunk.choices = [choice]
            chunk.usage = usage
            return chunk

        async def mock_stream():
            yield _make_chunk(content="Hello")
            yield _make_chunk(content=" world")
            yield _make_chunk(content="!", finish_reason="stop")
            final_usage = MagicMock()
            final_usage.prompt_tokens = 1
            final_usage.completion_tokens = 1
            yield _make_chunk(finish_reason=None, usage=final_usage)

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_stream(),
        ):
            events = []
            async for event in provider.stream_message(
                system="You are helpful.",
                messages=[{"role": "user", "content": "Hi"}],
                tools=[],
            ):
                events.append(event)

        text_deltas = [e for e in events if isinstance(e, dict) and e.get("type") == "text_delta"]
        assert len(text_deltas) == 3
        assert text_deltas[0]["text"] == "Hello"
        assert text_deltas[1]["text"] == " world"
        assert text_deltas[2]["text"] == "!"

        final = events[-1]
        assert isinstance(final, ProviderResponse)
        assert final.text == "Hello world!"
        assert final.stop_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_create_message_with_custom_parameters(self):
        """Test message creation with custom max_tokens and temperature."""
        provider = OpenAIProvider(
            api_key="test-key",
            model="gpt-4",
            max_tokens=2048,
            temperature=0.5,
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
            )

            # Check that custom parameters were passed
            call_args = mock_create.call_args[1]
            assert call_args["max_tokens"] == 2048
            assert call_args["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_create_message_with_kwarg_override(self):
        """Test that kwargs override instance parameters."""
        provider = OpenAIProvider(
            api_key="test-key",
            model="gpt-4",
            max_tokens=2048,
            temperature=0.5,
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 10

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Test"}],
                tools=[],
                max_tokens=1024,
                temperature=0.8,
            )

            # Check that kwarg values were used
            call_args = mock_create.call_args[1]
            assert call_args["max_tokens"] == 1024
            assert call_args["temperature"] == 0.8

    @pytest.mark.asyncio
    async def test_create_message_max_tokens_stop(self):
        """Test response with max_tokens stop reason."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Partial response..."
        mock_response.choices[0].message.tool_calls = None
        mock_response.choices[0].finish_reason = "length"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 100

        with patch.object(
            provider.client.chat.completions,
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
    async def test_create_message_with_text_and_tools(self):
        """Test response with both text and tool calls."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "I'll help you with that."
        mock_response.choices[0].message.tool_calls = [MagicMock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_1"
        mock_response.choices[0].message.tool_calls[0].function.name = "search"
        mock_response.choices[
            0
        ].message.tool_calls[0].function.arguments = '{"query": "test"}'
        mock_response.choices[0].finish_reason = "tool_calls"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20

        with patch.object(
            provider.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await provider.create_message(
                system="System",
                messages=[{"role": "user", "content": "Search for something"}],
                tools=[],
            )

        # Should have both text and tool_use blocks
        assert len(response.content) == 2
        assert isinstance(response.content[0], TextBlock)
        assert isinstance(response.content[1], ToolUseBlock)
        assert response.text == "I'll help you with that."
        assert len(response.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_create_message_api_error(self):
        """Test handling of API errors."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        with patch.object(
            provider.client.chat.completions,
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
    async def test_count_tokens_with_content_blocks(self):
        """Test token counting with content blocks."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First part"},
                    {"type": "text", "text": "Second part"},
                ],
            }
        ]

        token_count = await provider.count_tokens(messages)

        assert isinstance(token_count, int)
        assert token_count > 0

    def test_convert_tools_empty_list(self):
        """Test tool conversion with empty list."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        result = provider._convert_tools_to_openai([])

        assert result == []

    def test_convert_messages_empty_list(self):
        """Test message conversion with empty messages."""
        provider = OpenAIProvider(api_key="test-key", model="gpt-4")

        result = provider._convert_messages_to_openai(
            system="System", messages=[]
        )

        # Should have system message only
        assert len(result) == 1
        assert result[0] == {"role": "system", "content": "System"}


class TestOpenAIProviderIntegration:
    """Integration tests that require actual API calls (skip in CI)."""

    @pytest.mark.skip(reason="Requires actual API key")
    @pytest.mark.asyncio
    async def test_real_api_call(self):
        """Test with real OpenAI API (requires API key in environment)."""
        import os

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        provider = OpenAIProvider(api_key=api_key, model="gpt-3.5-turbo")

        response = await provider.create_message(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Say 'test'"}],
            tools=[],
        )

        assert isinstance(response, ProviderResponse)
        assert len(response.content) > 0
        assert response.stop_reason in ["end_turn", "max_tokens"]
