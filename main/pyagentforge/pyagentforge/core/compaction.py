"""
上下文压缩模块 - 兼容层

注意：压缩核心逻辑已迁移到 plugins/middleware/compaction/ 目录。
此文件仅为向后兼容保留，新代码应直接从插件导入。

迁移说明:
- 旧: from pyagentforge.core.compaction import Compactor
- 新: from pyagentforge.plugins.middleware.compaction import Compactor
"""

# 从插件重新导出，保持向后兼容
from pyagentforge.plugins.middleware.compaction.compaction import (
    CompactionSettings,
    CompactionStrategy,
    CompactionResult,
    Compactor,
    AgentCompactor,
    DynamicCompactionConfig,
    MessageSegment,
    create_compactor,
)

__all__ = [
    "CompactionSettings",
    "CompactionStrategy",
    "CompactionResult",
    "Compactor",
    "AgentCompactor",
    "DynamicCompactionConfig",
    "MessageSegment",
    "create_compactor",
]

# 弃用警告将在未来版本中添加
# import warnings
# warnings.warn(
#     "从 pyagentforge.core.compaction 导入已弃用，"
#     "请改用 pyagentforge.plugins.middleware.compaction",
#     DeprecationWarning,
#     stacklevel=2,
# )
