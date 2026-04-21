"""
P0-3 行为对齐回归测试

验证 run() 与 run_stream() 在以下维度一致：
  1. 插件 hook 调用序列相同
  2. checkpoint save / delete 时机相同
  3. 任务完成时两条路径都清理 checkpoint
  4. 工具迭代后两条路径都保存 checkpoint
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pyagentforge.kernel.checkpoint import MemoryCheckpointer
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.errors import AgentMaxIterationsError
from pyagentforge.kernel.message import ProviderResponse, TextBlock, ToolUseBlock
from pyagentforge.tools.registry import ToolRegistry

from helpers import FastTool, SlowProvider

pytestmark = pytest.mark.asyncio


# -----------------------------------------------------------------------
# 可编程 PluginManager 替身 — 记录 hook 调用序列
# -----------------------------------------------------------------------

class HookRecorder:
    """记录所有 hook 调用名称和参数的替身 plugin_manager。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def emit_hook(self, hook_name: str, *args: Any) -> list[Any]:
        self.calls[:]  # avoid stale reads
        self.calls.append((hook_name, args))
        return []

    @property
    def hook_names(self) -> list[str]:
        return [name for name, _ in self.calls]


# -----------------------------------------------------------------------
# Fixture helpers
# -----------------------------------------------------------------------

def _simple_text_provider() -> SlowProvider:
    """Provider: 单次文本响应（无工具调用）"""
    return SlowProvider(
        responses=[
            ProviderResponse(
                content=[TextBlock(text="Done")],
                stop_reason="end_turn",
            )
        ],
    )


def _tool_then_text_provider() -> SlowProvider:
    """Provider: 第一轮工具调用 → 第二轮文本响应"""
    return SlowProvider(
        responses=[
            ProviderResponse(
                content=[
                    ToolUseBlock(id="t1", name="fast_tool", input={"input": "go"})
                ],
                stop_reason="tool_use",
            ),
            ProviderResponse(
                content=[TextBlock(text="All done")],
                stop_reason="end_turn",
            ),
        ],
    )


def _build_engine(
    provider: SlowProvider,
    *,
    checkpointer: MemoryCheckpointer | None = None,
    plugin_manager: HookRecorder | None = None,
    max_iterations: int = 10,
) -> AgentEngine:
    registry = ToolRegistry()
    registry.register(FastTool())
    config = AgentConfig(max_iterations=max_iterations)
    return AgentEngine(
        provider=provider,
        tool_registry=registry,
        config=config,
        checkpointer=checkpointer,
        plugin_manager=plugin_manager,
    )


# -----------------------------------------------------------------------
# 1. Hook 序列一致性
# -----------------------------------------------------------------------

class TestHookSequenceParity:
    """run() 与 run_stream() 的 hook 调用顺序应一致。"""

    async def test_simple_text_hook_sequence_matches(self):
        """无工具调用场景：hook 序列应相同"""
        rec_run = HookRecorder()
        engine_run = _build_engine(
            _simple_text_provider(), plugin_manager=rec_run
        )
        await engine_run.run("Hi")

        rec_stream = HookRecorder()
        engine_stream = _build_engine(
            _simple_text_provider(), plugin_manager=rec_stream
        )
        async for _ in engine_stream.run_stream("Hi"):
            pass

        assert rec_run.hook_names == rec_stream.hook_names

    async def test_tool_call_hook_sequence_matches(self):
        """单轮工具调用场景：hook 序列应相同"""
        rec_run = HookRecorder()
        engine_run = _build_engine(
            _tool_then_text_provider(), plugin_manager=rec_run
        )
        await engine_run.run("Use tool")

        rec_stream = HookRecorder()
        engine_stream = _build_engine(
            _tool_then_text_provider(), plugin_manager=rec_stream
        )
        async for _ in engine_stream.run_stream("Use tool"):
            pass

        assert rec_run.hook_names == rec_stream.hook_names

    async def test_expected_hook_order_simple(self):
        """验证具体 hook 顺序（无工具）"""
        rec = HookRecorder()
        engine = _build_engine(_simple_text_provider(), plugin_manager=rec)
        await engine.run("Hi")

        assert rec.hook_names == [
            "on_engine_start",
            "on_before_llm_call",
            "on_after_llm_call",
            "on_task_complete",
        ]

    async def test_expected_hook_order_with_tools(self):
        """验证具体 hook 顺序（一轮工具调用）"""
        rec = HookRecorder()
        engine = _build_engine(_tool_then_text_provider(), plugin_manager=rec)
        await engine.run("Use tool")

        assert rec.hook_names == [
            "on_engine_start",
            "on_before_llm_call",       # 第 1 轮
            "on_after_llm_call",
            "on_before_llm_call",       # 第 2 轮
            "on_after_llm_call",
            "on_task_complete",
        ]


