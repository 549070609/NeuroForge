"""
Automation Scheduler - 自动化调度器
"""

import asyncio
import hashlib
import hmac
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pyagentforge.automation.task import AutomationTask, TriggerType
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class AutomationManager:
    """
    自动化管理器

    支持:
    - Cron 定时任务
    - Webhook 触发
    - 事件触发

    Examples:
        >>> manager = AutomationManager(engine)
        >>> manager.add_cron_task("daily_report", "0 9 * * *", "Generate report")
        >>> await manager.start()
    """

    def __init__(self, engine: Any = None, event_bus: Any = None):
        """
        初始化自动化管理器

        Args:
            engine: Agent 引擎实例 (可选)
            event_bus: EventBus 实例 (可选)
        """
        self.engine = engine
        self.event_bus = event_bus
        self._tasks: dict[str, AutomationTask] = {}
        self._webhook_handlers: dict[str, dict[str, Any]] = {}
        self._running = False
        self._scheduler = None
        self._event_handlers: list[Any] = []  # 保存事件处理器引用

    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return

        self._running = True

        # 尝试使用 APScheduler (如果可用)
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
            self._scheduler.start()
            logger.info("Automation manager started with APScheduler")
        except ImportError:
            logger.info("Automation manager started (APScheduler not available)")

    async def stop(self) -> None:
        """停止调度器"""
        self._running = False

        # 停止 Cron 调度器
        if self._scheduler:
            self._scheduler.shutdown()
            self._scheduler = None

        # 取消事件订阅
        if self.event_bus:
            for handler in self._event_handlers:
                self.event_bus.unsubscribe(handler)
            self._event_handlers.clear()

        logger.info("Automation manager stopped")

    def add_cron_task(
        self,
        task_id: str,
        cron_expr: str,
        action: str,
        name: str | None = None,
        **kwargs: Any
    ) -> AutomationTask:
        """
        添加 Cron 定时任务

        Args:
            task_id: 任务 ID
            cron_expr: Cron 表达式，如 "0 9 * * 1-5" (工作日早9点)
            action: Agent 执行的 prompt
            name: 任务名称
            **kwargs: 额外参数

        Returns:
            创建的任务
        """
        task = AutomationTask(
            id=task_id,
            name=name or task_id,
            trigger_type=TriggerType.TIME,
            trigger_config={"cron": cron_expr},
            action=action,
            metadata=kwargs,
        )

        self._tasks[task_id] = task

        # 如果调度器可用，添加任务
        if self._scheduler:
            from apscheduler.triggers.cron import CronTrigger
            self._scheduler.add_job(
                self._execute_task,
                CronTrigger.from_crontab(cron_expr),
                args=[task_id],
                id=task_id,
            )

        logger.info(
            "Added cron task",
            extra_data={"task_id": task_id, "cron": cron_expr}
        )

        return task

    def add_webhook_handler(
        self,
        path: str,
        handler: Callable,
        secret: str | None = None
    ) -> None:
        """
        添加 Webhook 处理器

        Args:
            path: Webhook 路径，如 "/github/webhook"
            handler: 处理函数
            secret: 签名验证密钥
        """
        self._webhook_handlers[path] = {
            "handler": handler,
            "secret": secret,
        }
        logger.info(
            "Added webhook handler",
            extra_data={"path": path}
        )

    def add_event_task(
        self,
        task_id: str,
        event_type: str,
        action: str,
        name: str | None = None,
        condition: Callable[[dict], bool] | None = None,
        **kwargs: Any
    ) -> AutomationTask:
        """
        添加事件触发任务

        Args:
            task_id: 任务 ID
            event_type: 触发的事件类型
            action: Agent 执行的 prompt
            name: 任务名称
            condition: 可选条件检查函数，接收事件数据，返回是否执行
            **kwargs: 额外参数

        Returns:
            创建的任务

        Examples:
            >>> # 当收到特定消息时触发
            >>> manager.add_event_task(
            ...     "on_message",
            ...     "message.received",
            ...     "Summarize the received message",
            ...     condition=lambda data: data.get("urgent", False)
            ... )
        """
        task = AutomationTask(
            id=task_id,
            name=name or task_id,
            trigger_type=TriggerType.EVENT,
            trigger_config={
                "event_type": event_type,
                "condition": condition,
            },
            action=action,
            metadata=kwargs,
        )

        self._tasks[task_id] = task

        # 注册事件监听器
        if self.event_bus:
            async def event_handler(event: Any) -> None:
                """事件处理器"""
                if not task.enabled:
                    return

                # 检查条件
                if condition and not condition(event.data):
                    logger.debug(
                        f"Task {task_id} condition not met",
                        extra_data={"event_type": event_type}
                    )
                    return

                # 执行任务
                await self._execute_task(task_id)

            handler = self.event_bus.subscribe(
                event_handler,
                event_types=[event_type]
            )
            self._event_handlers.append(handler)

            logger.info(
                "Added event task",
                extra_data={
                    "task_id": task_id,
                    "event_type": event_type,
                }
            )

        return task

    async def handle_webhook(
        self,
        path: str,
        payload: dict[str, Any],
        headers: dict[str, str]
    ) -> Any:
        """
        处理 Webhook 请求

        Args:
            path: Webhook 路径
            payload: 请求体
            headers: 请求头

        Returns:
            处理结果

        Raises:
            ValueError: 路径未注册
            PermissionError: 签名验证失败
        """
        if path not in self._webhook_handlers:
            raise ValueError(f"No webhook handler for path: {path}")

        handler_info = self._webhook_handlers[path]

        # 验证签名
        if handler_info.get("secret"):
            signature = headers.get("X-Hub-Signature-256", "")
            if not self._verify_signature(payload, signature, handler_info["secret"]):
                raise PermissionError("Webhook signature verification failed")

        handler = handler_info["handler"]
        if asyncio.iscoroutinefunction(handler):
            return await handler(payload, headers)
        return handler(payload, headers)

    def list_tasks(self) -> list[AutomationTask]:
        """列出所有任务"""
        return list(self._tasks.values())

    def get_task(self, task_id: str) -> AutomationTask | None:
        """获取指定任务"""
        return self._tasks.get(task_id)

    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            if self._scheduler:
                self._scheduler.remove_job(task_id)
            return True
        return False

    async def _execute_task(self, task_id: str) -> None:
        """执行任务"""
        task = self._tasks.get(task_id)
        if not task or not task.enabled:
            return

        try:
            logger.info(f"Executing task: {task_id}")

            if self.engine:
                await self.engine.run(task.action)
            else:
                pass

            task.last_run = datetime.now()
            task.run_count += 1

            logger.info(
                f"Task completed: {task_id}",
                extra_data={"run_count": task.run_count}
            )

        except Exception as e:
            logger.error(
                f"Task failed: {task_id}",
                extra_data={"error": str(e)}
            )

    def _verify_signature(
        self,
        payload: dict[str, Any],
        signature: str,
        secret: str
    ) -> bool:
        """验证 Webhook 签名"""
        import json
        expected = "sha256=" + hmac.new(
            secret.encode(),
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
