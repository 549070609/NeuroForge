#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Strict test to verify GLM actually calls tools (not just text output)
"""

import sys
import asyncio
import json
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

from glm_provider import GLMProvider
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.tools.builtin import BashTool, WriteTool

print("=" * 70)
print(" Strict GLM Tool Calling Test")
print("=" * 70)

# 全局变量来跟踪工具是否真正执行
tool_executed = False
tool_args = None

class MockBashTool(BashTool):
    """Mock Bash tool that tracks execution"""

    async def execute(self, **kwargs):
        global tool_executed, tool_args
        tool_executed = True
        tool_args = kwargs
        print(f"\n[TOOL EXECUTED] Bash tool called with args: {kwargs}")
        # 调用父类执行实际命令
        return await super().execute(**kwargs)

class MockWriteTool(WriteTool):
    """Mock Write tool that tracks execution"""

    async def execute(self, **kwargs):
        global tool_executed, tool_args
        tool_executed = True
        tool_args = kwargs
        print(f"\n[TOOL EXECUTED] Write tool called with args: {kwargs}")
        # 调用父类执行实际写入
        return await super().execute(**kwargs)

async def test_glm_strict():
    """Strict test to verify tool execution"""

    global tool_executed, tool_args

    # 1. 创建 Provider
    print("\n[Test 1] Creating GLM Provider...")
    provider = GLMProvider(
        model="glm-5",
        use_functions_format=True,
    )
    print(f"  Model: {provider.model}")
    print(f"  Base URL: {provider.GLM_BASE_URL}")

    # 2. 创建工具注册表（使用 Mock 工具）
    print("\n[Test 2] Creating ToolRegistry with Mock tools...")
    registry = ToolRegistry()
    registry.register(MockBashTool())
    registry.register(MockWriteTool())
    print(f"  Registered {len(registry.get_all())} tools")

    # 3. 创建 AgentEngine
    print("\n[Test 3] Creating AgentEngine...")
    config = AgentConfig(
        system_prompt="你是一个有帮助的 AI 助手。当用户要求执行命令或操作时，必须使用工具。",
        max_iterations=5,
    )

    engine = AgentEngine(
        provider=provider,
        tool_registry=registry,
        config=config,
    )
    print(f"  Session: {engine.session_id}")

    # Test Case 1: Bash Tool
    print("\n" + "=" * 70)
    print("Test Case 1: Bash Tool")
    print("=" * 70)

    tool_executed = False
    tool_args = None

    print("\nPrompt: '请使用 bash 工具执行命令：echo Hello'")
    try:
        response = await engine.run("请使用 bash 工具执行命令：echo Hello")
        print(f"\nResponse: {response[:200]}...")
        print(f"\n[RESULT] Tool executed: {tool_executed}")
        print(f"[RESULT] Tool args: {tool_args}")

        if tool_executed and tool_args and "command" in tool_args:
            print("\n✅ PASS: GLM actually called the Bash tool!")
        else:
            print("\n❌ FAIL: GLM did NOT call the tool (just text output)")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Test Case 2: Write Tool
    print("\n" + "=" * 70)
    print("Test Case 2: Write Tool")
    print("=" * 70)

    tool_executed = False
    tool_args = None

    print("\nPrompt: '请将内容 Hello World 保存到文件 test_strict.md'")
    try:
        response = await engine.run("请将内容 Hello World 保存到文件 test_strict.md")
        print(f"\nResponse: {response[:200]}...")
        print(f"\n[RESULT] Tool executed: {tool_executed}")
        print(f"[RESULT] Tool args: {tool_args}")

        if tool_executed and tool_args and "file_path" in tool_args:
            print("\n✅ PASS: GLM actually called the Write tool!")

            # 检查文件是否真的创建了
            test_file = Path("test_strict.md")
            if test_file.exists():
                content = test_file.read_text(encoding="utf-8")
                print(f"[RESULT] File created with content: {content}")
                test_file.unlink()  # 清理
            else:
                print("[WARNING] File was not actually created")
        else:
            print("\n❌ FAIL: GLM did NOT call the Write tool (just text output)")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(test_glm_strict())
    except KeyboardInterrupt:
        print("\n\n[Interrupted]")
    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()
