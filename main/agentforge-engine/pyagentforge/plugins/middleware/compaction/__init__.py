"""
Compaction Plugin Package

提供上下文压缩功能，支持：
- 简单 LLM 摘要压缩
- Agent 智能压缩
- 动态配置压缩参数
"""

from pyagentforge.plugins.middleware.compaction.compaction import (
    AgentCompactor,
    CompactionResult,
    CompactionSettings,
    CompactionStrategy,
    Compactor,
    DynamicCompactionConfig,
    MessageSegment,
    create_compactor,
)
from pyagentforge.plugins.middleware.compaction.PLUGIN import CompactionPlugin

__all__ = [
    # Plugin
    "CompactionPlugin",
    # Core classes
    "CompactionSettings",
    "CompactionStrategy",
    "CompactionResult",
    "Compactor",
    "AgentCompactor",
    "DynamicCompactionConfig",
    "MessageSegment",
    "create_compactor",
]
