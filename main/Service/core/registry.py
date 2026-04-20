"""
Service Registry - Singleton container for all services.

This module implements a singleton registry that manages:
1. Service instances
2. Service lifecycle (initialize/shutdown)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .services.base import BaseService

logger = logging.getLogger(__name__)

# Canonical service keys shared across routes/tests/app.
AGENT_SERVICE_KEY = "agent"
PROXY_SERVICE_KEY = "proxy"
MODEL_CONFIG_SERVICE_KEY = "model_config"


class ServiceRegistry:
    """
    Singleton registry for managing services.

    Thread-safe singleton that holds service instances.
    """

    _instance: ServiceRegistry | None = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __new__(cls) -> ServiceRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services: dict[str, BaseService] = {}
            cls._instance._initialized: bool = False
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def register(self, name: str, service: BaseService) -> None:
        """
        Register a service instance.

        Args:
            name: Service identifier
            service: Service instance
        """
        if name in self._services:
            logger.warning(f"Overwriting existing service: {name}")
        self._services[name] = service
        logger.debug(f"Registered service: {name}")

    def get(self, name: str) -> BaseService | None:
        """
        Get a registered service.

        Args:
            name: Service identifier

        Returns:
            Service instance or None if not found
        """
        return self._services.get(name)

    def get_service(self, name: str) -> BaseService:
        """
        Get a registered service (raises if not found).

        Args:
            name: Service identifier

        Returns:
            Service instance

        Raises:
            KeyError: If service not registered
        """
        if name not in self._services:
            raise KeyError(f"Service not registered: {name}")
        return self._services[name]

    # === Lifecycle Management ===

    async def initialize_all(self) -> None:
        """Initialize all registered services."""
        if self._initialized:
            logger.warning("Registry already initialized")
            return

        logger.info(f"Initializing {len(self._services)} services...")
        for name, service in self._services.items():
            try:
                await service.initialize()
                logger.debug(f"Initialized service: {name}")
            except Exception as e:
                logger.error(f"Failed to initialize service {name}: {e}")
                raise

        self._initialized = True
        logger.info("All services initialized")

    async def shutdown_all(self) -> None:
        """Shutdown all registered services."""
        if not self._initialized:
            return

        logger.info("Shutting down services...")

        # Shutdown services in reverse order
        for name, service in reversed(list(self._services.items())):
            try:
                await service.shutdown()
                logger.debug(f"Shutdown service: {name}")
            except Exception as e:
                logger.error(f"Failed to shutdown service {name}: {e}")

        self._initialized = False
        logger.info("All services shut down")


# Convenience function
def get_registry() -> ServiceRegistry:
    """Get the singleton ServiceRegistry instance."""
    return ServiceRegistry()
