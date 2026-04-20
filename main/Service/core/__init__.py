"""Core module - Service Registry and Lifecycle Management."""

from .registry import (
    AGENT_SERVICE_KEY,
    MODEL_CONFIG_SERVICE_KEY,
    PROXY_SERVICE_KEY,
    ServiceRegistry,
    get_registry,
)

__all__ = [
    "ServiceRegistry",
    "get_registry",
    "AGENT_SERVICE_KEY",
    "PROXY_SERVICE_KEY",
    "MODEL_CONFIG_SERVICE_KEY",
]
