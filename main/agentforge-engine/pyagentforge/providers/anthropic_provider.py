"""
Anthropic 提供商

支持 Claude 系列模型
"""

from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message as AnthropicMessage

from pyagentforge.kernel.message import (
    ProviderResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)
from pyagentforge.providers.base import BaseProvider
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


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
        self.client = AsyncAnthropic(api_key=api_key)
        logger.info(
            "Initialized Anthropic provider",
            extra_data={"model": model},
        )

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """创建消息"""
        # 构建 API 请求参数
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "system": system,
            "messages": messages,
        }

        # 添加工具
        if tools:
            params["tools"] = tools

        # 添加温度参数
        if "temperature" in kwargs or self.temperature != 1.0:
            params["temperature"] = kwargs.get("temperature", self.temperature)

        # 添加额外参数
        for key in ["top_p", "top_k", "stop_sequences"]:
            if key in kwargs:
                params[key] = kwargs[key]

        try:
            response: AnthropicMessage = await self.client.messages.create(**params)

            # 解析响应内容
            content: list[TextBlock | ToolUseBlock | ThinkingBlock] = []
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
                elif block.type == "thinking":
                    content.append(
                        ThinkingBlock(
                            thinking=block.thinking,
                            signature=getattr(block, "signature", None),
                        )
                    )

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            logger.debug(
                "Received Anthropic response",
                extra_data={
                    "stop_reason": response.stop_reason,
                    "usage": usage,
                    "content_blocks": len(content),
                },
            )

            return ProviderResponse(
                content=content,
                stop_reason=response.stop_reason,
                usage=usage,
            )

        except Exception as e:
            logger.error(
                "Anthropic API error",
                extra_data={"error": str(e)},
            )
            raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """计算 Token 数量"""
        try:
            # 使用 Anthropic 的 Token 计数 API
            total = 0
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    # 粗略估计：每 4 个字符约 1 个 token
                    total += len(content) // 4
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                total += len(block.get("text", "")) // 4
                            elif block.get("type") == "tool_result":
                                total += len(block.get("content", "")) // 4
            return total
        except Exception:
            return 0

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

            # 获取最终响应
            final_response = await stream.get_final_message()

            # 解析最终响应
            content: list[TextBlock | ToolUseBlock | ThinkingBlock] = []
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
                elif block.type == "thinking":
                    content.append(
                        ThinkingBlock(
                            thinking=block.thinking,
                            signature=getattr(block, "signature", None),
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
