"""
OpenAI 提供商

支持 GPT 系列模型
"""

from typing import Any

from openai import AsyncOpenAI

from pyagentforge.core.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.providers.base import BaseProvider
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI (GPT) 提供商"""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, max_tokens, temperature, **kwargs)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        logger.info(
            "Initialized OpenAI provider",
            extra_data={"model": model, "base_url": base_url},
        )

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

            logger.debug(
                "Received OpenAI response",
                extra_data={
                    "stop_reason": stop_reason,
                    "usage": usage,
                    "content_blocks": len(content),
                },
            )

            return ProviderResponse(
                content=content,
                stop_reason=stop_reason,
                usage=usage,
            )

        except Exception as e:
            logger.error(
                "OpenAI API error",
                extra_data={"error": str(e)},
            )
            raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """计算 Token 数量"""
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.model)
            total = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total += len(encoding.encode(content))
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            total += len(encoding.encode(block.get("text", "")))
            return total
        except Exception:
            # 粗略估计
            total = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    total += len(content) // 4
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

        stream = await self.client.chat.completions.create(**params)

        async for chunk in stream:
            yield chunk

        # 最终响应会在流结束后单独处理
