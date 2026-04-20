"""OpenAI Chat Completions 协议适配器（``api_type = openai-completions``）。"""

from __future__ import annotations

import json
from typing import Any

from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.kernel.model_registry import ModelConfig
from pyagentforge.protocols import BaseProtocolAdapter, StreamEvent


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
        stop_reason = self._map_finish_reason(finish_reason)

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

    @staticmethod
    def _map_finish_reason(finish_reason: Any) -> str:
        if finish_reason == "tool_calls":
            return "tool_use"
        if finish_reason == "length":
            return "max_tokens"
        if finish_reason == "stop":
            return "end_turn"
        if finish_reason is None:
            return "end_turn"
        return str(finish_reason)

    # ------------------- 流式 SSE 解析 -------------------

    def parse_stream_chunk_payload(self, payload: dict[str, Any]) -> StreamEvent | None:
        """解析 OpenAI Chat Completion 流式 chunk。

        一帧 ``data: {...}`` 的典型结构::

            {"choices":[{"delta":{"content":"he"},"index":0,"finish_reason":null}]}
            {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"...","type":"function",
                                                  "function":{"name":"...","arguments":"..."}}]}}]}
            {"choices":[{"delta":{},"finish_reason":"stop"}], "usage":{...}}
        """
        usage_payload = payload.get("usage")
        if usage_payload and not payload.get("choices"):
            # 独立 usage 帧（某些厂商单独发送）
            return StreamEvent(
                type="usage",
                usage={
                    "input_tokens": int(usage_payload.get("prompt_tokens", 0) or 0),
                    "output_tokens": int(usage_payload.get("completion_tokens", 0) or 0),
                },
                raw=payload,
            )

        choices = payload.get("choices") or []
        if not choices:
            return None
        choice = choices[0]
        delta = choice.get("delta") or {}
        finish_reason = choice.get("finish_reason")

        # 1) tool_call 分片（优先级最高）
        tool_calls = delta.get("tool_calls") or []
        if tool_calls:
            tc = tool_calls[0]
            function = tc.get("function") or {}
            return StreamEvent(
                type="tool_call_delta",
                tool_call_id=tc.get("id") or None,
                tool_call_name=function.get("name") or None,
                tool_call_arguments_delta=function.get("arguments") or None,
                tool_call_index=tc.get("index") if isinstance(tc.get("index"), int) else 0,
                raw=payload,
            )

        # 2) 文本增量
        content = delta.get("content")
        if isinstance(content, str) and content:
            return StreamEvent(type="text_delta", text=content, raw=payload)

        # 3) finish 信号（即使没有文本也可能携带 usage）
        if finish_reason is not None:
            usage = payload.get("usage") or {}
            return StreamEvent(
                type="done",
                stop_reason=self._map_finish_reason(finish_reason),
                usage={
                    "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
                    "output_tokens": int(usage.get("completion_tokens", 0) or 0),
                } if usage else None,
                raw=payload,
            )

        return None
