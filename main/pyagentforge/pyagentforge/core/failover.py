"""
Provider 故障转移系统 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.plugins.middleware.failover.failover
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.failover import ProviderPool, FailoverConfig
- 新: from pyagentforge.plugins.middleware.failover.failover import ProviderPool, FailoverConfig
"""

# 重导出所有内容
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

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.failover is deprecated. "
    "Use pyagentforge.plugins.middleware.failover.failover instead.",
    DeprecationWarning,
    stacklevel=2,
)
