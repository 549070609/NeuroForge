#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test GLM function calling using official zhipuai SDK
使用官方 zhipuai SDK 测试工具调用
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent.parent / "glm-provider" / ".env")

print("=" * 70)
print(" GLM Function Calling Test - Official SDK")
print("=" * 70)

from zhipuai import ZhipuAI

# Initialize client
api_key = os.environ.get("GLM_API_KEY")
print(f"\nAPI Key: {api_key[:20]}...{api_key[-10:]}")

client = ZhipuAI(api_key=api_key)

# Define tools (functions)
tools = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute bash command",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    }
]

# Test 1: Simple echo command
print("\n" + "=" * 70)
print("Test 1: Simple Echo Command")
print("=" * 70)
print("\nPrompt: 请使用 bash 工具执行命令：echo Hello World")

try:
    response = client.chat.completions.create(
        model="glm-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "请使用 bash 工具执行命令：echo Hello World"}
        ],
        tools=tools,
        tool_choice="auto",
    )

    print("\n--- Response ---")
    print(f"Model: {response.model}")
    print(f"Finish Reason: {response.choices[0].finish_reason}")

    message = response.choices[0].message
    print(f"Content: {message.content[:200] if message.content else 'None'}")
    print(f"Has tool_calls: {message.tool_calls is not None}")

    if message.tool_calls:
        print(f"\nTool Calls Count: {len(message.tool_calls)}")
        for tc in message.tool_calls:
            print(f"  - Function: {tc.function.name}")
            print(f"    Arguments: {tc.function.arguments}")
        print("\n✅ SUCCESS: GLM called the tool!")
    else:
        print("\n❌ FAIL: No tool calls in response")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Using functions format
print("\n" + "=" * 70)
print("Test 2: Using functions format (old OpenAI style)")
print("=" * 70)

functions = [
    {
        "name": "bash",
        "description": "Execute bash command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }
]

print("\nPrompt: 使用 bash 工具执行：echo Test")

try:
    response = client.chat.completions.create(
        model="glm-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "使用 bash 工具执行：echo Test"}
        ],
        functions=functions,
        function_call="auto",
    )

    print("\n--- Response ---")
    print(f"Model: {response.model}")
    print(f"Finish Reason: {response.choices[0].finish_reason}")

    message = response.choices[0].message
    print(f"Content: {message.content[:200] if message.content else 'None'}")
    print(f"Has function_call: {message.function_call is not None}")

    if message.function_call:
        print(f"\nFunction Call: {message.function_call.name}")
        print(f"Arguments: {message.function_call.arguments}")
        print("\n✅ SUCCESS: GLM called the function!")
    else:
        print("\n❌ FAIL: No function call in response")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("Test Complete")
print("=" * 70)
