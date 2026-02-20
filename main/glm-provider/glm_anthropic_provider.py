"""
GLM Anthropic Provider - 使用 Anthropic 格式调用 GLM API

这个 Provider 使用 GLM 的 Anthropic 兼容端点，支持完整的工具调用能力。
端点: https://open.bigmodel.cn/api/anthropic
"""

import os
import json
import uuid
from typing import Any

from dotenv import load_dotenv
load_dotenv()

import httpx
from pydantic import BaseModel

from pyagentforge.core.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.providers.base import BaseProvider


class GLMAnthropicProvider(BaseProvider):
    """GLM Anthropic 端点提供商

    使用 Anthropic Messages API 格式调用 GLM
    支持完整的工具调用功能
    """

    GLM_ANTHROPIC_URL = os.environ.get(
        "GLM_ANTHROPIC_URL",
        "https://open.bigmodel.cn/api/anthropic"
    )

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-6",  # GLM 会映射到实际模型
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, max_tokens, **kwargs)

        self.api_key = api_key or os.environ.get("GLM_API_KEY")
        if not self.api_key:
            raise ValueError("GLM API Key is required. Set GLM_API_KEY environment variable.")

        print(f"[GLM Anthropic Provider] Initialized")
        print(f"[GLM Anthropic Provider] Endpoint: {self.GLM_ANTHROPIC_URL}")

    def _convert_tools_to_anthropic(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 Anthropic 格式"""
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append({
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema", tool.get("parameters", {})),
            })
        return anthropic_tools

    def _convert_messages_to_anthropic(
        self,
        system: str,
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """将消息格式转换为 Anthropic 格式

        Anthropic 格式:
        - system 是单独的参数
        - messages 只包含 user 和 assistant 消息
        """
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            # 跳过 system 消息（已经单独处理）
            if role == "system":
                continue

            # 处理字符串内容
            if isinstance(content, str):
                anthropic_messages.append({
                    "role": role,
                    "content": content
                })
            # 处理内容块列表
            elif isinstance(content, list):
                blocks = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")

                        if block_type == "text":
                            blocks.append({
                                "type": "text",
                                "text": block.get("text", "")
                            })
                        elif block_type == "tool_use":
                            blocks.append({
                                "type": "tool_use",
                                "id": block.get("id", str(uuid.uuid4())),
                                "name": block.get("name", ""),
                                "input": block.get("input", {})
                            })
                        elif block_type == "tool_result":
                            blocks.append({
                                "type": "tool_result",
                                "tool_use_id": block.get("tool_use_id", ""),
                                "content": block.get("content", "")
                            })

                if blocks:
                    anthropic_messages.append({
                        "role": role,
                        "content": blocks
                    })

        return system, anthropic_messages

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """创建消息 - Anthropic 格式"""

        # 转换消息和工具
        system_prompt, anthropic_messages = self._convert_messages_to_anthropic(system, messages)
        anthropic_tools = self._convert_tools_to_anthropic(tools) if tools else None

        # 构建请求
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "system": system_prompt,
            "messages": anthropic_messages,
        }

        if anthropic_tools:
            payload["tools"] = anthropic_tools

        print(f"[GLM Anthropic Provider] Sending request...")
        print(f"[GLM Anthropic Provider] Tools count: {len(anthropic_tools) if anthropic_tools else 0}")

        # 发送请求
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.GLM_ANTHROPIC_URL}/v1/messages",
                    headers=headers,
                    json=payload,
                )

                response.raise_for_status()
                data = response.json()

                print(f"[GLM Anthropic Provider] Response received")
                print(f"[GLM Anthropic Provider] Model: {data.get('model')}")
                print(f"[GLM Anthropic Provider] Stop reason: {data.get('stop_reason')}")

                # 解析响应
                content: list[TextBlock | ToolUseBlock] = []

                for block in data.get("content", []):
                    block_type = block.get("type")

                    if block_type == "text":
                        content.append(TextBlock(text=block.get("text", "")))
                    elif block_type == "tool_use":
                        content.append(ToolUseBlock(
                            id=block.get("id", str(uuid.uuid4())),
                            name=block.get("name", ""),
                            input=block.get("input", {}),
                        ))
                        print(f"[GLM Anthropic Provider] Tool use: {block.get('name')}")

                # 获取 usage
                usage_data = data.get("usage", {})
                usage = {
                    "input_tokens": usage_data.get("input_tokens", 0),
                    "output_tokens": usage_data.get("output_tokens", 0),
                }

                return ProviderResponse(
                    content=content,
                    stop_reason=data.get("stop_reason", "end_turn"),
                    usage=usage,
                )

            except httpx.HTTPStatusError as e:
                print(f"[GLM Anthropic Provider] HTTP error: {e}")
                print(f"[GLM Anthropic Provider] Response: {e.response.text}")
                raise
            except Exception as e:
                print(f"[GLM Anthropic Provider] Error: {e}")
                raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算 Token 数量"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 3
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total += len(block.get("text", "")) // 3
        return total

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ):
        """流式创建消息 - 暂不支持"""
        raise NotImplementedError("Streaming not yet implemented for GLM Anthropic Provider")
