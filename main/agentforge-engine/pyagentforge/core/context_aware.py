"""
AGENTS.md 自动加载机制 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.plugins.integration.context_aware.prompt_manager
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.context_aware import AgentsMdLoader, ContextAwarePromptManager
- 新: from pyagentforge.plugins.integration.context_aware.prompt_manager import AgentsMdLoader, ContextAwarePromptManager
"""

# 重导出所有内容
from pyagentforge.plugins.integration.context_aware.prompt_manager import (
    AgentsMdLoader,
    DynamicPromptInjector,
    ContextAwarePromptManager,
)

__all__ = [
    "AgentsMdLoader",
    "DynamicPromptInjector",
    "ContextAwarePromptManager",
]

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.context_aware is deprecated. "
    "Use pyagentforge.plugins.integration.context_aware.prompt_manager instead.",
    DeprecationWarning,
    stacklevel=2,
)
