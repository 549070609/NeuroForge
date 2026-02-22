"""
Base Service - Abstract base class for all services.

All services inherit from this class.
Provides lifecycle hooks for initialization and shutdown.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """
    Abstract base class for all services.

    Services are managed by ServiceRegistry and follow a lifecycle:
    1. __init__(registry) - Service receives registry reference
    2. initialize() - Called during app startup
    3. [Service is active]
    4. shutdown() - Called during app shutdown

    Attributes:
        registry: Reference to ServiceRegistry singleton
        _initialized: Whether service has been initialized
    """

    def __init__(self, registry: ServiceRegistry):
        """
        Initialize base service.

        Args:
            registry: ServiceRegistry singleton for accessing other services
        """
        self.registry = registry
        self._initialized = False
        self._logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    async def initialize(self) -> None:
        """
        Initialize the service.

        Calls _on_initialize() hook and marks service as initialized.
        """
        if self._initialized:
            self._logger.warning(f"{self.__class__.__name__} already initialized")
            return

        self._logger.debug(f"Initializing {self.__class__.__name__}...")
        await self._on_initialize()
        self._initialized = True
        self._logger.debug(f"{self.__class__.__name__} initialized")

    async def shutdown(self) -> None:
        """
        Shutdown the service.

        Calls _on_shutdown() hook and marks service as not initialized.
        """
        if not self._initialized:
            return

        self._logger.debug(f"Shutting down {self.__class__.__name__}...")
        await self._on_shutdown()
        self._initialized = False
        self._logger.debug(f"{self.__class__.__name__} shut down")

    @abstractmethod
    async def _on_initialize(self) -> None:
        """
        Hook called during initialization.

        Override this method to perform service-specific initialization
        (e.g., connecting to databases, loading resources).

        This method MUST be implemented by subclasses.
        """
        pass

    async def _on_shutdown(self) -> None:
        """
        Hook called during shutdown.

        Override this method to perform service-specific cleanup
        (e.g., closing connections, releasing resources).

        Default implementation does nothing.
        """
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if service has been initialized."""
        return self._initialized
