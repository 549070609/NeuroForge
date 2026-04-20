"""Anthropic Messages 协议适配器（``api_type = anthropic-messages``）。"""

from __future__ import annotations

from typing import Any

from pyagentforge.kernel.message import ProviderResponse, TextBlock, ThinkingBlock, ToolUseBlock
from pyagentforge.kernel.model_registry import ModelConfig
from pyagentforge.protocols import BaseProtocolAdapter


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
