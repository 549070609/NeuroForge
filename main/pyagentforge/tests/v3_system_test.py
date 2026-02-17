"""
PyAgentForge v3.0 系统集成测试

测试范围:
- Phase 1: SessionKey, 环境变量解析, Channel 基类
- Phase 2: Middleware Pipeline, Telemetry, Provider Pool 增强, Automation

测试策略:
1. 单元功能测试 - 验证各模块基本功能
2. 集成测试 - 验证模块间协作
3. 边界测试 - 验证异常处理
"""

import pytest
import asyncio
import os
import time
from datetime import datetime

# Phase 1 导入
from pyagentforge.foundation.session.session_key import SessionKey
from pyagentforge.foundation.config.env_parser import (
    resolve_env_vars,
    resolve_config,
    has_env_vars,
    get_referenced_vars,
)
from pyagentforge.capabilities.channels.base import (
    ChannelStatus,
    ChannelMessage,
    SendMessageResult,
    BaseChannel,
)

# Phase 2 导入
from pyagentforge.middleware.base import BaseMiddleware, MiddlewareContext
from pyagentforge.middleware.pipeline import MiddlewarePipeline
from pyagentforge.middleware.telemetry.collector import TelemetryCollector
from pyagentforge.middleware.telemetry.telemetry import TelemetryMiddleware
from pyagentforge.automation.task import TriggerType, AutomationTask
from pyagentforge.automation.scheduler import AutomationManager


# ============================================================
# Phase 1: Session Key 体系
# ============================================================

class TestSessionKeySystem:
    """Session Key 体系系统测试"""

    def test_parse_all_channel_types(self):
        """测试所有通道类型的 Session Key 解析"""
        test_cases = [
            ("telegram:-100123456", "telegram", "-100123456", None),
            ("discord:789012345", "discord", "789012345", None),
            ("webchat:session-abc123", "webchat", "session-abc123", None),
            ("slack:C12345678", "slack", "C12345678", None),
            ("agent:main:subagent:task-001", "agent", "main", "subagent:task-001"),
        ]

        for key_str, expected_channel, expected_conv, expected_sub in test_cases:
            key = SessionKey.parse(key_str)
            assert key.channel == expected_channel, f"Failed for {key_str}"
            assert key.conversation_id == expected_conv, f"Failed for {key_str}"
            assert key.sub_key == expected_sub, f"Failed for {key_str}"

    def test_session_key_hierarchy(self):
        """测试 Session Key 层级关系"""
        parent = SessionKey("agent", "main")
        child = parent.with_sub_key("task-001")

        assert str(parent) == "agent:main"
        assert str(child) == "agent:main:task-001"

        # with_sub_key 是替换 sub_key，不是追加
        new_child = child.with_sub_key("new-task")
        assert str(new_child) == "agent:main:new-task"

        # parent_key 返回去掉 sub_key 的父会话
        assert child.parent_key == parent
        assert parent.parent_key is None

    def test_session_key_as_dict_key(self):
        """测试 Session Key 作为字典键"""
        sessions = {}
        key1 = SessionKey.parse("telegram:123")
        key2 = SessionKey.parse("telegram:123")
        key3 = SessionKey.parse("telegram:456")

        sessions[key1] = "session_data_1"
        sessions[key2] = "session_data_2"  # 应该覆盖
        sessions[key3] = "session_data_3"

        assert len(sessions) == 2
        assert sessions[key1] == "session_data_2"

    def test_session_key_invalid_formats(self):
        """测试无效格式处理"""
        invalid_keys = [
            "",                 # 空字符串
            "no_colon",        # 无冒号
            ":",               # 只有冒号
        ]

        for invalid in invalid_keys:
            with pytest.raises(ValueError):
                SessionKey.parse(invalid)


# ============================================================
# Phase 1: 环境变量解析
# ============================================================

