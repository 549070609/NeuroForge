"""
Google Generative AI Provider

使用 Google Gemini API 实现 LLM Provider
"""

from typing import Any, AsyncIterator

from pyagentforge.core.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.core.thinking import ThinkingBlock
from pyagentforge.providers.base import BaseProvider
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


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
        """
        初始化 Google Provider

        Args:
            model: 模型 ID (如 gemini-2.0-flash, gemini-1.5-pro)
            api_key: Google API Key (也可通过 GOOGLE_API_KEY 环境变量设置)
            max_tokens: 最大输出 tokens
            temperature: 温度参数
            **kwargs: 额外参数
        """
        super().__init__(model, max_tokens, temperature, **kwargs)
        self.api_key = api_key

        # 延迟导入 google-generativeai
        self._client = None
        self._model_instance = None

    def _get_client(self) -> Any:
        """获取 Google AI 客户端"""
        if self._client is None:
            try:
                import google.generativeai as genai

                # 配置 API Key
                api_key = self.api_key
                if not api_key:
                    import os
                    api_key = os.environ.get("GOOGLE_API_KEY")

                if not api_key:
                    raise ValueError(
                        "Google API Key not provided. "
                        "Set GOOGLE_API_KEY environment variable or pass api_key parameter."
                    )

                genai.configure(api_key=api_key)
                self._client = genai

            except ImportError:
                raise ImportError(
                    "google-generativeai package not installed. "
                    "Install with: pip install google-generativeai"
                )

        return self._client

    def _get_model(self) -> Any:
        """获取模型实例"""
        if self._model_instance is None:
            genai = self._get_client()

            # 配置生成参数
            generation_config = {
                "max_output_tokens": self.max_tokens,
                "temperature": self.temperature,
            }

            # 添加额外参数
            if self.extra_params:
                generation_config.update(self.extra_params)

            self._model_instance = genai.GenerativeModel(
                model_name=self.model,
                generation_config=generation_config,
            )

        return self._model_instance

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        创建消息

        Args:
            system: 系统提示词
            messages: 消息历史
            tools: 可用工具列表
            **kwargs: 额外参数

        Returns:
            Provider 响应
        """
        model = self._get_model()

        # 转换消息格式
        contents = self._convert_messages(messages, system)

        # 转换工具格式
        tool_declarations = self._convert_tools(tools) if tools else None

        try:
            # 调用 API
            if tool_declarations:
                response = await model.generate_content_async(
                    contents,
                    tools=tool_declarations,
                )
            else:
                response = await model.generate_content_async(contents)

            # 解析响应
            return self._parse_response(response)

        except Exception as e:
            logger.error(
                "Google API error",
                extra_data={"error": str(e)},
            )
            raise

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """
        流式创建消息

        Args:
            system: 系统提示词
            messages: 消息历史
            tools: 可用工具列表
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        model = self._get_model()

        # 转换消息格式
        contents = self._convert_messages(messages, system)

        # 转换工具格式
        tool_declarations = self._convert_tools(tools) if tools else None

        try:
            # 流式调用 API
            if tool_declarations:
                response_stream = await model.generate_content_async(
                    contents,
                    tools=tool_declarations,
                    stream=True,
                )
            else:
                response_stream = await model.generate_content_async(
                    contents,
                    stream=True,
                )

            full_text = ""
            full_response = None

            async for chunk in response_stream:
                if chunk.text:
                    full_text += chunk.text
                    yield {"type": "text_delta", "text": chunk.text}
                full_response = chunk

            # 返回完整响应
            if full_response:
                yield self._parse_response(full_response)

        except Exception as e:
            logger.error(
                "Google streaming error",
                extra_data={"error": str(e)},
            )
            raise

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """
        计算 Token 数量

        Args:
            messages: 消息列表

        Returns:
            Token 数量
        """
        model = self._get_model()

        # 简单计算：转换为文本后计算
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
            # 回退到估算
            return len(total_text) // 4

    def _convert_messages(
        self,
        messages: list[dict[str, Any]],
        system: str,
    ) -> list[dict[str, Any]]:
        """
        转换消息格式为 Google 格式

        Google 使用 "user" 和 "model" 角色
        """
        contents = []

        # 添加系统提示作为第一条用户消息
        if system:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System: {system}"}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "I understand. I will follow these instructions."}],
            })

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 转换角色
            google_role = "user" if role == "user" else "model"

            # 处理内容
            if isinstance(content, str):
                parts = [{"text": content}]
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        if "text" in block:
                            parts.append({"text": block["text"]})
                        elif "tool_use" in block or block.get("type") == "tool_use":
                            # 工具调用
                            tool_use = block.get("tool_use", block)
                            parts.append({
                                "function_call": {
                                    "name": tool_use.get("name", ""),
                                    "args": tool_use.get("input", {}),
                                }
                            })
                    elif hasattr(block, "text"):
                        parts.append({"text": block.text})
                if not parts:
                    parts = [{"text": str(content)}]
            else:
                parts = [{"text": str(content)}]

            contents.append({
                "role": google_role,
                "parts": parts,
            })

        return contents

    def _convert_tools(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        转换工具格式为 Google 格式

        Google 使用 FunctionDeclaration 格式
        """
        declarations = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})

                declaration = {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                }

                # 转换参数
                parameters = func.get("parameters", {})
                if parameters:
                    declaration["parameters"] = self._convert_schema(parameters)

                declarations.append(declaration)

        return [{"function_declarations": declarations}] if declarations else None

    def _convert_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """转换 JSON Schema 为 Google 格式"""
        # Google 使用类似的 Schema 格式
        result = {
            "type": schema.get("type", "object"),
        }

        if "properties" in schema:
            result["properties"] = schema["properties"]

        if "required" in schema:
            result["required"] = schema["required"]

        if "description" in schema:
            result["description"] = schema["description"]

        return result

    def _parse_response(self, response: Any) -> ProviderResponse:
        """
        解析 Google API 响应

        Args:
            response: Google API 响应对象

        Returns:
            统一的 Provider 响应
        """
        content_blocks = []
        text_parts = []
        tool_calls = []

        # 获取候选结果
        candidate = response.candidates[0] if response.candidates else None

        if candidate and candidate.content:
            for part in candidate.content.parts:
                # 文本内容
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                    content_blocks.append(TextBlock(type="text", text=part.text))

                # 函数调用
                if hasattr(part, "function_call") and part.function_call:
                    tool_call = ToolUseBlock(
                        type="tool_use",
                        id=f"call_{len(tool_calls) + 1}",
                        name=part.function_call.name,
                        input=dict(part.function_call.args) if part.function_call.args else {},
                    )
                    tool_calls.append(tool_call)
                    content_blocks.append(tool_call)

        # 构建响应
        return ProviderResponse(
            text="".join(text_parts),
            content=content_blocks if content_blocks else [TextBlock(type="text", text="")],
            tool_calls=tool_calls,
            has_tool_calls=len(tool_calls) > 0,
            stop_reason="tool_use" if tool_calls else "end_turn",
            usage={
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
            },
        )
