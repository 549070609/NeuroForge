"""
Failover 兼容层

将旧的 pyagentforge.core.failover 导入重定向到新位置
使用延迟导入避免循环依赖
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyagentforge.plugins.middleware.failover.failover import (
        FailoverCondition,
        LoadBalanceStrategy,
        ProviderHealth,
        FailoverConfig,
        ProviderPool,
        create_provider_pool_from_config,
    )

__all__ = [
    "FailoverCondition",
    "LoadBalanceStrategy",
    "ProviderHealth",
    "FailoverConfig",
    "ProviderPool",
    "create_provider_pool_from_config",
]


def __getattr__(name: str):
    """延迟导入"""
    if name in __all__:
        from pyagentforge.plugins.middleware.failover.failover import (
            FailoverCondition,
            LoadBalanceStrategy,
            ProviderHealth,
            FailoverConfig,
            ProviderPool,
            create_provider_pool_from_config,
        )
        globals().update({
            "FailoverCondition": FailoverCondition,
            "LoadBalanceStrategy": LoadBalanceStrategy,
            "ProviderHealth": ProviderHealth,
            "FailoverConfig": FailoverConfig,
            "ProviderPool": ProviderPool,
            "create_provider_pool_from_config": create_provider_pool_from_config,
        })
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
