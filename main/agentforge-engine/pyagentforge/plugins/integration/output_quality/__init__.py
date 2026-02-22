"""
Output Quality Plugin

Detects excessive comments and intelligently truncates tool output.
"""

from pyagentforge.plugins.integration.output_quality.PLUGIN import (
    OutputQualityPlugin,
    CommentChecker,
    CommentCheckResult,
    CommentThresholds,
    OutputTruncator,
    TruncationConfig,
    TruncationResult,
)

__all__ = [
    "OutputQualityPlugin",
    "CommentChecker",
    "CommentCheckResult",
    "CommentThresholds",
    "OutputTruncator",
    "TruncationConfig",
    "TruncationResult",
]
