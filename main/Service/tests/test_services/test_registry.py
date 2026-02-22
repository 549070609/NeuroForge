"""Tests for ServiceRegistry."""

import pytest

from Service.core import ServiceRegistry, get_registry
from Service.services.base import BaseService


class MockService(BaseService):
    """Mock service for testing."""

    def __init__(self, registry: ServiceRegistry):
        super().__init__(registry)
        self.initialized = False
        self.shutdown = False

    async def _on_initialize(self) -> None:
        self.initialized = True

    async def _on_shutdown(self) -> None:
        self.shutdown = True


def test_registry_singleton():
    """Test registry is singleton."""
    registry1 = ServiceRegistry()
    registry2 = ServiceRegistry()
    assert registry1 is registry2


def test_get_registry():
    """Test get_registry helper."""
    registry = get_registry()
    assert isinstance(registry, ServiceRegistry)


def test_register_service():
    """Test service registration."""
    registry = ServiceRegistry()
    registry.reset()

    service = MockService(registry)
    registry.register("mock", service)

    assert registry.get("mock") is service


def test_get_nonexistent_service():
    """Test getting non-existent service returns None."""
    registry = ServiceRegistry()
    registry.reset()

    assert registry.get("nonexistent") is None


def test_get_service_raises():
    """Test get_service raises for non-existent service."""
    registry = ServiceRegistry()
    registry.reset()

    with pytest.raises(KeyError):
        registry.get_service("nonexistent")


@pytest.mark.asyncio
async def test_initialize_all():
    """Test initializing all services."""
    registry = ServiceRegistry()
    registry.reset()

    service = MockService(registry)
    registry.register("mock", service)

    await registry.initialize_all()

    assert service.initialized


@pytest.mark.asyncio
async def test_shutdown_all():
    """Test shutting down all services."""
    registry = ServiceRegistry()
    registry.reset()

    service = MockService(registry)
    registry.register("mock", service)

    await registry.initialize_all()
    await registry.shutdown_all()

    assert service.shutdown
