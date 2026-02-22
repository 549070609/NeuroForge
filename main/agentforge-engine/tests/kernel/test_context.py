"""
Tests for ContextManager class

Comprehensive tests for context management, message handling, and state persistence.
"""

import json
import pytest

from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.message import (
    Message,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
)


class TestContextManagerAddMessages:
    """Tests for adding messages."""

    @pytest.fixture
    def context(self) -> ContextManager:
        """Create a context manager."""
        return ContextManager(max_messages=100)

    def test_add_user_message_increases_count(self, context: ContextManager):
        """Test that adding user messages increases message count."""
        assert len(context) == 0

        context.add_user_message("Hello")
        assert len(context) == 1

        context.add_user_message("World")
        assert len(context) == 2

    def test_add_assistant_text(self, context: ContextManager):
        """Test adding assistant text message."""
        context.add_assistant_text("Hello back!")

        assert len(context) == 1
        messages = context.get_messages_for_api()
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"][0]["text"] == "Hello back!"

    def test_add_assistant_message_with_blocks(self, context: ContextManager):
        """Test adding assistant message with content blocks."""
        blocks = [
            TextBlock(text="Here's the result:"),
            ToolUseBlock(id="tool_1", name="read", input={"file_path": "/test"}),
        ]
        context.add_assistant_message(blocks)

        assert len(context) == 1
        messages = context.get_messages_for_api()
        assert messages[0]["role"] == "assistant"
        assert len(messages[0]["content"]) == 2


class TestContextManagerToolResults:
    """Tests for tool result handling."""

    @pytest.fixture
    def context(self) -> ContextManager:
        """Create a context manager."""
        return ContextManager()

    def test_add_tool_result_preserves_order(self, context: ContextManager):
        """Test that tool results are added in order."""
        context.add_user_message("Use tool")
        context.add_assistant_message([
            ToolUseBlock(id="tool_1", name="read", input={}),
            ToolUseBlock(id="tool_2", name="write", input={}),
        ])

        context.add_tool_result("tool_1", "Result 1")
        context.add_tool_result("tool_2", "Result 2")

        messages = context.get_messages_for_api()

        # Find tool result messages
        tool_results = [
            msg for msg in messages
            if msg["role"] == "user" and isinstance(msg["content"], list)
        ]

        assert len(tool_results) == 2

    def test_add_tool_result_with_error(self, context: ContextManager):
        """Test adding error tool result."""
        context.add_tool_result("tool_1", "Error occurred", is_error=True)

        assert len(context) == 1
        messages = context.get_messages_for_api()
        assert messages[0]["content"][0]["is_error"] is True

    def test_add_tool_result_without_error(self, context: ContextManager):
        """Test adding successful tool result."""
        context.add_tool_result("tool_1", "Success", is_error=False)

        messages = context.get_messages_for_api()
        assert messages[0]["content"][0]["is_error"] is False


class TestContextManagerTruncation:
    """Tests for context truncation."""

    def test_truncate_removes_oldest_messages(self):
        """Test that truncate removes oldest messages."""
        context = ContextManager(max_messages=5)

        # Add 10 messages
        for i in range(10):
            context.add_user_message(f"Message {i}")

        assert len(context) == 10

        # Truncate to 5
        removed = context.truncate(keep_last=5)

        assert removed == 5
        assert len(context) == 5

        # Verify newest messages are kept
        messages = context.get_messages_for_api()
        assert "Message 5" in messages[0]["content"]
        assert "Message 9" in messages[-1]["content"]

    def test_truncate_with_no_excess(self):
        """Test truncate when no truncation needed."""
        context = ContextManager(max_messages=10)

        for i in range(5):
            context.add_user_message(f"Message {i}")

        removed = context.truncate()

        assert removed == 0
        assert len(context) == 5

    def test_truncate_with_custom_keep_last(self):
        """Test truncate with custom keep_last value."""
        context = ContextManager(max_messages=100)

        for i in range(20):
            context.add_user_message(f"Message {i}")

        removed = context.truncate(keep_last=10)

        assert removed == 10
        assert len(context) == 10

    def test_truncate_keeps_last_n_messages(self):
        """Test that truncate properly keeps the last N messages."""
        context = ContextManager(max_messages=5)

        for i in range(8):
            context.add_user_message(f"Message {i}")

        context.truncate(keep_last=5)

        messages = context.get_messages_for_api()
        assert len(messages) == 5
        # First message should be "Message 3" (index 3)
        assert "Message 3" in messages[0]["content"]
        # Last message should be "Message 7"
        assert "Message 7" in messages[-1]["content"]