class TestEnvParserSystem:
    """环境变量解析系统测试"""

    def test_resolve_nested_config(self, monkeypatch):
        """测试嵌套配置解析"""
        monkeypatch.setenv("API_HOST", "api.example.com")
        monkeypatch.setenv("API_PORT", "443")
        monkeypatch.delenv("DB_HOST", raising=False)

        config = {
            "api": {
                "host": "${API_HOST}",
                "port": "${API_PORT:-80}",
                "timeout": "${API_TIMEOUT:-30}"
            },
            "database": {
                "host": "${DB_HOST:-localhost}",
                "port": "${DB_PORT:-5432}"
            },
            "features": ["${FEATURE_1:-enabled}", "${FEATURE_2:-disabled}"]
        }

        resolved = resolve_config(config)

        assert resolved["api"]["host"] == "api.example.com"
        assert resolved["api"]["port"] == "443"
        assert resolved["api"]["timeout"] == "30"
        assert resolved["database"]["host"] == "localhost"
        assert resolved["database"]["port"] == "5432"
        assert resolved["features"][0] == "enabled"

    def test_missing_required_var(self, monkeypatch):
        """测试缺失必需变量"""
        monkeypatch.delenv("REQUIRED_VAR", raising=False)

        with pytest.raises(ValueError) as exc_info:
            resolve_env_vars("${REQUIRED_VAR}")
        assert "REQUIRED_VAR" in str(exc_info.value)

    def test_special_chars_in_default(self, monkeypatch):
        """测试默认值中的特殊字符"""
        monkeypatch.delenv("PATH_VAR", raising=False)

        result = resolve_env_vars("${PATH_VAR:-/usr/local/bin:/home/user/bin}")
        assert result == "/usr/local/bin:/home/user/bin"

    def test_complex_interpolation(self, monkeypatch):
        """测试复杂插值场景"""
        monkeypatch.setenv("SCHEME", "https")
        monkeypatch.setenv("HOST", "example.com")
        monkeypatch.setenv("PORT", "8080")

        template = "${SCHEME}://${HOST}:${PORT}/api/v1"
        result = resolve_env_vars(template)
        assert result == "https://example.com:8080/api/v1"


# ============================================================
# Phase 1: Channel 基类
# ============================================================

class MockChannel(BaseChannel):
    """用于测试的 Mock 通道"""

    name = "mock"
    version = "1.0.0"

    def __init__(self, config):
        super().__init__(config)
        self._messages_sent = []

    async def initialize(self) -> None:
        await asyncio.sleep(0.01)  # 模拟初始化
        self._set_status(ChannelStatus.CONNECTED)

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        self._set_status(ChannelStatus.DISCONNECTED)

    async def send_message(self, to: str, content: str, **kwargs) -> SendMessageResult:
        self._messages_sent.append({"to": to, "content": content})
        return SendMessageResult(success=True, message_id=f"msg_{len(self._messages_sent)}")

    async def get_channel_info(self) -> dict:
        return {
            "name": self.name,
            "status": self._status.value,
            "messages_count": len(self._messages_sent),
        }


class TestChannelSystem:
    """Channel 系统测试"""

    @pytest.mark.asyncio
    async def test_channel_lifecycle(self):
        """测试通道完整生命周期"""
        channel = MockChannel({})

        # 初始状态
        assert channel.status == ChannelStatus.DISCONNECTED

        # 初始化
        await channel.initialize()
        assert channel.status == ChannelStatus.CONNECTED

        # 发送消息
        result = await channel.send_message("user_123", "Hello!")
        assert result.success is True
        assert result.message_id == "msg_1"

        # 停止
        await channel.stop()
        assert channel.status == ChannelStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_channel_message_callback(self):
        """测试通道消息回调"""
        channel = MockChannel({})
        received = []

        async def callback(msg: ChannelMessage):
            received.append(msg)

        channel.on_message(callback)

        # 模拟收到消息
        test_msg = ChannelMessage(
            session_key="mock:123",
            content="Test message",
            sender="user",
            channel="mock"
        )
        await channel._emit_message(test_msg)

        assert len(received) == 1
        assert received[0].content == "Test message"

    def test_channel_message_serialization(self):
        """测试消息序列化"""
        msg = ChannelMessage(
            session_key="telegram:123",
            content="Hello",
            sender="user_456",
            channel="telegram",
            metadata={"platform": "telegram"},
            attachments=[{"type": "image", "url": "http://example.com/img.jpg"}],
            reply_to="msg_001"
        )

        d = msg.to_dict()
        assert d["session_key"] == "telegram:123"
        assert len(d["attachments"]) == 1
        assert d["reply_to"] == "msg_001"


