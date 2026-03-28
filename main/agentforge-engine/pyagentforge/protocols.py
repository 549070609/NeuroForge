"""协议格式适配与通用 HTTP 调用支持。"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urljoin

from pyagentforge.kernel.message import ProviderResponse, TextBlock, ThinkingBlock, ToolUseBlock
from pyagentforge.kernel.model_registry import ModelConfig


class BaseProtocolAdapter(ABC):
    api_type: str
    endpoint: str

    def build_url(self, config: ModelConfig) -> str:
        if not config.base_url:
            raise ValueError(f"Base URL is required for model: {config.id}")
        return urljoin(config.base_url.rstrip("/") + "/", self.endpoint.lstrip("/"))

    def build_headers(self, config: ModelConfig) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers.update(config.headers)
        return headers

    @abstractmethod
    def build_request(self, request_params: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        pass

    @abstractmethod
    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        pass

    def supports_streaming(self) -> bool:
        return False


class OpenAIChatProtocol(BaseProtocolAdapter):
    api_type = "openai-completions"
    endpoint = "/chat/completions"

    def build_headers(self, config: ModelConfig) -> dict[str, str]:
        headers = super().build_headers(config)
        api_key = config.resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def build_request(self, request_params: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        messages = []
        system = request_params.get("system")
        if system:
            messages.append({"role": "system", "content": system})
        for msg in request_params.get("messages", []):
            messages.extend(self._convert_message(msg))

        params: dict[str, Any] = {
            "model": config.resolved_model_name,
            "messages": messages,
            "max_tokens": request_params.get("max_tokens", config.max_output_tokens),
            "temperature": request_params.get("temperature", 1.0),
        }
        tools = request_params.get("tools")
        if tools:
            params["tools"] = self._convert_tools(tools)
        if request_params.get("stream"):
            params["stream"] = True
        for key in ["top_p", "stop", "presence_penalty", "frequency_penalty", "response_format"]:
            if key in request_params:
                params[key] = request_params[key]
        return params

    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        content: list[TextBlock | ToolUseBlock] = []
        choices = response.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}

        message_content = message.get("content")
        if isinstance(message_content, str) and message_content:
            content.append(TextBlock(text=message_content))
        elif isinstance(message_content, list):
            for block in message_content:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    content.append(TextBlock(text=str(block["text"])))

        for tc in message.get("tool_calls") or []:
            function = tc.get("function") or {}
            arguments = function.get("arguments")
            try:
                tool_input = json.loads(arguments) if isinstance(arguments, str) and arguments else arguments or {}
            except json.JSONDecodeError:
                tool_input = {}
            content.append(
                ToolUseBlock(
                    id=str(tc.get("id", "")),
                    name=str(function.get("name", "")),
                    input=tool_input if isinstance(tool_input, dict) else {},
                )
            )

        finish_reason = choice.get("finish_reason")
        if finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif finish_reason == "length":
            stop_reason = "max_tokens"
        else:
            stop_reason = "end_turn"

        usage = response.get("usage") or {}
        return ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage={
                "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "output_tokens": int(usage.get("completion_tokens", 0) or 0),
            },
        )

    def _convert_message(self, msg: dict[str, Any]) -> list[dict[str, Any]]:
        role = msg.get("role")
        content = msg.get("content")
        if isinstance(content, str):
            return [{"role": role, "content": content}]

        text_parts = []
        tool_calls = []
        converted_messages = []
        for block in content or []:
            if not isinstance(block, dict):
                continue
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
                            "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                        },
                    }
                )
            elif block_type == "tool_result":
                converted_messages.append(
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
            converted_messages.append(msg_dict)
        return converted_messages

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for tool in tools:
            item = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                },
            }
            if "input_schema" in tool:
                item["function"]["parameters"] = tool["input_schema"]
            elif "parameters" in tool:
                item["function"]["parameters"] = tool["parameters"]
            converted.append(item)
        return converted


class AnthropicMessagesProtocol(BaseProtocolAdapter):
    api_type = "anthropic-messages"
    endpoint = "/messages"

    def build_headers(self, config: ModelConfig) -> dict[str, str]:
        headers = super().build_headers(config)
        api_key = config.resolve_api_key()
        if api_key:
            headers["x-api-key"] = api_key
        headers.setdefault("anthropic-version", str(config.extra.get("anthropic_version", "2023-06-01")))
        return headers

    def build_request(self, request_params: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": config.resolved_model_name,
            "max_tokens": request_params.get("max_tokens", config.max_output_tokens),
            "system": request_params.get("system", ""),
            "messages": request_params.get("messages", []),
        }
        tools = request_params.get("tools")
        if tools:
            params["tools"] = self._convert_tools(tools)
        temperature = request_params.get("temperature")
        if temperature is not None and temperature != 1.0:
            params["temperature"] = temperature
        for key in ["top_p", "top_k", "stop_sequences", "thinking"]:
            if key in request_params:
                params[key] = request_params[key]
        return params

    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        content: list[TextBlock | ToolUseBlock | ThinkingBlock] = []
        for block in response.get("content") or []:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                content.append(TextBlock(text=str(block.get("text", ""))))
            elif block_type == "tool_use":
                content.append(
                    ToolUseBlock(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        input=block.get("input", {}) if isinstance(block.get("input"), dict) else {},
                    )
                )
            elif block_type == "thinking":
                content.append(
                    ThinkingBlock(
                        thinking=str(block.get("thinking", "")),
                        signature=block.get("signature"),
                    )
                )

        usage = response.get("usage") or {}
        return ProviderResponse(
            content=content,
            stop_reason=str(response.get("stop_reason", "end_turn")),
            usage={
                "input_tokens": int(usage.get("input_tokens", 0) or 0),
                "output_tokens": int(usage.get("output_tokens", 0) or 0),
            },
        )

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for tool in tools:
            item = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
            }
            if "input_schema" in tool:
                item["input_schema"] = tool["input_schema"]
            elif "parameters" in tool:
                item["input_schema"] = tool["parameters"]
            converted.append(item)
        return converted


class OpenAIResponsesProtocol(BaseProtocolAdapter):
    api_type = "openai-responses"
    endpoint = "/responses"

    def build_headers(self, config: ModelConfig) -> dict[str, str]:
        headers = super().build_headers(config)
        api_key = config.resolve_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def build_request(self, request_params: dict[str, Any], config: ModelConfig) -> dict[str, Any]:
        input_items = []
        system = request_params.get("system")
        if system:
            input_items.append({"role": "system", "content": [{"type": "input_text", "text": system}]})

        for msg in request_params.get("messages", []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, str):
                input_items.append({"role": role, "content": [{"type": "input_text", "text": content}]})
            elif isinstance(content, list):
                blocks = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        blocks.append({"type": "input_text", "text": block.get("text", "")})
                if blocks:
                    input_items.append({"role": role, "content": blocks})

        params: dict[str, Any] = {
            "model": config.resolved_model_name,
            "input": input_items,
            "max_output_tokens": request_params.get("max_tokens", config.max_output_tokens),
        }
        temperature = request_params.get("temperature")
        if temperature is not None:
            params["temperature"] = temperature
        return params

    def parse_response(self, response: dict[str, Any]) -> ProviderResponse:
        content: list[TextBlock | ToolUseBlock] = []
        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "function_call":
                arguments = item.get("arguments")
                try:
                    tool_input = json.loads(arguments) if isinstance(arguments, str) and arguments else arguments or {}
                except json.JSONDecodeError:
                    tool_input = {}
                content.append(
                    ToolUseBlock(
                        id=str(item.get("call_id", item.get("id", ""))),
                        name=str(item.get("name", "")),
                        input=tool_input if isinstance(tool_input, dict) else {},
                    )
                )
                continue

            for block in item.get("content") or []:
                if isinstance(block, dict) and block.get("type") in {"output_text", "text"}:
                    text = block.get("text", "")
                    if text:
                        content.append(TextBlock(text=str(text)))

        usage = response.get("usage") or {}
        stop_reason = "tool_use" if any(isinstance(block, ToolUseBlock) for block in content) else "end_turn"
        return ProviderResponse(
            content=content,
            stop_reason=stop_reason,
            usage={
                "input_tokens": int(usage.get("input_tokens", 0) or 0),
                "output_tokens": int(usage.get("output_tokens", 0) or 0),
            },
        )


PROTOCOL_ADAPTERS: dict[str, BaseProtocolAdapter] = {
    OpenAIChatProtocol.api_type: OpenAIChatProtocol(),
    AnthropicMessagesProtocol.api_type: AnthropicMessagesProtocol(),
    OpenAIResponsesProtocol.api_type: OpenAIResponsesProtocol(),
}
