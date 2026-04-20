"""
Ralph Loop Plugin

Auto-continuation system for agent task completion.
"""

from pyagentforge.plugins.integration.ralph_loop.engine import RalphLoopEngine
from pyagentforge.plugins.integration.ralph_loop.PLUGIN import RalphLoopPlugin

__all__ = [
    "RalphLoopPlugin",
    "RalphLoopEngine",
]
