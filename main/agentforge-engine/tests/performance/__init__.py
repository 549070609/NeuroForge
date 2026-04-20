"""
Performance Tests for PyAgentForge

This module contains performance benchmarks and stress tests to ensure
the system meets performance requirements under various load conditions.
"""

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from pyagentforge.kernel.concurrency_manager import ConcurrencyConfig, ConcurrencyManager
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.message import (
    ProviderResponse,
    TextBlock,
    ToolUseBlock,
)
from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.registry import ToolRegistry
from tests.test_config import PerformanceMetrics, TestConfig

# ============================================================================
# Performance Test Utilities
# ============================================================================

@dataclass
class BenchmarkResult:
    """Result of a performance benchmark."""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    ops_per_second: float
    errors: int = 0

    @classmethod
    def from_metrics(cls, name: str, metrics: PerformanceMetrics) -> "BenchmarkResult":
        """Create result from performance metrics."""
        return cls(
            name=name,
            iterations=metrics.iterations,
            total_time=metrics.total_time,
            avg_time=metrics.avg_time,
            min_time=metrics.min_time if metrics.min_time != float('inf') else 0,
            max_time=metrics.max_time,
            ops_per_second=metrics.iterations / metrics.total_time if metrics.total_time > 0 else 0,
            errors=metrics.errors,
        )


async def benchmark_async(
    func: Any,
    iterations: int = 100,
    warmup: int = 10,
    **kwargs,
) -> BenchmarkResult:
    """
    Benchmark an async function.

    Args:
        func: Async function to benchmark.
        iterations: Number of iterations to run.
        warmup: Number of warmup iterations (not counted).
        **kwargs: Arguments to pass to the function.

    Returns:
        BenchmarkResult with timing statistics.
    """
    metrics = PerformanceMetrics()

    # Warmup iterations
    for _ in range(warmup):
        with contextlib.suppress(Exception):
            await func(**kwargs)

    # Benchmark iterations
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            await func(**kwargs)
            elapsed = time.perf_counter() - start
            metrics.add_result(elapsed, error=False)
        except Exception:
            elapsed = time.perf_counter() - start
            metrics.add_result(elapsed, error=True)

    return BenchmarkResult.from_metrics(func.__name__, metrics)


# ============================================================================
# Mock Components for Performance Testing
# ============================================================================

