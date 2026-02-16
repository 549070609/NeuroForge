"""
Events Plugin

提供事件总线功能
"""

import logging
from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class EventsPlugin(Plugin):
    """事件总线插件"""

    metadata = PluginMetadata(
        id="integration.events",
        name="Event Bus",
        version="1.0.0",
        type=PluginType.INTEGRATION,
        description="提供组件间解耦的事件发布订阅机制",
        author="PyAgentForge",
        provides=["events"],
        dependencies=[],
    )

    def __init__(self):
        super().__init__()
        self._event_bus = None

    async def on_plugin_activate(self) -> None:
        """激活插件"""
        await super().on_plugin_activate()
        # 延迟导入避免循环依赖
        from pyagentforge.core.events import EventBus
        self._event_bus = EventBus("plugin_events")
        self.context.logger.info("Event bus initialized")

    async def on_plugin_deactivate(self) -> None:
        """停用插件"""
        if self._event_bus:
            self._event_bus.clear_handlers()
        await super().on_plugin_deactivate()

    def get_event_bus(self):
        """获取事件总线实例"""
        return self._event_bus
