"""
Service Layer — FastAPI gateway + business services for NeuroForge.

Architecture:
    Gateway Layer   (FastAPI, HTTP routes, middleware)
         ↓
    Service Layer   (AgentService, AgentProxyService, ModelConfigService, ...)
         ↓
    Core Layer      (ServiceRegistry, service keys, persistence)

Public entry points:
    - ``Service.gateway.create_app`` — FastAPI application factory.
    - ``Service.gateway.run``        — uvicorn launcher using settings env.
    - ``Service.core.ServiceRegistry`` plus the canonical service keys
      (``AGENT_SERVICE_KEY``, ``PROXY_SERVICE_KEY``, ``MODEL_CONFIG_SERVICE_KEY``).
"""

from __future__ import annotations

from .core import (
    AGENT_SERVICE_KEY,
    MODEL_CONFIG_SERVICE_KEY,
    PROXY_SERVICE_KEY,
    ServiceRegistry,
)
from .gateway import create_app, run

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "AGENT_SERVICE_KEY",
    "MODEL_CONFIG_SERVICE_KEY",
    "PROXY_SERVICE_KEY",
    "ServiceRegistry",
    "create_app",
    "run",
]
