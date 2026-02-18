"""
Context Lifecycle Plugin

Monitors context usage and triggers preemptive compaction.
"""

from pyagentforge.plugins.middleware.context_lifecycle.PLUGIN import (
    ContextLifecycleConfig,
    ContextLifecyclePlugin,
)

__all__ = [
    "ContextLifecyclePlugin",
    "ContextLifecycleConfig",
]
