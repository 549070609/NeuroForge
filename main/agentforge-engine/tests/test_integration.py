"""
集成测试 - 使用真实 LLM API

这些测试需要真实的 API Key，通过环境变量配置：
- ANTHROPIC_API_KEY
- OPENAI_API_KEY
- GOOGLE_API_KEY (或 GEMINI_API_KEY)

运行方式：
    pytest tests/test_integration.py -v -m integration
    pytest tests/test_integration.py -v -m "integration and anthropic"
    pytest tests/test_integration.py -v -m "integration and openai"
    pytest tests/test_integration.py -v -m "integration and google"
"""

import os

import pytest

from pyagentforge import LLMClient
from pyagentforge.kernel.message import ProviderResponse


# 检查 API Key 是否可用
def has_anthropic_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def has_openai_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def has_google_key() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


@pytest.fixture
def llm_client():
    """创建 LLM 客户端"""
    return LLMClient()


# ============================================================================
# Anthropic (Claude) 集成测试
# ============================================================================


@pytest.mark.integration
@pytest.mark.anthropic
@pytest.mark.skipif(not has_anthropic_key(), reason="需要 ANTHROPIC_API_KEY")
class TestAnthropicIntegration:
    """Anthropic Claude 真实 API 测试"""

    @pytest.mark.asyncio
    async def test_simple_message(self, llm_client):
        """测试简单消息调用"""
        response = await llm_client.create_message(
            model_id="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Say 'Hello, World!' and nothing else."}],
            max_tokens=100,
        )

        assert response is not None
        assert isinstance(response, ProviderResponse)
        assert response.text is not None
        assert len(response.text) > 0
        assert response.stop_reason in ["end_turn", "max_tokens"]
        assert response.usage["input_tokens"] > 0
        assert response.usage["output_tokens"] > 0
        print(f"\n✅ Claude Response: {response.text}")

    @pytest.mark.asyncio
    async def test_system_prompt(self, llm_client):
        """测试系统提示"""
        response = await llm_client.create_message(
            model_id="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "What is your name?"}],
            system="You are a helpful assistant named TestBot.",
            max_tokens=100,
        )

        assert response is not None
        assert "TestBot" in response.text or "test" in response.text.lower()
        print(f"\n✅ Claude with System: {response.text}")

    @pytest.mark.asyncio
    async def test_tool_use(self, llm_client):
        """测试工具调用"""
        tools = [
            {
                "name": "get_weather",
                "description": "Get the current weather in a location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "The unit of temperature",
                        },
                    },
                    "required": ["location"],
                },
            }
        ]

        response = await llm_client.create_message(
            model_id="claude-sonnet-4-20250514",
            messages=[
                {"role": "user", "content": "What's the weather like in San Francisco?"}
            ],
            tools=tools,
            max_tokens=500,
        )

        assert response is not None
        assert response.has_tool_calls
        assert len(response.tool_calls) > 0
        assert response.tool_calls[0].name == "get_weather"
        assert "location" in response.tool_calls[0].input
        print(f"\n✅ Claude Tool Call: {response.tool_calls[0].name}({response.tool_calls[0].input})")

    @pytest.mark.asyncio
    async def test_streaming(self, llm_client):
        """测试流式响应"""
        chunks = []
        final_response = None

        async for chunk in llm_client.stream_message(
            model_id="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Count from 1 to 5."}],
            max_tokens=100,
        ):
            if isinstance(chunk, ProviderResponse):
                final_response = chunk
            else:
                chunks.append(chunk)

        assert len(chunks) > 0
        assert final_response is not None
        assert final_response.text is not None
        print(f"\n✅ Claude Streaming: {len(chunks)} chunks, final: {final_response.text}")

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, llm_client):
        """测试多轮对话"""
        messages = [
            {"role": "user", "content": "My name is Alice."},
            {"role": "assistant", "content": "Nice to meet you, Alice!"},
            {"role": "user", "content": "What's my name?"},
        ]

        response = await llm_client.create_message(
            model_id="claude-sonnet-4-20250514",
            messages=messages,
            max_tokens=100,
        )

        assert response is not None
        assert "Alice" in response.text
        print(f"\n✅ Claude Multi-turn: {response.text}")

    @pytest.mark.asyncio
    async def test_count_tokens(self, llm_client):
        """测试 Token 计数"""
        messages = [
            {"role": "user", "content": "Hello, how are you today?"},
        ]

        count = await llm_client.count_tokens(
            model_id="claude-sonnet-4-20250514",
            messages=messages,
        )

        assert count > 0
        print(f"\n✅ Claude Token Count: {count}")


