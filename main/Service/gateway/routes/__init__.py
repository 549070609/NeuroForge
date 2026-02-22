"""
Helper function to get registry from app state.
This is a workaround to avoid circular imports.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...core import ServiceRegistry


def get_app_registry() -> "ServiceRegistry":
    """Get registry from FastAPI app state."""
    from fastapi import Request
    from starlette.concurrency import run_in_threadpool

    # This will be set during request handling
    # For now, return the singleton
    from ...core import ServiceRegistry

    return ServiceRegistry()
