"""
插件加载器

发现和加载插件
"""

import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pyagentforge.plugin.base import Plugin
from pyagentforge.plugin.registry import PluginRegistry
from pyagentforge.plugin.dependencies import DependencyResolver

logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """插件加载错误"""
    pass


class PluginLoader:
    """插件加载器"""

    def __init__(
        self,
        registry: PluginRegistry,
        resolver: DependencyResolver,
    ):
        self.registry = registry
        self.resolver = resolver

    def discover(self, plugin_dirs: List[str]) -> List[str]:
        """
        发现插件目录

        Args:
            plugin_dirs: 插件搜索目录列表

        Returns:
            发现的插件路径列表
        """
        discovered = []

        for base_dir in plugin_dirs:
            base_path = Path(base_dir)
            if not base_path.exists():
                logger.warning(f"Plugin directory does not exist: {base_dir}")
                continue

            # 查找包含 PLUGIN.py 或 plugin.py 的目录
            for plugin_file in base_path.rglob("PLUGIN.py"):
                discovered.append(str(plugin_file.parent))

            for plugin_file in base_path.rglob("plugin.py"):
                plugin_file_name = plugin_file.name
                # 避免重复发现
                if str(plugin_file.parent) not in discovered:
                    discovered.append(str(plugin_file.parent))

        logger.info(f"Discovered {len(discovered)} plugin directories")
        return discovered

    def load(self, plugin_path: str) -> Plugin:
        """
        从路径加载插件

        Args:
            plugin_path: 插件目录路径

        Returns:
            插件实例

        Raises:
            PluginLoadError: 加载失败
        """
        path = Path(plugin_path)

        if not path.exists():
            raise PluginLoadError(f"Plugin path does not exist: {plugin_path}")

        # 尝试加载 PLUGIN.py 或 plugin.py
        plugin_file = path / "PLUGIN.py"
        if not plugin_file.exists():
            plugin_file = path / "plugin.py"

        if not plugin_file.exists():
            raise PluginLoadError(
                f"No PLUGIN.py or plugin.py found in {plugin_path}"
            )

        try:
            # 动态导入模块
            spec = importlib.util.spec_from_file_location(
                f"plugin_{path.name}",
                plugin_file,
            )
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Cannot load spec from {plugin_file}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 查找 Plugin 子类
            plugin_class = self._find_plugin_class(module)
            if plugin_class is None:
                raise PluginLoadError(
                    f"No Plugin subclass found in {plugin_file}"
                )

            # 实例化插件
            plugin = plugin_class()

            return plugin

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin from {plugin_path}: {e}")

    def load_from_module(self, module_name: str) -> Plugin:
        """
        从Python模块加载插件

        Args:
            module_name: 模块名 (如 pyagentforge.plugins.integration.events)

        Returns:
            插件实例
        """
        try:
            module = importlib.import_module(module_name)
            plugin_class = self._find_plugin_class(module)

            if plugin_class is None:
                raise PluginLoadError(
                    f"No Plugin subclass found in module {module_name}"
                )

            return plugin_class()

        except ImportError as e:
            raise PluginLoadError(f"Cannot import module {module_name}: {e}")

    def load_all(
        self,
        plugin_ids: List[str],
        plugin_dirs: List[str] | None = None,
    ) -> Dict[str, Plugin]:
        """
        加载所有插件

        Args:
            plugin_ids: 要加载的插件ID列表
            plugin_dirs: 插件搜索目录

        Returns:
            {plugin_id: Plugin} 字典
        """
        loaded = {}
        discovered_paths = {}

        # 发现所有插件
        if plugin_dirs:
            for plugin_path in self.discover(plugin_dirs):
                try:
                    # 临时加载获取ID
                    temp_plugin = self.load(plugin_path)
                    discovered_paths[temp_plugin.metadata.id] = plugin_path
                except Exception as e:
                    logger.warning(f"Failed to discover plugin at {plugin_path}: {e}")

        # 按依赖顺序加载
        for plugin_id in plugin_ids:
            if plugin_id in loaded:
                continue

            try:
                # 先尝试从已发现的路径加载
                if plugin_id in discovered_paths:
                    plugin = self.load(discovered_paths[plugin_id])
                else:
                    # 尝试作为模块加载
                    module_name = self._plugin_id_to_module(plugin_id)
                    plugin = self.load_from_module(module_name)

                loaded[plugin_id] = plugin
                self.registry.register(plugin)

            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_id}: {e}")
                self.registry.set_error(plugin_id, str(e))

        return loaded

    def _find_plugin_class(self, module) -> Optional[Type[Plugin]]:
        """在模块中查找 Plugin 子类"""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, Plugin)
                and attr is not Plugin
            ):
                return attr
        return None

    def _plugin_id_to_module(self, plugin_id: str) -> str:
        """
        将插件ID转换为模块名

        例如: "interface.rest-api" -> "pyagentforge.plugins.interface.rest_api"
        """
        parts = plugin_id.replace("-", "_").split(".")
        return f"pyagentforge.plugins.{'.'.join(parts)}"
