"""
Failover Plugin

支持多 Provider 配置、自动故障转移和负载均衡
"""

import logging
from typing import Any, List, Optional

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType


class FailoverPlugin(Plugin):
    """Provider 故障转移插件"""

    metadata = PluginMetadata(
        id="middleware.failover",
        name="Provider Failover",
        version="1.0.0",
        type=PluginType.MIDDLEWARE,
        description="支持多 Provider 配置、自动故障转移和负载均衡",
        author="PyAgentForge",
        dependencies=[],
        provides=["failover"],
        priority=5,
    )

    def __init__(self):
        super().__init__()
        self._provider_pool = None

    async def on_plugin_activate(self) -> None:
        """激活插件"""
        await super().on_plugin_activate()
        from pyagentforge.plugins.middleware.failover.failover import ProviderPool, FailoverConfig

        config = self.context.config or {}
        failover_config = FailoverConfig(
            enabled=config.get("enabled", True),
            max_retries=config.get("max_retries", 3),
            retry_delay_ms=config.get("retry_delay_ms", 1000),
        )
        self._provider_pool = ProviderPool(failover_config)
        self.context.logger.info("Failover plugin activated")

    def get_provider_pool(self):
        """获取 Provider 池"""
        return self._provider_pool
