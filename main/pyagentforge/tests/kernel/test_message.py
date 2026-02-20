"""
Tests for Message dataclass and related types

Comprehensive tests for Message, TextBlock, ToolUseBlock, ToolResultBlock, and ProviderResponse.
"""

import pytest
from typing import Any

from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
)


class TestTextBlock:
    """Tests for TextBlock."""

    def test_text_block_creation(self):
        """Test creating a text block."""
        block = TextBlock(text="Hello, world!")

        assert block.type == "text"
        assert block.text == "Hello, world!"

    def test_text_block_empty_text(self):
        """Test text block with empty text."""
        block = TextBlock(text="")

        assert block.type == "text"
        assert block.text == ""

    def test_text_block_long_text(self):
        """Test text block with long text."""
        long_text = "a" * 10000
        block = TextBlock(text=long_text)

        assert block.text == long_text

    def test_text_block_unicode(self):
        """Test text block with unicode characters."""
        block = TextBlock(text="Hello \u4e16\u754c \U0001F600")

        assert block.text == "Hello \u4e16\u754c \U0001F600"

    def test_text_block_model_dump(self):
        """Test text block serialization."""
        block = TextBlock(text="Test")
        data = block.model_dump()

        assert data["type"] == "text"
        assert data["text"] == "Test"


class TestToolUseBlock:
    """Tests for ToolUseBlock."""

    def test_tool_use_block_creation(self):
        """Test creating a tool use block."""
        block = ToolUseBlock(
            id="tool_123",
            name="read_file",
            input={"file_path": "/tmp/test.txt"}
        )

        assert block.type == "tool_use"
        assert block.id == "tool_123"
        assert block.name == "read_file"
        assert block.input == {"file_path": "/tmp/test.txt"}

    def test_tool_use_block_empty_input(self):
        """Test tool use block with empty input."""
        block = ToolUseBlock(id="tool_1", name="list", input={})

        assert block.input == {}

    def test_tool_use_block_complex_input(self):
        """Test tool use block with complex input."""
        complex_input = {
            "nested": {
                "key": "value",
                "list": [1, 2, 3]
            },
            "boolean": True,
            "null": None
        }
        block = ToolUseBlock(
            id="tool_1",
            name="complex_tool",
            input=complex_input
        )

        assert block.input == complex_input

    def test_tool_use_block_model_dump(self):
        """Test tool use block serialization."""
        block = ToolUseBlock(
            id="tool_1",
            name="test",
            input={"key": "value"}
        )
        data = block.model_dump()

        assert data["type"] == "tool_use"
        assert data["id"] == "tool_1"
        assert data["name"] == "test"
        assert data["input"] == {"key": "value"}


class TestToolResultBlock:
    """Tests for ToolResultBlock."""

    def test_tool_result_block_creation(self):
        """Test creating a tool result block."""
        block = ToolResultBlock(
            tool_use_id="tool_123",
            content="File content here",
            is_error=False
        )

        assert block.type == "tool_result"
        assert block.tool_use_id == "tool_123"
        assert block.content == "File content here"
        assert block.is_error is False

    def test_tool_result_block_error(self):
        """Test tool result block with error."""
        block = ToolResultBlock(
            tool_use_id="tool_123",
            content="File not found",
            is_error=True
        )

        assert block.is_error is True
        assert "File not found" in block.content

    def test_tool_result_block_default_is_error(self):
        """Test tool result block default is_error value."""
        block = ToolResultBlock(
            tool_use_id="tool_1",
            content="Success"
        )

        assert block.is_error is False

    def test_tool_result_block_long_content(self):
        """Test tool result block with long content."""
        long_content = "x" * 100000
        block = ToolResultBlock(
            tool_use_id="tool_1",
            content=long_content
        )

        assert block.content == long_content


