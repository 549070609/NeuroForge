#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Bash tool calling with GLM

测试 GLM 是否能正确调用 Bash 工具
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

print("=" * 70)
print(" GLM Bash Tool Calling Test")
print("=" * 70)

async def test_bash_tool():
    """测试 Bash 工具调用"""

    # 1. 创建 Provider
    print("\n[Step 1] Creating GLM Provider...")
    provider = GLMProvider(
        model="glm-4-flash",
        use_functions_format=True,
    )
    provider.GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    provider.client.base_url = "https://open.bigmodel.cn/api/paas/v4"
    print(f"  [OK] Model: {provider.model}")
    print(f"  [OK] base_url: {provider.GLM_BASE_URL}")

    # 2. 创建工具注册表
    print("\n[Step 2] Creating ToolRegistry...")
    registry = ToolRegistry()
    registry.register(BashTool())
    print(f"  [OK] Registered {len(registry.get_all())} tools")

    # 3. 获取工具 schema
    print("\n[Step 3] Getting tool schemas...")
    schemas = registry.get_schemas()
    print(f"  [OK] {len(schemas)} schemas available")
    for schema in schemas:
        print(f"    - {schema.get('name')}")

    # 4. 创建 AgentEngine
    print("\n[Step 4] Creating AgentEngine...")
    config = AgentConfig(
        system_prompt="你是一个有帮助的 AI 助手，可以执行各种任务。",
        max_iterations=5,
    )

    engine = AgentEngine(
        provider=provider,
        tool_registry=registry,
        config=config,
    )
    print(f"  [OK] Session: {engine.session_id}")

    # 5. 测试 Bash 工具调用
    print("\n[Step 5] Testing Bash tool calling...")
    print("  Prompt: '请使用 bash 工具执行命令：echo Hello World'")

    try:
        response = await engine.run("请使用 bash 工具执行命令：echo Hello World")
        print(f"  [Response]: {response}")

        if "Hello World" in response:
            print(f"  [SUCCESS] Bash tool executed!")
        else:
            print(f"  [WARNING] 'Hello World' not in response")

    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print(" Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(test_bash_tool())
    except KeyboardInterrupt:
        print("\n\n[Interrupted]")
    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()
