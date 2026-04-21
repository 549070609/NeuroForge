"""
test/engine 公共可编程替身

提供 SlowProvider / SlowTool / FastTool，用于超时和取消测试。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

ENGINE_ROOT = Path(__file__).resolve().parents[2] / "main" / "agentforge-engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from pyagentforge.kernel.base_provider import BaseProvider
from pyagentforge.kernel.message import ProviderResponse, TextBlock
from pyagentforge.tools.base import BaseTool


class SlowProvider(BaseProvider):
    """可编程延迟的 Provider，用于超时测试。"""

    def __init__(
        self,
        responses: list[ProviderResponse] | None = None,
        delay: float = 0,
        model: str = "test-model",
    ):
        super().__init__(model=model)
        self.responses = responses or []
        self.call_count = 0
        self.delay = delay

    async def create_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        self.call_count += 1
        if self.delay > 0:
            await asyncio.sleep(self.delay)

        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return ProviderResponse(
            content=[TextBlock(text="Default response")],
            stop_reason="end_turn",
        )

    async def count_tokens(self, messages: list[dict]) -> int:
        return sum(len(str(m)) // 4 for m in messages)

    async def stream_message(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs: Any,
    ):
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        response = await self.create_message(system, messages, tools, **kwargs)
        yield response


class SlowTool(BaseTool):
    """可编程延迟的工具，用于超时测试。"""

    name = "slow_tool"
    description = "A tool that sleeps for a configurable duration"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"},
        },
        "required": ["input"],
    }

    def __init__(self, delay: float = 0, return_value: str = "slow tool done"):
        self.delay = delay
        self.return_value = return_value
        self.execute_count = 0

    async def execute(self, **kwargs: Any) -> str:
        self.execute_count += 1
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        return self.return_value


class FastTool(BaseTool):
    """即时完成的工具，用于对照测试。"""

    name = "fast_tool"
    description = "A tool that returns immediately"
    parameters_schema = {
        "type": "object",
        "properties": {
            "input": {"type": "string"},
        },
        "required": ["input"],
    }

    def __init__(self, return_value: str = "fast tool done"):
        self.return_value = return_value

    async def execute(self, **kwargs: Any) -> str:
        return self.return_value
