"""
钩子系统

定义和管理插件钩子
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Tuple
import logging
import asyncio

logger = logging.getLogger(__name__)


class HookType(str, Enum):
    """钩子类型"""
    # 生命周期钩子
    ON_PLUGIN_LOAD = "on_plugin_load"
    ON_PLUGIN_ACTIVATE = "on_plugin_activate"
    ON_PLUGIN_DEACTIVATE = "on_plugin_deactivate"

    # 引擎钩子
    ON_ENGINE_INIT = "on_engine_init"
    ON_ENGINE_START = "on_engine_start"
    ON_ENGINE_STOP = "on_engine_stop"

    # 执行钩子
    ON_BEFORE_LLM_CALL = "on_before_llm_call"
    ON_AFTER_LLM_CALL = "on_after_llm_call"
    ON_BEFORE_TOOL_CALL = "on_before_tool_call"
    ON_AFTER_TOOL_CALL = "on_after_tool_call"

    # 上下文钩子
    ON_CONTEXT_OVERFLOW = "on_context_overflow"
    ON_TASK_COMPLETE = "on_task_complete"
    ON_SKILL_LOAD = "on_skill_load"
    ON_SUBAGENT_SPAWN = "on_subagent_spawn"


class HookRegistry:
    """钩子注册表 - 管理所有插件的钩子注册和执行"""

    def __init__(self):
        # hook_type -> [(plugin, callback), ...]
        self._hooks: Dict[HookType, List[Tuple[Any, Callable]]] = {
            hook_type: [] for hook_type in HookType
        }

    def register(
        self,
        hook_type: HookType,
        plugin: Any,
        callback: Callable,
    ) -> None:
        """
        注册钩子

        Args:
            hook_type: 钩子类型
            plugin: 插件实例
            callback: 回调函数
        """
        self._hooks[hook_type].append((plugin, callback))
        logger.debug(
            f"Registered hook: {hook_type.value} for plugin {plugin.metadata.id}"
        )

    def unregister(
        self,
        hook_type: HookType,
        plugin: Any,
    ) -> None:
        """
        注销钩子

        Args:
            hook_type: 钩子类型
            plugin: 插件实例
        """
        self._hooks[hook_type] = [
            (p, cb) for p, cb in self._hooks[hook_type]
            if p is not plugin
        ]
        logger.debug(
            f"Unregistered hook: {hook_type.value} for plugin {plugin.metadata.id}"
        )

    def unregister_all(self, plugin: Any) -> None:
        """
        注销插件的所有钩子

        Args:
            plugin: 插件实例
        """
        for hook_type in HookType:
            self.unregister(hook_type, plugin)

    async def emit(
        self,
        hook_type: HookType,
        *args,
        **kwargs,
    ) -> List[Any]:
        """
        触发钩子事件

        Args:
            hook_type: 钩子类型
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            所有非None的返回值列表
        """
        results = []
        hooks = self._hooks.get(hook_type, [])

        logger.debug(
            f"Emitting hook: {hook_type.value} to {len(hooks)} listeners"
        )

        for plugin, callback in hooks:
            try:
                result = callback(*args, **kwargs)
                # 处理协程
                if asyncio.iscoroutine(result):
                    result = await result

                if result is not None:
                    results.append(result)
                    logger.debug(
                        f"Hook {hook_type.value} from {plugin.metadata.id} "
                        f"returned: {type(result).__name__}"
                    )
            except Exception as e:
                logger.error(
                    f"Error in hook {hook_type.value} from {plugin.metadata.id}: {e}"
                )

        return results

    def get_hooks(self, hook_type: HookType) -> List[Tuple[Any, Callable]]:
        """获取特定类型的所有钩子"""
        return self._hooks.get(hook_type, [])

    def has_hooks(self, hook_type: HookType) -> bool:
        """检查是否有特定类型的钩子"""
        return len(self._hooks.get(hook_type, [])) > 0