# ============================================================
# Phase 2: Middleware Pipeline
# ============================================================

class TestMiddlewarePipelineSystem:
    """Middleware Pipeline 系统测试"""

    @pytest.mark.asyncio
    async def test_middleware_chain_execution(self):
        """测试中间件链式执行"""
        execution_order = []

        class FirstMiddleware(BaseMiddleware):
            name = "first"
            priority = 10
            async def process(self, ctx, next):
                execution_order.append("first_start")
                result = await next(ctx)
                execution_order.append("first_end")
                return result

        class SecondMiddleware(BaseMiddleware):
            name = "second"
            priority = 20
            async def process(self, ctx, next):
                execution_order.append("second_start")
                result = await next(ctx)
                execution_order.append("second_end")
                return result

        class ThirdMiddleware(BaseMiddleware):
            name = "third"
            priority = 30
            async def process(self, ctx, next):
                execution_order.append("third_start")
                result = await next(ctx)
                execution_order.append("third_end")
                return result

        pipeline = MiddlewarePipeline()
        pipeline.add(ThirdMiddleware()).add(FirstMiddleware()).add(SecondMiddleware())

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c):
            execution_order.append("handler")
            return "done"

        result = await pipeline.execute(ctx, handler)

        # 验证执行顺序
        expected = [
            "first_start", "second_start", "third_start",
            "handler",
            "third_end", "second_end", "first_end"
        ]
        assert execution_order == expected
        assert result == "done"

    @pytest.mark.asyncio
    async def test_middleware_short_circuit(self):
        """测试中间件短路"""
        reached_handler = False

        class AuthMiddleware(BaseMiddleware):
            name = "auth"
            priority = 10
            async def process(self, ctx, next):
                # 认证失败，不调用 next
                return {"error": "unauthorized"}

        pipeline = MiddlewarePipeline()
        pipeline.add(AuthMiddleware())

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c):
            nonlocal reached_handler
            reached_handler = True
            return "ok"

        result = await pipeline.execute(ctx, handler)

        assert result["error"] == "unauthorized"
        assert reached_handler is False

    @pytest.mark.asyncio
    async def test_middleware_context_propagation(self):
        """测试上下文在中间件间传播"""
        class AddMetadataMiddleware(BaseMiddleware):
            name = "add_meta"
            priority = 10
            async def process(self, ctx, next):
                ctx.metadata["added_by"] = "middleware1"
                return await next(ctx)

        class ReadMetadataMiddleware(BaseMiddleware):
            name = "read_meta"
            priority = 20
            async def process(self, ctx, next):
                ctx.metadata["seen"] = ctx.metadata.get("added_by")
                return await next(ctx)

        pipeline = MiddlewarePipeline()
        pipeline.add(AddMetadataMiddleware()).add(ReadMetadataMiddleware())

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        final_metadata = {}

        async def handler(c):
            final_metadata.update(c.metadata)
            return "ok"

        await pipeline.execute(ctx, handler)

        assert final_metadata["added_by"] == "middleware1"
        assert final_metadata["seen"] == "middleware1"


# ============================================================
# Phase 2: Telemetry
# ============================================================