class TestContextManagerSerialization:
    """Tests for serialization and deserialization."""

    @pytest.fixture
    def context_with_data(self) -> ContextManager:
        """Create a context manager with data."""
        context = ContextManager(
            max_messages=100,
            system_prompt="Test prompt"
        )
        context.add_user_message("Hello")
        context.add_assistant_text("Hi there!")
        context.mark_skill_loaded("skill_1")
        context.mark_skill_loaded("skill_2")
        return context

    def test_serialize_deserialize_preserves_state(
        self, context_with_data: ContextManager
    ):
        """Test that serialize/deserialize preserves state."""
        # Serialize
        data = context_with_data.to_dict()

        # Deserialize
        restored = ContextManager.from_dict(data)

        assert len(restored) == len(context_with_data)
        assert restored.system_prompt == context_with_data.system_prompt
        assert restored.get_loaded_skills() == context_with_data.get_loaded_skills()

        # Check messages are preserved
        original_messages = context_with_data.get_messages_for_api()
        restored_messages = restored.get_messages_for_api()
        assert len(original_messages) == len(restored_messages)

    def test_to_json_from_json(self, context_with_data: ContextManager):
        """Test JSON serialization."""
        json_str = context_with_data.to_json()

        assert isinstance(json_str, str)

        restored = ContextManager.from_json(json_str)

        assert len(restored) == len(context_with_data)
        assert restored.system_prompt == context_with_data.system_prompt

    def test_serialize_empty_context(self):
        """Test serializing empty context."""
        context = ContextManager()
        data = context.to_dict()

        assert data["messages"] == []
        assert data["loaded_skills"] == []

    def test_deserialize_with_missing_fields(self):
        """Test deserializing with missing fields."""
        data = {"messages": []}
        context = ContextManager.from_dict(data)

        assert len(context) == 0
        assert context.system_prompt is None
        assert len(context.get_loaded_skills()) == 0

    def test_serialize_with_tool_results(self):
        """Test serialization with tool results."""
        context = ContextManager()
        context.add_user_message("Use tool")
        context.add_assistant_message([
            TextBlock(text="Using tool"),
            ToolUseBlock(id="tool_1", name="read", input={"file_path": "/test"}),
        ])
        context.add_tool_result("tool_1", "File content")

        data = context.to_dict()
        restored = ContextManager.from_dict(data)

        assert len(restored) == 3
        restored_messages = restored.get_messages_for_api()
        assert len(restored_messages) == 3


class TestContextManagerSkillTracking:
    """Tests for skill tracking."""

    @pytest.fixture
    def context(self) -> ContextManager:
        """Create a context manager."""
        return ContextManager()

    def test_skill_tracking_prevents_reload(self, context: ContextManager):
        """Test that skill tracking prevents reloading skills."""
        # Initially not loaded
        assert not context.is_skill_loaded("skill_1")

        # Mark as loaded
        context.mark_skill_loaded("skill_1")
        assert context.is_skill_loaded("skill_1")

        # Mark again (idempotent)
        context.mark_skill_loaded("skill_1")
        assert context.is_skill_loaded("skill_1")

        # Check loaded skills
        skills = context.get_loaded_skills()
        assert "skill_1" in skills

    def test_multiple_skills(self, context: ContextManager):
        """Test tracking multiple skills."""
        context.mark_skill_loaded("skill_1")
        context.mark_skill_loaded("skill_2")
        context.mark_skill_loaded("skill_3")

        skills = context.get_loaded_skills()
        assert len(skills) == 3
        assert "skill_1" in skills
        assert "skill_2" in skills
        assert "skill_3" in skills

    def test_clear_clears_skills(self, context: ContextManager):
        """Test that clear also clears loaded skills."""
        context.mark_skill_loaded("skill_1")
        context.mark_skill_loaded("skill_2")

        context.clear()

        assert len(context.get_loaded_skills()) == 0
        assert not context.is_skill_loaded("skill_1")
        assert not context.is_skill_loaded("skill_2")


class TestContextManagerAPIFormat:
    """Tests for API format conversion."""

    @pytest.fixture
    def context(self) -> ContextManager:
        """Create a context manager."""
        return ContextManager()

    def test_get_messages_for_api_formats_correctly(self, context: ContextManager):
        """Test that get_messages_for_api formats messages correctly."""
        context.add_user_message("Hello")
        context.add_assistant_text("Hi!")

        messages = context.get_messages_for_api()

        assert isinstance(messages, list)
        assert len(messages) == 2

        # User message
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

        # Assistant message
        assert messages[1]["role"] == "assistant"
        assert isinstance(messages[1]["content"], list)

    def test_api_format_with_tool_calls(self, context: ContextManager):
        """Test API format with tool calls."""
        context.add_assistant_message([
            TextBlock(text="Using tool"),
            ToolUseBlock(id="tool_1", name="read", input={"file_path": "/test"}),
        ])

        messages = context.get_messages_for_api()

        assert messages[0]["role"] == "assistant"
        content = messages[0]["content"]
        assert len(content) == 2

        # Text block
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Using tool"

        # Tool use block
        assert content[1]["type"] == "tool_use"
        assert content[1]["name"] == "read"
        assert content[1]["input"] == {"file_path": "/test"}

    def test_api_format_with_tool_result(self, context: ContextManager):
        """Test API format with tool result."""
        context.add_tool_result("tool_1", "Result content")

        messages = context.get_messages_for_api()

        assert messages[0]["role"] == "user"
        content = messages[0]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "tool_result"
        assert content[0]["tool_use_id"] == "tool_1"
        assert content[0]["content"] == "Result content"


