#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test GLM Anthropic endpoint directly
直接测试 GLM Anthropic 端点
"""

import os
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).parent.parent / "glm-provider" / ".env")

print("=" * 70)
print(" GLM Anthropic Endpoint Test")
print("=" * 70)

import httpx

async def test_anthropic_endpoint():
    """Test GLM Anthropic endpoint"""

    api_key = os.environ.get("GLM_API_KEY")
    base_url = "https://open.bigmodel.cn/api/anthropic"

    print(f"\nAPI Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Base URL: {base_url}")

    # Anthropic style request
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    # Define tools in Anthropic format
    tools = [
        {
            "name": "bash",
            "description": "Execute a bash command",
            "input_schema": {
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

    payload = {
        "model": "claude-sonnet-4-6",  # GLM Anthropic endpoint uses Claude model names
        "max_tokens": 1024,
        "system": "You are a helpful assistant.",
        "messages": [
            {"role": "user", "content": "Please use bash tool to execute: echo Hello World"}
        ],
        "tools": tools,
    }

    print(f"\n{'='*70}")
    print("Sending Request (Anthropic format)...")
    print("=" * 70)

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{base_url}/v1/messages",
                headers=headers,
                json=payload,
            )

            print(f"\nStatus: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"\n--- Response ---")
                response_str = json.dumps(data, indent=2, ensure_ascii=False)
                print(response_str[:1500])

                # Check for tool use
                content = data.get("content", [])
                has_tool_use = any(block.get("type") == "tool_use" for block in content)

                if has_tool_use:
                    print("\n[SUCCESS] Tool use detected!")
                    for block in content:
                        if block.get("type") == "tool_use":
                            print(f"  Tool: {block.get('name')}")
                            print(f"  Input: {block.get('input')}")
                else:
                    print("\n[FAIL] No tool use in response")
            else:
                print(f"\n[ERROR] {response.text}")

        except Exception as e:
            print(f"\n[ERROR] {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_anthropic_endpoint())
