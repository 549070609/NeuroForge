"""
Session Recovery Plugin

Auto-recovery from session crashes with automatic state saving.
"""

from pyagentforge.plugins.integration.session_recovery.PLUGIN import (
    SessionRecoveryConfig,
    SessionRecoveryPlugin,
)

__all__ = [
    "SessionRecoveryPlugin",
    "SessionRecoveryConfig",
]
