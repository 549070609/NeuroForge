"""
钩子系统

定义和管理插件钩子，支持优先级和链式处理。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Tuple, Union
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


class HookResult(str, Enum):
    """
    钩子执行结果

    CONTINUE: 继续执行下一个钩子
    STOP: 停止执行链，返回当前结果
    MODIFY: 修改数据后继续（用于链式处理）
    """

    CONTINUE = "continue"
    STOP = "stop"
    MODIFY = "modify"


class HookPriority(int, Enum):
    """钩子优先级 - 越高越先执行"""

    HIGHEST = 1000
    HIGH = 750
    NORMAL = 500
    LOW = 250
    LOWEST = 0


@dataclass
class HookEntry:
    """钩子条目"""

    plugin: Any
    callback: Callable
    priority: int = HookPriority.NORMAL.value

    def __lt__(self, other: "HookEntry") -> bool:
        """用于排序，优先级高的排前面"""
        return self.priority > other.priority


@dataclass
class HookChainResult:
    """钩子链执行结果"""

    results: List[Any] = field(default_factory=list)
    stopped: bool = False
    stopped_by: str = ""  # 停止的插件 ID
    last_modified_data: Any = None


class HookRegistry:
    """
    钩子注册表 - 管理所有插件的钩子注册和执行

    Features:
    - 支持优先级排序
    - 支持链式处理
    - 支持 HookResult 控制
    - 异步回调支持
    """

    def __init__(self):
        # hook_type -> [HookEntry, ...]
        self._hooks: Dict[HookType, List[HookEntry]] = {
            hook_type: [] for hook_type in HookType
        }
        # 缓存排序后的钩子
        self._sorted_cache: Dict[HookType, bool] = {
            hook_type: False for hook_type in HookType
        }

    def register(
        self,
        hook_type: HookType,
        plugin: Any,
        callback: Callable,
        priority: int = HookPriority.NORMAL.value,
    ) -> None:
        """
        注册钩子

        Args:
            hook_type: 钩子类型
            plugin: 插件实例
            callback: 回调函数
            priority: 优先级（越高越先执行）
        """
        entry = HookEntry(
            plugin=plugin,
            callback=callback,
            priority=priority,
        )
        self._hooks[hook_type].append(entry)
        # 标记需要重新排序
        self._sorted_cache[hook_type] = False

        plugin_id = getattr(plugin, "metadata", None)
        plugin_id = plugin_id.id if plugin_id else str(id(plugin))

        logger.debug(
            f"Registered hook: {hook_type.value} for plugin {plugin_id}",
            extra_data={"priority": priority},
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
        original_count = len(self._hooks[hook_type])
        self._hooks[hook_type] = [
            entry for entry in self._hooks[hook_type]
            if entry.plugin is not plugin
        ]

        plugin_id = getattr(plugin, "metadata", None)
        plugin_id = plugin_id.id if plugin_id else str(id(plugin))

        if len(self._hooks[hook_type]) < original_count:
            self._sorted_cache[hook_type] = False
            logger.debug(
                f"Unregistered hook: {hook_type.value} for plugin {plugin_id}"
            )

    def unregister_all(self, plugin: Any) -> None:
        """
        注销插件的所有钩子

        Args:
            plugin: 插件实例
        """
        for hook_type in HookType:
            self.unregister(hook_type, plugin)

    def _ensure_sorted(self, hook_type: HookType) -> None:
        """确保钩子按优先级排序"""
        if not self._sorted_cache[hook_type]:
            self._hooks[hook_type].sort()
            self._sorted_cache[hook_type] = True

    async def emit(
        self,
        hook_type: HookType,
        *args,
        **kwargs,
    ) -> List[Any]:
        """
        触发钩子事件（标准模式）

        按优先级顺序执行所有钩子，收集所有非 None 返回值。

        Args:
            hook_type: 钩子类型
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            所有非None的返回值列表
        """
        self._ensure_sorted(hook_type)
        results = []
        hooks = self._hooks.get(hook_type, [])

        logger.debug(
            f"Emitting hook: {hook_type.value} to {len(hooks)} listeners"
        )

        for entry in hooks:
            try:
                result = entry.callback(*args, **kwargs)
                # 处理协程
                if asyncio.iscoroutine(result):
                    result = await result

                if result is not None:
                    results.append(result)

                    plugin_id = getattr(entry.plugin, "metadata", None)
                    plugin_id = plugin_id.id if plugin_id else str(id(entry.plugin))

                    logger.debug(
                        f"Hook {hook_type.value} from {plugin_id} "
                        f"returned: {type(result).__name__}"
                    )

            except Exception as e:
                plugin_id = getattr(entry.plugin, "metadata", None)
                plugin_id = plugin_id.id if plugin_id else str(id(entry.plugin))

                logger.error(
                    f"Error in hook {hook_type.value} from {plugin_id}: {e}"
                )

        return results

    async def emit_chain(
        self,
        hook_type: HookType,
        initial_data: Any = None,
        *args,
        **kwargs,
    ) -> HookChainResult:
        """
        触发钩子事件（链式处理模式）

        按优先级顺序执行钩子，支持：
        - 前一个钩子的输出作为下一个的输入
        - 通过返回 HookResult.STOP 停止链
        - 通过返回 HookResult.MODIFY 修改数据

        Args:
            hook_type: 钩子类型
            initial_data: 初始数据
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            HookChainResult 包含所有结果和链状态
        """
        self._ensure_sorted(hook_type)
        hooks = self._hooks.get(hook_type, [])

        result = HookChainResult(last_modified_data=initial_data)

        logger.debug(
            f"Emitting chain hook: {hook_type.value} to {len(hooks)} listeners"
        )

        for entry in hooks:
            try:
                # 调用回调，传入当前数据
                hook_result = entry.callback(
                    result.last_modified_data,
                    *args,
                    **kwargs,
                )

                # 处理协程
                if asyncio.iscoroutine(hook_result):
                    hook_result = await hook_result

                plugin_id = getattr(entry.plugin, "metadata", None)
                plugin_id = plugin_id.id if plugin_id else str(id(entry.plugin))

                # 解析结果
                if hook_result is None:
                    continue

                # 检查是否返回了 HookResult
                if isinstance(hook_result, HookResult):
                    if hook_result == HookResult.STOP:
                        result.stopped = True
                        result.stopped_by = plugin_id
                        logger.debug(
                            f"Hook chain stopped by {plugin_id}"
                        )
                        break
                    # CONTINUE 或 MODIFY 都继续
                else:
                    # 非 HookResult 类型，作为数据修改
                    result.results.append(hook_result)
                    result.last_modified_data = hook_result

            except Exception as e:
                plugin_id = getattr(entry.plugin, "metadata", None)
                plugin_id = plugin_id.id if plugin_id else str(id(entry.plugin))

                logger.error(
                    f"Error in chain hook {hook_type.value} from {plugin_id}: {e}"
                )

        return result

    async def emit_until_handled(
        self,
        hook_type: HookType,
        *args,
        **kwargs,
    ) -> Tuple[bool, Any]:
        """
        触发钩子事件（首次处理模式）

        按优先级执行钩子，直到有一个钩子返回非 None 结果。
        适用于事件处理场景，如 ON_CONTEXT_OVERFLOW。

        Args:
            hook_type: 钩子类型
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            (是否被处理, 处理结果)
        """
        self._ensure_sorted(hook_type)
        hooks = self._hooks.get(hook_type, [])

        logger.debug(
            f"Emitting until handled hook: {hook_type.value} to {len(hooks)} listeners"
        )

        for entry in hooks:
            try:
                result = entry.callback(*args, **kwargs)

                # 处理协程
                if asyncio.iscoroutine(result):
                    result = await result

                # 检查是否处理了
                if result is not None:
                    plugin_id = getattr(entry.plugin, "metadata", None)
                    plugin_id = plugin_id.id if plugin_id else str(id(entry.plugin))

                    logger.debug(
                        f"Hook {hook_type.value} handled by {plugin_id}"
                    )
                    return True, result

            except Exception as e:
                plugin_id = getattr(entry.plugin, "metadata", None)
                plugin_id = plugin_id.id if plugin_id else str(id(entry.plugin))

                logger.error(
                    f"Error in hook {hook_type.value} from {plugin_id}: {e}"
                )

        return False, None

    def get_hooks(self, hook_type: HookType) -> List[HookEntry]:
        """获取特定类型的所有钩子（已排序）"""
        self._ensure_sorted(hook_type)
        return self._hooks.get(hook_type, [])

    def has_hooks(self, hook_type: HookType) -> bool:
        """检查是否有特定类型的钩子"""
        return len(self._hooks.get(hook_type, [])) > 0

    def get_hook_count(self, hook_type: HookType) -> int:
        """获取特定类型钩子的数量"""
        return len(self._hooks.get(hook_type, []))

    def clear(self, hook_type: HookType | None = None) -> None:
        """
        清除钩子

        Args:
            hook_type: 要清除的钩子类型，None 表示清除所有
        """
        if hook_type is None:
            for ht in HookType:
                self._hooks[ht] = []
                self._sorted_cache[ht] = False
        else:
            self._hooks[hook_type] = []
            self._sorted_cache[hook_type] = False

        logger.debug(f"Cleared hooks: {hook_type or 'ALL'}")


# 便捷函数
def create_hook_registry() -> HookRegistry:
    """创建新的钩子注册表"""
    return HookRegistry()
