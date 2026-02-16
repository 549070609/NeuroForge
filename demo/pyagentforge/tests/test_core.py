"""
核心引擎测试
"""

import pytest

from pyagentforge.core.context import ContextManager
from pyagentforge.core.message import (
    Message,
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)


class TestMessage:
    """消息测试"""

    def test_user_message(self) -> None:
        """测试创建用户消息"""
        msg = Message.user_message("Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_text(self) -> None:
        """测试创建助手文本消息"""
        msg = Message.assistant_text("Hi there")
        assert msg.role == "assistant"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)

    def test_to_api_format(self) -> None:
        """测试转换为 API 格式"""
        msg = Message.user_message("Test")
        api_format = msg.to_api_format()
        assert api_format["role"] == "user"
        assert api_format["content"] == "Test"


class TestProviderResponse:
    """提供商响应测试"""

    def test_text_extraction(self) -> None:
        """测试文本提取"""
        response = ProviderResponse(
            content=[
                TextBlock(text="Hello"),
                TextBlock(text="World"),
            ],
            stop_reason="end_turn",
        )
        assert response.text == "Hello\nWorld"

    def test_tool_calls_extraction(self) -> None:
        """测试工具调用提取"""
        response = ProviderResponse(
            content=[
                TextBlock(text="Let me help"),
                ToolUseBlock(id="1", name="bash", input={"command": "ls"}),
            ],
            stop_reason="tool_use",
        )
        assert len(response.tool_calls) == 1
        assert response.has_tool_calls is True


class TestContextManager:
    """上下文管理器测试"""

    def test_add_user_message(self) -> None:
        """测试添加用户消息"""
        ctx = ContextManager()
        ctx.add_user_message("Hello")
        assert len(ctx) == 1

    def test_add_tool_result(self) -> None:
        """测试添加工具结果"""
        ctx = ContextManager()
        ctx.add_user_message("Test")
        ctx.add_tool_result("tool-1", "result")
        assert len(ctx) == 2

    def test_truncate(self) -> None:
        """测试截断"""
        ctx = ContextManager(max_messages=5)
        for i in range(10):
            ctx.add_user_message(f"Message {i}")
        assert len(ctx) == 10
        removed = ctx.truncate(keep_last=5)
        assert removed == 5
        assert len(ctx) == 5

    def test_serialization(self) -> None:
        """测试序列化"""
        ctx = ContextManager()
        ctx.add_user_message("Test")
        ctx.mark_skill_loaded("test-skill")

        json_str = ctx.to_json()
        ctx2 = ContextManager.from_json(json_str)

        assert len(ctx2) == 1
        assert ctx2.is_skill_loaded("test-skill")
