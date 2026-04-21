"""
P0-2 异常族回归测试

验证 AgentEngine.run / run_stream 在各种错误场景下
抛出正确的 AgentError 子类，而非返回字符串。
"""

from __future__ import annotations

import asyncio

import pytest

from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.errors import (
    AgentError,
    AgentMaxIterationsError,
    AgentProviderError,
    AgentToolError,
)
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.tools.registry import ToolRegistry

from helpers import FastTool, SlowProvider


# -----------------------------------------------------------------------
# run() — max_iterations 抛异常而非返回字符串
# -----------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunMaxIterationsError:
    """run() 达到 max_iterations 时抛 AgentMaxIterationsError"""

    @pytest.fixture
    def infinite_tool_provider(self) -> SlowProvider:
        return SlowProvider(
            responses=[
                ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id=f"t{i}",
                            name="fast_tool",
                            input={"input": f"iter_{i}"},
                        )
                    ],
                    stop_reason="tool_use",
                )
                for i in range(20)
            ],
        )

    async def test_run_raises_max_iterations_error(
        self, infinite_tool_provider: SlowProvider
    ):
        registry = ToolRegistry()
        registry.register(FastTool())

        config = AgentConfig(max_iterations=3)
        engine = AgentEngine(
            provider=infinite_tool_provider,
            tool_registry=registry,
            config=config,
        )

        with pytest.raises(AgentMaxIterationsError) as exc_info:
            await engine.run("Go forever")

        err = exc_info.value
        assert err.max_iterations == 3
        assert err.iteration == 3
        assert err.session_id == engine.session_id

    async def test_run_does_not_return_error_string(
        self, infinite_tool_provider: SlowProvider
    ):
        """确保不再以字符串形式返回错误"""
        registry = ToolRegistry()
        registry.register(FastTool())

        config = AgentConfig(max_iterations=2)
        engine = AgentEngine(
            provider=infinite_tool_provider,
            tool_registry=registry,
            config=config,
        )

        with pytest.raises(AgentMaxIterationsError):
            result = await engine.run("Go")
            assert not isinstance(result, str) or "Error" not in result


# -----------------------------------------------------------------------
# run_stream() — max_iterations 抛异常
# -----------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunStreamMaxIterationsError:
    """run_stream() 达到 max_iterations 时抛 AgentMaxIterationsError"""

    async def test_stream_raises_max_iterations_error(self):
        provider = SlowProvider(
            responses=[
                ProviderResponse(
                    content=[
                        ToolUseBlock(
                            id=f"t{i}",
                            name="fast_tool",
                            input={"input": f"iter_{i}"},
                        )
                    ],
                    stop_reason="tool_use",
                )
                for i in range(20)
            ],
        )
        registry = ToolRegistry()
        registry.register(FastTool())

        config = AgentConfig(max_iterations=2)
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        with pytest.raises(AgentMaxIterationsError) as exc_info:
            async for _ in engine.run_stream("Go forever"):
                pass

        err = exc_info.value
        assert err.max_iterations == 2
        assert err.iteration == 2

    async def test_stream_does_not_yield_error_string(self):
        """确保不再 yield {"type": "error", "message": "Maximum iterations reached"}"""
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
                )
                for _ in range(10)
            ],
        )
        registry = ToolRegistry()
        registry.register(FastTool())

        config = AgentConfig(max_iterations=2)
        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=config,
        )

        events = []
        with pytest.raises(AgentMaxIterationsError):
            async for event in engine.run_stream("Go"):
                events.append(event)

        error_events = [
            e for e in events
            if isinstance(e, dict)
            and e.get("type") == "error"
            and "Maximum iterations" in e.get("message", "")
        ]
        assert len(error_events) == 0


# -----------------------------------------------------------------------
# 异常继承关系
# -----------------------------------------------------------------------

class TestErrorHierarchy:
    """AgentError 是所有引擎异常的基类"""

    def test_max_iterations_is_agent_error(self):
        err = AgentMaxIterationsError(max_iterations=5)
        assert isinstance(err, AgentError)

    def test_provider_error_is_agent_error(self):
        err = AgentProviderError(detail="test")
        assert isinstance(err, AgentError)

    def test_tool_error_is_agent_error(self):
        err = AgentToolError(tool_name="foo")
        assert isinstance(err, AgentError)

    def test_max_iterations_default_message(self):
        err = AgentMaxIterationsError(max_iterations=10)
        assert "10" in str(err)

    def test_provider_error_with_cause(self):
        cause = ValueError("bad response")
        err = AgentProviderError(provider_error=cause)
        assert "bad response" in str(err)

    def test_tool_error_with_name(self):
        err = AgentToolError(tool_name="read_file")
        assert "read_file" in str(err)

    def test_tool_error_attributes(self):
        cause = RuntimeError("boom")
        err = AgentToolError(
            session_id="s1",
            iteration=3,
            tool_name="exec",
            tool_error=cause,
        )
        assert err.session_id == "s1"
        assert err.iteration == 3
        assert err.tool_name == "exec"
        assert err.tool_error is cause
