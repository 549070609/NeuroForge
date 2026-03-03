"""
Deep verification tests for the LLM provider refactoring.

Tests cover:
  - ThinkingBlock in compaction (token estimation, summary extraction)
  - AnthropicProvider thinking block parsing (mock)
  - ContextManager add_assistant_message with ThinkingBlock
  - AgentExecutor new create_provider_from_config path (mock)
  - Message.to_api_format round-trip with ThinkingBlock
  - ProviderResponse property behavior with ThinkingBlock
"""

import warnings
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pyagentforge.kernel.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)


# ---------------------------------------------------------------------------
# 1. Compaction – ThinkingBlock 处理
# ---------------------------------------------------------------------------

class TestCompactionThinkingBlock:
    """Verify compaction module handles ThinkingBlock correctly."""

    def _make_compactor(self):
        from pyagentforge.plugins.middleware.compaction.compaction import Compactor
        provider = AsyncMock()
        return Compactor(provider=provider, max_context_tokens=200000)

    def test_estimate_tokens_text_only(self):
        c = self._make_compactor()
        msgs = [Message(role="user", content="Hello world")]
        tokens = c.estimate_tokens(msgs)
        assert tokens == len("Hello world") // 4

    def test_estimate_tokens_with_thinking_block(self):
        c = self._make_compactor()
        thinking_text = "Let me analyze this step by step..." * 10
        msgs = [
            Message(
                role="assistant",
                content=[
                    ThinkingBlock(thinking=thinking_text, signature="sig123"),
                    TextBlock(text="Here is my answer"),
                ],
            )
        ]
        tokens = c.estimate_tokens(msgs)
        expected = len(thinking_text) // 4 + len("Here is my answer") // 4
        assert tokens == expected

    def test_estimate_tokens_mixed_blocks(self):
        c = self._make_compactor()
        msgs = [
            Message(
                role="assistant",
                content=[
                    ThinkingBlock(thinking="deep thought"),
                    TextBlock(text="answer"),
                    ToolUseBlock(id="t1", name="bash", input={"cmd": "ls"}),
                ],
            )
        ]
        tokens = c.estimate_tokens(msgs)
        expected = (
            len("deep thought") // 4
            + len("answer") // 4
            + len("bash") // 4
            + len(str({"cmd": "ls"})) // 4
        )
        assert tokens == expected

    def test_extract_text_content_thinking_becomes_placeholder(self):
        c = self._make_compactor()
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="secret reasoning"),
                TextBlock(text="visible answer"),
            ],
        )
        text = c._extract_text_content(msg)
        assert "[thinking]" in text
        assert "secret reasoning" not in text
        assert "visible answer" in text

    def test_extract_text_content_only_thinking(self):
        c = self._make_compactor()
        msg = Message(
            role="assistant",
            content=[ThinkingBlock(thinking="only thinking")],
        )
        text = c._extract_text_content(msg)
        assert text == "[thinking]"

    def test_single_message_estimate_with_thinking(self):
        c = self._make_compactor()
        msg = Message(
            role="assistant",
            content=[ThinkingBlock(thinking="x" * 400)],
        )
        tokens = c._estimate_single_message(msg)
        assert tokens == 100  # 400 chars / 4


# ---------------------------------------------------------------------------
# 2. AnthropicProvider thinking 块解析 (mock)
# ---------------------------------------------------------------------------

