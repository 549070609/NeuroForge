"""
GLM Provider - 智谱 AI GLM 模型提供商

GLM API 兼容 OpenAI 格式，使用 OpenAI SDK
支持两种工具调用格式：tools (OpenAI 新版) 和 functions (OpenAI 旧版/GLM)
"""

import os
import sys
from typing import Any

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()

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
    支持 GLM-4 系列、GLM-5、GLM-4.7 等模型
    支持两种工具调用格式
    """

    # GLM OpenAI 兼容 API 地址（从环境变量读取）
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
        "glm-4.7",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.95,
        use_functions_format: bool = True,  # 使用 functions 格式（GLM 可能需要）
        **kwargs: Any,
    ) -> None:
        # 从环境变量或参数获取模型名称（优先使用参数）
        selected_model = model or os.environ.get("GLM_MODEL", "glm-4-flash")
        super().__init__(selected_model, max_tokens, temperature, **kwargs)

        # 从环境变量或参数获取 API Key
        self.api_key = api_key or os.environ.get("GLM_API_KEY")
        if not self.api_key:
            raise ValueError("GLM API Key is required. Set GLM_API_KEY environment variable or pass api_key parameter.")

        # 是否使用 functions 格式（GLM 可能需要旧版 OpenAI 格式）
        self.use_functions_format = use_functions_format

        # 创建 OpenAI 兼容客户端
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.GLM_BASE_URL,
        )

        print(f"[GLM Provider] Initialized with model: {selected_model}, base_url: {self.GLM_BASE_URL}")
        print(f"[GLM Provider] Using functions format: {use_functions_format}")

    def _convert_tools_to_openai(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 OpenAI tools 格式（新版）"""
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

    def _convert_tools_to_glm_functions(
        self,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """将工具格式转换为 GLM functions 格式（旧版 OpenAI 格式）

        GLM API 可能使用 functions 参数而非 tools 参数
        参考: https://open.bigmodel.cn/dev/api
        """
        glm_functions = []
        for tool in tools:
            glm_functions.append({
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            })
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
            # 尝试使用 functions 格式（GLM 可能需要）
            if self.use_functions_format:
                params["functions"] = self._convert_tools_to_glm_functions(tools)
                params["function_call"] = "auto"
                # DEBUG: 打印工具定义
                import json
                print(f"[GLM Provider DEBUG] Sending functions (count={len(params['functions'])}):")
                for func in params["functions"]:
                    print(f"  - {func.get('name')}: {func.get('description', '')[:50]}...")
            else:
                params["tools"] = openai_tools
                print(f"[GLM Provider DEBUG] Sending tools (count={len(params['tools'])}):")
                for tool in params["tools"]:
                    print(f"  - {tool.get('function', {}).get('name')}")

        try:
            response = await self.client.chat.completions.create(**params)

            # DEBUG: 打印原始响应（使用 model_dump 而不是 dict）
            try:
                raw_json = response.model_dump_json(indent=2)
                print(f"[GLM Provider DEBUG] Raw response (first 500 chars):")
                print(raw_json[:500])
            except Exception as e:
                print(f"[GLM Provider DEBUG] Could not serialize response: {e}")

            # 解析响应
            content: list[TextBlock | ToolUseBlock] = []
            choice = response.choices[0]

            # DEBUG: 打印原始响应
            print(f"[GLM Provider DEBUG] Response finish_reason: {choice.finish_reason}")
            print(f"[GLM Provider DEBUG] Has tool_calls: {hasattr(choice.message, 'tool_calls')}")
            print(f"[GLM Provider DEBUG] Has function_call: {hasattr(choice.message, 'function_call')}")

            # 更详细的调试
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                print(f"[GLM Provider DEBUG] tool_calls count: {len(choice.message.tool_calls)}")
                for i, tc in enumerate(choice.message.tool_calls):
                    print(f"[GLM Provider DEBUG]   tool_call[{i}]: {tc.function.name if tc.function else 'N/A'}")
            else:
                print(f"[GLM Provider DEBUG] tool_calls is None or empty")

            if hasattr(choice.message, 'function_call') and choice.message.function_call:
                print(f"[GLM Provider DEBUG] function_call name: {choice.message.function_call.name}")
            else:
                print(f"[GLM Provider DEBUG] function_call is None or empty")

            if choice.message.content:
                content.append(TextBlock(text=choice.message.content))

            # 处理 OpenAI 新版 tools 格式
            if hasattr(choice.message, 'tool_calls') and choice.message.tool_calls:
                print(f"[GLM Provider DEBUG] Processing tool_calls: {len(choice.message.tool_calls)} calls")
                import json
                import uuid
                for tc in choice.message.tool_calls:
                    # 关键修复：arguments 可能是 JSON 字符串，需要解析
                    args = tc.function.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                            print(f"[GLM Provider DEBUG] Parsed tool_arguments from JSON string")
                        except json.JSONDecodeError as e:
                            print(f"[GLM Provider DEBUG] Failed to parse tool_arguments: {e}")
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
                    print(f"[GLM Provider DEBUG] Created ToolUseBlock: {tc.function.name}")

            # 处理 OpenAI 旧版 functions 格式（GLM 可能使用这个）
            elif hasattr(choice.message, 'function_call') and choice.message.function_call:
                print(f"[GLM Provider DEBUG] Processing function_call: {choice.message.function_call.name}")
                import json
                import uuid

                # 关键修复：arguments 可能是 JSON 字符串
                args = choice.message.function_call.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                        print(f"[GLM Provider DEBUG] Parsed function_arguments from JSON string")
                    except json.JSONDecodeError as e:
                        print(f"[GLM Provider DEBUG] Failed to parse function_arguments: {e}")
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
                print(f"[GLM Provider DEBUG] Created ToolUseBlock from function_call: {choice.message.function_call.name}")

            # 确定停止原因（关键修复：必须正确识别工具调用）
            finish_reason = choice.finish_reason

            # 如果有工具调用内容，强制设置 stop_reason 为 tool_use
            has_tool_content = any(isinstance(b, ToolUseBlock) for b in content)

            if has_tool_content or finish_reason in ["tool_calls", "function_call"]:
                stop_reason = "tool_use"
                print(f"[GLM Provider DEBUG] Set stop_reason to 'tool_use' (has_tool_content={has_tool_content})")
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
            # 使用 GLM functions 格式
            if self.use_functions_format:
                params["functions"] = self._convert_tools_to_glm_functions(tools)
                params["function_call"] = "auto"
            else:
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
