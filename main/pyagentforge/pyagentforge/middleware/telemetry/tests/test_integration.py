"""
Telemetry Integration Tests - Phase 3
"""

import pytest
from unittest.mock import MagicMock

from pyagentforge.middleware.telemetry.collector import TelemetryCollector


class TestTelemetryIntegration:
    """Telemetry 集成测试"""

    @pytest.fixture
    def collector(self):
        """创建 Collector 实例"""
        return TelemetryCollector()

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.get_stats = MagicMock(return_value={
            "events_emitted": 150,
            "handlers_called": 300,
            "errors": 5,
        })
        return event_bus

    @pytest.fixture
    def mock_provider_pool(self):
        """创建 Mock ProviderPool"""
        pool = MagicMock()
        pool.get_health_status = MagicMock(return_value={
            "openai": {
                "healthy": True,
                "average_latency_ms": 120.5,
                "total_requests": 100,
                "total_failures": 2,
            },
            "anthropic": {
                "healthy": True,
                "average_latency_ms": 95.3,
                "total_requests": 80,
                "total_failures": 0,
            },
        })
        return pool

    def test_track_request_basic(self, collector):
        """测试基本请求追踪"""
        collector.track_request("session:123", latency_ms=150.5, success=True)
        collector.track_request("session:123", latency_ms=200.0, success=True)
        collector.track_request("session:456", latency_ms=100.0, success=False)

        metrics = collector.get_all_metrics()

        assert metrics["requests"]["total"] == 3
        assert metrics["requests"]["errors"] == 1
        assert metrics["requests"]["error_rate"] == pytest.approx(1/3, rel=0.01)

    def test_track_tokens(self, collector):
        """测试 Token 追踪"""
        collector.track_tokens("session:123", input_tokens=100, output_tokens=50)
        collector.track_tokens("session:123", input_tokens=200, output_tokens=75)

        metrics = collector.get_all_metrics()

        assert metrics["tokens"]["total_input"] == 300
        assert metrics["tokens"]["total_output"] == 125
        assert metrics["tokens"]["total"] == 425

    def test_sync_from_event_bus(self, collector, mock_event_bus):
        """测试从 EventBus 同步"""
        stats = mock_event_bus.get_stats()
        collector.sync_from_event_bus(stats)

        metrics = collector.get_all_metrics()

        assert metrics["events"]["emitted"] == 150
        assert metrics["events"]["handlers_called"] == 300

    def test_sync_from_provider_pool(self, collector, mock_provider_pool):
        """测试从 ProviderPool 同步"""
        status = mock_provider_pool.get_health_status()
        collector.sync_from_provider_pool(status)

        metrics = collector.get_all_metrics()

        assert "openai" in metrics["providers"]
        assert metrics["providers"]["openai"]["average_latency_ms"] == 120.5
        assert metrics["providers"]["anthropic"]["average_latency_ms"] == 95.3

    def test_attach_to_event_bus(self, collector, mock_event_bus):
        """测试自动附加到 EventBus"""
        collector.attach_to_event_bus(mock_event_bus)

        metrics = collector.get_all_metrics()

        assert metrics["events"]["emitted"] == 150

    def test_attach_to_provider_pool(self, collector, mock_provider_pool):
        """测试自动附加到 ProviderPool"""
        collector.attach_to_provider_pool(mock_provider_pool)

        metrics = collector.get_all_metrics()

        assert "openai" in metrics["providers"]

    def test_session_metrics(self, collector):
        """测试会话级指标"""
        collector.track_request("session:abc", 100.0)
        collector.track_tokens("session:abc", 50, 25)

        session_metrics = collector.get_session_metrics("session:abc")

        assert session_metrics is not None
        assert session_metrics.request_count == 1
        assert session_metrics.total_input_tokens == 50
        assert session_metrics.total_output_tokens == 25

    def test_latency_percentiles(self, collector):
        """测试延迟百分位数计算"""
        # 添加 100 个请求，延迟从 50ms 到 149ms
        for i in range(100):
            collector.track_request("session:test", float(50 + i))

        metrics = collector.get_all_metrics()

        # P50 应该接近 99.5ms
        assert 95 <= metrics["latency"]["p50_ms"] <= 105

        # P95 应该接近 144ms
        assert 140 <= metrics["latency"]["p95_ms"] <= 148

        # P99 应该接近 148ms
        assert 145 <= metrics["latency"]["p99_ms"] <= 149

    def test_export_json(self, collector):
        """测试 JSON 导出"""
        collector.track_request("session:1", 100.0)
        collector.track_tokens("session:1", 50, 25)

        json_str = collector.export_json()

        import json
        data = json.loads(json_str)

        assert "requests" in data
        assert "tokens" in data
        assert data["requests"]["total"] == 1
        assert data["tokens"]["total"] == 75

    def test_export_prometheus(self, collector):
        """测试 Prometheus 导出"""
        collector.track_request("session:1", 100.0)
        collector.track_tokens("session:1", 50, 25)

        prometheus_str = collector.export_prometheus()

        # 验证 Prometheus 格式
        assert "pyagentforge_requests_total 1" in prometheus_str
        assert "pyagentforge_tokens_input_total 50" in prometheus_str
        assert "pyagentforge_tokens_output_total 25" in prometheus_str
        assert "# TYPE pyagentforge_requests_total counter" in prometheus_str
        assert "# HELP" in prometheus_str

    def test_full_integration(self, collector, mock_event_bus, mock_provider_pool):
        """测试完整集成场景"""
        # 模拟 100 个请求
        for i in range(100):
            success = i % 10 != 0  # 90% 成功率
            collector.track_request(f"session:{i % 5}", float(100 + i), success=success)

            if success:
                collector.track_tokens(f"session:{i % 5}", 100, 50)

        # 同步外部数据
        collector.attach_to_event_bus(mock_event_bus)
        collector.attach_to_provider_pool(mock_provider_pool)

        # 获取所有指标
        metrics = collector.get_all_metrics()

        # 验证请求统计
        assert metrics["requests"]["total"] == 100
        assert metrics["requests"]["errors"] == 10  # 每 10 个失败 1 个

        # 验证 Token 统计
        assert metrics["tokens"]["total_input"] == 90 * 100  # 90 个成功请求
        assert metrics["tokens"]["total_output"] == 90 * 50

        # 验证事件统计
        assert metrics["events"]["emitted"] == 150

        # 验证 Provider 统计
        assert "openai" in metrics["providers"]

        # 验证会话统计
        assert metrics["sessions"]["active_count"] == 5  # 5 个不同会话

        # 验证导出
        json_export = collector.export_json()
        assert len(json_export) > 0

        prometheus_export = collector.export_prometheus()
        assert "pyagentforge_requests_total 100" in prometheus_export