class TestMessage:
    """Tests for Message."""

    def test_user_message_creation(self):
        """Test creating a user message."""
        msg = Message(role="user", content="Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_message_creation(self):
        """Test creating an assistant message."""
        msg = Message(role="assistant", content="Hi there")

        assert msg.role == "assistant"
        assert msg.content == "Hi there"

    def test_user_message_factory(self):
        """Test user_message factory method."""
        msg = Message.user_message("Hello from user")

        assert msg.role == "user"
        assert msg.content == "Hello from user"

    def test_assistant_text_factory(self):
        """Test assistant_text factory method."""
        msg = Message.assistant_text("Hello from assistant")

        assert msg.role == "assistant"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)
        assert msg.content[0].text == "Hello from assistant"

    def test_assistant_tool_calls_factory(self):
        """Test assistant_tool_calls factory method."""
        tool_calls = [
            ToolUseBlock(id="tool_1", name="read", input={"file": "/test"}),
            ToolUseBlock(id="tool_2", name="write", input={"file": "/test", "content": "data"}),
        ]
        msg = Message.assistant_tool_calls(tool_calls)

        assert msg.role == "assistant"
        assert msg.content == tool_calls

    def test_tool_result_factory(self):
        """Test tool_result factory method."""
        msg = Message.tool_result("tool_123", "Result content", is_error=False)

        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], ToolResultBlock)
        assert msg.content[0].tool_use_id == "tool_123"
        assert msg.content[0].content == "Result content"

    def test_tool_result_factory_with_error(self):
        """Test tool_result factory with error."""
        msg = Message.tool_result("tool_123", "Error occurred", is_error=True)

        result_block = msg.content[0]
        assert result_block.is_error is True

    def test_message_with_block_content(self):
        """Test message with block content."""
        blocks = [
            TextBlock(text="Here's the result:"),
            ToolUseBlock(id="tool_1", name="read", input={"file": "/test"}),
        ]
        msg = Message(role="assistant", content=blocks)

        assert isinstance(msg.content, list)
        assert len(msg.content) == 2


class TestMessageToAPIFormat:
    """Tests for Message.to_api_format method."""

    def test_to_api_format_string_content(self):
        """Test to_api_format with string content."""
        msg = Message(role="user", content="Hello")

        api_format = msg.to_api_format()

        assert api_format["role"] == "user"
        assert api_format["content"] == "Hello"

    def test_to_api_format_text_block(self):
        """Test to_api_format with text block."""
        msg = Message(role="assistant", content=[TextBlock(text="Response")])

        api_format = msg.to_api_format()

        assert api_format["role"] == "assistant"
        assert isinstance(api_format["content"], list)
        assert api_format["content"][0]["type"] == "text"
        assert api_format["content"][0]["text"] == "Response"

    def test_to_api_format_tool_use_block(self):
        """Test to_api_format with tool use block."""
        msg = Message(
            role="assistant",
            content=[ToolUseBlock(id="tool_1", name="read", input={"file": "/test"})]
        )

        api_format = msg.to_api_format()

        assert api_format["role"] == "assistant"
        assert api_format["content"][0]["type"] == "tool_use"
        assert api_format["content"][0]["id"] == "tool_1"
        assert api_format["content"][0]["name"] == "read"

    def test_to_api_format_tool_result_block(self):
        """Test to_api_format with tool result block."""
        msg = Message(
            role="user",
            content=[ToolResultBlock(tool_use_id="tool_1", content="Result", is_error=False)]
        )

        api_format = msg.to_api_format()

        assert api_format["role"] == "user"
        assert api_format["content"][0]["type"] == "tool_result"
        assert api_format["content"][0]["tool_use_id"] == "tool_1"
        assert api_format["content"][0]["content"] == "Result"
        assert api_format["content"][0]["is_error"] is False

    def test_to_api_format_mixed_blocks(self):
        """Test to_api_format with mixed blocks."""
        msg = Message(
            role="assistant",
            content=[
                TextBlock(text="Using tool:"),
                ToolUseBlock(id="tool_1", name="read", input={"file": "/test"}),
                TextBlock(text="More text"),
            ]
        )

        api_format = msg.to_api_format()

        assert len(api_format["content"]) == 3
        assert api_format["content"][0]["type"] == "text"
        assert api_format["content"][1]["type"] == "tool_use"
        assert api_format["content"][2]["type"] == "text"


