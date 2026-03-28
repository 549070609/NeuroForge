"""
Checkpoint Plugin

通过 Hook 系统为 AgentEngine 提供自动 checkpoint 能力。
可独立于 AgentEngine 内置 checkpoint 使用——即使引擎未配置
checkpointer，此插件也能在 hook 层面自动保存和恢复状态。
"""

from __future__ import annotations

from typing import Any

from pyagentforge.kernel.checkpoint import (
    BaseCheckpointer,
    FileCheckpointer,
)
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class CheckpointPlugin(Plugin):
    """自动 Checkpoint 插件

    在每次 LLM 调用后自动保存 checkpoint，
    在引擎启动时检查是否有可恢复的 checkpoint。
    """

    metadata = PluginMetadata(
        id="middleware.checkpoint",
        name="Auto Checkpoint",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="自动保存和恢复 Agent 执行状态",
        author="PyAgentForge",
        dependencies=[],
        provides=["checkpoint", "checkpointer"],
        priority=10,
    )

    def __init__(self) -> None:
        super().__init__()
        self._checkpointer: BaseCheckpointer | None = None
        self._iteration: int = 0
        self._engine: Any = None

    async def on_plugin_activate(self) -> None:
        await super().on_plugin_activate()

        config = self.context.config or {}
        backend = config.get("backend", "file")
        directory = config.get("directory", ".checkpoints")

        if backend == "file":
            self._checkpointer = FileCheckpointer(directory=directory)
        elif backend == "memory":
            from pyagentforge.kernel.checkpoint import MemoryCheckpointer
            self._checkpointer = MemoryCheckpointer()
        else:
            logger.warning(f"Unknown checkpoint backend: {backend}, using file")
            self._checkpointer = FileCheckpointer(directory=directory)

        if hasattr(self.context, "hook_registry") and self.context.hook_registry:
            self.context.hook_registry.register(
                HookType.ON_ENGINE_START, self, self._on_engine_start
            )
            self.context.hook_registry.register(
                HookType.ON_AFTER_LLM_CALL, self, self._on_after_llm_call
            )
            self.context.hook_registry.register(
                HookType.ON_TASK_COMPLETE, self, self._on_task_complete
            )

        logger.info(
            "Checkpoint plugin activated",
            extra_data={"backend": backend, "directory": directory},
        )

    async def on_plugin_deactivate(self) -> None:
        if hasattr(self.context, "hook_registry") and self.context.hook_registry:
            self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    async def _on_engine_start(self, engine: Any) -> None:
        """引擎启动时绑定引擎引用并注入 checkpointer"""
        self._engine = engine
        self._iteration = 0

        if self._checkpointer and not engine.checkpointer:
            engine.checkpointer = self._checkpointer
            logger.info("Injected checkpointer into engine via plugin")

    async def _on_after_llm_call(self, response: Any, **kwargs: Any) -> None:
        """每次 LLM 调用后递增 iteration 计数器（实际 checkpoint 由引擎执行）"""
        self._iteration += 1

    async def _on_task_complete(self, result: Any, **kwargs: Any) -> None:
        """任务完成后清理 checkpoint"""
        if self._engine and self._checkpointer:
            session_id = getattr(self._engine, "_session_id", None)
            if session_id:
                await self._checkpointer.delete(session_id)
                logger.debug(
                    "Cleaned up checkpoint on task complete",
                    extra_data={"session_id": session_id},
                )

    def get_checkpointer(self) -> BaseCheckpointer | None:
        return self._checkpointer