class TestTelemetryMetrics:
    """详细指标测试"""

    @pytest.fixture
    def collector_with_data(self):
        """创建带数据的 Collector"""
        collector = TelemetryCollector()

        # 添加一些测试数据
        for i in range(50):
            collector.track_request(f"session:{i % 3}", float(100 + i * 2))
            collector.track_tokens(f"session:{i % 3}", input_tokens=100 + i, output_tokens=50 + i)

        return collector

    def test_average_latency_calculation(self, collector_with_data):
        """测试平均延迟计算"""
        metrics = collector_with_data.get_all_metrics()

        # 平均延迟应该是 (100 + 102 + 104 + ... + 198) / 50 = 149
        expected_avg = sum(100 + i * 2 for i in range(50)) / 50

        assert metrics["latency"]["average_ms"] == pytest.approx(expected_avg, rel=0.01)

    def test_session_isolation(self, collector_with_data):
        """测试会话隔离"""
        # 获取每个会话的指标
        session_0 = collector_with_data.get_session_metrics("session:0")
        session_1 = collector_with_data.get_session_metrics("session:1")
        session_2 = collector_with_data.get_session_metrics("session:2")

        # 每个会话应该有大约 17 个请求 (50 / 3 ≈ 17)
        assert 16 <= session_0.request_count <= 17
        assert 16 <= session_1.request_count <= 17
        assert 16 <= session_2.request_count <= 17

    def test_error_rate_calculation(self, collector_with_data):
        """测试错误率计算"""
        # 添加一些失败请求
        for i in range(10):
            collector_with_data.track_request(
                "error_session",
                100.0,
                success=False
            )

        metrics = collector_with_data.get_all_metrics()

        # 总请求 = 50 + 10 = 60
        # 错误请求 = 10
        assert metrics["requests"]["total"] == 60
        assert metrics["requests"]["errors"] == 10
        assert metrics["requests"]["error_rate"] == pytest.approx(10/60, rel=0.01)

    def test_get_summary(self, collector_with_data):
        """测试摘要输出"""
        summary = collector_with_data.get_summary()

        assert "Requests:" in summary
        assert "Avg Latency:" in summary
        assert "Tokens:" in summary
