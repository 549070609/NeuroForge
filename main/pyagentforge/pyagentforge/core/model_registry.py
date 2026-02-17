"""
模型注册模块 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.kernel.model_registry
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.model_registry import ModelRegistry
- 新: from pyagentforge.kernel import ModelRegistry
"""

# 重导出所有内容
from pyagentforge.kernel.model_registry import (
    ProviderType,
    ModelConfig,
    ProviderInfo,
    ModelRegistry,
    BUILTIN_MODELS,
    get_registry,
    register_model,
    get_model,
    register_provider,
)

__all__ = [
    "ProviderType",
    "ModelConfig",
    "ProviderInfo",
    "ModelRegistry",
    "BUILTIN_MODELS",
    "get_registry",
    "register_model",
    "get_model",
    "register_provider",
]

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.model_registry is deprecated. "
    "Use pyagentforge.kernel.model_registry instead.",
    DeprecationWarning,
    stacklevel=2,
)
