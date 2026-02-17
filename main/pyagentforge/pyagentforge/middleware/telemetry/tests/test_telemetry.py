"""
Telemetry 单元测试
"""

import pytest
from pyagentforge.middleware.telemetry.collector import (
    TelemetryCollector,
    MetricType,
    SessionMetrics,
)
from pyagentforge.middleware.telemetry.telemetry import TelemetryMiddleware
from pyagentforge.middleware.base import MiddlewareContext


class TestSessionMetrics:
    """测试 SessionMetrics"""

    def test_create_session_metrics(self):
        """创建会话指标"""
        metrics = SessionMetrics(session_key="test:123")
        assert metrics.session_key == "test:123"
        assert metrics.request_count == 0
        assert metrics.error_count == 0
        assert metrics.total_input_tokens == 0

    def test_average_latency(self):
        """平均延迟计算"""
        metrics = SessionMetrics(session_key="test:123")
        metrics.latencies = [100.0, 200.0, 300.0]
        assert metrics.average_latency_ms == 200.0

    def test_average_latency_empty(self):
        """空延迟列表"""
        metrics = SessionMetrics(session_key="test:123")
        assert metrics.average_latency_ms == 0.0

    def test_to_dict(self):
        """转换为字典"""
        metrics = SessionMetrics(
            session_key="test:123",
            request_count=5,
            error_count=1,
            total_input_tokens=100,
            total_output_tokens=50,
            latencies=[100.0, 200.0]
        )
        d = metrics.to_dict()
        assert d["session_key"] == "test:123"
        assert d["request_count"] == 5
        assert d["error_count"] == 1
        assert d["average_latency_ms"] == 150.0


class TestTelemetryCollector:
    """测试 TelemetryCollector"""

    def test_create_collector(self):
        """创建收集器"""
        collector = TelemetryCollector()
        metrics = collector.get_all_metrics()
        assert metrics["requests"]["total"] == 0
        assert metrics["tokens"]["total"] == 0

    def test_track_request(self):
        """追踪请求"""
        collector = TelemetryCollector()
        collector.track_request("session:123", latency_ms=150.5, success=True)

        metrics = collector.get_all_metrics()
        assert metrics["requests"]["total"] == 1
        assert metrics["requests"]["errors"] == 0
        assert metrics["latency"]["total_samples"] == 1

    def test_track_request_error(self):
        """追踪错误请求"""
        collector = TelemetryCollector()
        collector.track_request("session:123", latency_ms=100.0, success=False)

        metrics = collector.get_all_metrics()
        assert metrics["requests"]["total"] == 1
        assert metrics["requests"]["errors"] == 1

    def test_track_tokens(self):
        """追踪 Token"""
        collector = TelemetryCollector()
        collector.track_tokens("session:123", input_tokens=100, output_tokens=50)

        metrics = collector.get_all_metrics()
        assert metrics["tokens"]["total_input"] == 100
        assert metrics["tokens"]["total_output"] == 50
        assert metrics["tokens"]["total"] == 150

    def test_sync_from_event_bus(self):
        """从 EventBus 同步"""
        collector = TelemetryCollector()
        collector.sync_from_event_bus({
            "events_emitted": 10,
            "handlers_called": 25
        })

        metrics = collector.get_all_metrics()
        assert metrics["events"]["emitted"] == 10
        assert metrics["events"]["handlers_called"] == 25

    def test_sync_from_provider_pool(self):
        """从 ProviderPool 同步"""
        collector = TelemetryCollector()
        collector.sync_from_provider_pool({
            "anthropic": {"is_healthy": True, "average_latency_ms": 150.0},
            "openai": {"is_healthy": False, "average_latency_ms": 200.0}
        })

        metrics = collector.get_all_metrics()
        assert "anthropic" in metrics["providers"]
        assert metrics["providers"]["anthropic"]["is_healthy"] is True

    def test_session_metrics_tracking(self):
        """会话级指标追踪"""
        collector = TelemetryCollector()
        collector.track_request("session:abc", 100.0)
        collector.track_tokens("session:abc", 50, 25)

        session = collector.get_session_metrics("session:abc")
        assert session is not None
        assert session.request_count == 1
        assert session.total_input_tokens == 50
        assert session.total_output_tokens == 25

    def test_multiple_requests_latency(self):
        """多次请求延迟统计"""
        collector = TelemetryCollector()
        for latency in [100, 150, 200, 250, 300]:
            collector.track_request("session:1", latency)

        metrics = collector.get_all_metrics()
        assert metrics["latency"]["average_ms"] == 200.0
        assert metrics["latency"]["p50_ms"] == 200.0

    def test_get_summary(self):
        """获取摘要"""
        collector = TelemetryCollector()
        collector.track_request("session:1", 150.0)
        collector.track_tokens("session:1", 100, 50)

        summary = collector.get_summary()
        assert "Requests: 1" in summary
        assert "Tokens: 150" in summary

    def test_reset(self):
        """重置"""
        collector = TelemetryCollector()
        collector.track_request("session:1", 100.0)
        collector.track_tokens("session:1", 50, 25)

        collector.reset()

        metrics = collector.get_all_metrics()
        assert metrics["requests"]["total"] == 0
        assert metrics["tokens"]["total"] == 0


class TestTelemetryMiddleware:
    """测试 TelemetryMiddleware"""

    @pytest.fixture
    def middleware(self):
        """创建中间件"""
        collector = TelemetryCollector()
        return TelemetryMiddleware(collector)

    @pytest.fixture
    def context(self):
        """创建上下文"""
        return MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

    @pytest.mark.asyncio
    async def test_tracks_latency(self, middleware, context):
        """追踪延迟"""
        import asyncio

        async def handler(ctx):
            await asyncio.sleep(0.01)  # 10ms 延迟
            return {"result": "ok"}

        await middleware.process(context, handler)

        metrics = middleware.collector.get_all_metrics()
        assert metrics["requests"]["total"] == 1
        assert metrics["latency"]["average_ms"] >= 10  # 至少 10ms

    @pytest.mark.asyncio
    async def test_tracks_tokens_from_dict_response(self, middleware, context):
        """从字典响应追踪 Token"""
        async def handler(ctx):
            return {
                "result": "ok",
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }

        await middleware.process(context, handler)

        metrics = middleware.collector.get_all_metrics()
        assert metrics["tokens"]["total_input"] == 100
        assert metrics["tokens"]["total_output"] == 50

    @pytest.mark.asyncio
    async def test_tracks_error(self, middleware, context):
        """追踪错误"""
        async def handler(ctx):
            raise ValueError("test error")

        with pytest.raises(ValueError):
            await middleware.process(context, handler)

        metrics = middleware.collector.get_all_metrics()
        assert metrics["requests"]["errors"] == 1

    def test_middleware_properties(self, middleware):
        """中间件属性"""
        assert middleware.name == "telemetry"
        assert middleware.priority == 200

    def test_sync_event_bus(self, middleware):
        """同步 EventBus"""
        class MockEventBus:
            def get_stats(self):
                return {"events_emitted": 5, "handlers_called": 10}

        middleware.sync_event_bus(MockEventBus())

        metrics = middleware.collector.get_all_metrics()
        assert metrics["events"]["emitted"] == 5

    def test_sync_provider_pool(self, middleware):
        """同步 ProviderPool"""
        class MockProviderPool:
            def get_health_status(self):
                return {"test_provider": {"is_healthy": True}}

        middleware.sync_provider_pool(MockProviderPool())

        metrics = middleware.collector.get_all_metrics()
        assert "test_provider" in metrics["providers"]
