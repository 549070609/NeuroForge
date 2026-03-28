"""
ScriptedProvider — 按脚本返回预定义响应的 LLM Provider

用于确定性 E2E 测试，无需真实 LLM API 调用。

用法::

    script = (
        ScriptBuilder()
        .add_tool_call("Read", {"path": "/tmp/test.py"})
        .add_text("分析完成，代码质量良好。")
        .build()
    )
    provider = ScriptedProvider(script)
    engine = AgentEngine(provider=provider, tool_registry=tools)
    result = await engine.run("Review this code")
"""

from __future__ import annotations

from collections import deque
from typing import Any

from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)


class ScriptedProvider(BaseProvider):
    """按脚本返回预定义响应的 Provider"""

    def __init__(
        self,
        script: list[ProviderResponse],
        model: str = "scripted-test",
    ) -> None:
        super().__init__(model=model)
        self._script = deque(script)
        self.call_log: list[dict[str, Any]] = []

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        self.call_log.append({
            "system": system,
            "messages": messages,
            "tools": tools,
            "kwargs": kwargs,
        })

        if not self._script:
            return ProviderResponse(
                content=[TextBlock(text="[ScriptedProvider] No more responses in script.")],
                stop_reason="end_turn",
                usage={"input_tokens": 0, "output_tokens": 0},
            )

        return self._script.popleft()

    async def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        return sum(
            len(str(m.get("content", ""))) // 4
            for m in messages
        )

    @property
    def remaining_responses(self) -> int:
        return len(self._script)


class ScriptBuilder:
    """流式构建 ScriptedProvider 的响应脚本"""

    def __init__(self) -> None:
        self._responses: list[ProviderResponse] = []
        self._tool_id_counter = 0

    def add_text(self, text: str) -> ScriptBuilder:
        """添加一个纯文本响应（结束当前迭代）"""
        self._responses.append(ProviderResponse(
            content=[TextBlock(text=text)],
            stop_reason="end_turn",
            usage={"input_tokens": 100, "output_tokens": len(text) // 4},
        ))
        return self

    def add_tool_call(
        self,
        name: str,
        input_data: dict[str, Any] | None = None,
        *,
        also_text: str = "",
    ) -> ScriptBuilder:
        """添加一个工具调用响应（触发工具执行后继续循环）"""
        self._tool_id_counter += 1
        content: list[TextBlock | ToolUseBlock] = []
        if also_text:
            content.append(TextBlock(text=also_text))
        content.append(ToolUseBlock(
            id=f"tool_{self._tool_id_counter:04d}",
            name=name,
            input=input_data or {},
        ))
        self._responses.append(ProviderResponse(
            content=content,
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 50},
        ))
        return self

    def add_multi_tool(
        self,
        calls: list[tuple[str, dict[str, Any]]],
    ) -> ScriptBuilder:
        """添加多工具并行调用响应"""
        content: list[TextBlock | ToolUseBlock] = []
        for name, input_data in calls:
            self._tool_id_counter += 1
            content.append(ToolUseBlock(
                id=f"tool_{self._tool_id_counter:04d}",
                name=name,
                input=input_data,
            ))
        self._responses.append(ProviderResponse(
            content=content,
            stop_reason="tool_use",
            usage={"input_tokens": 100, "output_tokens": 50},
        ))
        return self

    def build(self) -> list[ProviderResponse]:
        return list(self._responses)
