"""
Automation 单元测试
"""

import pytest
from datetime import datetime

from pyagentforge.automation.task import TriggerType, AutomationTask
from pyagentforge.automation.scheduler import AutomationManager


class TestTriggerType:
    """测试 TriggerType"""

    def test_trigger_types(self):
        """触发类型值"""
        assert TriggerType.TIME.value == "time"
        assert TriggerType.EVENT.value == "event"
        assert TriggerType.WEBHOOK.value == "webhook"


class TestAutomationTask:
    """测试 AutomationTask"""

    def test_create_task(self):
        """创建任务"""
        task = AutomationTask(
            id="task_001",
            name="Daily Report",
            trigger_type=TriggerType.TIME,
            trigger_config={"cron": "0 9 * * *"},
            action="Generate daily report"
        )
        assert task.id == "task_001"
        assert task.name == "Daily Report"
        assert task.trigger_type == TriggerType.TIME
        assert task.enabled is True
        assert task.run_count == 0

    def test_task_to_dict(self):
        """任务转字典"""
        task = AutomationTask(
            id="task_001",
            name="Test Task",
            trigger_type=TriggerType.WEBHOOK,
            trigger_config={"path": "/webhook"},
            action="Handle webhook"
        )
        d = task.to_dict()
        assert d["id"] == "task_001"
        assert d["trigger_type"] == "webhook"
        assert d["enabled"] is True


class TestAutomationManager:
    """测试 AutomationManager"""

    @pytest.fixture
    def manager(self):
        """创建管理器"""
        return AutomationManager()

    def test_create_manager(self, manager):
        """创建管理器"""
        assert len(manager.list_tasks()) == 0

    def test_add_cron_task(self, manager):
        """添加 Cron 任务"""
        task = manager.add_cron_task(
            task_id="daily_report",
            cron_expr="0 9 * * *",
            action="Generate report"
        )
        assert task.id == "daily_report"
        assert task.trigger_type == TriggerType.TIME
        assert len(manager.list_tasks()) == 1

    def test_get_task(self, manager):
        """获取任务"""
        manager.add_cron_task("task_1", "* * * * *", "action")
        task = manager.get_task("task_1")
        assert task is not None
        assert task.id == "task_1"

    def test_get_nonexistent_task(self, manager):
        """获取不存在的任务"""
        task = manager.get_task("nonexistent")
        assert task is None

    def test_remove_task(self, manager):
        """移除任务"""
        manager.add_cron_task("task_1", "* * * * *", "action")
        removed = manager.remove_task("task_1")
        assert removed is True
        assert len(manager.list_tasks()) == 0

    def test_remove_nonexistent_task(self, manager):
        """移除不存在的任务"""
        removed = manager.remove_task("nonexistent")
        assert removed is False

    def test_add_webhook_handler(self, manager):
        """添加 Webhook 处理器"""
        def handler(payload, headers):
            return "ok"

        manager.add_webhook_handler("/webhook", handler, secret="test_secret")
        assert "/webhook" in manager._webhook_handlers

    @pytest.mark.asyncio
    async def test_start_stop(self, manager):
        """启动和停止"""
        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

    @pytest.mark.asyncio
    async def test_handle_webhook(self, manager):
        """处理 Webhook"""
        received = []

        async def handler(payload, headers):
            received.append(payload)
            return {"status": "ok"}

        manager.add_webhook_handler("/test", handler)

        result = await manager.handle_webhook(
            "/test",
            {"event": "push"},
            {}
        )
        assert result["status"] == "ok"
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_path(self, manager):
        """处理无效路径的 Webhook"""
        with pytest.raises(ValueError):
            await manager.handle_webhook("/invalid", {}, {})

    @pytest.mark.asyncio
    async def test_handle_webhook_with_signature(self, manager):
        """带签名验证的 Webhook"""
        async def handler(payload, headers):
            return "ok"

        manager.add_webhook_handler("/secure", handler, secret="my_secret")

        # 无签名应该失败
        with pytest.raises(PermissionError):
            await manager.handle_webhook(
                "/secure",
                {"test": "data"},
                {"X-Hub-Signature-256": "invalid"}
            )
