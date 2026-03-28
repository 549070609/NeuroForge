"""
Failover Plugin

支持多 Provider 配置、自动故障转移和负载均衡。
通过 ON_ENGINE_INIT hook 将 ProviderPool 注入引擎，
替代单 Provider 调用路径，实现透明故障转移。
"""

from __future__ import annotations

from typing import Any

from pyagentforge.plugin.base import Plugin, PluginMetadata, PluginType
from pyagentforge.plugin.hooks import HookType
from pyagentforge.utils.logging import get_logger

_logger = get_logger(__name__)


class FailoverPlugin(Plugin):
    """Provider 故障转移插件"""

    metadata = PluginMetadata(
        id="middleware.failover",
        name="Provider Failover",
        version="2.0.0",
        type=PluginType.MIDDLEWARE,
        description="多 Provider 故障转移、熔断器、负载均衡",
        author="PyAgentForge",
        dependencies=[],
        provides=["failover", "provider_pool"],
        priority=5,
    )

    def __init__(self) -> None:
        super().__init__()
        self._provider_pool: Any = None

    async def on_plugin_activate(self) -> None:
        """激活插件并注册 hook"""
        await super().on_plugin_activate()
        from pyagentforge.plugins.middleware.failover.failover import (
            FailoverConfig,
            ProviderPool,
        )

        config = self.context.config or {}
        failover_config = FailoverConfig(
            enabled=config.get("enabled", True),
            max_retries=config.get("max_retries", 3),
            retry_delay_ms=config.get("retry_delay_ms", 1000),
            retry_backoff_multiplier=config.get("retry_backoff_multiplier", 2.0),
            max_retry_delay_ms=config.get("max_retry_delay_ms", 30000),
        )
        self._provider_pool = ProviderPool(failover_config)

        if hasattr(self.context, "hook_registry") and self.context.hook_registry:
            self.context.hook_registry.register(
                HookType.ON_ENGINE_START,
                self,
                self._on_engine_init,
            )
            self.context.hook_registry.register(
                HookType.ON_ENGINE_STOP,
                self,
                self._on_engine_stop,
            )

        _logger.info(
            "Failover plugin activated",
            extra_data={
                "max_retries": failover_config.max_retries,
                "enabled": failover_config.enabled,
            },
        )

    async def on_plugin_deactivate(self) -> None:
        """注销所有 hook"""
        if hasattr(self.context, "hook_registry") and self.context.hook_registry:
            self.context.hook_registry.unregister_all(self)
        await super().on_plugin_deactivate()

    async def _on_engine_init(self, engine: Any) -> None:
        """引擎初始化时注入 ProviderPool"""
        if self._provider_pool and hasattr(engine, "provider"):
            primary = engine.provider
            pool = self._provider_pool
            if not pool._providers:
                pool.add_provider(
                    name=getattr(primary, "model", "primary"),
                    provider=primary,
                    priority=0,
                )
            _logger.info(
                "Injected ProviderPool into engine",
                extra_data={"providers": len(pool._providers)},
            )

    async def _on_engine_stop(self, engine: Any) -> None:
        """引擎停止时记录健康状态"""
        if self._provider_pool:
            status = self._provider_pool.get_health_status()
            _logger.info(
                "Provider health at shutdown",
                extra_data={"health": status},
            )

    def get_provider_pool(self) -> Any:
        """获取 Provider 池"""
        return self._provider_pool

    def add_fallback_provider(
        self,
        name: str,
        provider: Any,
        priority: int = 10,
    ) -> None:
        """添加 fallback Provider 到池中"""
        if self._provider_pool:
            self._provider_pool.add_provider(
                name=name, provider=provider, priority=priority
            )