# ============================================================================
# OpenAI (GPT) 集成测试
# ============================================================================


@pytest.mark.integration
@pytest.mark.openai
@pytest.mark.skipif(not has_openai_key(), reason="需要 OPENAI_API_KEY")
class TestOpenAIIntegration:
    """OpenAI GPT 真实 API 测试"""

    @pytest.mark.asyncio
    async def test_simple_message(self, llm_client):
        """测试简单消息调用"""
        response = await llm_client.create_message(
            model_id="gpt-4o",
            messages=[{"role": "user", "content": "Say 'Hello, World!' and nothing else."}],
            max_tokens=100,
        )

        assert response is not None
        assert isinstance(response, ProviderResponse)
        assert response.text is not None
        assert len(response.text) > 0
        assert response.stop_reason in ["end_turn", "max_tokens", "stop"]
        print(f"\n✅ GPT Response: {response.text}")

    @pytest.mark.asyncio
    async def test_system_prompt(self, llm_client):
        """测试系统提示"""
        response = await llm_client.create_message(
            model_id="gpt-4o",
            messages=[{"role": "user", "content": "What is your name?"}],
            system="You are a helpful assistant named GPT-TestBot.",
            max_tokens=100,
        )

        assert response is not None
        assert "GPT" in response.text or "TestBot" in response.text
        print(f"\n✅ GPT with System: {response.text}")

    @pytest.mark.asyncio
    async def test_tool_use(self, llm_client):
        """测试工具调用"""
        tools = [
            {
                "name": "calculate_sum",
                "description": "Calculate the sum of two numbers",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"},
                    },
                    "required": ["a", "b"],
                },
            }
        ]

        response = await llm_client.create_message(
            model_id="gpt-4o",
            messages=[{"role": "user", "content": "What is 25 + 17?"}],
            tools=tools,
            max_tokens=500,
        )

        assert response is not None
        assert response.has_tool_calls
        assert len(response.tool_calls) > 0
        assert response.tool_calls[0].name == "calculate_sum"
        print(f"\n✅ GPT Tool Call: {response.tool_calls[0].name}({response.tool_calls[0].input})")

    @pytest.mark.asyncio
    async def test_streaming(self, llm_client):
        """测试流式响应"""
        chunks = []
        final_response = None

        async for chunk in llm_client.stream_message(
            model_id="gpt-4o",
            messages=[{"role": "user", "content": "Count from 1 to 5."}],
            max_tokens=100,
        ):
            if isinstance(chunk, ProviderResponse):
                final_response = chunk
            else:
                chunks.append(chunk)

        assert len(chunks) > 0 or final_response is not None
        print(f"\n✅ GPT Streaming: {len(chunks)} chunks")

    @pytest.mark.asyncio
    async def test_temperature_and_max_tokens(self, llm_client):
        """测试 temperature 和 max_tokens 参数"""
        response = await llm_client.create_message(
            model_id="gpt-4o",
            messages=[{"role": "user", "content": "Say 'test'"}],
            max_tokens=5,
            temperature=0.0,
        )

        assert response is not None
        assert response.usage["output_tokens"] <= 10  # 给一点余量
        print(f"\n✅ GPT with params: {response.text}")


# ============================================================================
# Google (Gemini) 集成测试
# ============================================================================


