"""
Telemetry Collector - 遥测收集器

聚合来自 EventBus 和 ProviderHealth 的遥测数据，
提供统一的指标访问接口。
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class MetricType(StrEnum):
    """指标类型"""
    COUNTER = "counter"      # 单调递增计数
    GAUGE = "gauge"          # 可增可减的瞬时值
    HISTOGRAM = "histogram"  # 分布统计


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: Any
    metric_type: MetricType
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class SessionMetrics:
    """会话级指标"""
    session_key: str
    request_count: int = 0
    error_count: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_ms: float = 0.0
    latencies: list[float] = field(default_factory=list)

    @property
    def average_latency_ms(self) -> float:
        """平均延迟"""
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_key": self.session_key,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "average_latency_ms": self.average_latency_ms,
        }


class TelemetryCollector:
    """
    遥测收集器

    聚合来自多个来源的遥测数据：
    - EventBus: 事件统计、事件历史
    - ProviderHealth: 延迟、请求计数、健康状态
    - Token 使用: input/output tokens

    Examples:
        >>> collector = TelemetryCollector()
        >>> collector.track_request("session:123", latency_ms=150.5)
        >>> collector.track_tokens("session:123", input_tokens=100, output_tokens=50)
        >>> metrics = collector.get_all_metrics()
    """

    def __init__(self):
        """初始化收集器"""
        # 全局计数器
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0

        # 延迟追踪
        self._latencies: list[float] = []

        # 会话级指标
        self._session_metrics: dict[str, SessionMetrics] = {}

        # 事件统计 (从 EventBus 同步)
        self._events_emitted: int = 0
        self._handlers_called: int = 0

        # Provider 健康状态 (从 ProviderPool 同步)
        self._provider_health: dict[str, dict[str, Any]] = {}

    # === 请求追踪 ===

    def track_request(
        self,
        session_key: str,
        latency_ms: float,
        success: bool = True
    ) -> None:
        """
        追踪请求

        Args:
            session_key: 会话标识
            latency_ms: 请求延迟 (毫秒)
            success: 是否成功
        """
        self._total_requests += 1
        self._latencies.append(latency_ms)

        if not success:
            self._total_errors += 1

        # 更新会话级指标
        if session_key not in self._session_metrics:
            self._session_metrics[session_key] = SessionMetrics(session_key=session_key)

        session = self._session_metrics[session_key]
        session.request_count += 1
        session.latencies.append(latency_ms)
        session.total_latency_ms += latency_ms

        if not success:
            session.error_count += 1

    def track_tokens(
        self,
        session_key: str,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        """
        追踪 Token 使用

        Args:
            session_key: 会话标识
            input_tokens: 输入 tokens
            output_tokens: 输出 tokens
        """
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens

        # 更新会话级指标
        if session_key not in self._session_metrics:
            self._session_metrics[session_key] = SessionMetrics(session_key=session_key)

        session = self._session_metrics[session_key]
        session.total_input_tokens += input_tokens
        session.total_output_tokens += output_tokens

    # === 从外部同步数据 ===

    def sync_from_event_bus(self, stats: dict[str, Any]) -> None:
        """
        从 EventBus 同步统计数据

        Args:
            stats: EventBus.get_stats() 返回的统计数据
        """
        self._events_emitted = stats.get("events_emitted", 0)
        self._handlers_called = stats.get("handlers_called", 0)

    def sync_from_provider_pool(self, health_status: dict[str, Any]) -> None:
        """
        从 ProviderPool 同步健康状态

        Args:
            health_status: ProviderPool.get_health_status() 返回的数据
        """
        self._provider_health = health_status

    # === 获取指标 ===

    def get_all_metrics(self) -> dict[str, Any]:
        """
        获取所有聚合后的指标

        Returns:
            指标字典
        """
        return {
            "requests": {
                "total": self._total_requests,
                "errors": self._total_errors,
                "error_rate": self._total_errors / max(1, self._total_requests),
            },
            "latency": {
                "total_samples": len(self._latencies),
                "average_ms": self._calculate_average_latency(),
                "p50_ms": self._calculate_percentile(50),
                "p95_ms": self._calculate_percentile(95),
                "p99_ms": self._calculate_percentile(99),
            },
            "tokens": {
                "total_input": self._total_input_tokens,
                "total_output": self._total_output_tokens,
                "total": self._total_input_tokens + self._total_output_tokens,
            },
            "events": {
                "emitted": self._events_emitted,
                "handlers_called": self._handlers_called,
            },
            "providers": self._provider_health,
            "sessions": {
                "active_count": len(self._session_metrics),
                "metrics": {
                    k: v.to_dict() for k, v in self._session_metrics.items()
                },
            },
        }

    def get_session_metrics(self, session_key: str) -> SessionMetrics | None:
        """获取指定会话的指标"""
        return self._session_metrics.get(session_key)

    def get_summary(self) -> str:
        """获取人类可读的摘要"""
        metrics = self.get_all_metrics()
        return (
            f"Requests: {metrics['requests']['total']} "
            f"(errors: {metrics['requests']['errors']}), "
            f"Avg Latency: {metrics['latency']['average_ms']:.1f}ms, "
            f"Tokens: {metrics['tokens']['total']}"
        )

    # === 延迟计算 ===

    def _calculate_average_latency(self) -> float:
        """计算平均延迟"""
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)

    def _calculate_percentile(self, percentile: int) -> float:
        """计算延迟百分位数"""
        if not self._latencies:
            return 0.0
        sorted_latencies = sorted(self._latencies)
        index = int(len(sorted_latencies) * percentile / 100)
        return sorted_latencies[min(index, len(sorted_latencies) - 1)]

    # === 导出格式 ===

    def export_json(self) -> str:
        """
        导出为 JSON 格式

        Returns:
            JSON 字符串
        """
        import json
        return json.dumps(self.get_all_metrics(), indent=2)

    def export_prometheus(self) -> str:
        """
        导出为 Prometheus 格式

        Returns:
            Prometheus 格式文本
        """
        metrics = self.get_all_metrics()
        lines = []

        # 请求指标
        lines.append("# HELP pyagentforge_requests_total Total number of requests")
        lines.append("# TYPE pyagentforge_requests_total counter")
        lines.append(f"pyagentforge_requests_total {metrics['requests']['total']}")

        lines.append("# HELP pyagentforge_requests_errors_total Total number of request errors")
        lines.append("# TYPE pyagentforge_requests_errors_total counter")
        lines.append(f"pyagentforge_requests_errors_total {metrics['requests']['errors']}")

        # Token 指标
        lines.append("# HELP pyagentforge_tokens_input_total Total input tokens")
        lines.append("# TYPE pyagentforge_tokens_input_total counter")
        lines.append(f"pyagentforge_tokens_input_total {metrics['tokens']['total_input']}")

        lines.append("# HELP pyagentforge_tokens_output_total Total output tokens")
        lines.append("# TYPE pyagentforge_tokens_output_total counter")
        lines.append(f"pyagentforge_tokens_output_total {metrics['tokens']['total_output']}")

        # 延迟指标
        lines.append("# HELP pyagentforge_latency_ms Request latency in milliseconds")
        lines.append("# TYPE pyagentforge_latency_ms gauge")
        lines.append(f"pyagentforge_latency_ms{{quantile=\"avg\"}} {metrics['latency']['average_ms']:.2f}")
        lines.append(f"pyagentforge_latency_ms{{quantile=\"p50\"}} {metrics['latency']['p50_ms']:.2f}")
        lines.append(f"pyagentforge_latency_ms{{quantile=\"p95\"}} {metrics['latency']['p95_ms']:.2f}")
        lines.append(f"pyagentforge_latency_ms{{quantile=\"p99\"}} {metrics['latency']['p99_ms']:.2f}")

        # 事件指标
        lines.append("# HELP pyagentforge_events_emitted_total Total events emitted")
        lines.append("# TYPE pyagentforge_events_emitted_total counter")
        lines.append(f"pyagentforge_events_emitted_total {metrics['events']['emitted']}")

        # 会话指标
        lines.append("# HELP pyagentforge_sessions_active Number of active sessions")
        lines.append("# TYPE pyagentforge_sessions_active gauge")
        lines.append(f"pyagentforge_sessions_active {metrics['sessions']['active_count']}")

        return "\n".join(lines)

    # === 集成辅助方法 ===

    def attach_to_event_bus(self, event_bus: Any) -> None:
        """
        自动附加到 EventBus 以定期同步数据

        Args:
            event_bus: EventBus 实例
        """
        if hasattr(event_bus, 'get_stats'):
            stats = event_bus.get_stats()
            self.sync_from_event_bus(stats)

    def attach_to_provider_pool(self, provider_pool: Any) -> None:
        """
        自动附加到 ProviderPool 以同步健康状态

        Args:
            provider_pool: ProviderPool 实例
        """
        if hasattr(provider_pool, 'get_health_status'):
            status = provider_pool.get_health_status()
            self.sync_from_provider_pool(status)

    # === 重置 ===

    def reset(self) -> None:
        """重置所有指标"""
        self._total_requests = 0
        self._total_errors = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._latencies.clear()
        self._session_metrics.clear()
        self._events_emitted = 0
        self._handlers_called = 0
        self._provider_health.clear()
