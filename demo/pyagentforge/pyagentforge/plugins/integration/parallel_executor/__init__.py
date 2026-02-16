"""
Parallel Executor Plugin Package
"""

from pyagentforge.plugins.integration.parallel_executor.PLUGIN import (
    ParallelExecutorPlugin,
    SubagentStatus,
    SubagentTask,
    SubagentResult,
)

__all__ = ["ParallelExecutorPlugin", "SubagentStatus", "SubagentTask", "SubagentResult"]
