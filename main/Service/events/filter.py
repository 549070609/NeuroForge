"""
Event Filter - Pattern matching for SSE event subscriptions.

Supports:
- Exact match: "stream"
- Wildcard: "plugin:thinking:*"
- Negation: "!plugin:thinking:debug"
- Multiple patterns: ["stream", "tool_*"]
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable


def match_pattern(event_type: str, pattern: str) -> bool:
    """
    Check if event type matches a pattern.

    Args:
        event_type: Event type to match (e.g., "plugin:thinking:debug")
        pattern: Pattern to match against
            - Exact: "stream"
            - Wildcard: "plugin:thinking:*" (matches any plugin:thinking:*)
            - Negation: "!stream" (excludes stream events)

    Returns:
        True if matches
    """
    # Handle negation
    if pattern.startswith("!"):
        return not match_pattern(event_type, pattern[1:])

    # Exact match
    if pattern == event_type:
        return True

    # Wildcard match using fnmatch
    if fnmatch.fnmatch(event_type, pattern):
        return True

    # Convert wildcard to regex for more complex patterns
    regex_pattern = pattern.replace("*", ".*").replace("?", ".")
    return bool(re.fullmatch(regex_pattern, event_type))


def should_emit_event(event_type: str, patterns: Iterable[str]) -> bool:
    """
    Determine if an event should be emitted based on filter patterns.

    Args:
        event_type: Event type to check
        patterns: List of patterns (inclusion/exclusion)
            - Positive patterns: include matching events
            - Negative patterns (!pattern): exclude matching events
            - If only negative patterns, include all except excluded
            - If positive patterns exist, only include those not excluded

    Returns:
        True if event should be emitted

    Examples:
        >>> should_emit_event("stream", ["stream", "tool_*"])
        True
        >>> should_emit_event("plugin:thinking:debug", ["plugin:thinking:*", "!plugin:thinking:debug"])
        False
        >>> should_emit_event("stream", ["!complete"])
        True
    """
    patterns = list(patterns)

    # Separate positive and negative patterns
    positive = [p for p in patterns if not p.startswith("!")]
    negative = [p for p in patterns if p.startswith("!")]

    # If no positive patterns, include all by default
    included = True if not positive else any(match_pattern(event_type, p) for p in positive)

    # Check if excluded by negative pattern
    if included and negative:
        excluded = any(match_pattern(event_type, p) for p in negative)
        included = not excluded

    return included


class EventFilter:
    """
    Event filter with pattern support.

    Usage:
        filter = EventFilter(["stream", "tool_*"])
        if filter.should_emit("stream"):
            # emit event
    """

    def __init__(self, patterns: Iterable[str] | None = None):
        """
        Initialize filter.

        Args:
            patterns: Filter patterns (None = allow all)
        """
        self.patterns = list(patterns) if patterns else []

    def should_emit(self, event_type: str) -> bool:
        """
        Check if event should be emitted.

        Args:
            event_type: Event type

        Returns:
            True if should emit
        """
        if not self.patterns:
            return True
        return should_emit_event(event_type, self.patterns)

    def add_pattern(self, pattern: str) -> None:
        """Add a filter pattern."""
        self.patterns.append(pattern)

    def remove_pattern(self, pattern: str) -> None:
        """Remove a filter pattern."""
        if pattern in self.patterns:
            self.patterns.remove(pattern)

    def clear(self) -> None:
        """Clear all patterns (allow all)."""
        self.patterns.clear()
