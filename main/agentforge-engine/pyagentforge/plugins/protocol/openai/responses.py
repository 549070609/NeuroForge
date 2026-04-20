"""OpenAI Responses 协议适配器（``api_type = openai-responses``）。"""

from __future__ import annotations

import json
from typing import Any

from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.kernel.model_registry import ModelConfig
from pyagentforge.protocols import BaseProtocolAdapter


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
