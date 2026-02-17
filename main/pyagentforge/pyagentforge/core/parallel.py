"""
并行子代理执行器 - 兼容层

注意: 核心逻辑已迁移到 pyagentforge.plugins.integration.parallel_executor.executor
此文件仅用于向后兼容，将在未来版本中移除。

迁移指南:
- 旧: from pyagentforge.core.parallel import ParallelSubagentExecutor, SubagentTask
- 新: from pyagentforge.plugins.integration.parallel_executor.executor import ParallelSubagentExecutor, SubagentTask
"""

# 重导出所有内容
from pyagentforge.plugins.integration.parallel_executor.executor import (
    SubagentStatus,
    SubagentTask,
    SubagentResult,
    AGENT_TYPES,
    get_agent_type_config,
    ParallelSubagentExecutor,
    ParallelTaskTool,
)

__all__ = [
    "SubagentStatus",
    "SubagentTask",
    "SubagentResult",
    "AGENT_TYPES",
    "get_agent_type_config",
    "ParallelSubagentExecutor",
    "ParallelTaskTool",
]

# 发出弃用警告
import warnings

warnings.warn(
    "Importing from pyagentforge.core.parallel is deprecated. "
    "Use pyagentforge.plugins.integration.parallel_executor.executor instead.",
    DeprecationWarning,
    stacklevel=2,
)
