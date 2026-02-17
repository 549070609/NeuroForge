"""
Automation Scheduler - 自动化调度器
"""

import asyncio
import hashlib
import hmac
from datetime import datetime
from typing import Any, Callable, Optional

from pyagentforge.automation.task import TriggerType, AutomationTask
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

    def __init__(self, engine: Any = None):
        """
        初始化自动化管理器

        Args:
            engine: Agent 引擎实例 (可选)
        """
        self.engine = engine
        self._tasks: dict[str, AutomationTask] = {}
        self._webhook_handlers: dict[str, dict[str, Any]] = {}
        self._running = False
        self._scheduler = None

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
        if self._scheduler:
            self._scheduler.shutdown()
            self._scheduler = None
        logger.info("Automation manager stopped")

    def add_cron_task(
        self,
        task_id: str,
        cron_expr: str,
        action: str,
        name: Optional[str] = None,
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
        secret: Optional[str] = None
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

    def get_task(self, task_id: str) -> Optional[AutomationTask]:
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
                result = await self.engine.run(task.action)
            else:
                result = None

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