class TestContextManagerClear:
    """Tests for clear functionality."""

    def test_clear_removes_all_messages(self):
        """Test that clear removes all messages."""
        context = ContextManager()

        for i in range(10):
            context.add_user_message(f"Message {i}")

        assert len(context) == 10

        context.clear()

        assert len(context) == 0


class TestContextManagerLength:
    """Tests for length operations."""

    def test_len_returns_message_count(self):
        """Test that __len__ returns message count."""
        context = ContextManager()

        assert len(context) == 0

        context.add_user_message("One")
        assert len(context) == 1

        context.add_assistant_text("Two")
        assert len(context) == 2


class TestContextManagerRepr:
    """Tests for string representation."""

    def test_repr_shows_message_count(self):
        """Test that __repr__ shows message count."""
        context = ContextManager()

        repr_str = repr(context)
        assert "messages=0" in repr_str

        context.add_user_message("Test")
        repr_str = repr(context)
        assert "messages=1" in repr_str

    def test_repr_shows_skill_count(self):
        """Test that __repr__ shows skill count."""
        context = ContextManager()
        context.mark_skill_loaded("skill_1")

        repr_str = repr(context)
        assert "skills=1" in repr_str


class TestContextManagerEdgeCases:
    """Tests for edge cases."""

    def test_empty_context_messages(self):
        """Test getting messages from empty context."""
        context = ContextManager()
        messages = context.get_messages_for_api()

        assert messages == []

    def test_large_message_count(self):
        """Test handling large number of messages."""
        context = ContextManager(max_messages=1000)

        for i in range(500):
            context.add_user_message(f"Message {i}")

        assert len(context) == 500

        messages = context.get_messages_for_api()
        assert len(messages) == 500

    def test_truncate_to_zero(self):
        """Test truncating to zero messages."""
        context = ContextManager()

        for i in range(10):
            context.add_user_message(f"Message {i}")

        removed = context.truncate(keep_last=0)

        assert removed == 10
        assert len(context) == 0

    def test_message_preservation_order(self):
        """Test that messages are preserved in correct order."""
        context = ContextManager()

        context.add_user_message("First")
        context.add_user_message("Second")
        context.add_user_message("Third")

        messages = context.get_messages_for_api()

        assert messages[0]["content"] == "First"
        assert messages[1]["content"] == "Second"
        assert messages[2]["content"] == "Third"

    def test_system_prompt_preserved_in_serialization(self):
        """Test that system prompt is preserved during serialization."""
        context = ContextManager(system_prompt="Custom system prompt")
        context.add_user_message("Hello")

        data = context.to_dict()
        assert data["system_prompt"] == "Custom system prompt"

        restored = ContextManager.from_dict(data)
        assert restored.system_prompt == "Custom system prompt"

    def test_context_with_none_system_prompt(self):
        """Test context with None system prompt."""
        context = ContextManager(system_prompt=None)

        data = context.to_dict()
        restored = ContextManager.from_dict(data)

        assert restored.system_prompt is None


class TestContextManagerMessageTypes:
    """Tests for different message types."""

    def test_user_message_creation(self):
        """Test user message creation."""
        msg = Message.user_message("Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_text_creation(self):
        """Test assistant text message creation."""
        msg = Message.assistant_text("Response")

        assert msg.role == "assistant"
        assert isinstance(msg.content, list)
        assert msg.content[0].text == "Response"

    def test_tool_result_creation(self):
        """Test tool result message creation."""
        msg = Message.tool_result("tool_123", "Result", is_error=False)

        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert msg.content[0].tool_use_id == "tool_123"
        assert msg.content[0].content == "Result"
        assert msg.content[0].is_error is False


class TestContextManagerMaxMessages:
    """Tests for max_messages configuration."""

    def test_max_messages_default(self):
        """Test default max_messages value."""
        context = ContextManager()
        assert context.max_messages == 100

    def test_max_messages_custom(self):
        """Test custom max_messages value."""
        context = ContextManager(max_messages=50)
        assert context.max_messages == 50

    def test_max_messages_used_in_truncation(self):
        """Test that max_messages is used in default truncation."""
        context = ContextManager(max_messages=5)

        for i in range(10):
            context.add_user_message(f"Message {i}")

        # Truncate without argument should use max_messages
        removed = context.truncate()

        assert len(context) == 5
        assert removed == 5
