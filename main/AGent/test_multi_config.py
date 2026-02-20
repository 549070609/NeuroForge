#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test GLM tool calling with different models and prompts
尝试不同的模型和提示词格式
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

from glm_provider import GLMProvider
from pyagentforge.kernel.engine import AgentEngine, AgentConfig
from pyagentforge.kernel.executor import ToolRegistry
from pyagentforge.tools.builtin import BashTool

tool_called = False

class TrackedBashTool(BashTool):
    async def execute(self, **kwargs):
        global tool_called
        tool_called = True
        print(f"\n[TOOL EXECUTED] command: {kwargs.get('command', 'N/A')}")
        return await super().execute(**kwargs)

async def test_model(model_name, endpoint):
    """Test a specific model"""

    global tool_called

    print(f"\n{'='*70}")
    print(f"Testing: {model_name} @ {endpoint}")
    print("=" * 70)

    try:
        provider = GLMProvider(
            model=model_name,
            use_functions_format=True,
        )
        provider.GLM_BASE_URL = endpoint
        provider.client.base_url = endpoint

        registry = ToolRegistry()
        registry.register(TrackedBashTool())

        config = AgentConfig(
            system_prompt="You are a helpful assistant.",
            max_iterations=5,
        )

        engine = AgentEngine(provider=provider, tool_registry=registry, config=config)

        # Use the exact prompt from successful tests
        tool_called = False
        response = await engine.run("请使用 bash 工具执行命令：echo 'Hello World'")

        print(f"Response: {response[:200]}...")
        print(f"Tool Called: {tool_called}")

        return tool_called

    except Exception as e:
        print(f"[ERROR] {e}")
        return False

async def main():
    """Test multiple configurations"""

    print("=" * 70)
    print(" GLM Tool Calling - Multi-Configuration Test")
    print("=" * 70)

    # Test configurations
    configs = [
        # (model, endpoint)
        ("glm-5", "https://api.z.ai/api/coding/paas/v4"),
        ("glm-4-flash", "https://api.z.ai/api/coding/paas/v4"),
        ("glm-4-plus", "https://api.z.ai/api/coding/paas/v4"),
        ("glm-5", "https://open.bigmodel.cn/api/coding/paas/v4"),
        ("glm-4-flash", "https://open.bigmodel.cn/api/coding/paas/v4"),
    ]

    results = []

    for model, endpoint in configs:
        success = await test_model(model, endpoint)
        results.append((model, endpoint, success))

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)

    for model, endpoint, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"  {status} {model} @ {endpoint.split('//')[1].split('/')[0]}")

    passed = sum(1 for _, _, s in results if s)
    print(f"\nPassed: {passed}/{len(results)}")

    if passed > 0:
        print("\nGLM tool calling IS supported on some configurations!")
    else:
        print("\nGLM tool calling is NOT working on any configuration.")
        print("This may be an API Key permission issue.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
