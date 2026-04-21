"""
P1-12 可编程 FakeProvider — 用于故障注入 / 弹性测试。

支持场景：
  - 正常返回
  - 模拟 429 / 500 / 超时 / 半截 SSE
  - 按调用次序编排行为（sequence 模式）
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock


@dataclass
class FakeAction:
    """单次调用行为描述。"""

    text: str = "fake response"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raise_exc: Exception | None = None
    delay: float = 0.0


class FakeProvider(BaseProvider):
    """可编程的 LLM Provider 替身（P1-12 故障注入）。

    用法::

        provider = FakeProvider("fake-model", actions=[
            FakeAction(text="step 1"),
            FakeAction(raise_exc=TimeoutError("boom")),
            FakeAction(text="step 3"),
        ])
        engine = AgentEngine(provider=provider, ...)
    """

    def __init__(
        self,
        model: str = "fake-model",
        *,
        actions: list[FakeAction] | None = None,
        default_action: FakeAction | None = None,
    ) -> None:
        self.model = model
        self._actions = list(actions or [])
        self._default = default_action or FakeAction()
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def _next_action(self) -> FakeAction:
        if self._call_count < len(self._actions):
            action = self._actions[self._call_count]
        else:
            action = self._default
        self._call_count += 1
        return action

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> ProviderResponse:
        action = self._next_action()
        if action.delay > 0:
            await asyncio.sleep(action.delay)
        if action.raise_exc is not None:
            raise action.raise_exc
        content: list = [TextBlock(type="text", text=action.text)]
        for tc in action.tool_calls:
            content.append(ToolUseBlock(
                type="tool_use", id=tc.get("id", "call-1"),
                name=tc.get("name", "unknown"), input=tc.get("input", {}),
            ))
        return ProviderResponse(
            content=content,
            usage={"input_tokens": 10, "output_tokens": 20},
            stop_reason="end_turn" if not action.tool_calls else "tool_use",
        )

    async def count_tokens(self, messages: list[dict]) -> int:
        return sum(len(str(m)) for m in messages)

    async def create_message_stream(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> AsyncIterator[dict]:
        action = self._next_action()
        if action.delay > 0:
            await asyncio.sleep(action.delay)
        if action.raise_exc is not None:
            raise action.raise_exc
        yield {"type": "text", "text": action.text}
        yield {
            "type": "message_complete",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
