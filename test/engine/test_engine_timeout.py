"""
P0-1 超时测试

验证 AgentEngine.run / run_stream 在 LLM 调用和工具执行超时时
正确抛出 AgentTimeoutError 并携带诊断信息。
"""

from __future__ import annotations

import pytest

from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.errors import AgentTimeoutError
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.tools.registry import ToolRegistry

from helpers import FastTool, SlowProvider, SlowTool


# -----------------------------------------------------------------------
# run() 路径 — LLM 调用超时
# -----------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunLLMTimeout:
    """run() 中 _call_llm 超时 → AgentTimeoutError"""

    @pytest.fixture
    def slow_llm_provider(self) -> SlowProvider:
        return SlowProvider(
            responses=[
                ProviderResponse(
                    content=[TextBlock(text="too slow")],
                    stop_reason="end_turn",
                )
            ],
            delay=5.0,
        )

    async def test_llm_call_timeout_raises(self, slow_llm_provider: SlowProvider):
        config = AgentConfig(timeout=1)
        engine = AgentEngine(
            provider=slow_llm_provider,
            tool_registry=ToolRegistry(),
            config=config,
        )

        with pytest.raises(AgentTimeoutError) as exc_info:
            await engine.run("Hello")

        err = exc_info.value
        assert err.timeout == 1
        assert err.detail == "llm_call"
        assert err.session_id == engine.session_id

    async def test_llm_call_within_timeout_succeeds(self):
        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[TextBlock(text="fast enough")],
                    stop_reason="end_turn",
                )
            ],
            delay=0.1,
        )
        config = AgentConfig(timeout=5)
        engine = AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
            config=config,
        )

        result = await engine.run("Hello")
        assert result == "fast enough"


# -----------------------------------------------------------------------
# run() 路径 — 工具批量执行超时
# -----------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunToolBatchTimeout:
    """run() 中 execute_batch 超时 → AgentTimeoutError(detail='tool_batch_execution')"""

    @pytest.fixture
    def provider_with_tool_call(self) -> SlowProvider:
        return SlowProvider(
            responses=[
                ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id="t1",
                            name="slow_tool",
                            input={"input": "test"},
                        )
                    ],
                    stop_reason="tool_use",
                ),
                ProviderResponse(
                    content=[TextBlock(text="done")],
                    stop_reason="end_turn",
                ),
            ],
            delay=0,
        )

    async def test_tool_batch_timeout_raises(
        self, provider_with_tool_call: SlowProvider
    ):
        registry = ToolRegistry()
        registry.register(SlowTool(delay=5.0))

        config = AgentConfig(timeout=1)
        engine = AgentEngine(
            provider=provider_with_tool_call,
            tool_registry=registry,
            config=config,
        )

        with pytest.raises(AgentTimeoutError) as exc_info:
            await engine.run("Use slow tool")

        err = exc_info.value
        assert err.detail == "tool_batch_execution"
        assert err.timeout == 1
        assert err.iteration == 1

    async def test_fast_tool_within_timeout_succeeds(self):
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
                    content=[TextBlock(text="all done")],
                    stop_reason="end_turn",
                ),
            ],
            delay=0,
        )
        registry = ToolRegistry()
        registry.register(FastTool())

        config = AgentConfig(timeout=5)
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        result = await engine.run("Use fast tool")
        assert result == "all done"


# -----------------------------------------------------------------------
# run_stream() 路径 — LLM 流式超时
# -----------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunStreamLLMTimeout:
    """run_stream() 中 LLM 流式调用超时 → AgentTimeoutError(detail='llm_stream')"""

    @pytest.fixture
    def slow_stream_provider(self) -> SlowProvider:
        return SlowProvider(
            responses=[
                ProviderResponse(
                    content=[TextBlock(text="too slow stream")],
                    stop_reason="end_turn",
                )
            ],
            delay=5.0,
        )

    async def test_stream_llm_timeout_raises(
        self, slow_stream_provider: SlowProvider
    ):
        config = AgentConfig(timeout=1)
        engine = AgentEngine(
            provider=slow_stream_provider,
            tool_registry=ToolRegistry(),
            config=config,
        )

        with pytest.raises(AgentTimeoutError) as exc_info:
            async for _ in engine.run_stream("Hello"):
                pass

        err = exc_info.value
        assert err.detail == "llm_stream"
        assert err.timeout == 1


# -----------------------------------------------------------------------
# run_stream() 路径 — 工具执行超时
# -----------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunStreamToolTimeout:
    """run_stream() 中单工具执行超时 → AgentTimeoutError"""

    async def test_stream_tool_timeout_raises(self):
        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id="t1",
                            name="slow_tool",
                            input={"input": "x"},
                        )
                    ],
                    stop_reason="tool_use",
                ),
                ProviderResponse(
                    content=[TextBlock(text="done")],
                    stop_reason="end_turn",
                ),
            ],
            delay=0,
        )
        registry = ToolRegistry()
        registry.register(SlowTool(delay=5.0))

        config = AgentConfig(timeout=1)
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        with pytest.raises(AgentTimeoutError) as exc_info:
            async for _ in engine.run_stream("Use slow tool"):
                pass

        err = exc_info.value
        assert "tool_execution:slow_tool" in err.detail


# -----------------------------------------------------------------------
# AgentTimeoutError 属性验证
# -----------------------------------------------------------------------

class TestAgentTimeoutErrorAttributes:
    """验证异常对象携带完整诊断信息"""

    def test_default_message(self):
        err = AgentTimeoutError(timeout=30)
        assert "30" in str(err)

    def test_custom_message(self):
        err = AgentTimeoutError("custom msg", timeout=10)
        assert str(err) == "custom msg"

    def test_attributes(self):
        err = AgentTimeoutError(
            session_id="s1",
            iteration=3,
            timeout=60,
            detail="llm_call",
        )
        assert err.session_id == "s1"
        assert err.iteration == 3
        assert err.timeout == 60
        assert err.detail == "llm_call"
