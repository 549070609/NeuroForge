"""GLM 全功能回归测试"""
import asyncio
from pyagentforge.client import LLMClient
from pyagentforge.kernel.model_registry import ModelRegistry, ModelConfig
from pyagentforge.kernel.message import ProviderResponse

MODEL = "glm-5.1"
passed = 0
failed = 0


def report(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  PASS  {name}" + (f" - {detail}" if detail else ""))
    else:
        failed += 1
        print(f"  FAIL  {name}" + (f" - {detail}" if detail else ""))


async def run_all():
    global passed, failed
    registry = ModelRegistry(load_from_config=True)
    client = LLMClient(registry=registry)

    # ========== 1. 基础消息 ==========
    print("\n=== 1. 基础消息 ===")
    try:
        r = await client.create_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "Say hello world and nothing else."}],
            max_tokens=50,
        )
        report("simple_message",
               r is not None and isinstance(r, ProviderResponse) and len(r.text) > 0,
               f"text={r.text!r}")
    except Exception as e:
        report("simple_message", False, str(e))

    # ========== 2. 系统提示 ==========
    print("\n=== 2. 系统提示 ===")
    try:
        r = await client.create_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "What is your name?"}],
            system="You are a helpful assistant named TestBot. Always introduce yourself as TestBot.",
            max_tokens=100,
        )
        report("system_prompt",
               r is not None and len(r.text) > 0,
               f"text={r.text!r}")
    except Exception as e:
        report("system_prompt", False, str(e))

    # ========== 3. 多轮对话 ==========
    print("\n=== 3. 多轮对话 ===")
    try:
        r = await client.create_message(
            model_id=MODEL,
            messages=[
                {"role": "user", "content": "My name is Alice."},
                {"role": "assistant", "content": "Nice to meet you, Alice!"},
                {"role": "user", "content": "What is my name?"},
            ],
            max_tokens=50,
        )
        report("multi_turn",
               r is not None and "alice" in r.text.lower(),
               f"text={r.text!r}")
    except Exception as e:
        report("multi_turn", False, str(e))

    # ========== 4. 参数控制 ==========
    print("\n=== 4. 参数控制 ===")
    try:
        r = await client.create_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "Write a very long story about dragons."}],
            max_tokens=5,
            temperature=0.0,
        )
        report("max_tokens_control",
               r is not None and r.stop_reason in ["max_tokens", "end_turn"],
               f"stop_reason={r.stop_reason}, output_tokens={r.usage.get('output_tokens')}")
    except Exception as e:
        report("max_tokens_control", False, str(e))

    # ========== 5. Usage 统计 ==========
    print("\n=== 5. Usage 统计 ===")
    try:
        r = await client.create_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=10,
        )
        report("usage_stats",
               r.usage.get("input_tokens", 0) > 0 and r.usage.get("output_tokens", 0) > 0,
               f"usage={r.usage}")
    except Exception as e:
        report("usage_stats", False, str(e))

    # ========== 6. 工具调用 ==========
    print("\n=== 6. 工具调用 ===")
    tools = [{
        "name": "get_weather",
        "description": "Get the current weather in a location",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
            },
            "required": ["location"],
        },
    }]
    try:
        r = await client.create_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "What is the weather like in Beijing?"}],
            tools=tools,
            max_tokens=200,
        )
        has_tools = r.has_tool_calls and len(r.tool_calls) > 0
        tool_name = r.tool_calls[0].name if has_tools else "N/A"
        tool_input = r.tool_calls[0].input if has_tools else {}
        report("tool_use_trigger",
               has_tools and tool_name == "get_weather",
               f"tool={tool_name}, input={tool_input}")
    except Exception as e:
        report("tool_use_trigger", False, str(e))

    # ========== 7. 工具结果回传 ==========
    print("\n=== 7. 工具结果回传 ===")
    try:
        r1 = await client.create_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "What is the weather in Shanghai?"}],
            tools=tools,
            max_tokens=200,
        )
        if r1.has_tool_calls:
            tc = r1.tool_calls[0]
            r2 = await client.create_message(
                model_id=MODEL,
                messages=[
                    {"role": "user", "content": "What is the weather in Shanghai?"},
                    {"role": "assistant", "content": [
                        {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input}
                    ]},
                    {"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": tc.id, "content": "Sunny, 25 degrees Celsius"}
                    ]},
                ],
                tools=tools,
                max_tokens=200,
            )
            report("tool_result_roundtrip",
                   r2 is not None and len(r2.text) > 0,
                   f"text={r2.text!r}")
        else:
            report("tool_result_roundtrip", False, "initial call did not trigger tool use")
    except Exception as e:
        report("tool_result_roundtrip", False, str(e))

    # ========== 8. 流式响应 ==========
    print("\n=== 8. 流式响应 ===")
    try:
        chunks = []
        final = None
        async for chunk in client.stream_message(
            model_id=MODEL,
            messages=[{"role": "user", "content": "Count from 1 to 5."}],
            max_tokens=100,
        ):
            if isinstance(chunk, ProviderResponse):
                final = chunk
            else:
                chunks.append(chunk)
        report("streaming",
               final is not None and len(final.text) > 0,
               f"chunks={len(chunks)}, text={final.text!r}" if final else "no final response")
    except Exception as e:
        report("streaming", False, str(e))

    # ========== 9. 错误处理 ==========
    print("\n=== 9. 错误处理 ===")
    try:
        await client.create_message(
            model_id="invalid-model-xyz-999",
            messages=[{"role": "user", "content": "test"}],
        )
        report("invalid_model_error", False, "should have raised")
    except ValueError:
        report("invalid_model_error", True, "ValueError raised as expected")
    except Exception as e:
        report("invalid_model_error", False, f"unexpected: {type(e).__name__}: {e}")

    # ========== 10. Runtime Registration ==========
    print("\n=== 10. Runtime Registration ===")
    try:
        reg = ModelRegistry(load_from_config=False)
        reg.register_model(ModelConfig(
            id="test-rt",
            name="Test Runtime",
            provider="test",
            api_type="anthropic-messages",
            base_url="https://open.bigmodel.cn/api/anthropic/v1",
            api_key="8da577d11e204c698642bceaa164f434.1uX0WfqmB6Cgn4qM",
            model_name="glm-5.1",
        ))
        c2 = LLMClient(registry=reg)
        r = await c2.create_message(
            model_id="test-rt",
            messages=[{"role": "user", "content": "Say runtime OK"}],
            max_tokens=20,
        )
        report("runtime_registration",
               r is not None and len(r.text) > 0,
               f"text={r.text!r}")
    except Exception as e:
        report("runtime_registration", False, str(e))

    # ========== Summary ==========
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Total: {total} tests, {passed} passed, {failed} failed")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_all())
    exit(0 if ok else 1)
