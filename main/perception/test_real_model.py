"""
使用真实模型 (GLM-4 Flash) 测试 Perception 插件全部功能

运行: cd Agent-Learn/main && python -m perception.test_real_model

测试内容：
  Part 1: 直接调用 Tools（不经过 LLM）
  Part 2: 引擎集成 + 真实 LLM Tool-Calling
"""

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path

_main = Path(__file__).resolve().parent.parent
if str(_main) not in sys.path:
    sys.path.insert(0, str(_main))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("test_real_model")

LLM_CONFIG_PATH = _main / "llm_config.json"


def load_llm_config() -> dict:
    with open(LLM_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Part 1: 直接测试 Tools
# ============================================================

async def test_perceive_tool_error():
    """PerceiveTool 检测 error 级别事件"""
    from perception.tools import PerceiveTool

    tool = PerceiveTool(default_rules={
        "levels": ["error", "warn"],
        "error_triggers": "find_user",
    })
    data = {
        "events": [
            {"id": 1, "level": "error", "message": "Database connection timeout after 30s"},
        ]
    }
    result = await tool.execute(data=data)
    print(result)
    assert "find_user" in result, f"Expected 'find_user' in result, got: {result}"
    return True


async def test_perceive_tool_normal():
    """PerceiveTool 正常事件不触发"""
    from perception.tools import PerceiveTool

    tool = PerceiveTool(default_rules={"levels": ["error", "warn"]})
    data = {
        "events": [
            {"id": 1, "level": "info", "message": "Service started successfully"},
        ]
    }
    result = await tool.execute(data=data)
    print(result)
    assert "none" in result.lower(), f"Expected 'none' in result, got: {result}"
    return True


async def test_perceive_tool_warn():
    """PerceiveTool 检测 warn 级别事件"""
    from perception.tools import PerceiveTool

    tool = PerceiveTool(default_rules={
        "levels": ["error", "warn"],
        "warn_triggers": "find_user",
    })
    data = {
        "events": [
            {"id": 1, "level": "warn", "message": "Memory usage at 85%"},
        ]
    }
    result = await tool.execute(data=data)
    print(result)
    assert "find_user" in result, f"Expected 'find_user' in result, got: {result}"
    return True


async def test_execute_decision_tool_shell():
    """ExecuteDecisionTool 执行 shell 动作"""
    from perception.tools import ExecuteDecisionTool
    from perception.executor import DecisionExecutor

    executor = DecisionExecutor(
        execute_actions={"default": {"type": "shell", "cmd": "echo perception_alert_triggered"}},
    )
    tool = ExecuteDecisionTool(
        default_rules={"error_triggers": "execute"},
        executor=executor,
    )
    data = {
        "events": [
            {"id": 1, "level": "error", "message": "Disk usage critical: 95%"},
        ]
    }
    result = await tool.execute(data=data)
    print(result)
    assert "execute" in result.lower(), f"Expected 'execute' in result, got: {result}"
    assert "perception_alert_triggered" in result, f"Expected shell output in result, got: {result}"
    return True


async def test_execute_decision_tool_none():
    """ExecuteDecisionTool 无异常不执行"""
    from perception.tools import ExecuteDecisionTool

    tool = ExecuteDecisionTool(default_rules={"error_triggers": "execute"})
    data = {
        "events": [
            {"id": 1, "level": "info", "message": "All healthy"},
        ]
    }
    result = await tool.execute(data=data)
    print(result)
    assert "none" in result.lower(), f"Expected 'none' in result, got: {result}"
    return True


async def test_read_logs_tool(tmpdir: str):
    """ReadLogsTool 读取并过滤日志文件"""
    from perception.tools import ReadLogsTool

    log_file = Path(tmpdir) / "app.log"
    log_file.write_text(
        "[ERROR] 2024-01-15 10:00:01 Database connection refused\n"
        "[INFO]  2024-01-15 10:00:02 Health check passed\n"
        "[WARN]  2024-01-15 10:00:03 Slow query detected: 2.5s\n"
        "[INFO]  2024-01-15 10:00:04 Request handled: GET /api/status\n"
        "[ERROR] 2024-01-15 10:00:05 Out of memory: heap allocation failed\n",
        encoding="utf-8",
    )
    tool = ReadLogsTool(default_path=tmpdir)

    result_all = await tool.execute()
    print(f"All lines:\n{result_all}")
    assert "Database connection refused" in result_all

    result_filtered = await tool.execute(level_filter="ERROR|WARN")
    print(f"\nFiltered (ERROR|WARN):\n{result_filtered}")
    assert "Database connection refused" in result_filtered
    assert "Slow query detected" in result_filtered
    assert "Health check passed" not in result_filtered
    return True


async def test_execute_decision_call_agent():
    """ExecuteDecisionTool call_agent 路径 (mock engine)"""
    from perception.tools import ExecuteDecisionTool
    from perception.executor import DecisionExecutor

    call_results = []

    class MockEngine:
        async def run(self, prompt):
            call_results.append(prompt)
            return "Alert handled by sub-agent"

    executor = DecisionExecutor(
        engine=MockEngine(),
        call_agent_config={
            "target_agent": "main",
            "prompt_template": "Handle alert.\nReason: {reason}\nData: {data}",
        },
    )
    tool = ExecuteDecisionTool(
        default_rules={"error_triggers": "call_agent"},
        executor=executor,
    )
    data = {
        "events": [
            {"id": 1, "level": "error", "message": "Critical failure in payment service"},
        ]
    }
    result = await tool.execute(data=data)
    print(result)
    assert "call_agent" in result.lower(), f"Expected 'call_agent' in result"
    assert len(call_results) == 1, "Expected engine.run to be called once"
    assert "Critical failure" in call_results[0]
    return True


async def run_part1():
    print("\n" + "=" * 60)
    print("Part 1: 直接测试 Perception Tools")
    print("=" * 60)

    tests = [
        ("PerceiveTool (error event)", test_perceive_tool_error),
        ("PerceiveTool (normal event)", test_perceive_tool_normal),
        ("PerceiveTool (warn event)", test_perceive_tool_warn),
        ("ExecuteDecisionTool (shell)", test_execute_decision_tool_shell),
        ("ExecuteDecisionTool (none)", test_execute_decision_tool_none),
        ("ExecuteDecisionTool (call_agent)", test_execute_decision_call_agent),
    ]

    passed = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tests.append(("ReadLogsTool", lambda: test_read_logs_tool(tmpdir)))

        for name, fn in tests:
            print(f"\n--- {name} ---")
            try:
                ok = await fn()
                if ok:
                    print(f"[OK] {name}")
                    passed += 1
                else:
                    print(f"[FAIL] {name}")
            except Exception as e:
                print(f"[FAIL] {name}: {e}")

    print(f"\n[Part 1] {passed}/{len(tests)} tests passed")
    return passed == len(tests)


# ============================================================
# Part 2: 真实 LLM 引擎集成测试
# ============================================================

def _create_zhipu_provider(config: dict):
    """基于 llm_config.json 创建智谱 Provider"""
    from pyagentforge.kernel.base_provider import BaseProvider
    from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
    from openai import AsyncOpenAI

    provider_cfg = config["providers"]["zhipu"]
    model_cfg = config["models"][config["default_model"]]

    api_key = provider_cfg["api_key_env"]
    base_url = provider_cfg["base_url"]
    model_id = model_cfg["id"]

    class ZhipuProvider(BaseProvider):
        """智谱 GLM Provider (OpenAI-compatible API)"""

        def __init__(self):
            super().__init__(
                model=model_id,
                max_tokens=config.get("max_tokens", 4096),
                temperature=0.7,
            )
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        def _convert_tools(self, tools):
            return [
                {
                    "type": "function",
                    "function": {
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in tools
            ]

        def _convert_messages(self, system, messages):
            result = [{"role": "system", "content": system}]
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")
                if isinstance(content, str):
                    result.append({"role": role, "content": content})
                elif isinstance(content, list):
                    text_parts = []
                    tool_calls = []
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        bt = block.get("type")
                        if bt == "text":
                            text_parts.append(block.get("text", ""))
                        elif bt == "tool_use":
                            args = block.get("input", {})
                            tool_calls.append({
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": json.dumps(args, ensure_ascii=False)
                                    if isinstance(args, (dict, list))
                                    else str(args),
                                },
                            })
                        elif bt == "tool_result":
                            result.append({
                                "role": "tool",
                                "tool_call_id": block.get("tool_use_id", ""),
                                "content": block.get("content", ""),
                            })
                    if text_parts or tool_calls:
                        msg_dict = {"role": role}
                        if text_parts:
                            msg_dict["content"] = "\n".join(text_parts)
                        if tool_calls:
                            msg_dict["tool_calls"] = tool_calls
                        result.append(msg_dict)
            return result

        async def create_message(self, system, messages, tools, **kwargs):
            openai_msgs = self._convert_messages(system, messages)
            openai_tools = self._convert_tools(tools) if tools else None

            params = {
                "model": self.model,
                "messages": openai_msgs,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
            }
            if openai_tools:
                params["tools"] = openai_tools

            log.info(f"Calling LLM: model={self.model}, tools={[t['function']['name'] for t in (openai_tools or [])]}")
            response = await self.client.chat.completions.create(**params)
            choice = response.choices[0]

            content = []
            if choice.message.content:
                content.append(TextBlock(text=choice.message.content))

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    try:
                        if isinstance(tc.function.arguments, str):
                            tool_input = json.loads(tc.function.arguments)
                        elif isinstance(tc.function.arguments, dict):
                            tool_input = tc.function.arguments
                        else:
                            tool_input = {}
                    except json.JSONDecodeError:
                        log.warning(f"Failed to parse tool args: {tc.function.arguments}")
                        tool_input = {}
                    content.append(ToolUseBlock(
                        id=tc.id, name=tc.function.name, input=tool_input,
                    ))

            finish = choice.finish_reason
            stop_reason = (
                "tool_use" if finish == "tool_calls"
                else "max_tokens" if finish == "length"
                else "end_turn"
            )
            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            }
            log.info(f"LLM response: stop={stop_reason}, usage={usage}, blocks={len(content)}")

            return ProviderResponse(content=content, stop_reason=stop_reason, usage=usage)

        async def count_tokens(self, messages):
            total = 0
            for msg in messages:
                c = msg.get("content", "")
                if isinstance(c, str):
                    total += len(c) // 4
            return total

    return ZhipuProvider()


async def test_engine_integration():
    """引擎 + Perception 插件 + 真实 LLM"""
    config = load_llm_config()
    provider = _create_zhipu_provider(config)

    from pyagentforge import create_engine
    from pyagentforge.config.plugin_config import PluginConfig

    plugin_config = PluginConfig(
        preset="minimal",
        enabled=["integration.perception"],
        plugin_dirs=[str(_main)],
        config={
            "integration.perception": {
                "log_path": "./logs",
                "filter_rules": {"level": ["error", "warn"]},
            }
        },
    )

    engine = await create_engine(
        provider=provider,
        plugin_config=plugin_config,
        working_dir=str(_main),
        config={
            "system_prompt": (
                "你是一个智能日志分析代理。你可以使用以下工具来分析日志数据：\n"
                "- perceive: 分析解析后的日志数据并做出决策（输入 data 参数为 dict/list）\n"
                "- execute_decision: 执行感知决策（输入 data 参数为 dict/list）\n"
                "- read_logs: 从路径读取日志文件\n"
                "- parse_log: 解析 ATON/TOON 格式日志\n\n"
                "当用户提供日志数据时，请使用 perceive 工具进行分析，然后报告分析结果。\n"
                "回答请使用中文。"
            ),
            "max_iterations": 10,
        },
    )

    all_tools = engine.tools.get_all()
    tool_names = sorted(all_tools.keys())
    perception_tools = ["parse_log", "perceive", "read_logs", "execute_decision"]
    found = [t for t in perception_tools if t in tool_names]
    print(f"  已注册工具总数: {len(tool_names)}")
    print(f"  感知工具: {found}")
    assert len(found) == len(perception_tools), (
        f"感知工具注册不完整: 期望 {perception_tools}, 实际 {found}"
    )
    print("[OK] 插件加载并注册了所有工具\n")
    return engine


async def test_llm_perceive(engine):
    """让 LLM 使用 perceive 工具分析日志"""
    prompt = (
        "请使用 perceive 工具分析以下日志数据，告诉我系统是否有异常：\n\n"
        "日志数据（JSON 格式，请直接传入 perceive 工具的 data 参数）：\n"
        '{"events": ['
        '{"id": 1, "level": "error", "message": "Database connection timeout after 30s"}, '
        '{"id": 2, "level": "info", "message": "User login successful"}, '
        '{"id": 3, "level": "warn", "message": "Memory usage at 85%"}'
        "]}"
    )
    print(f"  Prompt:\n  {prompt}\n")
    response = await engine.run(prompt)
    print(f"  Agent Response:\n  {response}\n")
    assert response and len(response) > 10, "Response too short or empty"
    return True


async def test_llm_no_anomaly(engine):
    """让 LLM 分析正常日志"""
    engine.context.clear()
    prompt = (
        "请使用 perceive 工具分析以下日志数据：\n\n"
        "日志数据：\n"
        '{"events": ['
        '{"id": 1, "level": "info", "message": "Service started on port 8080"}, '
        '{"id": 2, "level": "info", "message": "Health check passed"}, '
        '{"id": 3, "level": "info", "message": "Request handled successfully"}'
        "]}"
    )
    print(f"  Prompt:\n  {prompt}\n")
    response = await engine.run(prompt)
    print(f"  Agent Response:\n  {response}\n")
    assert response and len(response) > 10, "Response too short or empty"
    return True


async def run_part2():
    print("\n" + "=" * 60)
    print("Part 2: 真实 LLM (GLM-4 Flash) 引擎集成测试")
    print("=" * 60)

    tests_pass = 0
    tests_total = 0

    print("\n--- Test 2.1: 引擎 + 插件加载 ---")
    tests_total += 1
    try:
        engine = await test_engine_integration()
        tests_pass += 1
    except Exception as e:
        print(f"[FAIL] 引擎加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("--- Test 2.2: LLM + perceive (有异常日志) ---")
    tests_total += 1
    try:
        ok = await test_llm_perceive(engine)
        if ok:
            print("[OK] LLM perceive (error) passed")
            tests_pass += 1
        else:
            print("[FAIL] LLM perceive (error)")
    except Exception as e:
        print(f"[FAIL] LLM perceive (error): {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Test 2.3: LLM + perceive (正常日志) ---")
    tests_total += 1
    try:
        ok = await test_llm_no_anomaly(engine)
        if ok:
            print("[OK] LLM perceive (normal) passed")
            tests_pass += 1
        else:
            print("[FAIL] LLM perceive (normal)")
    except Exception as e:
        print(f"[FAIL] LLM perceive (normal): {e}")
        import traceback
        traceback.print_exc()

    print(f"\n[Part 2] {tests_pass}/{tests_total} tests passed")
    return tests_pass == tests_total


# ============================================================
# Main
# ============================================================

async def main():
    print("=" * 60)
    print("Perception 插件真实模型集成测试")
    print("=" * 60)

    ok1 = await run_part1()

    try:
        ok2 = await run_part2()
    except Exception as e:
        print(f"\n[Part 2 ERROR] {e}")
        import traceback
        traceback.print_exc()
        ok2 = False

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"  Part 1 (Tools 直接测试): {'PASS' if ok1 else 'FAIL'}")
    print(f"  Part 2 (LLM 集成测试):   {'PASS' if ok2 else 'FAIL'}")

    if ok1 and ok2:
        print("\n[ALL PASS] 所有测试通过！")
    else:
        print("\n[PARTIAL] 部分测试失败")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
