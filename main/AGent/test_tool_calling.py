#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test tool calling with GLM Provider

测试 GLM Provider 是否能正确调用和执行工具
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
from pyagentforge.tools.builtin import WriteTool

print("=" * 70)
print(" GLM Tool Calling Test")
print("=" * 70)

async def test_tool_calling():
    """测试工具调用"""

    # 1. 创建 Provider（关键：use_functions_format=True，使用标准端点）
    print("\n[Step 1] Creating GLM Provider...")
    provider = GLMProvider(
        model="glm-4-flash",  # 尝试 glm-4-flash（成功测试使用的模型）
        use_functions_format=True,  # 关键！使用 GLM functions 格式
        # base_url 覆盖：使用标准端点而非 Coding Plan
    )
    # 手动覆盖端点
    provider.GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    provider.client.base_url = "https://open.bigmodel.cn/api/paas/v4"
    print(f"  [OK] Model: {provider.model}")
    print(f"  [OK] use_functions_format: {provider.use_functions_format}")
    print(f"  [OK] base_url: {provider.GLM_BASE_URL}")

    # 2. 创建工具注册表
    print("\n[Step 2] Creating ToolRegistry...")
    registry = ToolRegistry()
    registry.register(WriteTool())
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
        system_prompt="""你是一个有帮助的 AI 助手。

# 重要规则
当用户要求执行操作时，你必须调用相应的工具。

## 示例
用户："请将 'Hello' 保存到 test.md"
你的行为：调用 write 工具，参数为 file_path="test.md", content="Hello"
""",
        max_iterations=5,
    )

    engine = AgentEngine(
        provider=provider,
        tool_registry=registry,
        config=config,
    )
    print(f"  [OK] Session: {engine.session_id}")

    # 5. 测试简单对话（无工具）
    print("\n[Step 5] Testing simple conversation (no tool)...")
    try:
        response = await engine.run("你好，请说 '测试成功'")
        print(f"  [OK] Response: {response[:100]}...")
    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()

    # 6. 测试工具调用
    print("\n[Step 6] Testing tool calling...")
    print("  Prompt: '请将以下内容保存到 test_file.md: 这是一个测试文件'")

    try:
        response = await engine.run("请将以下内容保存到 test_file.md: 这是一个测试文件")
        print(f"  [Response]: {response[:200]}...")

        # 检查文件是否被创建
        test_file = Path("test_file.md")
        if test_file.exists():
            print(f"  [SUCCESS] File created!")
            content = test_file.read_text(encoding="utf-8")
            print(f"  [Content]: {content[:100]}...")
            test_file.unlink()  # 清理
        else:
            print(f"  [WARNING] File not created")

    except Exception as e:
        print(f"  [FAIL] {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print(" Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(test_tool_calling())
    except KeyboardInterrupt:
        print("\n\n[Interrupted]")
    except Exception as e:
        print(f"\n[Error] {e}")
        import traceback
        traceback.print_exc()
