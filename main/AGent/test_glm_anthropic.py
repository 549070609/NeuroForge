#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test GLM Anthropic Provider with tool calling
测试新的 GLM Anthropic Provider 工具调用
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

from glm_anthropic_provider import GLMAnthropicProvider
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.tools.builtin import BashTool, WriteTool

# Global tracking
tool_executed = False
executed_tools = []

class TrackedBashTool(BashTool):
    async def execute(self, **kwargs):
        global tool_executed, executed_tools
        tool_executed = True
        executed_tools.append(("bash", kwargs))
        print(f"\n[TOOL EXECUTED] bash: {kwargs.get('command', 'N/A')}")
        return await super().execute(**kwargs)

class TrackedWriteTool(WriteTool):
    async def execute(self, **kwargs):
        global tool_executed, executed_tools
        tool_executed = True
        executed_tools.append(("write", kwargs))
        print(f"\n[TOOL EXECUTED] write: {kwargs.get('file_path', 'N/A')}")
        return await super().execute(**kwargs)

async def main():
    global tool_executed, executed_tools

    print("=" * 70)
    print(" GLM Anthropic Provider - Tool Calling Test")
    print("=" * 70)

    # 1. Create Provider
    print("\n[Step 1] Creating GLM Anthropic Provider...")
    provider = GLMAnthropicProvider()
    print("  [OK] Provider created")

    # 2. Create Tool Registry
    print("\n[Step 2] Creating Tool Registry...")
    registry = ToolRegistry()
    registry.register(TrackedBashTool())
    registry.register(TrackedWriteTool())
    print(f"  [OK] Registered {len(registry.get_all())} tools")

    # 3. Create Agent Engine
    print("\n[Step 3] Creating Agent Engine...")
    config = AgentConfig(
        system_prompt="You are a helpful assistant. Execute commands using the bash tool when asked.",
        max_iterations=5,
    )
    engine = AgentEngine(provider=provider, tool_registry=registry, config=config)
    print(f"  [OK] Session: {engine.session_id}")

    # Test Case 1: Bash Tool
    print("\n" + "=" * 70)
    print("Test Case 1: Bash Tool")
    print("=" * 70)

    tool_executed = False
    executed_tools = []

    prompt = "Please use bash tool to execute: echo Hello World"
    print(f"\nPrompt: {prompt}")

    try:
        response = await engine.run(prompt)
        print(f"\nResponse: {response}")

        if tool_executed:
            print("\n[PASS] Tool was executed!")
            for tool_name, args in executed_tools:
                print(f"  - {tool_name}: {args}")
        else:
            print("\n[FAIL] Tool was NOT executed")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    # Test Case 2: Write Tool
    print("\n" + "=" * 70)
    print("Test Case 2: Write Tool")
    print("=" * 70)

    tool_executed = False
    executed_tools = []

    prompt = "Please save the content 'This is a test file created by GLM' to test_glm.md"
    print(f"\nPrompt: {prompt}")

    try:
        response = await engine.run(prompt)
        print(f"\nResponse: {response}")

        if tool_executed:
            print("\n[PASS] Tool was executed!")
            for tool_name, args in executed_tools:
                print(f"  - {tool_name}: {args}")

            # Check if file was created
            if Path("test_glm.md").exists():
                content = Path("test_glm.md").read_text(encoding="utf-8")
                print(f"\nFile content: {content}")
                Path("test_glm.md").unlink()  # Clean up
        else:
            print("\n[FAIL] Tool was NOT executed")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