class TestTelemetrySystem:
    """Telemetry 系统测试"""

    def test_collector_aggregation(self):
        """测试收集器聚合功能"""
        collector = TelemetryCollector()

        # 模拟多个请求
        for i in range(10):
            latency = 100 + i * 10
            success = i != 5  # 第 6 个请求失败
            collector.track_request(f"session:{i % 3}", latency, success)

        # 模拟 Token 使用
        collector.track_tokens("session:0", 100, 50)
        collector.track_tokens("session:1", 200, 100)

        # 同步外部数据
        collector.sync_from_event_bus({
            "events_emitted": 100,
            "handlers_called": 250
        })
        collector.sync_from_provider_pool({
            "anthropic": {"is_healthy": True, "average_latency_ms": 150}
        })

        metrics = collector.get_all_metrics()

        assert metrics["requests"]["total"] == 10
        assert metrics["requests"]["errors"] == 1
        assert metrics["tokens"]["total"] == 450
        assert metrics["events"]["emitted"] == 100
        assert "anthropic" in metrics["providers"]
        assert metrics["sessions"]["active_count"] == 3

    @pytest.mark.asyncio
    async def test_telemetry_middleware_integration(self):
        """测试 Telemetry 中间件集成"""
        collector = TelemetryCollector()
        telemetry = TelemetryMiddleware(collector)

        pipeline = MiddlewarePipeline()
        pipeline.add(telemetry)

        ctx = MiddlewareContext(
            session_key="test:123",
            messages=[],
            tools=[]
        )

        async def handler(c):
            await asyncio.sleep(0.01)
            return {
                "result": "ok",
                "usage": {"input_tokens": 100, "output_tokens": 50}
            }

        await pipeline.execute(ctx, handler)

        metrics = collector.get_all_metrics()
        assert metrics["requests"]["total"] == 1
        assert metrics["tokens"]["total_input"] == 100
        assert metrics["latency"]["average_ms"] >= 10

    def test_latency_percentiles(self):
        """测试延迟百分位数计算"""
        collector = TelemetryCollector()

        # 添加 100 个请求，延迟从 10ms 到 1000ms
        latencies = [10 + i * 10 for i in range(100)]
        for latency in latencies:
            collector.track_request("session:1", latency)

        metrics = collector.get_all_metrics()

        # P50 应该接近 505ms
        assert 450 < metrics["latency"]["p50_ms"] < 550
        # P95 应该接近 955ms
        assert 900 < metrics["latency"]["p95_ms"] < 1000


# ============================================================
# Phase 2: Automation
# ============================================================

class TestAutomationSystem:
    """Automation 系统测试"""

    @pytest.mark.asyncio
    async def test_task_lifecycle(self):
        """测试任务生命周期"""
        manager = AutomationManager()

        # 添加任务
        task = manager.add_cron_task(
            task_id="test_task",
            cron_expr="* * * * *",
            action="Test action"
        )

        assert task.id == "test_task"
        assert task.enabled is True
        assert len(manager.list_tasks()) == 1

        # 获取任务
        retrieved = manager.get_task("test_task")
        assert retrieved == task

        # 移除任务
        removed = manager.remove_task("test_task")
        assert removed is True
        assert len(manager.list_tasks()) == 0

    @pytest.mark.asyncio
    async def test_webhook_handling(self):
        """测试 Webhook 处理"""
        manager = AutomationManager()
        handled_payloads = []

        async def handler(payload, headers):
            handled_payloads.append(payload)
            return {"status": "processed"}

        manager.add_webhook_handler("/github", handler)

        result = await manager.handle_webhook(
            "/github",
            {"event": "push", "repo": "test/repo"},
            {"Content-Type": "application/json"}
        )

        assert result["status"] == "processed"
        assert len(handled_payloads) == 1

    @pytest.mark.asyncio
    async def test_manager_start_stop(self):
        """测试管理器启动停止"""
        manager = AutomationManager()

        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False


# ============================================================
# 集成测试: 端到端场景
# ============================================================

