"""Deprecated pyagentforge API module.

API serving moved to `main/Service` gateway.
"""

from pyagentforge.api.app import APIRemovedError, create_app

__all__ = [
    "APIRemovedError",
    "create_app",
]