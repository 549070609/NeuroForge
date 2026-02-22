"""
Google Generative AI Provider

支持 Gemini 系列模型
"""

import logging
from typing import Any, AsyncIterator

from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.kernel.base_provider import BaseProvider

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    """Google Generative AI Provider"""

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, max_tokens, temperature, **kwargs)
        self.api_key = api_key
        self._client = None
        self._model_instance = None
        logger.info(f"Initialized Google provider: model={model}")

    def _get_client(self) -> Any:
        """获取 Google AI 客户端"""
        if self._client is None:
            import google.generativeai as genai
            import os

            api_key = self.api_key or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("Google API Key not provided")

            genai.configure(api_key=api_key)
            self._client = genai

        return self._client

    def _get_model(self) -> Any:
        """获取模型实例"""
        if self._model_instance is None:
            genai = self._get_client()
            self._model_instance = genai.GenerativeModel(
                model_name=self.model,
                generation_config={
                    "max_output_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    **self.extra_params,
                },
            )
        return self._model_instance

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """创建消息"""
        model = self._get_model()
        contents = self._convert_messages(messages, system)
        tool_declarations = self._convert_tools(tools) if tools else None

        try:
            if tool_declarations:
                response = await model.generate_content_async(contents, tools=tool_declarations)
            else:
                response = await model.generate_content_async(contents)

            return self._parse_response(response)

        except Exception as e:
            logger.error(f"Google API error: {e}")
            raise

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """流式创建消息"""
        model = self._get_model()
        contents = self._convert_messages(messages, system)
        tool_declarations = self._convert_tools(tools) if tools else None

        try:
            if tool_declarations:
                response_stream = await model.generate_content_async(
                    contents, tools=tool_declarations, stream=True
                )
            else:
                response_stream = await model.generate_content_async(contents, stream=True)

            full_response = None
            async for chunk in response_stream:
                if chunk.text:
                    yield {"type": "text_delta", "text": chunk.text}
                full_response = chunk

            if full_response:
                yield self._parse_response(full_response)

        except Exception as e:
            logger.error(f"Google streaming error: {e}")
            raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """计算 Token 数量"""
        model = self._get_model()
        total_text = ""
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_text += content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        total_text += block["text"]

        try:
            result = model.count_tokens(total_text)
            return result.total_tokens
        except Exception:
            return len(total_text) // 4

    def _convert_messages(
        self, messages: list[dict[str, Any]], system: str
    ) -> list[dict[str, Any]]:
        """转换消息格式为 Google 格式"""
        contents = []

        if system:
            contents.append({"role": "user", "parts": [{"text": f"System: {system}"}]})
            contents.append({
                "role": "model",
                "parts": [{"text": "I understand. I will follow these instructions."}],
            })

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            google_role = "user" if role == "user" else "model"

            if isinstance(content, str):
                parts = [{"text": content}]
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        if "text" in block:
                            parts.append({"text": block["text"]})
                        elif block.get("type") == "tool_use":
                            parts.append({
                                "function_call": {
                                    "name": block.get("name", ""),
                                    "args": block.get("input", {}),
                                }
                            })
                if not parts:
                    parts = [{"text": str(content)}]
            else:
                parts = [{"text": str(content)}]

            contents.append({"role": google_role, "parts": parts})

        return contents

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """转换工具格式为 Google 格式"""
        declarations = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                declaration = {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                }
                parameters = func.get("parameters", {})
                if parameters:
                    declaration["parameters"] = parameters
                declarations.append(declaration)

        return [{"function_declarations": declarations}] if declarations else None

    def _parse_response(self, response: Any) -> ProviderResponse:
        """解析 Google API 响应"""
        content_blocks = []
        tool_calls = []

        candidate = response.candidates[0] if response.candidates else None

        if candidate and candidate.content:
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content_blocks.append(TextBlock(text=part.text))

                if hasattr(part, "function_call") and part.function_call:
                    tool_call = ToolUseBlock(
                        id=f"call_{len(tool_calls) + 1}",
                        name=part.function_call.name,
                        input=dict(part.function_call.args) if part.function_call.args else {},
                    )
                    tool_calls.append(tool_call)
                    content_blocks.append(tool_call)

        return ProviderResponse(
            content=content_blocks if content_blocks else [TextBlock(text="")],
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage={
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
            },
        )