@pytest.mark.integration
@pytest.mark.google
@pytest.mark.skipif(not has_google_key(), reason="需要 GOOGLE_API_KEY 或 GEMINI_API_KEY")
class TestGoogleIntegration:
    """Google Gemini 真实 API 测试"""

    @pytest.mark.asyncio
    async def test_simple_message(self, llm_client):
        """测试简单消息调用"""
        response = await llm_client.create_message(
            model_id="gemini-2.0-flash",
            messages=[{"role": "user", "content": "Say 'Hello, World!' and nothing else."}],
            max_tokens=100,
        )

        assert response is not None
        assert isinstance(response, ProviderResponse)
        assert response.text is not None
        assert len(response.text) > 0
        print(f"\n✅ Gemini Response: {response.text}")

    @pytest.mark.asyncio
    async def test_system_prompt(self, llm_client):
        """测试系统提示"""
        response = await llm_client.create_message(
            model_id="gemini-2.0-flash",
            messages=[{"role": "user", "content": "What is your name?"}],
            system="You are a helpful assistant named Gemini-Bot.",
            max_tokens=100,
        )

        assert response is not None
        # Gemini 可能会在 system prompt 中看到名字
        print(f"\n✅ Gemini with System: {response.text}")

    @pytest.mark.asyncio
    async def test_multi_turn_conversation(self, llm_client):
        """测试多轮对话"""
        messages = [
            {"role": "user", "content": "My favorite color is blue."},
            {"role": "assistant", "content": "That's great! Blue is a beautiful color."},
            {"role": "user", "content": "What's my favorite color?"},
        ]

        response = await llm_client.create_message(
            model_id="gemini-2.0-flash",
            messages=messages,
            max_tokens=100,
        )

        assert response is not None
        assert "blue" in response.text.lower()
        print(f"\n✅ Gemini Multi-turn: {response.text}")


# ============================================================================
# 跨厂商对比测试
# ============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    not (has_anthropic_key() and has_openai_key()),
    reason="需要 ANTHROPIC_API_KEY 和 OPENAI_API_KEY",
)
class TestCrossProviderComparison:
    """跨厂商对比测试"""

    @pytest.mark.asyncio
    async def test_same_question_different_providers(self, llm_client):
        """测试同一问题在不同厂商的表现"""
        question = "What is 2 + 2?"
        messages = [{"role": "user", "content": question}]

        # Claude
        claude_response = await llm_client.create_message(
            model_id="claude-sonnet-4-20250514",
            messages=messages,
            max_tokens=50,
        )

        # GPT
        gpt_response = await llm_client.create_message(
            model_id="gpt-4o",
            messages=messages,
            max_tokens=50,
        )

        assert claude_response is not None
        assert gpt_response is not None
        assert "4" in claude_response.text
        assert "4" in gpt_response.text

        print(f"\n✅ Question: {question}")
        print(f"   Claude: {claude_response.text}")
        print(f"   GPT: {gpt_response.text}")


# ============================================================================
# 错误处理测试
# ============================================================================


@pytest.mark.integration
class TestErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_invalid_model_id(self, llm_client):
        """测试无效的模型 ID"""
        with pytest.raises(ValueError, match="not found"):
            await llm_client.create_message(
                model_id="invalid-model-xyz",
                messages=[{"role": "user", "content": "test"}],
            )

    @pytest.mark.asyncio
    @pytest.mark.skipif(not has_anthropic_key(), reason="需要 ANTHROPIC_API_KEY")
    async def test_max_tokens_too_small(self, llm_client):
        """测试 max_tokens 过小"""
        response = await llm_client.create_message(
            model_id="claude-sonnet-4-20250514",
            messages=[{"role": "user", "content": "Write a long story."}],
            max_tokens=1,  # 极小的值
        )

        # 应该返回结果，但可能被截断
        assert response is not None
        assert response.stop_reason in ["max_tokens", "end_turn"]
        print(f"\n✅ Max tokens too small: stop_reason={response.stop_reason}")


if __name__ == "__main__":
    # 运行所有集成测试
    pytest.main([__file__, "-v", "-s", "-m", "integration"])
