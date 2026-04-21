"""P0-6 Observability metrics + hooks 回归测试"""

from __future__ import annotations

import pytest

from pyagentforge.observability import (
    InMemoryBackend,
    MetricsCollector,
    NoOpBackend,
    ObservabilityHooks,
    get_collector,
    set_collector,
)


# ── InMemoryBackend 基础 ──────────────────────────────────────

class TestInMemoryBackend:
    def test_counter_accumulates(self):
        b = InMemoryBackend()
        b.inc_counter("agent_iterations_total")
        b.inc_counter("agent_iterations_total")
        b.inc_counter("agent_iterations_total", value=3.0)
        assert b.get_counter("agent_iterations_total") == 5.0

    def test_counter_with_labels_separate(self):
        b = InMemoryBackend()
        b.inc_counter("llm_tokens_total", labels={"model": "a", "type": "input"})
        b.inc_counter("llm_tokens_total", labels={"model": "a", "type": "output"})
        b.inc_counter("llm_tokens_total", labels={"model": "b", "type": "input"})

        assert b.get_counter("llm_tokens_total",
                             labels={"model": "a", "type": "input"}) == 1.0
        assert b.get_counter("llm_tokens_total",
                             labels={"model": "a", "type": "output"}) == 1.0
        assert b.get_counter("llm_tokens_total",
                             labels={"model": "b", "type": "input"}) == 1.0

    def test_histogram_records_observations(self):
        b = InMemoryBackend()
        b.observe_histogram("llm_latency_seconds", 0.5, labels={"model": "a"})
        b.observe_histogram("llm_latency_seconds", 1.2, labels={"model": "a"})
        values = b.get_histogram_values("llm_latency_seconds", labels={"model": "a"})
        assert values == [0.5, 1.2]

    def test_clear(self):
        b = InMemoryBackend()
        b.inc_counter("x")
        b.observe_histogram("y", 1.0)
        b.clear()
        assert b.counter_names() == []
        assert b.histogram_names() == []


# ── NoOpBackend ──────────────────────────────────────────────

class TestNoOpBackend:
    def test_silent(self):
        b = NoOpBackend()
        b.inc_counter("foo")
        b.observe_histogram("bar", 1.0)


# ── MetricsCollector 门面 ────────────────────────────────────

class TestMetricsCollector:
    def test_collector_delegates_to_backend(self):
        b = InMemoryBackend()
        c = MetricsCollector(backend=b)
        c.inc("agent_iterations_total")
        c.observe("llm_latency_seconds", 0.3, model="gpt")
        assert b.get_counter("agent_iterations_total") == 1.0
        assert b.get_histogram_values(
            "llm_latency_seconds", labels={"model": "gpt"}
        ) == [0.3]

    def test_default_collector_is_noop(self):
        # 重置全局 collector 为默认
        set_collector(MetricsCollector())
        c = get_collector()
        # 不抛错即可
        c.inc("foo")
        c.observe("bar", 1.0)


# ── ObservabilityHooks 集成 AgentEngine ──────────────────────

@pytest.mark.asyncio
class TestObservabilityHooks:
    """hooks 被 AgentEngine 调用时应产生 metrics。"""

    async def test_hooks_produce_metrics_on_llm_cycle(self):
        backend = InMemoryBackend()
        collector = MetricsCollector(backend=backend)
        hooks = ObservabilityHooks(collector=collector)

        # 模拟引擎一次完整 LLM 调用
        await hooks.emit_hook("on_engine_start", object())
        await hooks.emit_hook("on_before_llm_call", ["msg"])

        class FakeUsage:
            input_tokens = 10
            output_tokens = 20

        class FakeResponse:
            model = "test-model"
            usage = FakeUsage()

        await hooks.emit_hook("on_after_llm_call", FakeResponse())

        assert backend.get_counter("agent_iterations_total") == 1.0
        assert backend.get_counter(
            "llm_tokens_total",
            labels={"model": "test-model", "type": "input_tokens"},
        ) == 10.0
        assert backend.get_counter(
            "llm_tokens_total",
            labels={"model": "test-model", "type": "output_tokens"},
        ) == 20.0
        # latency 至少记录了一次
        values = backend.get_histogram_values(
            "llm_latency_seconds", labels={"model": "test-model"}
        )
        assert len(values) == 1
        assert values[0] >= 0

    async def test_hooks_record_run_duration_on_complete(self):
        backend = InMemoryBackend()
        hooks = ObservabilityHooks(collector=MetricsCollector(backend=backend))

        await hooks.emit_hook("on_engine_start", object())
        await hooks.emit_hook("on_task_complete", "done")

        vals = backend.get_histogram_values("agent_run_duration_seconds")
        assert len(vals) == 1

    async def test_hooks_tolerate_missing_usage(self):
        """response 无 usage / model 也不应报错。"""
        backend = InMemoryBackend()
        hooks = ObservabilityHooks(collector=MetricsCollector(backend=backend))

        await hooks.emit_hook("on_before_llm_call", ["msg"])

        class BareResponse:
            pass

        await hooks.emit_hook("on_after_llm_call", BareResponse())
        # iteration 仍被计数
        assert backend.get_counter("agent_iterations_total") == 1.0

    async def test_hook_errors_do_not_propagate(self):
        """可观测性 handler 抛错不应中断引擎。"""
        backend = InMemoryBackend()
        hooks = ObservabilityHooks(collector=MetricsCollector(backend=backend))

        # 传递错误类型参数触发内部异常
        class BadRecord:
            @property
            def model(self):
                raise RuntimeError("boom")

        # emit_hook 应吞掉异常并返回 []
        result = await hooks.emit_hook("on_after_llm_call", BadRecord())
        assert result == []

    async def test_unknown_hook_is_noop(self):
        hooks = ObservabilityHooks()
        result = await hooks.emit_hook("on_nonexistent_hook", object())
        assert result == []
