"""
思考级别控制模块 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.plugins.middleware.thinking.thinking
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.thinking import ThinkingLevel
- 新: from pyagentforge.plugins.middleware.thinking.thinking import ThinkingLevel
"""

# 重导出所有内容
from pyagentforge.plugins.middleware.thinking.thinking import (
    ThinkingLevel,
    ThinkingConfig,
    ThinkingBlock,
    THINKING_CAPABLE_MODELS,
    supports_thinking,
    get_thinking_provider,
    get_max_thinking_tokens,
    create_thinking_config,
)

__all__ = [
    "ThinkingLevel",
    "ThinkingConfig",
    "ThinkingBlock",
    "THINKING_CAPABLE_MODELS",
    "supports_thinking",
    "get_thinking_provider",
    "get_max_thinking_tokens",
    "create_thinking_config",
]

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.thinking is deprecated. "
    "Use pyagentforge.plugins.middleware.thinking.thinking instead.",
    DeprecationWarning,
    stacklevel=2,
)