class TestEndToEndScenarios:
    """端到端场景测试"""

    @pytest.mark.asyncio
    async def test_full_request_flow(self):
        """测试完整请求流程"""
        # 1. 创建遥测收集器
        collector = TelemetryCollector()

        # 2. 创建中间件管道
        pipeline = MiddlewarePipeline()
        pipeline.add(TelemetryMiddleware(collector))

        # 3. 模拟请求处理
        ctx = MiddlewareContext(
            session_key="telegram:123456",
            messages=[{"role": "user", "content": "Hello"}],
            tools=[]
        )

        async def final_handler(c):
            return {
                "response": "Hi there!",
                "usage": {"input_tokens": 50, "output_tokens": 25}
            }

        result = await pipeline.execute(ctx, final_handler)

        # 4. 验证结果
        assert result["response"] == "Hi there!"

        metrics = collector.get_all_metrics()
        assert metrics["requests"]["total"] == 1
        assert metrics["tokens"]["total"] == 75

    @pytest.mark.asyncio
    async def test_multi_session_tracking(self):
        """测试多会话追踪"""
        collector = TelemetryCollector()
        pipeline = MiddlewarePipeline()
        pipeline.add(TelemetryMiddleware(collector))

        # 模拟多个会话的请求
        sessions = ["telegram:111", "discord:222", "webchat:333"]

        for session_key in sessions:
            ctx = MiddlewareContext(
                session_key=session_key,
                messages=[],
                tools=[]
            )

            async def handler(c):
                return {"usage": {"input_tokens": 100, "output_tokens": 50}}

            await pipeline.execute(ctx, handler)

        metrics = collector.get_all_metrics()

        assert metrics["requests"]["total"] == 3
        assert metrics["sessions"]["active_count"] == 3
        assert "telegram:111" in metrics["sessions"]["metrics"]
        assert "discord:222" in metrics["sessions"]["metrics"]

    def test_session_key_with_env_config(self, monkeypatch):
        """测试 Session Key 与环境变量配置结合"""
        monkeypatch.setenv("DEFAULT_CHANNEL", "webchat")
        monkeypatch.setenv("DEFAULT_CONVERSATION", "default-session")

        config = {
            "session_key": "${DEFAULT_CHANNEL}:${DEFAULT_CONVERSATION}"
        }

        resolved = resolve_config(config)
        key = SessionKey.parse(resolved["session_key"])

        assert key.channel == "webchat"
        assert key.conversation_id == "default-session"


# ============================================================
# 性能测试
# ============================================================

class TestPerformance:
    """性能测试"""

    @pytest.mark.asyncio
    async def test_middleware_pipeline_performance(self):
        """测试中间件管道性能"""
        class NoOpMiddleware(BaseMiddleware):
            name = "noop"
            priority = 100
            async def process(self, ctx, next):
                return await next(ctx)

        pipeline = MiddlewarePipeline()
        for i in range(10):
            pipeline.add(NoOpMiddleware())

        ctx = MiddlewareContext(
            session_key="test:perf",
            messages=[],
            tools=[]
        )

        async def handler(c):
            return "ok"

        # 执行 100 次
        start = time.time()
        for _ in range(100):
            await pipeline.execute(ctx, handler)
        elapsed = time.time() - start

        # 100 次执行应该在 1 秒内完成
        assert elapsed < 1.0, f"Pipeline too slow: {elapsed:.3f}s for 100 iterations"

    def test_session_key_parse_performance(self):
        """测试 Session Key 解析性能"""
        key_strings = [f"channel:{i}:subkey:{j}" for i in range(100) for j in range(10)]

        start = time.time()
        for key_str in key_strings:
            SessionKey.parse(key_str)
        elapsed = time.time() - start

        # 1000 次解析应该在 0.1 秒内完成
        assert elapsed < 0.1, f"SessionKey parse too slow: {elapsed:.3f}s for 1000 parses"

    def test_telemetry_collector_performance(self):
        """测试遥测收集器性能"""
        collector = TelemetryCollector()

        start = time.time()
        for i in range(10000):
            collector.track_request(f"session:{i % 100}", 100.0 + i * 0.01)
            collector.track_tokens(f"session:{i % 100}", 100, 50)
        elapsed = time.time() - start

        # 10000 次追踪应该在 0.5 秒内完成
        assert elapsed < 0.5, f"Telemetry too slow: {elapsed:.3f}s for 10000 tracks"
