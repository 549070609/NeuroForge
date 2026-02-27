"""
OpenAI 提供商

支持 GPT 系列模型
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
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        logger.info(f"Initialized OpenAI provider: model={model}")

    def _convert_tools_to_openai(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """将工具格式转换为 OpenAI 格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            }
            for tool in tools
        ]

    def _convert_messages_to_openai(
        self, system: str, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """将消息格式转换为 OpenAI 格式"""
        openai_messages = [{"role": "system", "content": system}]

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if isinstance(content, str):
                openai_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
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

            finish_reason = choice.finish_reason
            if finish_reason == "tool_calls":
                stop_reason = "tool_use"
            elif finish_reason == "length":
                stop_reason = "max_tokens"
            else:
                stop_reason = "end_turn"

            usage = {
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            }

            logger.debug(f"OpenAI response: stop={stop_reason}, usage={usage}")

            return ProviderResponse(
                content=content,
                stop_reason=stop_reason,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
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
        import json as _json

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

        full_text = ""
        tool_calls_map: dict[int, dict[str, Any]] = {}
        finish_reason = "end_turn"
        prompt_tokens = 0
        completion_tokens = 0

        async for chunk in stream:
            if not chunk.choices:
                if hasattr(chunk, "usage") and chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens or 0
                    completion_tokens = chunk.usage.completion_tokens or 0
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if delta and delta.content:
                full_text += delta.content
                yield {"type": "text_delta", "text": delta.content}

            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_map:
                        tool_calls_map[idx] = {
                            "id": tc_delta.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    entry = tool_calls_map[idx]
                    if tc_delta.id:
                        entry["id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["arguments"] += tc_delta.function.arguments

            if choice.finish_reason:
                finish_reason = choice.finish_reason

            if hasattr(chunk, "usage") and chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens or 0
                completion_tokens = chunk.usage.completion_tokens or 0

        content: list[TextBlock | ToolUseBlock] = []
        if full_text:
            content.append(TextBlock(text=full_text))

        for _idx in sorted(tool_calls_map):
            tc_data = tool_calls_map[_idx]
            try:
                tool_input = (
                    _json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                )
            except _json.JSONDecodeError:
                tool_input = {}
            content.append(
                ToolUseBlock(id=tc_data["id"], name=tc_data["name"], input=tool_input)
            )

        if finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        yield ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage={"input_tokens": prompt_tokens, "output_tokens": completion_tokens},
        )
