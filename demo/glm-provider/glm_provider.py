"""
GLM Provider - 智谱 AI GLM 模型提供商

GLM API 兼容 OpenAI 格式，使用 OpenAI SDK
"""

import os
import sys
from typing import Any

# 添加 pyagentforge 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pyagentforge"))

from openai import AsyncOpenAI

from pyagentforge.core.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.providers.base import BaseProvider


class GLMProvider(BaseProvider):
    """智谱 AI GLM 模型提供商

    GLM API 兼容 OpenAI 格式
    支持 GLM-4 系列、GLM-5 等模型
    """

    # GLM OpenAI 兼容 API 地址
    GLM_BASE_URL = os.environ.get("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")

    # 支持的模型列表
    SUPPORTED_MODELS = [
        "glm-4-plus",
        "glm-4-0520",
        "glm-4-air",
        "glm-4-airx",
        "glm-4-long",
        "glm-4-flash",
        "glm-4",
        "glm-3-turbo",
        "glm-5",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "glm-4-flash",
        max_tokens: int = 4096,
        temperature: float = 0.95,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, max_tokens, temperature, **kwargs)

        # 从环境变量或参数获取 API Key
        self.api_key = api_key or os.environ.get("GLM_API_KEY")
        if not self.api_key:
            raise ValueError("GLM API Key is required. Set GLM_API_KEY environment variable or pass api_key parameter.")

        # 创建 OpenAI 兼容客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.GLM_BASE_URL,
        )

        print(f"[GLM Provider] Initialized with model: {model}, base_url: {self.GLM_BASE_URL}")

    def _convert_tools_to_openai(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 OpenAI 格式"""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return openai_tools

    def _convert_messages_to_openai(
        self,
        system: str,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将消息格式转换为 OpenAI 格式"""
        openai_messages = [{"role": "system", "content": system}]

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if isinstance(content, str):
                openai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                # 处理内容块
                text_parts = []
                tool_calls = []

                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        if block_type == "text":
                            text_parts.append(block.get("text", ""))
                        elif block_type == "tool_use":
                            tool_calls.append({
                                "id": block.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": block.get("name", ""),
                                    "arguments": block.get("input", {}),
                                },
                            })
                        elif block_type == "tool_result":
                            openai_messages.append({
                                "role": "tool",
                                "tool_call_id": block.get("tool_use_id", ""),
                                "content": block.get("content", ""),
                            })

                if text_parts or tool_calls:
                    msg_dict: dict[str, Any] = {"role": role}
                    if text_parts:
                        msg_dict["content"] = "\n".join(text_parts)
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    openai_messages.append(msg_dict)

        return openai_messages

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """创建消息"""
        openai_messages = self._convert_messages_to_openai(system, messages)
        openai_tools = self._convert_tools_to_openai(tools) if tools else None

        params: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if openai_tools:
            params["tools"] = openai_tools

        try:
            response = await self.client.chat.completions.create(**params)

            # 解析响应
            content: list[TextBlock | ToolUseBlock] = []
            choice = response.choices[0]

            if choice.message.content:
                content.append(TextBlock(text=choice.message.content))

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    content.append(
                        ToolUseBlock(
                            id=tc.id,
                            name=tc.function.name,
                            input=tc.function.arguments
                            if isinstance(tc.function.arguments, dict)
                            else {},
                        )
                    )

            # 确定停止原因
            finish_reason = choice.finish_reason
            if finish_reason == "tool_calls":
                stop_reason = "tool_use"
            elif finish_reason == "length":
                stop_reason = "max_tokens"
            else:
                stop_reason = "end_turn"

            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens
                if response.usage
                else 0,
            }

            print(f"[GLM Provider] Response: stop_reason={stop_reason}, usage={usage}")

            return ProviderResponse(
                content=content,
                stop_reason=stop_reason,
                usage=usage,
            )

        except Exception as e:
            print(f"[GLM Provider] API error: {e}")
            raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算 Token 数量"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                # 中文约 1.5 字符/token，英文约 4 字符/token
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
        """流式创建消息"""
        openai_messages = self._convert_messages_to_openai(system, messages)
        openai_tools = self._convert_tools_to_openai(tools) if tools else None

        params: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }

        if openai_tools:
            params["tools"] = openai_tools

        # 收集完整响应用于最终返回
        full_content = ""
        tool_calls_list = []
        finish_reason = "end_turn"
        input_tokens = 0
        output_tokens = 0

        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta

                # 处理文本内容
                if delta.content:
                    full_content += delta.content
                    yield {"type": "text", "text": delta.content}

                # 处理工具调用
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        # OpenAI 流式返回工具调用是增量的，这里简化处理
                        if tc.function and tc.function.name:
                            tool_calls_list.append({
                                "id": tc.id or f"tool_{len(tool_calls_list)}",
                                "name": tc.function.name,
                                "input": tc.function.arguments if isinstance(tc.function.arguments, dict) else {},
                            })

                # 获取结束原因
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            # 获取 usage 信息
            if hasattr(chunk, 'usage') and chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0

        # 构建最终响应
        content = []
        if full_content:
            content.append(TextBlock(text=full_content))
        for tc in tool_calls_list:
            content.append(ToolUseBlock(id=tc["id"], name=tc["name"], input=tc["input"]))

        # 确定停止原因
        if finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        # 返回最终 ProviderResponse
        yield ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )
