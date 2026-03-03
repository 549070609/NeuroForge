"""
Tests for ThinkingBlock integration into the message type system.

Validates that ThinkingBlock is properly integrated into MessageContent,
ProviderResponse, and Message.to_api_format().
"""

import pytest

from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)


class TestThinkingBlock:
    """Tests for ThinkingBlock."""

    def test_creation(self):
        block = ThinkingBlock(thinking="Let me reason about this...")

        assert block.type == "thinking"
        assert block.thinking == "Let me reason about this..."
        assert block.signature is None

    def test_creation_with_signature(self):
        block = ThinkingBlock(
            thinking="Step-by-step reasoning",
            signature="sig_abc123",
        )

        assert block.thinking == "Step-by-step reasoning"
        assert block.signature == "sig_abc123"

    def test_model_dump(self):
        block = ThinkingBlock(thinking="reasoning", signature="sig_1")
        data = block.model_dump()

        assert data["type"] == "thinking"
        assert data["thinking"] == "reasoning"
        assert data["signature"] == "sig_1"

    def test_equality(self):
        b1 = ThinkingBlock(thinking="same")
        b2 = ThinkingBlock(thinking="same")
        b3 = ThinkingBlock(thinking="different")

        assert b1 == b2
        assert b1 != b3


class TestMessageWithThinkingBlock:
    """Tests for Message containing ThinkingBlock."""

    def test_assistant_message_with_thinking(self):
        blocks = [
            ThinkingBlock(thinking="Let me think..."),
            TextBlock(text="Here is my answer"),
        ]
        msg = Message(role="assistant", content=blocks)

        assert len(msg.content) == 2
        assert isinstance(msg.content[0], ThinkingBlock)
        assert isinstance(msg.content[1], TextBlock)

    def test_to_api_format_thinking_without_signature(self):
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="reasoning here"),
                TextBlock(text="answer"),
            ],
        )
        api = msg.to_api_format()

        assert api["role"] == "assistant"
        assert len(api["content"]) == 2

        thinking_block = api["content"][0]
        assert thinking_block["type"] == "thinking"
        assert thinking_block["thinking"] == "reasoning here"
        assert "signature" not in thinking_block

    def test_to_api_format_thinking_with_signature(self):
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="step by step", signature="sig_xyz"),
                TextBlock(text="final answer"),
            ],
        )
        api = msg.to_api_format()

        thinking_block = api["content"][0]
        assert thinking_block["type"] == "thinking"
        assert thinking_block["thinking"] == "step by step"
        assert thinking_block["signature"] == "sig_xyz"

    def test_to_api_format_thinking_with_tool_use(self):
        """Thinking + text + tool_use mixed message."""
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="I should read the file"),
                TextBlock(text="Let me check that file"),
                ToolUseBlock(id="t1", name="read", input={"path": "/a.txt"}),
            ],
        )
        api = msg.to_api_format()

        assert len(api["content"]) == 3
        assert api["content"][0]["type"] == "thinking"
        assert api["content"][1]["type"] == "text"
        assert api["content"][2]["type"] == "tool_use"


class TestProviderResponseWithThinkingBlock:
    """Tests for ProviderResponse containing ThinkingBlock."""

    def test_response_with_thinking(self):
        response = ProviderResponse(
            content=[
                ThinkingBlock(thinking="reasoning"),
                TextBlock(text="answer"),
            ],
            stop_reason="end_turn",
        )

        assert len(response.content) == 2
        assert response.text == "answer"
        assert response.has_tool_calls is False

    def test_response_thinking_not_in_text(self):
        """ThinkingBlock content should not appear in the .text property."""
        response = ProviderResponse(
            content=[
                ThinkingBlock(thinking="secret reasoning"),
                TextBlock(text="visible answer"),
            ],
            stop_reason="end_turn",
        )

        assert "secret reasoning" not in response.text
        assert response.text == "visible answer"

    def test_response_thinking_not_in_tool_calls(self):
        """ThinkingBlock should not appear in .tool_calls."""
        response = ProviderResponse(
            content=[
                ThinkingBlock(thinking="reasoning"),
                ToolUseBlock(id="t1", name="read", input={}),
            ],
            stop_reason="tool_use",
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "read"

    def test_response_with_thinking_and_usage(self):
        response = ProviderResponse(
            content=[
                ThinkingBlock(thinking="thought"),
                TextBlock(text="output"),
            ],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        assert response.usage["input_tokens"] == 100
        assert response.usage["output_tokens"] == 200


class TestThinkingBlockRoundTrip:
    """Test ThinkingBlock survives serialization round-trips."""

    def test_message_model_dump_and_reload(self):
        original = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="deep thought", signature="sig_1"),
                TextBlock(text="result"),
            ],
        )

        data = original.model_dump()
        restored = Message(**data)

        assert len(restored.content) == 2
        assert restored.content[0].type == "thinking"
        assert restored.content[0].thinking == "deep thought"

    def test_api_format_preserves_thinking_for_next_turn(self):
        """Thinking blocks must be passed back in the next API request."""
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="internal reasoning", signature="sig_abc"),
                TextBlock(text="visible"),
            ],
        )
        api = msg.to_api_format()

        assert any(
            b["type"] == "thinking" and b["thinking"] == "internal reasoning"
            for b in api["content"]
        )