class TestProviderResponse:
    """Tests for ProviderResponse."""

    def test_provider_response_creation(self):
        """Test creating a provider response."""
        response = ProviderResponse(
            content=[TextBlock(text="Hello")],
            stop_reason="end_turn"
        )

        assert response.stop_reason == "end_turn"
        assert len(response.content) == 1

    def test_text_property(self):
        """Test text property extraction."""
        response = ProviderResponse(
            content=[
                TextBlock(text="First"),
                TextBlock(text="Second"),
            ],
            stop_reason="end_turn"
        )

        assert response.text == "First\nSecond"

    def test_text_property_no_text(self):
        """Test text property with no text blocks."""
        response = ProviderResponse(
            content=[ToolUseBlock(id="tool_1", name="test", input={})],
            stop_reason="tool_use"
        )

        assert response.text == ""

    def test_tool_calls_property(self):
        """Test tool_calls property extraction."""
        response = ProviderResponse(
            content=[
                TextBlock(text="Using tool"),
                ToolUseBlock(id="tool_1", name="read", input={"file": "/test"}),
                ToolUseBlock(id="tool_2", name="write", input={}),
            ],
            stop_reason="tool_use"
        )

        tool_calls = response.tool_calls
        assert len(tool_calls) == 2
        assert tool_calls[0].name == "read"
        assert tool_calls[1].name == "write"

    def test_tool_calls_property_no_tools(self):
        """Test tool_calls property with no tool calls."""
        response = ProviderResponse(
            content=[TextBlock(text="Hello")],
            stop_reason="end_turn"
        )

        assert response.tool_calls == []

    def test_has_tool_calls_true(self):
        """Test has_tool_calls returns True when tools present."""
        response = ProviderResponse(
            content=[ToolUseBlock(id="tool_1", name="test", input={})],
            stop_reason="tool_use"
        )

        assert response.has_tool_calls is True

    def test_has_tool_calls_false(self):
        """Test has_tool_calls returns False when no tools."""
        response = ProviderResponse(
            content=[TextBlock(text="Hello")],
            stop_reason="end_turn"
        )

        assert response.has_tool_calls is False

    def test_usage_dict(self):
        """Test usage dictionary."""
        response = ProviderResponse(
            content=[TextBlock(text="Hello")],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 50}
        )

        assert response.usage["input_tokens"] == 100
        assert response.usage["output_tokens"] == 50

    def test_usage_default(self):
        """Test usage default value."""
        response = ProviderResponse(
            content=[TextBlock(text="Hello")],
            stop_reason="end_turn"
        )

        assert response.usage == {}

    def test_stop_reasons(self):
        """Test different stop reasons."""
        for reason in ["end_turn", "tool_use", "max_tokens"]:
            response = ProviderResponse(
                content=[TextBlock(text="Test")],
                stop_reason=reason
            )
            assert response.stop_reason == reason


class TestProviderResponseModelDump:
    """Tests for ProviderResponse serialization."""

    def test_model_dump(self):
        """Test ProviderResponse serialization."""
        response = ProviderResponse(
            content=[TextBlock(text="Hello")],
            stop_reason="end_turn",
            usage={"input_tokens": 10}
        )

        data = response.model_dump()

        assert data["stop_reason"] == "end_turn"
        assert data["usage"]["input_tokens"] == 10
        assert isinstance(data["content"], list)


