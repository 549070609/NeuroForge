#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test GLM API response directly

直接测试 GLM API 的原始响应
"""

import sys
import asyncio
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent / "pyagentforge"))
sys.path.insert(0, str(Path(__file__).parent.parent / "glm-provider"))

from openai import AsyncOpenAI
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / "glm-provider" / ".env")

async def test_glm_direct():
    """直接测试 GLM API"""

    print("=" * 70)
    print(" GLM API Direct Test")
    print("=" * 70)

    client = AsyncOpenAI(
        api_key=os.environ.get("GLM_API_KEY"),
        base_url=os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
    )

    # Test 1: 使用 functions 格式
    print("\n[Test 1] Using functions format...")

    response = await client.chat.completions.create(
        model="glm-5",
        messages=[
            {"role": "system", "content": "你是一个助手。"},
            {"role": "user", "content": "请将内容 'Hello World' 保存到 test.md 文件"},
        ],
        functions=[
            {
                "name": "write",
                "description": "写入文件",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "文件内容"},
                    },
                    "required": ["file_path", "content"],
                },
            }
        ],
        function_call="auto",
    )

    choice = response.choices[0]
    print(f"  finish_reason: {choice.finish_reason}")
    print(f"  content: {choice.message.content[:100] if choice.message.content else 'None'}")
    print(f"  has function_call: {hasattr(choice.message, 'function_call') and choice.message.function_call}")

    if hasattr(choice.message, 'function_call') and choice.message.function_call:
        fc = choice.message.function_call
        print(f"  function_call.name: {fc.name}")
        print(f"  function_call.arguments type: {type(fc.arguments)}")
        print(f"  function_call.arguments: {fc.arguments}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    asyncio.run(test_glm_direct())
