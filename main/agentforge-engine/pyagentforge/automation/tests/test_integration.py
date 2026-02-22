"""
Automation Integration Tests - Phase 3
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from pyagentforge.automation.task import TriggerType, AutomationTask
from pyagentforge.automation.scheduler import AutomationManager


class TestAutomationIntegration:
    """Automation 集成测试"""

    @pytest.fixture
    def mock_engine(self):
        """创建 Mock Engine"""
        engine = MagicMock()
        engine.run = AsyncMock(return_value="Task executed successfully")
        return engine

    @pytest.fixture
    def mock_event_bus(self):
        """创建 Mock EventBus"""
        event_bus = MagicMock()
        event_bus.subscribe = MagicMock()
        event_bus.unsubscribe = MagicMock()
        return event_bus

    @pytest.mark.asyncio
    async def test_event_task_registration(self, mock_engine, mock_event_bus):
        """测试事件任务注册"""
        manager = AutomationManager(engine=mock_engine, event_bus=mock_event_bus)

        # 添加事件任务
        task = manager.add_event_task(
            task_id="on_message",
            event_type="message.received",
            action="Process message",
            name="Message Processor"
        )

        assert task.id == "on_message"
        assert task.trigger_type == TriggerType.EVENT
        assert task.trigger_config["event_type"] == "message.received"
        assert mock_event_bus.subscribe.called

    @pytest.mark.asyncio
    async def test_event_task_with_condition(self, mock_engine, mock_event_bus):
        """测试带条件的事件任务"""
        manager = AutomationManager(engine=mock_engine, event_bus=mock_event_bus)

        # 添加带条件的事件任务
        condition = lambda data: data.get("urgent", False)
        task = manager.add_event_task(
            task_id="urgent_only",
            event_type="message.received",
            action="Handle urgent message",
            condition=condition
        )

        assert task.trigger_config["condition"] == condition

    @pytest.mark.asyncio
    async def test_cron_task_with_scheduler(self, mock_engine):
        """测试 Cron 任务调度"""
        manager = AutomationManager(engine=mock_engine)

        # 添加 Cron 任务
        task = manager.add_cron_task(
            task_id="daily_report",
            cron_expr="0 9 * * *",
            action="Generate daily report"
        )

        assert task.id == "daily_report"
        assert task.trigger_type == TriggerType.TIME

    @pytest.mark.asyncio
    async def test_webhook_handler_registration(self, mock_engine):
        """测试 Webhook 处理器注册"""
        manager = AutomationManager(engine=mock_engine)

        async def handler(payload, headers):
            return {"status": "ok"}

        manager.add_webhook_handler("/github/webhook", handler, secret="test_secret")

        assert "/github/webhook" in manager._webhook_handlers
        assert manager._webhook_handlers["/github/webhook"]["secret"] == "test_secret"

    @pytest.mark.asyncio
    async def test_task_execution(self, mock_engine):
        """测试任务实际执行"""
        manager = AutomationManager(engine=mock_engine)

        task = manager.add_cron_task(
            task_id="test_task",
            cron_expr="* * * * *",
            action="Test action"
        )

        # 手动触发任务执行
        await manager._execute_task("test_task")

        assert mock_engine.run.called
        assert task.run_count == 1
        assert task.last_run is not None

    @pytest.mark.asyncio
    async def test_disabled_task_not_executed(self, mock_engine):
        """测试禁用的任务不执行"""
        manager = AutomationManager(engine=mock_engine)

        task = manager.add_cron_task(
            task_id="disabled_task",
            cron_expr="* * * * *",
            action="Test action"
        )

        # 禁用任务
        task.enabled = False

        # 尝试执行
        await manager._execute_task("disabled_task")

        assert not mock_engine.run.called
        assert task.run_count == 0

    @pytest.mark.asyncio
    async def test_manager_lifecycle(self, mock_engine, mock_event_bus):
        """测试管理器生命周期"""
        manager = AutomationManager(engine=mock_engine, event_bus=mock_event_bus)

        # 启动
        await manager.start()
        assert manager._running is True

        # 添加任务
        manager.add_cron_task("task1", "* * * * *", "action1")
        manager.add_event_task("task2", "test.event", "action2")

        # 停止
        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_multiple_event_tasks(self, mock_engine, mock_event_bus):
        """测试多个事件任务"""
        manager = AutomationManager(engine=mock_engine, event_bus=mock_event_bus)

        # 添加多个事件任务
        manager.add_event_task("task1", "event.type1", "action1")
        manager.add_event_task("task2", "event.type2", "action2")
        manager.add_event_task("task3", "event.type1", "action3")

        # 应该有3个订阅
        assert mock_event_bus.subscribe.call_count == 3


class TestAutomationTaskExecution:
    """任务执行测试"""

    @pytest.fixture
    def manager_with_engine(self):
        """创建带真实 Mock Engine 的管理器"""
        engine = MagicMock()
        engine.run = AsyncMock(return_value="Success")
        return AutomationManager(engine=engine)

    @pytest.mark.asyncio
    async def test_cron_task_execution_success(self, manager_with_engine):
        """测试 Cron 任务成功执行"""
        manager = manager_with_engine

        task = manager.add_cron_task(
            task_id="success_task",
            cron_expr="0 0 * * *",
            action="Daily task"
        )

        await manager._execute_task("success_task")

        assert task.run_count == 1
        assert task.last_run is not None
        assert manager.engine.run.called

    @pytest.mark.asyncio
    async def test_task_execution_with_error(self, manager_with_engine):
        """测试任务执行失败"""
        manager = manager_with_engine
        manager.engine.run = AsyncMock(side_effect=Exception("Engine error"))

        task = manager.add_cron_task(
            task_id="error_task",
            cron_expr="0 0 * * *",
            action="Failing task"
        )

        # 执行应该不抛出异常
        await manager._execute_task("error_task")

        # 任务不应该计数（因为失败了）
        assert task.run_count == 0

    @pytest.mark.asyncio
    async def test_webhook_execution(self):
        """测试 Webhook 执行"""
        manager = AutomationManager()

        received_payloads = []

        async def handler(payload, headers):
            received_payloads.append(payload)
            return {"processed": True}

        manager.add_webhook_handler("/test", handler)

        result = await manager.handle_webhook(
            "/test",
            {"event": "test"},
            {}
        )

        assert result == {"processed": True}
        assert len(received_payloads) == 1

    @pytest.mark.asyncio
    async def test_webhook_with_signature(self):
        """测试带签名的 Webhook"""
        manager = AutomationManager()

        async def handler(payload, headers):
            return "ok"

        manager.add_webhook_handler("/secure", handler, secret="my_secret")

        # 生成有效签名
        import json
        import hmac
        import hashlib

        payload = {"test": "data"}
        signature = "sha256=" + hmac.new(
            b"my_secret",
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()

        # 应该成功
        result = await manager.handle_webhook(
            "/secure",
            payload,
            {"X-Hub-Signature-256": signature}
        )
        assert result == "ok"

        # 无效签名应该失败
        with pytest.raises(PermissionError):
            await manager.handle_webhook(
                "/secure",
                payload,
                {"X-Hub-Signature-256": "invalid"}
            )
