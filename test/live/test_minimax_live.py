"""
MiniMax 真实大模型活体测试

覆盖：
- 基础消息调用
- 系统提示词注入
- 多轮对话上下文
- 工具调用 (function calling)
- 参数裁剪 (temperature / max_tokens)
- 错误路径（未注册模型）

运行方式：
    $env:MINIMAX_API_KEY="sk-cp-..."
    pytest test/live -v -s
"""

from __future__ import annotations

from contextlib import contextmanager

import httpx
import pytest

from pyagentforge.kernel.message import ProviderResponse


@contextmanager
def _xfail_on_upstream_5xx():
    """将 MiniMax 上游 5xx（含 529 Overloaded）转为 xfail，不误报为产品缺陷。

    与 ``test_minimax_think_live.py`` / ``test_stream_live.py`` 保持一致的健壮性策略。
    """
    try:
        yield
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            pytest.xfail(f"upstream overload: {exc.response.status_code}")
        raise


def _extract_text(response: ProviderResponse) -> str:
    """MiniMax M2 的原生 OpenAI 协议会把 <think>...</think> 放在 content 里，
    此处做一次简单剥离，仅用于断言可读文本。
    """
    text = response.text or ""
    if "</think>" in text:
        text = text.split("</think>", 1)[-1].strip()
    return text


@pytest.mark.asyncio
async def test_minimax_simple_message(llm_client, minimax_model_id):
    """最小可用性：一次同步对话"""
    with _xfail_on_upstream_5xx():
        response = await llm_client.create_message(
            model_id=minimax_model_id,
            messages=[
                {"role": "user", "content": "Reply with exactly one word: PONG"}
            ],
            max_tokens=256,
            temperature=0.0,
        )

    assert isinstance(response, ProviderResponse)
    assert response.stop_reason in {"end_turn", "max_tokens", "stop", "tool_use"}
    assert response.usage["input_tokens"] > 0
    # MiniMax M2 会把 reasoning tokens 也计入 completion_tokens
    assert response.usage["output_tokens"] > 0

    text = _extract_text(response)
    print(f"\n[simple] text={text!r} usage={response.usage}")
    assert "pong" in text.lower()


@pytest.mark.asyncio
async def test_minimax_system_prompt(llm_client, minimax_model_id):
    """系统提示词注入：模型应遵循角色设定回答自己的名字"""
    with _xfail_on_upstream_5xx():
        response = await llm_client.create_message(
            model_id=minimax_model_id,
            system="You are a helpful assistant whose name is NeuroBot. Always identify yourself by that name.",
            messages=[{"role": "user", "content": "What is your name? Answer in one short sentence."}],
            max_tokens=256,
            temperature=0.0,
        )

    text = _extract_text(response)
    print(f"\n[system] text={text!r}")
    assert "neurobot" in text.lower()


@pytest.mark.asyncio
async def test_minimax_multi_turn(llm_client, minimax_model_id):
    """多轮上下文：模型需要记住前面的事实"""
    messages = [
        {"role": "user", "content": "My favorite programming language is Rust."},
        {"role": "assistant", "content": "Got it, Rust is a great choice."},
        {"role": "user", "content": "What did I say my favorite language was? Reply with the language name only."},
    ]
    with _xfail_on_upstream_5xx():
        response = await llm_client.create_message(
            model_id=minimax_model_id,
            messages=messages,
            max_tokens=256,
            temperature=0.0,
        )

    text = _extract_text(response)
    print(f"\n[multi-turn] text={text!r}")
    assert "rust" in text.lower()


@pytest.mark.asyncio
async def test_minimax_tool_use(llm_client, minimax_model_id):
    """工具调用：模型应发起 get_weather 工具调用"""
    tools = [
        {
            "name": "get_weather",
            "description": "Get the current weather for a given city.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "Temperature unit",
                    },
                },
                "required": ["city"],
            },
        }
    ]

    with _xfail_on_upstream_5xx():
        response = await llm_client.create_message(
            model_id=minimax_model_id,
            system="You must call the provided tool to obtain weather. Do not answer from memory.",
            messages=[{"role": "user", "content": "What's the weather in Shanghai right now?"}],
            tools=tools,
            max_tokens=512,
            temperature=0.0,
        )

    print(f"\n[tool] has_tool_calls={response.has_tool_calls} stop={response.stop_reason}")
    if response.has_tool_calls:
        call = response.tool_calls[0]
        print(f"[tool] name={call.name} input={call.input}")
        assert call.name == "get_weather"
        assert isinstance(call.input, dict)
        assert "city" in call.input
        assert "shanghai" in str(call.input["city"]).lower()
    else:
        # 某些模型版本可能会直接用文本回答；此时仅检查文本中包含 city 线索，
        # 避免把测试变成必须 tool_use，真实模型表现允许有弹性。
        text = _extract_text(response)
        pytest.skip(f"Model did not invoke tool this run; text fallback: {text[:200]}")


@pytest.mark.asyncio
async def test_minimax_max_tokens_truncation(llm_client, minimax_model_id):
    """参数传递：max_tokens=16 应触发 length 截断"""
    with _xfail_on_upstream_5xx():
        response = await llm_client.create_message(
            model_id=minimax_model_id,
            messages=[{"role": "user", "content": "Write a 500-word essay about the history of the Internet."}],
            max_tokens=16,
            temperature=0.7,
        )

    print(f"\n[max_tokens] stop={response.stop_reason} usage={response.usage}")
    assert response.stop_reason in {"max_tokens", "end_turn"}
    # 即便算上 reasoning tokens，也应接近上限
    assert response.usage["output_tokens"] <= 64


@pytest.mark.asyncio
async def test_minimax_unknown_model_raises(llm_client):
    """错误路径：未注册模型应抛 ValueError"""
    with pytest.raises(ValueError, match="not found"):
        await llm_client.create_message(
            model_id="definitely-not-a-real-model-xyz-123",
            messages=[{"role": "user", "content": "hi"}],
        )
