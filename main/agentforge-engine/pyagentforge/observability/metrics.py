"""
Metrics abstraction (P0-6)

提供 Counter / Histogram 抽象 + 可插拔后端：
  - `NoOpBackend`：生产默认；零开销
  - `InMemoryBackend`：测试与本地调试；可查询

指标清单（P0-6 验收）：
  - agent_iterations_total{session_id}
  - llm_tokens_total{model, type}
  - llm_latency_seconds{model}
  - tool_duration_seconds{tool}
  - tool_error_total{tool, code}
  - agent_checkpoint_failed_total
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class CounterMetric:
    name: str
    labels: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class HistogramMetric:
    name: str
    labels: tuple[tuple[str, str], ...] = ()


def _labels_to_key(labels: dict[str, Any] | None) -> tuple[tuple[str, str], ...]:
    """dict → 稳定可哈希 key（按字母序排序）。"""
    if not labels:
        return ()
    return tuple(sorted((k, str(v)) for k, v in labels.items()))


# ── Backend 抽象 ──────────────────────────────────────────────

class MetricsBackend(ABC):
    """Metrics 后端抽象。"""

    @abstractmethod
    def inc_counter(
        self, name: str, value: float = 1.0, labels: dict[str, Any] | None = None
    ) -> None:
        """增加 counter。"""

    @abstractmethod
    def observe_histogram(
        self, name: str, value: float, labels: dict[str, Any] | None = None
    ) -> None:
        """记录 histogram 观测值。"""


class NoOpBackend(MetricsBackend):
    """生产默认：零开销实现。"""

    def inc_counter(
        self, name: str, value: float = 1.0, labels: dict[str, Any] | None = None
    ) -> None:
        return

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, Any] | None = None
    ) -> None:
        return


class InMemoryBackend(MetricsBackend):
    """测试 / 本地调试：累积计数，可查询。线程安全。"""

    def __init__(self) -> None:
        self._counters: dict[str, dict[tuple, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        self._histograms: dict[str, dict[tuple, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = Lock()

    def inc_counter(
        self, name: str, value: float = 1.0, labels: dict[str, Any] | None = None
    ) -> None:
        key = _labels_to_key(labels)
        with self._lock:
            self._counters[name][key] += value

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, Any] | None = None
    ) -> None:
        key = _labels_to_key(labels)
        with self._lock:
            self._histograms[name][key].append(value)

    # ── 查询 API ────────────────────────────────────────────────

    def get_counter(
        self, name: str, labels: dict[str, Any] | None = None
    ) -> float:
        key = _labels_to_key(labels)
        with self._lock:
            return self._counters.get(name, {}).get(key, 0.0)

    def get_histogram_values(
        self, name: str, labels: dict[str, Any] | None = None
    ) -> list[float]:
        key = _labels_to_key(labels)
        with self._lock:
            return list(self._histograms.get(name, {}).get(key, []))

    def counter_names(self) -> list[str]:
        with self._lock:
            return list(self._counters.keys())

    def histogram_names(self) -> list[str]:
        with self._lock:
            return list(self._histograms.keys())

    def clear(self) -> None:
        with self._lock:
            self._counters.clear()
            self._histograms.clear()


# ── Collector（简化门面）───────────────────────────────────────

@dataclass
class MetricsCollector:
    """门面类：封装 backend，提供便捷 API。"""

    backend: MetricsBackend = field(default_factory=NoOpBackend)

    def inc(
        self, name: str, value: float = 1.0, **labels: Any
    ) -> None:
        self.backend.inc_counter(name, value, labels or None)

    def observe(
        self, name: str, value: float, **labels: Any
    ) -> None:
        self.backend.observe_histogram(name, value, labels or None)


# ── 全局 collector（可替换）──────────────────────────────────

_global_collector: MetricsCollector = MetricsCollector()


def get_collector() -> MetricsCollector:
    """获取全局 collector（默认 NoOp）。"""
    return _global_collector


def set_collector(collector: MetricsCollector) -> None:
    """替换全局 collector（测试中用 InMemory）。"""
    global _global_collector
    _global_collector = collector
