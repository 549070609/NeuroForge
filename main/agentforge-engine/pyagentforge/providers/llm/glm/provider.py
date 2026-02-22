"""
GLM 统一 Provider - 智谱 AI GLM 模型提供商

支持两种 API 端点:
- OpenAI 兼容端点: https://open.bigmodel.cn/api/paas/v4
- Anthropic 兼容端点: https://open.bigmodel.cn/api/anthropic
"""

from __future__ import annotations

import json
import os
import uuid
from enum import Enum
from typing import Any

import httpx
from openai import AsyncOpenAI

from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class GLMEndpoint(str, Enum):
    """GLM API 端点类型"""

    OPENAI = "openai"  # OpenAI 兼容端点 (/api/paas/v4)
    ANTHROPIC = "anthropic"  # Anthropic 兼容端点 (/api/anthropic)


# 使用模块级延迟导入函数
def _import_dependencies():
    """延迟导入依赖以避免循环导入"""
    from pyagentforge.core.message import (
        ProviderResponse,
        TextBlock,
        ToolUseBlock,
    )
    from pyagentforge.providers.base import BaseProvider

    return BaseProvider, ProviderResponse, TextBlock, ToolUseBlock


# 延迟注册 - 在模块加载完成后执行
def _register_glm_provider():
    """注册 GLM Provider 到 ChineseLLMRegistry"""
    from pyagentforge.providers.llm.registry import ChineseLLMRegistry

    ChineseLLMRegistry._registry["zhipu"] = ChineseLLMRegistry._registry.get(
        "zhipu",
        type(
            "ChineseLLMInfo",
            (),
            {
                "vendor": "zhipu",
                "vendor_name": "智谱",
                "models": [
                    "glm-4-flash",
                    "glm-4-plus",
                    "glm-4-0520",
                    "glm-4-air",
                    "glm-4-airx",
                    "glm-4-long",
                    "glm-4",
                    "glm-3-turbo",
                    "glm-4.7",
                    "glm-5",
                ],
                "provider_class": GLMProvider,
                "default_model": "glm-4-flash",
                "api_key_env": "GLM_API_KEY",
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "description": "智谱 AI GLM 系列大模型",
                "extra": {},
            },
        )(),
    )


