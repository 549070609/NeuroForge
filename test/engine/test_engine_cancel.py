"""
P0-1 取消测试

验证 AgentEngine.run / run_stream 在 cancel_event 被 set 时
正确抛出 AgentCancelledError。
"""

from __future__ import annotations

import asyncio

import pytest

from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.errors import AgentCancelledError
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.tools.registry import ToolRegistry

from helpers import FastTool, SlowProvider

pytestmark = pytest.mark.asyncio


# -----------------------------------------------------------------------
# run() 路径 — 立即取消
# -----------------------------------------------------------------------

class TestRunCancelImmediate:
    """cancel_event 在 run() 前就已 set → 第一次循环入口即退出"""

    async def test_pre_set_cancel_event_raises(self):
        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[TextBlock(text="should not reach")],
                    stop_reason="end_turn",
                )
            ],
        )
        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
        )

        cancel = asyncio.Event()
        cancel.set()

        with pytest.raises(AgentCancelledError) as exc_info:
            await engine.run("Hello", cancel_event=cancel)

        err = exc_info.value
        assert err.session_id == engine.session_id
        assert err.iteration == 0
        assert provider.call_count == 0


# -----------------------------------------------------------------------
# run() 路径 — 迭代中途取消
# -----------------------------------------------------------------------

class TestRunCancelMidIteration:
    """cancel_event 在工具执行后、下一迭代入口 set → 引擎退出"""

    async def test_cancel_between_iterations(self):
        cancel = asyncio.Event()

        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id="t1",
                            name="fast_tool",
                            input={"input": "go"},
                        )
                    ],
                    stop_reason="tool_use",
                ),
                ProviderResponse(
                    content=[TextBlock(text="should not reach")],
                    stop_reason="end_turn",
                ),
            ],
            delay=0,
        )
        registry = ToolRegistry()
        registry.register(FastTool())

        config = AgentConfig(max_iterations=10)
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        async def cancel_after_first_llm():
            while provider.call_count < 1:
                await asyncio.sleep(0.01)
            cancel.set()

        task = asyncio.create_task(cancel_after_first_llm())

        with pytest.raises(AgentCancelledError) as exc_info:
            await engine.run("Use tool", cancel_event=cancel)

        err = exc_info.value
        assert err.iteration >= 1
        task.cancel()


# -----------------------------------------------------------------------
# run() — 无 cancel_event 时正常执行
# -----------------------------------------------------------------------

class TestRunWithoutCancel:
    """cancel_event=None 时 run 正常完成"""

    async def test_none_cancel_event_works(self):
        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[TextBlock(text="ok")],
                    stop_reason="end_turn",
                )
            ],
        )
        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
        )

        result = await engine.run("Hello", cancel_event=None)
        assert result == "ok"


# -----------------------------------------------------------------------
# run_stream() 路径 — 立即取消
# -----------------------------------------------------------------------

class TestRunStreamCancelImmediate:
    """cancel_event 在 run_stream() 前就已 set → 第一次循环入口即退出"""

    async def test_pre_set_cancel_event_raises(self):
        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[TextBlock(text="should not reach")],
                    stop_reason="end_turn",
                )
            ],
        )
        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
        )

        cancel = asyncio.Event()
        cancel.set()

        with pytest.raises(AgentCancelledError) as exc_info:
            async for _ in engine.run_stream("Hello", cancel_event=cancel):
                pass

        err = exc_info.value
        assert err.session_id == engine.session_id
        assert err.iteration == 0
        assert provider.call_count == 0


# -----------------------------------------------------------------------
# run_stream() 路径 — 迭代中途取消
# -----------------------------------------------------------------------

class TestRunStreamCancelMidIteration:
    """cancel_event 在工具执行后 set → 下一迭代入口退出"""

    async def test_cancel_between_stream_iterations(self):
        cancel = asyncio.Event()

        from pyagentforge.tools.base import BaseTool

        class CancelTriggerTool(BaseTool):
            """执行后设置 cancel_event 的工具"""

            name = "cancel_trigger"
            description = "triggers cancel"
            parameters_schema = {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
            }

            def __init__(self, event: asyncio.Event):
                self._event = event

            async def execute(self, **kwargs):
                self._event.set()
                return "triggered"

        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id="t1",
                            name="cancel_trigger",
                            input={"input": "go"},
                        )
                    ],
                    stop_reason="tool_use",
                ),
                ProviderResponse(
                    content=[TextBlock(text="should not reach")],
                    stop_reason="end_turn",
                ),
            ],
            delay=0,
        )
        registry = ToolRegistry()
        registry.register(CancelTriggerTool(cancel))

        config = AgentConfig(max_iterations=10)
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        with pytest.raises(AgentCancelledError):
            async for _ in engine.run_stream("Use tool", cancel_event=cancel):
                pass


# -----------------------------------------------------------------------
# AgentCancelledError 属性验证
# -----------------------------------------------------------------------

class TestAgentCancelledErrorAttributes:
    """验证异常对象携带完整诊断信息"""

    def test_default_message(self):
        err = AgentCancelledError(session_id="abc", iteration=2)
        assert "cancelled" in str(err).lower()

    def test_attributes(self):
        err = AgentCancelledError(session_id="s1", iteration=5)
        assert err.session_id == "s1"
        assert err.iteration == 5
