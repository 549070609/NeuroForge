"""Test configuration and fixtures."""

import asyncio
import pytest
from pathlib import Path
import sys

# Add repository `main/` to PYTHONPATH so `import Service` resolves correctly.
SERVICE_PATH = Path(__file__).resolve().parents[2]
if str(SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(SERVICE_PATH))
ENGINE_PATH = SERVICE_PATH / "agentforge-engine"
if str(ENGINE_PATH) not in sys.path:
    sys.path.insert(0, str(ENGINE_PATH))

from fastapi.testclient import TestClient

from Service.config import ServiceSettings, get_settings
from Service.core import ServiceRegistry
from Service.gateway import create_app
from Service.services.agent_service import AgentService


@pytest.fixture
def test_settings():
    """Create test settings."""
    return ServiceSettings(
        debug=True,
        log_level="DEBUG",
        default_model="claude-sonnet-4",
    )


@pytest.fixture
def app(test_settings):
    """Create test app."""
    return create_app(test_settings)


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_registry():
    """Reset registry singleton before each test."""
    ServiceRegistry.reset()
    yield
    ServiceRegistry.reset()


@pytest.fixture
async def async_client(test_settings):
    """Create async test client with initialized services."""
    from Service.config import _settings
    globals()["_settings"] = test_settings

    registry = ServiceRegistry()
    agent_service = AgentService(registry)
    registry.register("agent", agent_service)

    await registry.initialize_all()

    yield {
        "registry": registry,
        "agent_service": agent_service,
    }

    await registry.shutdown_all()