class GLMProvider:
    """智谱 AI GLM 统一 Provider

    支持通过 endpoint 参数选择使用 OpenAI 兼容端点或 Anthropic 兼容端点

    Args:
        api_key: API Key，如果不提供则从环境变量 GLM_API_KEY 读取
        model: 模型名称，默认 glm-4-flash
        endpoint: API 端点类型，默认 OPENAI
        max_tokens: 最大输出 Token 数
        temperature: 温度参数
        use_functions_format: (仅 OpenAI 端点) 是否使用 functions 格式

    Example:
        # 使用 OpenAI 兼容端点
        provider = GLMProvider(
            api_key="your-api-key",
            model="glm-4-flash",
            endpoint=GLMEndpoint.OPENAI,
        )

        # 使用 Anthropic 兼容端点
        provider = GLMProvider(
            api_key="your-api-key",
            model="glm-4-flash",
            endpoint=GLMEndpoint.ANTHROPIC,
        )
    """

    # API 端点 URL
    OPENAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
    ANTHROPIC_BASE_URL = "https://open.bigmodel.cn/api/anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "glm-4-flash",
        endpoint: GLMEndpoint = GLMEndpoint.OPENAI,
        max_tokens: int = 4096,
        temperature: float = 0.95,
        use_functions_format: bool = True,
        **kwargs: Any,
    ) -> None:
        # 获取 BaseProvider 并继承
        BaseProvider, _, _, _ = _import_dependencies()

        # 调用父类初始化
        BaseProvider.__init__(self, model, max_tokens, temperature, **kwargs)

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.endpoint = endpoint
        self.use_functions_format = use_functions_format

        # 从环境变量或参数获取 API Key
        self.api_key = api_key or os.environ.get("GLM_API_KEY")
        if not self.api_key:
            raise ValueError(
                "GLM API Key is required. "
                "Set GLM_API_KEY environment variable or pass api_key parameter."
            )

        # 根据端点类型初始化客户端
        if endpoint == GLMEndpoint.OPENAI:
            self._init_openai_client()
        else:
            self._init_anthropic_client()

        logger.info(
            "GLM Provider initialized",
            extra_data={
                "model": model,
                "endpoint": endpoint.value,
                "use_functions_format": use_functions_format,
            },
        )

    def _init_openai_client(self) -> None:
        """初始化 OpenAI 兼容客户端"""
        base_url = os.environ.get("GLM_BASE_URL", self.OPENAI_BASE_URL)
        self._openai_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=base_url,
        )
        self._anthropic_client = None

    def _init_anthropic_client(self) -> None:
        """初始化 Anthropic 端点 (使用 httpx)"""
        self._anthropic_url = os.environ.get(
            "GLM_ANTHROPIC_URL", self.ANTHROPIC_BASE_URL
        )
        self._openai_client = None

    # ==================== OpenAI 端点实现 ====================

    def _convert_tools_to_openai(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 OpenAI tools 格式"""
        openai_tools = []
        for tool in tools:
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                }
            )
        return openai_tools

    def _convert_tools_to_glm_functions(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 GLM functions 格式 (旧版 OpenAI 格式)"""
        glm_functions = []
        for tool in tools:
            glm_functions.append(
                {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            )
        return glm_functions

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
                text_parts = []
                tool_calls = []

                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        if block_type == "text":
                            text_parts.append(block.get("text", ""))
                        elif block_type == "tool_use":
                            tool_calls.append(
                                {
                                    "id": block.get("id", ""),
                                    "type": "function",
                                    "function": {
                                        "name": block.get("name", ""),
                                        "arguments": block.get("input", {}),
                                    },
                                }
                            )
                        elif block_type == "tool_result":
                            openai_messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": block.get("tool_use_id", ""),
                                    "content": block.get("content", ""),
                                }
                            )

                if text_parts or tool_calls:
                    msg_dict: dict[str, Any] = {"role": role}
                    if text_parts:
                        msg_dict["content"] = "\n".join(text_parts)
                    if tool_calls:
                        msg_dict["tool_calls"] = tool_calls
                    openai_messages.append(msg_dict)

        return openai_messages

    async def _create_message_openai(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> "ProviderResponse":
        """使用 OpenAI 兼容端点创建消息"""
        _, ProviderResponse, TextBlock, ToolUseBlock = _import_dependencies()

        openai_messages = self._convert_messages_to_openai(system, messages)
        openai_tools = self._convert_tools_to_openai(tools) if tools else None

        params: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if openai_tools:
            if self.use_functions_format:
                params["functions"] = self._convert_tools_to_glm_functions(tools)
                params["function_call"] = "auto"
            else:
                params["tools"] = openai_tools

        response = await self._openai_client.chat.completions.create(**params)

        # 解析响应
        content: list[Any] = []
        choice = response.choices[0]

        if choice.message.content:
            content.append(TextBlock(text=choice.message.content))

        # 处理 OpenAI 新版 tools 格式
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                elif not isinstance(args, dict):
                    args = {}

                content.append(
                    ToolUseBlock(
                        id=tc.id or f"tool_{uuid.uuid4().hex[:8]}",
                        name=tc.function.name,
                        input=args,
                    )
                )

        # 处理 OpenAI 旧版 functions 格式
        elif (
            hasattr(choice.message, "function_call")
            and choice.message.function_call
        ):
            args = choice.message.function_call.arguments
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            elif not isinstance(args, dict):
                args = {}

            content.append(
                ToolUseBlock(
                    id=f"func_{uuid.uuid4().hex[:8]}",
                    name=choice.message.function_call.name,
                    input=args,
                )
            )

        # 确定停止原因
        finish_reason = choice.finish_reason
        has_tool_content = any(isinstance(b, ToolUseBlock) for b in content)

        if has_tool_content or finish_reason in ["tool_calls", "function_call"]:
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        }

        return ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
        )

    # ==================== Anthropic 端点实现 ====================

    def _convert_tools_to_anthropic(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 Anthropic 格式"""
        anthropic_tools = []
        for tool in tools:
            anthropic_tools.append(
                {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get(
                        "input_schema", tool.get("parameters", {})
                    ),
                }
            )
        return anthropic_tools

    def _convert_messages_to_anthropic(
        self,
        system: str,
        messages: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """将消息格式转换为 Anthropic 格式"""
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role == "system":
                continue

            if isinstance(content, str):
                anthropic_messages.append({"role": role, "content": content})
            elif isinstance(content, list):
                blocks = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get("type")

                        if block_type == "text":
                            blocks.append(
                                {"type": "text", "text": block.get("text", "")}
                            )
                        elif block_type == "tool_use":
                            blocks.append(
                                {
                                    "type": "tool_use",
                                    "id": block.get("id", str(uuid.uuid4())),
                                    "name": block.get("name", ""),
                                    "input": block.get("input", {}),
                                }
                            )
                        elif block_type == "tool_result":
                            blocks.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.get("tool_use_id", ""),
                                    "content": block.get("content", ""),
                                }
                            )

                if blocks:
                    anthropic_messages.append({"role": role, "content": blocks})

        return system, anthropic_messages

    async def _create_message_anthropic(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> "ProviderResponse":
        """使用 Anthropic 兼容端点创建消息"""
        _, ProviderResponse, TextBlock, ToolUseBlock = _import_dependencies()

        system_prompt, anthropic_messages = self._convert_messages_to_anthropic(
            system, messages
        )
        anthropic_tools = (
            self._convert_tools_to_anthropic(tools) if tools else None
        )

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

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._anthropic_url}/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        # 解析响应
        content: list[Any] = []

        for block in data.get("content", []):
            block_type = block.get("type")

            if block_type == "text":
                content.append(TextBlock(text=block.get("text", "")))
            elif block_type == "tool_use":
                content.append(
                    ToolUseBlock(
                        id=block.get("id", str(uuid.uuid4())),
                        name=block.get("name", ""),
                        input=block.get("input", {}),
                    )
                )

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

    # ==================== 公共接口 ====================

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> "ProviderResponse":
        """创建消息

        根据端点类型委托给对应实现
        """
        if self.endpoint == GLMEndpoint.OPENAI:
            return await self._create_message_openai(system, messages, tools, **kwargs)
        else:
            return await self._create_message_anthropic(
                system, messages, tools, **kwargs
            )

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算 Token 数量

        中文约 1.5 字符/token，英文约 4 字符/token
        """
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
        """流式创建消息

        支持两种端点的流式输出
        """
        if self.endpoint == GLMEndpoint.ANTHROPIC:
            async for chunk in self._stream_message_anthropic(
                system, messages, tools, **kwargs
            ):
                yield chunk
            return

        # OpenAI 端点流式实现
        _, ProviderResponse, TextBlock, ToolUseBlock = _import_dependencies()

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
            if self.use_functions_format:
                params["functions"] = self._convert_tools_to_glm_functions(tools)
                params["function_call"] = "auto"
            else:
                params["tools"] = openai_tools

        # 收集完整响应
        full_content = ""
        tool_calls_list: list[dict[str, Any]] = []
        finish_reason = "end_turn"
        input_tokens = 0
        output_tokens = 0

        stream = await self._openai_client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    full_content += delta.content
                    yield {"type": "text", "text": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.function and tc.function.name:
                            tool_calls_list.append(
                                {
                                    "id": tc.id or f"tool_{len(tool_calls_list)}",
                                    "name": tc.function.name,
                                    "input": (
                                        tc.function.arguments
                                        if isinstance(tc.function.arguments, dict)
                                        else {}
                                    ),
                                }
                            )

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

            if hasattr(chunk, "usage") and chunk.usage:
                input_tokens = chunk.usage.prompt_tokens or 0
                output_tokens = chunk.usage.completion_tokens or 0

        # 构建最终响应
        content: list[Any] = []
        if full_content:
            content.append(TextBlock(text=full_content))
        for tc in tool_calls_list:
            content.append(
                ToolUseBlock(id=tc["id"], name=tc["name"], input=tc["input"])
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
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )

    async def _stream_message_anthropic(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ):
        """Anthropic 端点流式实现"""
        import json

        _, ProviderResponse, TextBlock, ToolUseBlock = _import_dependencies()

        system_prompt, anthropic_messages = self._convert_messages_to_anthropic(
            system, messages
        )
        anthropic_tools = (
            self._convert_tools_to_anthropic(tools) if tools else None
        )

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",  # SSE
        }

        payload = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "system": system_prompt,
            "messages": anthropic_messages,
            "stream": True,  # 启用流式
        }

        if anthropic_tools:
            payload["tools"] = anthropic_tools

        # 收集完整响应
        full_content = ""
        tool_use_blocks: list[dict[str, Any]] = []
        current_tool: dict[str, Any] | None = None
        current_tool_input = ""
        stop_reason = "end_turn"
        input_tokens = 0
        output_tokens = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._anthropic_url}/v1/messages",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # 移除 "data: " 前缀
                    if data_str == "[DONE]":
                        break

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    # 处理不同类型的事件
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            full_content += text
                            yield {"type": "text", "text": text}
                        elif delta.get("type") == "input_json_delta":
                            # 工具输入增量
                            partial = delta.get("partial_input", "")
                            if current_tool is not None:
                                current_tool_input += partial

                    elif event_type == "content_block_start":
                        block = event.get("content_block", {})
                        if block.get("type") == "tool_use":
                            current_tool = {
                                "id": event.get("index", len(tool_use_blocks)),
                                "tool_id": block.get("id", ""),
                                "name": block.get("name", ""),
                                "input": {},
                            }

                    elif event_type == "content_block_stop":
                        if current_tool is not None:
                            # 解析完整的工具输入
                            try:
                                current_tool["input"] = json.loads(current_tool_input)
                            except json.JSONDecodeError:
                                current_tool["input"] = {}
                            tool_use_blocks.append(current_tool)
                            current_tool = None
                            current_tool_input = ""

                    elif event_type == "message_delta":
                        delta = event.get("delta", {})
                        if "stop_reason" in delta:
                            stop_reason = delta["stop_reason"]
                        usage = event.get("usage", {})
                        if usage:
                            output_tokens = usage.get("output_tokens", output_tokens)

                    elif event_type == "message_start":
                        message = event.get("message", {})
                        usage = message.get("usage", {})
                        input_tokens = usage.get("input_tokens", 0)

                    elif event_type == "message_stop":
                        break

        # 构建最终响应
        content: list[Any] = []
        if full_content:
            content.append(TextBlock(text=full_content))
        for tool in tool_use_blocks:
            content.append(
                ToolUseBlock(
                    id=tool.get("tool_id", str(uuid.uuid4())),
                    name=tool.get("name", ""),
                    input=tool.get("input", {}),
                )
            )

        # 如果有工具调用，覆盖 stop_reason
        if tool_use_blocks:
            stop_reason = "tool_use"

        yield ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
        )


# 在模块加载后注册 Provider
_register_glm_provider()
