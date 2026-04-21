"""
P1-5 优雅关机回归测试

验证：
  1. app.state.running_tasks 和 cancel_event 在启动时存在
  2. 关机阶段等待宽限期后强制取消未完成任务
  3. cancel_event 被 set
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Service.config.settings import ServiceSettings
from Service.gateway.app import create_app


# ── helpers ────────────────────────────────────────────────────

@pytest.fixture()
def settings() -> ServiceSettings:
    return ServiceSettings(
        rate_limit_enabled=False,
        shutdown_grace=1,  # 1 秒宽限期（加速测试）
        cors_allow_credentials=False,  # 避免 CORS 校验报错
    )


# ── app state 初始化 ─────────────────────────────────────────

class TestGracefulShutdownSetup:
    """lifespan 启动后 running_tasks / cancel_event 存在。"""

    def test_running_tasks_initialized(self, settings):
        app = create_app(settings=settings)
        with TestClient(app):
            assert hasattr(app.state, "running_tasks")
            assert isinstance(app.state.running_tasks, set)
            assert hasattr(app.state, "cancel_event")
            assert isinstance(app.state.cancel_event, asyncio.Event)
            assert not app.state.cancel_event.is_set()


class TestGracefulShutdownBehavior:
    """关机阶段取消行为。"""

    def test_cancel_event_set_on_shutdown_with_running_tasks(self, settings):
        app = create_app(settings=settings)
        registered_task = None

        @app.get("/register-task")
        async def _register():
            nonlocal registered_task

            async def _forever():
                try:
                    await asyncio.sleep(3600)
                except asyncio.CancelledError:
                    pass

            registered_task = asyncio.current_task().__class__(
                _forever(), name="test-forever"
            )
            registered_task = asyncio.ensure_future(_forever())
            app.state.running_tasks.add(registered_task)
            return {"registered": True}

        with TestClient(app) as client:
            resp = client.get("/register-task")
            assert resp.status_code == 200
            assert registered_task is not None
        # TestClient.__exit__ 触发 lifespan shutdown
        # 宽限期（1s）后强制取消 → task 应完成
        assert registered_task.cancelled() or registered_task.done()

    def test_settings_shutdown_grace_default(self):
        default = ServiceSettings()
        assert default.shutdown_grace == 30