class FastMockProvider:
    """Fast mock provider for performance testing."""

    def __init__(self):
        self.model = "perf-test-model"
        self.max_tokens = 4096
        self.call_count = 0

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Fast response without any delay."""
        self.call_count += 1
        return ProviderResponse(
            content=[TextBlock(text="Response")],
            stop_reason="end_turn",
        )

    async def stream_message(self, system: str, messages: list[dict], tools: list[dict] | None = None, **kwargs):
        """Mock streaming."""
        response = await self.create_message(system, messages, tools, **kwargs)
        yield response


class SlowMockProvider:
    """Mock provider with intentional delay for latency testing."""

    def __init__(self, delay: float = 0.1):
        self.model = "slow-perf-test-model"
        self.max_tokens = 4096
        self.delay = delay
        self.call_count = 0

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """Response with configurable delay."""
        self.call_count += 1
        await asyncio.sleep(self.delay)
        return ProviderResponse(
            content=[TextBlock(text="Response")],
            stop_reason="end_turn",
        )


# ============================================================================
# Performance Tests: Core Operations
# ============================================================================

class TestCorePerformance:
    """Performance tests for core operations."""

    @pytest.fixture
    def perf_setup(self):
        """Set up performance test environment."""
        provider = FastMockProvider()
        registry = ToolRegistry()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        return {"provider": provider, "registry": registry, "engine": engine}

    @pytest.mark.asyncio
    async def test_simple_message_performance(self, perf_setup):
        """
        Performance Test: Simple message processing speed

        Requirements:
        - Average response time < 50ms (with mock provider)
        - No errors under normal load
        """
        engine = perf_setup["engine"]

        async def send_message():
            return await engine.run("Hello")

        result = await benchmark_async(send_message, iterations=50, warmup=5)

        print(f"\nSimple Message Benchmark: {result}")

        # Assert performance requirements
        assert result.errors == 0, "No errors should occur"
        assert result.avg_time < 0.05, f"Average time should be < 50ms, got {result.avg_time * 1000:.2f}ms"
        assert result.ops_per_second > 20, f"Should handle > 20 ops/sec, got {result.ops_per_second:.2f}"

    @pytest.mark.asyncio
    async def test_context_add_performance(self):
        """
        Performance Test: Context message addition speed

        Requirements:
        - Adding messages should be O(1)
        - Should handle 1000 messages in < 100ms total
        """
        context = ContextManager()

        async def add_message():
            context.add_message("user", "Test message content")
            return True

        result = await benchmark_async(add_message, iterations=1000, warmup=10)

        print(f"\nContext Add Benchmark: {result}")

        assert result.total_time < 0.1, f"Adding 1000 messages should take < 100ms, got {result.total_time * 1000:.2f}ms"


# ============================================================================
# Performance Tests: Concurrency
# ============================================================================

class TestConcurrencyPerformance:
    """Performance tests for concurrent operations."""

    @pytest.mark.asyncio
    async def test_concurrent_engine_runs(self):
        """
        Performance Test: Concurrent engine execution

        Requirements:
        - Should handle 10 concurrent runs efficiently
        - Total time should be close to single run time (parallel execution)
        """
        provider = FastMockProvider()
        registry = ToolRegistry()

        async def run_engine():
            engine = AgentEngine(
                provider=provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=10),
            )
            return await engine.run("Hello")

        # Run 10 concurrent operations
        start = time.perf_counter()
        results = await asyncio.gather(*[run_engine() for _ in range(10)])
        elapsed = time.perf_counter() - start

        assert len(results) == 10
        # With mock provider, 10 concurrent should complete in < 1 second
        assert elapsed < 1.0, f"10 concurrent runs took {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_concurrency_manager_throughput(self):
        """
        Performance Test: Concurrency manager throughput

        Requirements:
        - Should handle high request throughput
        - Should not significantly bottleneck operations
        """
        config = ConcurrencyConfig(max_global=100, max_per_model=50)
        manager = ConcurrencyManager(config=config)

        async def acquire_release():
            async with manager.acquire("test-model"):
                await asyncio.sleep(0.001)  # Simulate small work
            return True

        # Run 100 concurrent operations
        start = time.perf_counter()
        results = await asyncio.gather(*[acquire_release() for _ in range(100)])
        elapsed = time.perf_counter() - start

        manager.clear()

        assert len(results) == 100
        # Should handle 100 operations efficiently
        assert elapsed < 2.0, f"100 concurrent operations took {elapsed:.2f}s"


# ============================================================================
# Performance Tests: Memory Efficiency
# ============================================================================

class TestMemoryEfficiency:
    """Tests for memory efficiency."""

    @pytest.mark.asyncio
    async def test_context_memory_growth(self):
        """
        Performance Test: Context memory growth

        Requirements:
        - Memory should not grow unbounded
        - Truncation should keep memory bounded
        """
        provider = FastMockProvider()
        registry = ToolRegistry()
        context = ContextManager(max_messages=50)

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
            context=context,
        )

        # Run many messages
        for i in range(100):
            await engine.run(f"Message {i}")

        # Context should be truncated
        assert len(context) <= 100, "Context should not grow unbounded"

    @pytest.mark.asyncio
    async def test_large_message_handling(self):
        """
        Performance Test: Large message handling

        Requirements:
        - Should handle large messages without timing out
        - Performance should degrade gracefully
        """
        provider = FastMockProvider()
        registry = ToolRegistry()

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        # Create large message (10KB)
        large_message = "x" * 10000

        start = time.perf_counter()
        result = await engine.run(large_message)
        elapsed = time.perf_counter() - start

        assert result is not None
        # Should still respond quickly despite large message
        assert elapsed < 1.0, f"Large message took {elapsed:.2f}s"


# ============================================================================
# Performance Tests: Tool Execution
# ============================================================================

class TestToolExecutionPerformance:
    """Performance tests for tool execution."""

    @pytest.fixture
    def tool_perf_setup(self):
        """Set up tool performance test environment."""
        class FastTool(BaseTool):
            name: str = "fast_tool"
            description: str = "Fast tool"
            call_count: int = 0

            async def execute(self, **kwargs) -> str:
                self.call_count += 1
                return "done"

        provider = FastMockProvider()
        registry = ToolRegistry()
        fast_tool = FastTool()
        registry.register(fast_tool)

        engine = AgentEngine(
            provider=provider,
            tool_registry=registry,
            config=AgentConfig(max_iterations=10),
        )

        return {"provider": provider, "registry": registry, "engine": engine, "tool": fast_tool}

    @pytest.mark.asyncio
    async def test_tool_throughput(self, tool_perf_setup):
        """
        Performance Test: Tool execution throughput

        Requirements:
        - Should execute tools efficiently
        - Should not have significant overhead
        """
        # Directly test tool execution
        tool = tool_perf_setup["tool"]

        async def execute_tool():
            return await tool.execute()

        result = await benchmark_async(execute_tool, iterations=1000, warmup=10)

        print(f"\nTool Execution Benchmark: {result}")

        # Tool execution should be very fast
        assert result.avg_time < 0.001, f"Tool avg time < 1ms, got {result.avg_time * 1000:.4f}ms"
        assert result.ops_per_second > 1000, "Should handle > 1000 tool calls/sec"


# ============================================================================
# Performance Tests: Stress Testing
# ============================================================================

class TestStressScenarios:
    """Stress tests for extreme conditions."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_high_concurrent_load(self):
        """
        Stress Test: High concurrent load

        Requirements:
        - System should remain stable under high load
        - Should not crash or hang
        """
        provider = FastMockProvider()
        registry = ToolRegistry()

        async def run_engine():
            engine = AgentEngine(
                provider=provider,
                tool_registry=registry,
                config=AgentConfig(max_iterations=5),
            )
            return await engine.run("Hello")

        # Run 50 concurrent operations
        start = time.perf_counter()
        results = await asyncio.gather(*[run_engine() for _ in range(50)], return_exceptions=True)
        elapsed = time.perf_counter() - start

        # Count successful results
        successful = sum(1 for r in results if not isinstance(r, Exception))

        print(f"\nStress Test: {successful}/50 successful in {elapsed:.2f}s")

        # Most operations should succeed
        assert successful >= 45, f"Expected >= 45 successful, got {successful}"

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_sustained_load(self):
        """
        Stress Test: Sustained load over time

        Requirements:
        - Performance should not degrade over time
        - No memory leaks
        """
        provider = FastMockProvider()
        registry = ToolRegistry()

        # Run in batches to simulate sustained load
        batch_times = []

        for _batch in range(10):
            start = time.perf_counter()

            for _ in range(10):
                engine = AgentEngine(
                    provider=provider,
                    tool_registry=registry,
                    config=AgentConfig(max_iterations=5),
                )
                await engine.run("Hello")

            batch_time = time.perf_counter() - start
            batch_times.append(batch_time)

        # Performance should not degrade significantly
        first_half_avg = sum(batch_times[:5]) / 5
        second_half_avg = sum(batch_times[5:]) / 5

        degradation = (second_half_avg - first_half_avg) / first_half_avg

        print(f"\nSustained Load: First half avg: {first_half_avg:.3f}s, Second half avg: {second_half_avg:.3f}s")
        print(f"Degradation: {degradation * 100:.1f}%")

        # Degradation should be minimal (< 50%)
        assert degradation < 0.5, f"Performance degraded by {degradation * 100:.1f}%"


# ============================================================================
# Performance Report Generation
# ============================================================================

def generate_performance_report(results: list[BenchmarkResult]) -> str:
    """
    Generate a performance report from benchmark results.

    Args:
        results: List of benchmark results.

    Returns:
        Formatted report string.
    """
    lines = [
        "=" * 60,
        "PERFORMANCE TEST REPORT",
        "=" * 60,
        "",
    ]

    for result in results:
        lines.extend([
            f"Test: {result.name}",
            f"  Iterations: {result.iterations}",
            f"  Total Time: {result.total_time * 1000:.2f}ms",
            f"  Average Time: {result.avg_time * 1000:.4f}ms",
            f"  Min Time: {result.min_time * 1000:.4f}ms",
            f"  Max Time: {result.max_time * 1000:.4f}ms",
            f"  Ops/Second: {result.ops_per_second:.2f}",
            f"  Errors: {result.errors}",
            "",
        ])

    return "\n".join(lines)
