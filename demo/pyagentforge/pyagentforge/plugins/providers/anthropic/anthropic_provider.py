"""
Anthropic 提供商

支持 Claude 系列模型
"""

import logging
from typing import Any

from pyagentforge.kernel.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.kernel.base_provider import BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic (Claude) 提供商"""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, max_tokens, temperature, **kwargs)
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic(api_key=api_key)
        logger.info(f"Initialized Anthropic provider: model={model}")

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """创建消息"""
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "system": system,
            "messages": messages,
        }

        if tools:
            params["tools"] = tools

        if "temperature" in kwargs or self.temperature != 1.0:
            params["temperature"] = kwargs.get("temperature", self.temperature)

        for key in ["top_p", "top_k", "stop_sequences"]:
            if key in kwargs:
                params[key] = kwargs[key]

        try:
            response = await self.client.messages.create(**params)

            content: list[TextBlock | ToolUseBlock] = []
            for block in response.content:
                if block.type == "text":
                    content.append(TextBlock(text=block.text))
                elif block.type == "tool_use":
                    content.append(
                        ToolUseBlock(
                            id=block.id,
                            name=block.name,
                            input=block.input,
                        )
                    )

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            logger.debug(f"Anthropic response: stop={response.stop_reason}, usage={usage}")

            return ProviderResponse(
                content=content,
                stop_reason=response.stop_reason,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """计算 Token 数量"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            total += len(block.get("text", "")) // 4
                        elif block.get("type") == "tool_result":
                            total += len(block.get("content", "")) // 4
        return total

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ):
        """流式创建消息"""
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "system": system,
            "messages": messages,
        }

        if tools:
            params["tools"] = tools

        if "temperature" in kwargs or self.temperature != 1.0:
            params["temperature"] = kwargs.get("temperature", self.temperature)

        async with self.client.messages.stream(**params) as stream:
            async for event in stream:
                yield event

            final_response = await stream.get_final_message()

            content: list[TextBlock | ToolUseBlock] = []
            for block in final_response.content:
                if block.type == "text":
                    content.append(TextBlock(text=block.text))
                elif block.type == "tool_use":
                    content.append(
                        ToolUseBlock(
                            id=block.id,
                            name=block.name,
                            input=block.input,
                        )
                    )

            yield ProviderResponse(
                content=content,
                stop_reason=final_response.stop_reason,
                usage={
                    "input_tokens": final_response.usage.input_tokens,
                    "output_tokens": final_response.usage.output_tokens,
                },
            )
