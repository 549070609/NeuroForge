#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test GLM tool calling with operations it's willing to execute

根据 GLM 测试报告，以下操作 GLM 模型愿意执行：
- 简单计算（expr）
- 获取日期（date）
- 获取当前目录（pwd）
- echo 命令
- 管道操作

而以下操作 GLM 模型会拒绝：
- 涉及本地文件路径的命令
- 文件系统访问（read/write/list）
"""

import sys
import asyncio
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

from glm_provider import GLMProvider
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.tools.builtin import BashTool

# Global tracking
tool_called = False

class TrackedBashTool(BashTool):
    """Bash tool that tracks execution"""
    async def execute(self, **kwargs):
        global tool_called
        tool_called = True
        print(f"\n[TOOL EXECUTED] command: {kwargs.get('command', 'N/A')}")
        return await super().execute(**kwargs)

async def test_glm_supported_operations():
    """Test operations that GLM is willing to execute"""

    global tool_called

    print("=" * 70)
    print(" GLM Supported Operations Test")
    print("=" * 70)

    # Create provider with Anthropic-compatible endpoint
    print("\n[Setup] Creating GLM Provider...")
    provider = GLMProvider(
        model="glm-5",
        use_functions_format=True,
    )
    # Try Anthropic-compatible endpoint
    provider.GLM_BASE_URL = "https://api.z.ai/api/anthropic"
    provider.client.base_url = "https://api.z.ai/api/anthropic"
    print(f"  Model: {provider.model}")
    print(f"  Base URL: {provider.GLM_BASE_URL}")

    # Create registry
    print("\n[Setup] Creating ToolRegistry...")
    registry = ToolRegistry()
    registry.register(TrackedBashTool())
    print(f"  Registered: {list(registry.get_all().keys())}")

    # Create engine
    print("\n[Setup] Creating AgentEngine...")
    config = AgentConfig(
        system_prompt="You are a helpful assistant. Execute commands using bash tool when asked.",
        max_iterations=5,
    )
    engine = AgentEngine(provider=provider, tool_registry=registry, config=config)
    print(f"  Session: {engine.session_id}")

    # Test cases that GLM should accept
    test_cases = [
        ("Echo test", "Please use bash tool to execute: echo HelloGLM"),
        ("Date test", "Please use bash tool to get current date"),
        ("Calculation", "Please use bash tool to calculate: expr 100 + 200"),
        ("PWD test", "Please use bash tool to show current directory"),
    ]

    results = []

    for name, prompt in test_cases:
        print(f"\n{'='*70}")
        print(f"Test: {name}")
        print(f"Prompt: {prompt}")
        print("=" * 70)

        tool_called = False

        try:
            response = await engine.run(prompt)
            print(f"\nResponse: {response[:300]}...")
            print(f"\nTool Called: {tool_called}")

            if tool_called:
                print("[PASS] GLM called the tool!")
                results.append((name, True))
            else:
                print("[FAIL] GLM did NOT call the tool")
                results.append((name, False))
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append((name, False))

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"Passed: {passed}/{total} ({passed/total*100:.1f}%)")

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    if passed == total:
        print("\nGLM tool calling is working correctly!")
    else:
        print(f"\nGLM tool calling has limitations ({total-passed} tests failed)")

if __name__ == "__main__":
    try:
        asyncio.run(test_glm_supported_operations())
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
