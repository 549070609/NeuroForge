"""
插件注册表

管理已加载的插件
"""

import logging
from typing import Any, Dict, List, Optional
from pyagentforge.plugin.base import Plugin, PluginType

logger = logging.getLogger(__name__)


class PluginState(str):
    """插件状态"""
    DISCOVERED = "discovered"    # 已发现
    LOADED = "loaded"           # 已加载
    ACTIVATED = "activated"     # 已激活
    DEACTIVATED = "deactivated" # 已停用
    ERROR = "error"             # 错误


class PluginRegistry:
    """插件注册表"""

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._states: Dict[str, str] = {}
        self._errors: Dict[str, str] = {}  # plugin_id -> error_message

    def register(self, plugin: Plugin) -> None:
        """
        注册插件

        Args:
            plugin: 插件实例

        Raises:
            ValueError: 如果插件ID冲突
        """
        plugin_id = plugin.metadata.id

        if plugin_id in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin_id}")

        # 验证元数据
        self._validate_metadata(plugin.metadata)

        self._plugins[plugin_id] = plugin
        self._states[plugin_id] = PluginState.LOADED

        logger.info(f"Registered plugin: {plugin_id} v{plugin.metadata.version}")

    def unregister(self, plugin_id: str) -> None:
        """
        注销插件

        Args:
            plugin_id: 插件ID
        """
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            self._states.pop(plugin_id, None)
            self._errors.pop(plugin_id, None)
            logger.info(f"Unregistered plugin: {plugin_id}")

    def get(self, plugin_id: str) -> Optional[Plugin]:
        """获取插件"""
        return self._plugins.get(plugin_id)

    def get_all(self) -> List[Plugin]:
        """获取所有插件"""
        return list(self._plugins.values())

    def get_by_type(self, plugin_type: PluginType) -> List[Plugin]:
        """按类型获取插件"""
        return [
            p for p in self._plugins.values()
            if p.metadata.type == plugin_type
        ]

    def get_activated(self) -> List[Plugin]:
        """获取所有已激活的插件"""
        return [
            p for p in self._plugins.values()
            if self._states.get(p.metadata.id) == PluginState.ACTIVATED
        ]

    def get_state(self, plugin_id: str) -> Optional[str]:
        """获取插件状态"""
        return self._states.get(plugin_id)

    def set_state(self, plugin_id: str, state: str) -> None:
        """设置插件状态"""
        if plugin_id in self._plugins:
            self._states[plugin_id] = state
            logger.debug(f"Plugin {plugin_id} state changed to: {state}")

    def set_error(self, plugin_id: str, error: str) -> None:
        """设置插件错误"""
        self._errors[plugin_id] = error
        self._states[plugin_id] = PluginState.ERROR
        logger.error(f"Plugin {plugin_id} error: {error}")

    def get_error(self, plugin_id: str) -> Optional[str]:
        """获取插件错误信息"""
        return self._errors.get(plugin_id)

    def has_plugin(self, plugin_id: str) -> bool:
        """检查插件是否存在"""
        return plugin_id in self._plugins

    def is_activated(self, plugin_id: str) -> bool:
        """检查插件是否已激活"""
        return self._states.get(plugin_id) == PluginState.ACTIVATED

    def _validate_metadata(self, metadata) -> None:
        """验证插件元数据"""
        if not metadata.id:
            raise ValueError("Plugin metadata must have 'id'")
        if not metadata.name:
            raise ValueError("Plugin metadata must have 'name'")
        if not metadata.version:
            raise ValueError("Plugin metadata must have 'version'")
        if not isinstance(metadata.type, PluginType):
            raise ValueError(f"Invalid plugin type: {metadata.type}")

    def get_summary(self) -> Dict[str, Any]:
        """获取注册表摘要"""
        return {
            "total_plugins": len(self._plugins),
            "by_type": {
                pt.value: len(self.get_by_type(pt))
                for pt in PluginType
            },
            "by_state": {
                state: sum(1 for s in self._states.values() if s == state)
                for state in [
                    PluginState.LOADED,
                    PluginState.ACTIVATED,
                    PluginState.DEACTIVATED,
                    PluginState.ERROR,
                ]
            },
            "plugins": [
                {
                    "id": p.metadata.id,
                    "name": p.metadata.name,
                    "version": p.metadata.version,
                    "type": p.metadata.type.value,
                    "state": self._states.get(p.metadata.id),
                }
                for p in self._plugins.values()
            ],
        }
