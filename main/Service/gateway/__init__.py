"""Gateway module - FastAPI application and routes."""

from .app import create_app, run

__all__ = ["create_app", "run"]
