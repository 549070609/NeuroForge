"""
Parallel Executor Plugin Package
"""

from pyagentforge.plugins.integration.parallel_executor.PLUGIN import (
    ParallelExecutorPlugin,
    SubagentResult,
    SubagentStatus,
    SubagentTask,
)

__all__ = ["ParallelExecutorPlugin", "SubagentStatus", "SubagentTask", "SubagentResult"]