class TestMessageModelDump:
    """Tests for Message serialization."""

    def test_message_model_dump(self):
        """Test Message serialization."""
        msg = Message.user_message("Hello")
        data = msg.model_dump()

        assert data["role"] == "user"
        assert data["content"] == "Hello"

    def test_message_with_blocks_model_dump(self):
        """Test Message with blocks serialization."""
        msg = Message.assistant_text("Response")
        data = msg.model_dump()

        assert data["role"] == "assistant"
        assert isinstance(data["content"], list)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_message_content(self):
        """Test message with empty string content."""
        msg = Message(role="user", content="")

        api_format = msg.to_api_format()
        assert api_format["content"] == ""

    def test_message_role_validation(self):
        """Test that role must be user or assistant."""
        # Valid roles
        Message(role="user", content="test")
        Message(role="assistant", content="test")

    def test_text_block_type_literal(self):
        """Test that TextBlock type is always 'text'."""
        block = TextBlock(text="Test")
        assert block.type == "text"

    def test_tool_use_block_type_literal(self):
        """Test that ToolUseBlock type is always 'tool_use'."""
        block = ToolUseBlock(id="1", name="test", input={})
        assert block.type == "tool_use"

    def test_tool_result_block_type_literal(self):
        """Test that ToolResultBlock type is always 'tool_result'."""
        block = ToolResultBlock(tool_use_id="1", content="test")
        assert block.type == "tool_result"

    def test_provider_response_mixed_content(self):
        """Test ProviderResponse with mixed content types."""
        response = ProviderResponse(
            content=[
                TextBlock(text="Here's the result:"),
                ToolUseBlock(id="1", name="read", input={}),
                TextBlock(text="More info"),
                ToolUseBlock(id="2", name="write", input={}),
            ],
            stop_reason="tool_use"
        )

        assert len(response.content) == 4
        assert response.text == "Here's the result:\nMore info"
        assert len(response.tool_calls) == 2


class TestBlockEquality:
    """Tests for block equality and comparison."""

    def test_text_block_equality(self):
        """Test TextBlock equality."""
        block1 = TextBlock(text="Hello")
        block2 = TextBlock(text="Hello")
        block3 = TextBlock(text="Different")

        assert block1 == block2
        assert block1 != block3

    def test_tool_use_block_equality(self):
        """Test ToolUseBlock equality."""
        block1 = ToolUseBlock(id="1", name="read", input={"file": "/test"})
        block2 = ToolUseBlock(id="1", name="read", input={"file": "/test"})
        block3 = ToolUseBlock(id="2", name="write", input={})

        assert block1 == block2
        assert block1 != block3


class TestMessageWithSpecialCharacters:
    """Tests for messages with special characters."""

    def test_message_with_newlines(self):
        """Test message with newlines."""
        msg = Message.user_message("Line 1\nLine 2\nLine 3")

        assert "\n" in msg.content

    def test_message_with_tabs(self):
        """Test message with tabs."""
        msg = Message.user_message("Col1\tCol2\tCol3")

        assert "\t" in msg.content

    def test_message_with_quotes(self):
        """Test message with quotes."""
        msg = Message.user_message('He said "Hello" and \'Goodbye\'')

        assert '"' in msg.content
        assert "'" in msg.content

    def test_message_with_json(self):
        """Test message with JSON."""
        json_content = '{"key": "value", "number": 123}'
        msg = Message.user_message(json_content)

        assert msg.content == json_content


class TestMessageHashAndRepr:
    """Tests for message hash and representation."""

    def test_message_repr(self):
        """Test Message string representation."""
        msg = Message.user_message("Hello")

        repr_str = repr(msg)
        assert "Message" in repr_str
        assert "user" in repr_str

    def test_block_repr(self):
        """Test block string representations."""
        text_block = TextBlock(text="Test")
        assert "TextBlock" in repr(text_block)

        tool_block = ToolUseBlock(id="1", name="test", input={})
        assert "ToolUseBlock" in repr(tool_block)

        result_block = ToolResultBlock(tool_use_id="1", content="result")
        assert "ToolResultBlock" in repr(result_block)
