"""
插件管理器

协调插件的加载、激活和管理
"""

import logging
from typing import Any, Dict, List, Optional

from pyagentforge.plugin.base import Plugin, PluginContext
from pyagentforge.plugin.hooks import HookRegistry, HookType
from pyagentforge.plugin.registry import PluginRegistry, PluginState
from pyagentforge.plugin.dependencies import DependencyResolver
from pyagentforge.plugin.loader import PluginLoader

logger = logging.getLogger(__name__)


class PluginManager:
    """插件管理器"""

    def __init__(self, engine: Any = None):
        """
        初始化插件管理器

        Args:
            engine: AgentEngine 实例 (可选，稍后设置)
        """
        self.engine = engine
        self.registry = PluginRegistry()
        self.hooks = HookRegistry()
        self.resolver = DependencyResolver(self.registry)
        self.loader = PluginLoader(self.registry, self.resolver)
        self.context: Optional[PluginContext] = None
        self._config: Dict[str, Dict[str, Any]] = {}

    async def initialize(
        self,
        config: Dict[str, Any],
        plugin_dirs: List[str] | None = None,
    ) -> None:
        """
        初始化插件系统

        Args:
            config: 配置字典，包含 enabled, disabled, plugin_dirs 等
            plugin_dirs: 额外的插件搜索目录
        """
        logger.info("Initializing plugin manager")

        self._config = config.get("config", {})

        # 合并插件目录
        all_plugin_dirs = config.get("plugin_dirs", [])
        if plugin_dirs:
            all_plugin_dirs.extend(plugin_dirs)

        # 获取启用的插件列表
        enabled_plugins = self._get_effective_plugins(config)

        if not enabled_plugins:
            logger.info("No plugins to load")
            return

        # 加载插件
        loaded = self.loader.load_all(enabled_plugins, all_plugin_dirs)
        logger.info(f"Loaded {len(loaded)} plugins")

        # 解析加载顺序
        try:
            load_order = self.resolver.resolve_load_order(list(loaded.keys()))
        except Exception as e:
            logger.error(f"Failed to resolve plugin dependencies: {e}")
            return

        # 按顺序激活插件
        for plugin_id in load_order:
            await self.activate_plugin(plugin_id)

    def _get_effective_plugins(self, config: Dict[str, Any]) -> List[str]:
        """
        计算最终启用的插件列表

        Args:
            config: 配置字典

        Returns:
            启用的插件ID列表
        """
        # 从预设获取基础列表
        preset = config.get("preset", "minimal")
        enabled = set(config.get("enabled", []))
        disabled = set(config.get("disabled", []))

        # 应用预设
        preset_plugins = self._get_preset_plugins(preset)

        # 合并：预设 + enabled - disabled
        effective = (preset_plugins | enabled) - disabled

        return list(effective)

    def _get_preset_plugins(self, preset: str) -> set:
        """获取预设的插件列表"""
        presets = {
            "minimal": set(),
            "standard": {
                "tools.code_tools",
                "tools.file_tools",
                "middleware.compaction",
                "integration.events",
            },
            "full": {
                "interface.rest_api",
                "protocol.mcp_server",
                "protocol.mcp_client",
                "protocol.lsp",
                "tools.web_tools",
                "tools.code_tools",
                "tools.file_tools",
                "tools.interact_tools",
                "middleware.compaction",
                "middleware.failover",
                "middleware.thinking",
                "middleware.rate_limit",
                "integration.persistence",
                "integration.events",
                "integration.context_aware",
            },
        }
        return presets.get(preset, set())

    async def activate_plugin(self, plugin_id: str) -> bool:
        """
        激活插件

        Args:
            plugin_id: 插件ID

        Returns:
            是否激活成功
        """
        plugin = self.registry.get(plugin_id)
        if plugin is None:
            logger.error(f"Plugin not found: {plugin_id}")
            return False

        if self.registry.is_activated(plugin_id):
            logger.warning(f"Plugin already activated: {plugin_id}")
            return True

        # 检查依赖
        satisfied, missing = self.resolver.check_satisfaction(plugin)
        if not satisfied:
            logger.error(
                f"Plugin {plugin_id} has unsatisfied dependencies: {missing}"
            )
            self.registry.set_error(
                plugin_id,
                f"Missing dependencies: {missing}"
            )
            return False

        # 检查冲突
        has_conflicts, conflicts = self.resolver.check_conflicts(plugin)
        if has_conflicts:
            logger.error(f"Plugin {plugin_id} has conflicts: {conflicts}")
            self.registry.set_error(
                plugin_id,
                f"Conflicts with: {conflicts}"
            )
            return False

        try:
            # 创建上下文
            plugin_config = self._config.get(plugin_id, {})
            self.context = PluginContext(
                engine=self.engine,
                config=plugin_config,
                logger=logging.getLogger(f"plugin.{plugin_id}"),
            )

            # 调用 on_plugin_load
            await plugin.on_plugin_load(self.context)

            # 调用 on_plugin_activate
            await plugin.on_plugin_activate()

            # 注册钩子
            self._register_hooks(plugin)

            # 注册工具
            self._register_tools(plugin)

            # 更新状态
            self.registry.set_state(plugin_id, PluginState.ACTIVATED)

            logger.info(f"Plugin activated: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to activate plugin {plugin_id}: {e}")
            self.registry.set_error(plugin_id, str(e))
            return False

    async def deactivate_plugin(self, plugin_id: str) -> bool:
        """
        停用插件

        Args:
            plugin_id: 插件ID

        Returns:
            是否停用成功
        """
        plugin = self.registry.get(plugin_id)
        if plugin is None:
            logger.error(f"Plugin not found: {plugin_id}")
            return False

        if not self.registry.is_activated(plugin_id):
            logger.warning(f"Plugin not activated: {plugin_id}")
            return True

        try:
            # 调用 on_plugin_deactivate
            await plugin.on_plugin_deactivate()

            # 注销钩子
            self.hooks.unregister_all(plugin)

            # 注销工具
            self._unregister_tools(plugin)

            # 更新状态
            self.registry.set_state(plugin_id, PluginState.DEACTIVATED)

            logger.info(f"Plugin deactivated: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to deactivate plugin {plugin_id}: {e}")
            return False

    async def emit_hook(
        self,
        hook_type: str | HookType,
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
            钩子返回值列表
        """
        if isinstance(hook_type, str):
            hook_type = HookType(hook_type)
        return await self.hooks.emit(hook_type, *args, **kwargs)

    def get_tools_from_plugins(self) -> list:
        """获取所有已激活插件提供的工具"""
        tools = []
        for plugin in self.registry.get_activated():
            tools.extend(plugin.get_tools())
        return tools

    def _register_hooks(self, plugin: Plugin) -> None:
        """注册插件的钩子"""
        hooks = plugin.get_hooks()
        for hook_name, callback in hooks.items():
            try:
                hook_type = HookType(hook_name)
                self.hooks.register(hook_type, plugin, callback)
            except ValueError:
                logger.warning(f"Unknown hook type: {hook_name}")

    def _register_tools(self, plugin: Plugin) -> None:
        """注册插件的工具"""
        tools = plugin.get_tools()
        if tools and self.engine:
            for tool in tools:
                self.engine.tools.register(tool)
                logger.debug(f"Registered tool: {tool.name} from {plugin.metadata.id}")

    def _unregister_tools(self, plugin: Plugin) -> None:
        """注销插件的工具"""
        tools = plugin.get_tools()
        if tools and self.engine:
            for tool in tools:
                self.engine.tools.unregister(tool.name)
                logger.debug(f"Unregistered tool: {tool.name} from {plugin.metadata.id}")

    def get_summary(self) -> Dict[str, Any]:
        """获取插件系统摘要"""
        return {
            "registry": self.registry.get_summary(),
            "hooks_count": sum(
                len(self.hooks.get_hooks(ht))
                for ht in HookType
            ),
        }
