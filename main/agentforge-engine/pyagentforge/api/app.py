"""Legacy API entrypoint removed.

PyAgentForge no longer exposes REST or WebSocket APIs directly.
All gateway endpoints are hosted by `main/Service`.
"""

from __future__ import annotations


class APIRemovedError(RuntimeError):
    """Raised when deprecated pyagentforge API entrypoints are used."""


_REMOVAL_MESSAGE = (
    "pyagentforge built-in API endpoints have been removed. "
    "Use the Service gateway instead: "
    "`uvicorn Service.gateway.app:create_app --factory --reload --port 8000`"
)


def create_app(*args, **kwargs):
    """Removed API factory.

    Raises:
        APIRemovedError: Always, because API serving moved to main/Service.
    """
    raise APIRemovedError(_REMOVAL_MESSAGE)


def __getattr__(name: str):
    if name == "app":
        raise APIRemovedError(_REMOVAL_MESSAGE)
    raise AttributeError(name)