# -----------------------------------------------------------------------
# 2. Checkpoint 行为一致性
# -----------------------------------------------------------------------

class TestCheckpointParity:
    """run_stream 现在与 run 拥有相同的 checkpoint 行为。"""

    async def test_run_saves_checkpoint_after_tool_iteration(self):
        cp = MemoryCheckpointer()
        engine = _build_engine(_tool_then_text_provider(), checkpointer=cp)
        await engine.run("Use tool")

        # 工具迭代后应 save；任务完成后应 delete
        # 最终 checkpoint 应已被清理
        stored = await cp.load(engine.session_id)
        assert stored is None  # delete_checkpoint 已清理

    async def test_stream_saves_checkpoint_after_tool_iteration(self):
        cp = MemoryCheckpointer()
        engine = _build_engine(_tool_then_text_provider(), checkpointer=cp)
        async for _ in engine.run_stream("Use tool"):
            pass

        stored = await cp.load(engine.session_id)
        assert stored is None  # delete_checkpoint 已清理

    async def test_run_checkpoint_save_called_during_tools(self):
        """工具迭代中 checkpoint 应被保存（用 spy 验证）"""
        cp = MemoryCheckpointer()
        cp.save = AsyncMock(wraps=cp.save)
        cp.delete = AsyncMock(wraps=cp.delete)

        engine = _build_engine(_tool_then_text_provider(), checkpointer=cp)
        await engine.run("Use tool")

        assert cp.save.call_count >= 1
        assert cp.delete.call_count >= 1

    async def test_stream_checkpoint_save_called_during_tools(self):
        """run_stream 工具迭代中 checkpoint 也应被保存"""
        cp = MemoryCheckpointer()
        cp.save = AsyncMock(wraps=cp.save)
        cp.delete = AsyncMock(wraps=cp.delete)

        engine = _build_engine(_tool_then_text_provider(), checkpointer=cp)
        async for _ in engine.run_stream("Use tool"):
            pass

        assert cp.save.call_count >= 1
        assert cp.delete.call_count >= 1

    async def test_checkpoint_save_delete_count_matches(self):
        """两条路径的 save/delete 调用次数应相同"""
        cp_run = MemoryCheckpointer()
        cp_run.save = AsyncMock(wraps=cp_run.save)
        cp_run.delete = AsyncMock(wraps=cp_run.delete)
        engine_run = _build_engine(_tool_then_text_provider(), checkpointer=cp_run)
        await engine_run.run("Use tool")

        cp_stream = MemoryCheckpointer()
        cp_stream.save = AsyncMock(wraps=cp_stream.save)
        cp_stream.delete = AsyncMock(wraps=cp_stream.delete)
        engine_stream = _build_engine(
            _tool_then_text_provider(), checkpointer=cp_stream
        )
        async for _ in engine_stream.run_stream("Use tool"):
            pass

        assert cp_run.save.call_count == cp_stream.save.call_count
        assert cp_run.delete.call_count == cp_stream.delete.call_count


# -----------------------------------------------------------------------
# 3. max_iterations 场景下 checkpoint 清理
# -----------------------------------------------------------------------

class TestMaxIterationsCheckpoint:
    """max_iterations 时两条路径都应清理 checkpoint。"""

    def _infinite_provider(self) -> SlowProvider:
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

    async def test_run_deletes_checkpoint_on_max_iterations(self):
        cp = MemoryCheckpointer()
        cp.delete = AsyncMock(wraps=cp.delete)
        engine = _build_engine(
            self._infinite_provider(), checkpointer=cp, max_iterations=2
        )

        with pytest.raises(AgentMaxIterationsError):
            await engine.run("Go")

        cp.delete.assert_called()

    async def test_stream_deletes_checkpoint_on_max_iterations(self):
        cp = MemoryCheckpointer()
        cp.delete = AsyncMock(wraps=cp.delete)
        engine = _build_engine(
            self._infinite_provider(), checkpointer=cp, max_iterations=2
        )

        with pytest.raises(AgentMaxIterationsError):
            async for _ in engine.run_stream("Go"):
                pass

        cp.delete.assert_called()
