"""
FastAPI Application Factory.

Creates and configures the FastAPI application with:
- Service registry initialization
- Lifespan management
- Route registration
- Middleware setup
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import configure_logging, get_settings
from ..core import ServiceRegistry

if TYPE_CHECKING:
    from ..config.settings import ServiceSettings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles:
    - Service initialization on startup
    - Service cleanup on shutdown
    """
    settings = get_settings()
    configure_logging(settings)

    logger.info("Starting Service Layer...")
    registry = ServiceRegistry()

    # Register services here when adding new services
    from ..services.agent_service import AgentService
    from ..services.model_config_service import ModelConfigService
    from ..services.proxy.agent_proxy_service import AgentProxyService

    agent_service = AgentService(registry)
    registry.register("agent", agent_service)

    proxy_service = AgentProxyService(registry)
    registry.register("proxy", proxy_service)

    model_config_service = ModelConfigService(registry)
    registry.register("model_config", model_config_service)

    # Initialize all services
    try:
        await registry.initialize_all()
        logger.info("All services initialized")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    # Store registry in app state
    app.state.registry = registry

    yield

    # Shutdown
    logger.info("Shutting down Service Layer...")
    await registry.shutdown_all()
    logger.info("Service Layer shut down")


def create_app(settings: ServiceSettings | None = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        settings: Optional settings override

    Returns:
        Configured FastAPI application
    """
    if settings:
        from ..config import settings as settings_module

        settings_module._settings = settings

    settings = get_settings()

    app = FastAPI(
        title="Service Layer",
        description="Service-oriented API Layer",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from .routes import agents, health, models, proxy, tools

    app.include_router(health.router, tags=["Health"])
    app.include_router(tools.router, prefix="/api/v1", tags=["Tools"])
    app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
    app.include_router(agents.plan_router, prefix="/api/v1", tags=["Plans"])
    app.include_router(models.router, prefix="/api/v1", tags=["Models"])
    app.include_router(proxy.router, prefix="/api/v1", tags=["Proxy"])

    logger.info("FastAPI application created")
    return app


def run() -> None:
    """Run the server."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "Service.gateway.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
