"""
Observability Module (P0-6)

提供轻量级 metrics 收集 + 可插拔导出器（NoOp / InMemory / 可扩展 OTel）。
核心理念：Engine 不直接依赖任何可观测后端，而是通过 hooks 调用 `MetricsCollector`。
"""

from pyagentforge.observability.metrics import (
    CounterMetric,
    HistogramMetric,
    InMemoryBackend,
    MetricsBackend,
    MetricsCollector,
    NoOpBackend,
    get_collector,
    set_collector,
)
from pyagentforge.observability.hooks import ObservabilityHooks

__all__ = [
    "CounterMetric",
    "HistogramMetric",
    "InMemoryBackend",
    "MetricsBackend",
    "MetricsCollector",
    "NoOpBackend",
    "ObservabilityHooks",
    "get_collector",
    "set_collector",
]
