"""
基础功能测试

测试 PyAgentForge 的核心功能：消息、上下文、引擎
"""

import pytest
from pathlib import Path

from pyagentforge.core.message import Message, TextBlock, ToolUseBlock
from pyagentforge.core.context import ContextManager


# ============ 消息测试 ============

@pytest.mark.basic
@pytest.mark.asyncio
class TestBasicConversation:
    """基础对话测试"""

    async def test_simple_question(self, agent_engine):
        """测试简单问题"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "你好，请自我介绍一下。"
        )

        assert response is not None
        assert len(response) > 0
        assert "助手" in response or "AI" in response or "assistant" in response.lower()

    async def test_math_calculation(self, agent_engine):
        """测试数学计算"""
        check_api_key()

        response = await run_agent_with_timeout(
            agent_engine,
            "请计算 123 + 456 等于多少？"
        )

        assert response is not None
        assert "579" in response

    async def test_context_awareness(self, agent_engine):
        """测试上下文感知"""
        check_api_key()

        # 第一轮对话
        response1 = await run_agent_with_timeout(
            agent_engine,
            "我的名字叫张三。"
        )
        assert response1 is not None

        # 第二轮对话，测试是否记住名字
        response2 = await run_agent_with_timeout(
            agent_engine,
            "你还记得我的名字吗？"
        )

        assert response2 is not None
        assert "张三" in response2

    async def test_multi_turn_conversation(self, agent_engine):
        """测试多轮对话"""
        check_api_key()

        questions = [
            "请记住数字 42。",
            "刚才我让你记住的数字是什么？",
            "这个数字乘以 2 等于多少？"
        ]

        for question in questions:
            response = await run_agent_with_timeout(agent_engine, question)
            assert response is not None
            assert len(response) > 0

        # 验证最后一个答案
        assert "84" in response


# ============ 系统提示词测试 ============

@pytest.mark.basic
@pytest.mark.asyncio
class TestSystemPrompt:
    """系统提示词测试"""

    async def test_custom_system_prompt(self, glm_provider, tool_registry):
        """测试自定义系统提示词"""
        check_api_key()

        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine

        config = AgentConfig(
            system_prompt="你是一个专业的 Python 开发专家。回答问题时总是以 '作为 Python 专家...' 开头。"
        )

        engine = AgentEngine(
            provider=glm_provider,
            tool_registry=tool_registry,
            config=config,
        )

        response = await run_agent_with_timeout(
            engine,
            "什么是列表推导式？"
        )

        assert response is not None
        assert "Python" in response

    async def test_role_playing(self, glm_provider, tool_registry):
        """测试角色扮演"""
        check_api_key()

        from pyagentforge.agents.config import AgentConfig
        from pyagentforge.core.engine import AgentEngine

        config = AgentConfig(
            system_prompt="你是一个友好的机器人助手，名字叫 Robo。总是用 🤖 开头。"
        )

        engine = AgentEngine(
            provider=glm_provider,
            tool_registry=tool_registry,
            config=config,
        )

        response = await run_agent_with_timeout(
            engine,
            "你好！"
        )

        assert response is not None


# ============ 上下文管理测试 ============

@pytest.mark.basic
class TestContextManager:
    """上下文管理器测试"""

    def test_add_messages(self):
        """测试添加消息"""
        ctx = ContextManager()

        ctx.add_user_message("你好")
        ctx.add_assistant_message("你好！")

        assert len(ctx) == 2

    def test_context_truncation(self):
        """测试上下文截断"""
        ctx = ContextManager(max_messages=10)

        # 添加 15 条消息
        for i in range(15):
            ctx.add_user_message(f"消息 {i}")

        assert len(ctx) == 15

        # 截断保留最后 10 条
        removed = ctx.truncate(keep_last=10)
        assert removed == 5
        assert len(ctx) == 10

    def test_context_serialization(self):
        """测试上下文序列化"""
        ctx = ContextManager()
        ctx.add_user_message("测试")
        ctx.add_assistant_message("收到")
        ctx.mark_skill_loaded("test-skill")

        # 序列化
        json_str = ctx.to_json()

        # 反序列化
        ctx2 = ContextManager.from_json(json_str)

        assert len(ctx2) == 2
        assert ctx2.is_skill_loaded("test-skill")

    def test_tool_result_tracking(self):
        """测试工具结果跟踪"""
        ctx = ContextManager()
        ctx.add_user_message("执行命令")
        ctx.add_tool_result("tool-1", "命令执行成功")

        assert len(ctx) == 2

        messages = ctx.get_messages_for_api()
        assert any("命令执行成功" in str(msg) for msg in messages)


# ============ 消息格式测试 ============

@pytest.mark.basic
class TestMessageFormat:
    """消息格式测试"""

    def test_user_message_creation(self):
        """测试用户消息创建"""
        msg = Message.user_message("Hello")

        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_assistant_message_with_text(self):
        """测试助手消息（文本）"""
        msg = Message.assistant_text("Hi there")

        assert msg.role == "assistant"
        assert len(msg.content) == 1
        assert isinstance(msg.content[0], TextBlock)
        assert msg.content[0].text == "Hi there"

    def test_assistant_message_with_tool_use(self):
        """测试助手消息（工具调用）"""
        msg = Message.assistant_tool_calls(
            tool_calls=[
                ToolUseBlock(id="1", name="bash", input={"command": "ls"})
            ]
        )

        assert msg.role == "assistant"
        assert len(msg.content) == 1

    def test_message_to_api_format(self):
        """测试消息转换为 API 格式"""
        msg = Message.user_message("Test message")
        api_format = msg.to_api_format()

        assert api_format["role"] == "user"
        assert api_format["content"] == "Test message"


# ============ 导入辅助函数 ============

from conftest import check_api_key, run_agent_with_timeout
