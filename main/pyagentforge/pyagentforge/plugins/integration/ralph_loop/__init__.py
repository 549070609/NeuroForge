"""
Ralph Loop Plugin

Auto-continuation system for agent task completion.
"""

from pyagentforge.plugins.integration.ralph_loop.PLUGIN import RalphLoopPlugin
from pyagentforge.plugins.integration.ralph_loop.engine import RalphLoopEngine

__all__ = [
    "RalphLoopPlugin",
    "RalphLoopEngine",
]