class TestAnthropicProviderThinkingParsing:
    """Verify AnthropicProvider correctly parses thinking blocks from API response."""

    @pytest.fixture
    def provider(self):
        with patch("pyagentforge.providers.anthropic_provider.AsyncAnthropic"):
            from pyagentforge.providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")

    @pytest.mark.asyncio
    async def test_create_message_parses_thinking_block(self, provider):
        """Simulate API response with a thinking block."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "Let me think about this..."
        thinking_block.signature = "abc123"

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Here is my response"

        mock_response = MagicMock()
        mock_response.content = [thinking_block, text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.create_message(
            system="test",
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
        )

        assert isinstance(result, ProviderResponse)
        assert len(result.content) == 2

        tb = result.content[0]
        assert isinstance(tb, ThinkingBlock)
        assert tb.thinking == "Let me think about this..."
        assert tb.signature == "abc123"

        assert isinstance(result.content[1], TextBlock)
        assert result.content[1].text == "Here is my response"

    @pytest.mark.asyncio
    async def test_create_message_thinking_not_in_text_property(self, provider):
        """Thinking block content should NOT appear in .text property."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "secret thought"
        thinking_block.signature = None

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "visible"

        mock_response = MagicMock()
        mock_response.content = [thinking_block, text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.create_message(
            system="test",
            messages=[{"role": "user", "content": "Hi"}],
            tools=[],
        )

        assert result.text == "visible"
        assert "secret thought" not in (result.text or "")

    @pytest.mark.asyncio
    async def test_create_message_thinking_not_in_tool_calls(self, provider):
        """Thinking block should not appear in .tool_calls."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "reasoning"
        thinking_block.signature = None

        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.id = "t1"
        tool_block.name = "bash"
        tool_block.input = {"command": "ls"}

        mock_response = MagicMock()
        mock_response.content = [thinking_block, tool_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 5

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.create_message(
            system="test",
            messages=[{"role": "user", "content": "do it"}],
            tools=[],
        )

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "bash"
        assert result.has_tool_calls

    @pytest.mark.asyncio
    async def test_create_message_only_thinking_and_text(self, provider):
        """Response with only thinking + text, no tool calls."""
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        thinking_block.thinking = "deep analysis" * 50
        thinking_block.signature = "sig_long"

        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Final answer"

        mock_response = MagicMock()
        mock_response.content = [thinking_block, text_block]
        mock_response.stop_reason = "end_turn"
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100

        provider.client.messages.create = AsyncMock(return_value=mock_response)

        result = await provider.create_message(
            system="test",
            messages=[{"role": "user", "content": "analyze"}],
            tools=[],
        )

        assert not result.has_tool_calls
        assert result.text == "Final answer"
        assert result.content[0].signature == "sig_long"


# ---------------------------------------------------------------------------
# 3. ContextManager add_assistant_message with ThinkingBlock
# ---------------------------------------------------------------------------

class TestContextManagerThinkingBlock:
    """Verify ContextManager correctly stores ThinkingBlock in conversation history."""

    def _make_ctx(self):
        from pyagentforge.kernel.context import ContextManager
        return ContextManager()

    def test_add_assistant_message_with_thinking(self):
        ctx = self._make_ctx()
        ctx.add_assistant_message([
            ThinkingBlock(thinking="my reasoning", signature="sig1"),
            TextBlock(text="my answer"),
        ])
        assert len(ctx) == 1
        msg = ctx.messages[0]
        assert msg.role == "assistant"
        assert isinstance(msg.content, list)
        types = [getattr(b, "type", None) for b in msg.content]
        assert "thinking" in types
        assert "text" in types

    def test_thinking_block_signature_preserved(self):
        ctx = self._make_ctx()
        ctx.add_assistant_message([
            ThinkingBlock(thinking="t", signature="keep_me"),
        ])
        blocks = ctx.messages[0].content
        tb = next(b for b in blocks if getattr(b, "type", None) == "thinking")
        assert tb.signature == "keep_me"

    def test_thinking_block_no_signature(self):
        ctx = self._make_ctx()
        ctx.add_assistant_message([
            ThinkingBlock(thinking="t"),
        ])
        blocks = ctx.messages[0].content
        tb = next(b for b in blocks if getattr(b, "type", None) == "thinking")
        assert tb.signature is None

    def test_multi_turn_with_thinking(self):
        ctx = self._make_ctx()
        ctx.add_user_message("hello")
        ctx.add_assistant_message([
            ThinkingBlock(thinking="first thought"),
            TextBlock(text="first reply"),
        ])
        ctx.add_user_message("follow up")
        ctx.add_assistant_message([
            ThinkingBlock(thinking="second thought"),
            TextBlock(text="second reply"),
        ])
        assert len(ctx) == 4

    def test_api_format_includes_thinking(self):
        ctx = self._make_ctx()
        ctx.add_assistant_message([
            ThinkingBlock(thinking="r", signature="s"),
            TextBlock(text="a"),
        ])
        api_msgs = ctx.get_messages_for_api()
        assert len(api_msgs) == 1
        blocks = api_msgs[0]["content"]
        types = [b["type"] for b in blocks]
        assert "thinking" in types
        assert "text" in types


# ---------------------------------------------------------------------------
# 4. Message.to_api_format ThinkingBlock serialization
# ---------------------------------------------------------------------------

class TestMessageToApiFormatThinking:
    """Verify Message.to_api_format correctly serializes ThinkingBlock."""

    def test_thinking_without_signature(self):
        msg = Message(
            role="assistant",
            content=[ThinkingBlock(thinking="my thought")],
        )
        api = msg.to_api_format()
        blocks = api["content"]
        assert len(blocks) == 1
        assert blocks[0]["type"] == "thinking"
        assert blocks[0]["thinking"] == "my thought"
        assert "signature" not in blocks[0]

    def test_thinking_with_signature(self):
        msg = Message(
            role="assistant",
            content=[ThinkingBlock(thinking="thought", signature="sig123")],
        )
        api = msg.to_api_format()
        blocks = api["content"]
        assert blocks[0]["signature"] == "sig123"

    def test_mixed_thinking_text_tool(self):
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="t", signature="s"),
                TextBlock(text="answer"),
                ToolUseBlock(id="call_1", name="read", input={"path": "/a"}),
            ],
        )
        api = msg.to_api_format()
        blocks = api["content"]
        assert len(blocks) == 3
        assert blocks[0]["type"] == "thinking"
        assert blocks[1]["type"] == "text"
        assert blocks[2]["type"] == "tool_use"

    def test_thinking_round_trip_dict(self):
        """Serialized thinking block can be used as API input for next turn."""
        msg = Message(
            role="assistant",
            content=[
                ThinkingBlock(thinking="reasoning", signature="sig_abc"),
                TextBlock(text="answer text"),
            ],
        )
        api = msg.to_api_format()

        thinking_dict = api["content"][0]
        assert thinking_dict == {
            "type": "thinking",
            "thinking": "reasoning",
            "signature": "sig_abc",
        }


# ---------------------------------------------------------------------------
# 5. ProviderResponse property behavior with ThinkingBlock
# ---------------------------------------------------------------------------

class TestProviderResponseThinkingProperties:
    """Verify ProviderResponse .text, .tool_calls, .has_tool_calls with ThinkingBlock."""

    def test_text_ignores_thinking(self):
        resp = ProviderResponse(
            content=[
                ThinkingBlock(thinking="hidden"),
                TextBlock(text="visible"),
            ],
            stop_reason="end_turn",
        )
        assert resp.text == "visible"

    def test_text_only_thinking_returns_empty(self):
        resp = ProviderResponse(
            content=[ThinkingBlock(thinking="only thinking")],
            stop_reason="end_turn",
        )
        assert resp.text == ""

    def test_tool_calls_ignores_thinking(self):
        resp = ProviderResponse(
            content=[
                ThinkingBlock(thinking="reason"),
                ToolUseBlock(id="t1", name="bash", input={}),
            ],
            stop_reason="tool_use",
        )
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "bash"

    def test_has_tool_calls_with_thinking_only(self):
        resp = ProviderResponse(
            content=[ThinkingBlock(thinking="just thinking")],
            stop_reason="end_turn",
        )
        assert not resp.has_tool_calls

    def test_content_preserves_all_blocks(self):
        resp = ProviderResponse(
            content=[
                ThinkingBlock(thinking="t1"),
                TextBlock(text="t2"),
                ToolUseBlock(id="u1", name="n1", input={}),
            ],
            stop_reason="end_turn",
        )
        assert len(resp.content) == 3
        types = [type(b).__name__ for b in resp.content]
        assert types == ["ThinkingBlock", "TextBlock", "ToolUseBlock"]


# ---------------------------------------------------------------------------
# 6. create_provider_from_config factory path
# ---------------------------------------------------------------------------

class TestCreateProviderFromConfigBehavior:
    """Verify the new factory path works end-to-end."""

    def test_does_not_touch_registry(self):
        from pyagentforge.kernel.model_registry import ModelConfig, ModelRegistry, ProviderType
        from pyagentforge.providers.factory import ModelAdapterFactory

        registry = MagicMock(spec=ModelRegistry)
        config = ModelConfig(
            id="claude-sonnet-4-20250514",
            name="Claude Sonnet 4",
            provider=ProviderType.ANTHROPIC,
            api_type="anthropic-messages",
            api_key_env="ANTHROPIC_API_KEY",
            context_window=200000,
            max_output_tokens=8192,
        )

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            factory = ModelAdapterFactory(registry=registry)
            provider = factory.create_provider_from_config(config)

        registry.get_model.assert_not_called()
        from pyagentforge.providers.anthropic_provider import AnthropicProvider
        assert isinstance(provider, AnthropicProvider)

    def test_legacy_create_provider_warns(self):
        from pyagentforge.providers.factory import create_provider

        with patch("pyagentforge.providers.factory.get_factory") as mock:
            mock.return_value = MagicMock()
            with pytest.warns(DeprecationWarning, match="create_provider_from_config"):
                create_provider("gpt-4")

    def test_convenience_function_delegates(self):
        from pyagentforge.kernel.model_registry import ModelConfig, ProviderType
        from pyagentforge.providers.factory import create_provider_from_config

        config = ModelConfig(
            id="test",
            name="Test",
            provider=ProviderType.OPENAI,
            api_type="openai-completions",
            context_window=100,
            max_output_tokens=100,
        )

        with patch("pyagentforge.providers.factory.get_factory") as mock_gf:
            mock_factory = MagicMock()
            mock_gf.return_value = mock_factory

            create_provider_from_config(config, temperature=0.5)

            mock_factory.create_provider_from_config.assert_called_once_with(
                config, temperature=0.5,
            )


# ---------------------------------------------------------------------------
# 7. ThinkingBlock re-export compatibility
# ---------------------------------------------------------------------------

class TestThinkingBlockCompatibility:
    """Verify ThinkingBlock is the same class regardless of import path."""

    def test_all_paths_same_class(self):
        from pyagentforge.kernel.message import ThinkingBlock as TB1
        from pyagentforge.kernel import ThinkingBlock as TB2
        from pyagentforge import ThinkingBlock as TB3
        from pyagentforge.plugins.middleware.thinking.thinking import ThinkingBlock as TB4

        assert TB1 is TB2 is TB3 is TB4

    def test_instance_cross_path(self):
        from pyagentforge.kernel.message import ThinkingBlock as TB1
        from pyagentforge.plugins.middleware.thinking.thinking import ThinkingBlock as TB2

        obj = TB1(thinking="test")
        assert isinstance(obj, TB2)

        obj2 = TB2(thinking="test2", signature="s")
        assert isinstance(obj2, TB1)
