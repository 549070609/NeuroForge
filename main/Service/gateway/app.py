"""
FastAPI Application Factory.

Creates and configures the FastAPI application with:
- Service registry initialization
- Lifespan management
- Route registration
- Middleware setup
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import configure_logging, get_settings
from ..core import (
    AGENT_SERVICE_KEY,
    MODEL_CONFIG_SERVICE_KEY,
    PROXY_SERVICE_KEY,
    ServiceRegistry,
)
from .middleware import (
    AuthMiddleware,
    ErrorHandlerMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)

if TYPE_CHECKING:
    from ..config.settings import ServiceSettings

logger = logging.getLogger(__name__)


def _validate_cors_settings(settings: ServiceSettings) -> None:
    """P0-7: 生产环境拒绝 allow_origins=["*"] 与 allow_credentials=True 组合。

    该组合会让浏览器忽略 Access-Control-Allow-Origin（规范要求）；
    实际网络中这种配置通常是误配置，应在启动时失败。
    """
    origins = settings.cors_allowed_origins
    if (
        not settings.debug
        and settings.cors_allow_credentials
        and ("*" in origins or origins == ["*"])
    ):
        raise ValueError(
            "Invalid CORS config: cors_allowed_origins=['*'] is not allowed "
            "when cors_allow_credentials=True in non-debug mode. "
            "Set an explicit origin list or disable credentials."
        )


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
    settings.print_masked_summary()
    registry = ServiceRegistry()

    # Register services here when adding new services
    from ..services.agent_service import AgentService
    from ..services.model_config_service import ModelConfigService
    from ..services.proxy.agent_proxy_service import AgentProxyService

    agent_service = AgentService(registry)
    registry.register(AGENT_SERVICE_KEY, agent_service)

    proxy_service = AgentProxyService(registry)
    registry.register(PROXY_SERVICE_KEY, proxy_service)

    model_config_service = ModelConfigService(registry)
    registry.register(MODEL_CONFIG_SERVICE_KEY, model_config_service)

    # Initialize all services
    try:
        await registry.initialize_all()
        logger.info("All services initialized")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    # Store registry + uptime marker in app state
    app.state.registry = registry
    app.state._start_time = time.time()
    # P1-5: 追踪所有运行中的 agent 任务，用于优雅关机
    app.state.running_tasks: set[asyncio.Task] = set()  # type: ignore[assignment]
    app.state.cancel_event = asyncio.Event()

    yield

    # P1-5: 优雅关机——先广播取消信号，等待宽限期，再强制取消
    logger.info("Shutting down Service Layer...")
    running = set(app.state.running_tasks)
    if running:
        logger.info("Waiting for %d in-flight tasks to complete...", len(running))
        app.state.cancel_event.set()
        done, pending = await asyncio.wait(
            running, timeout=settings.shutdown_grace,
        )
        if pending:
            logger.warning("Force-cancelling %d tasks after grace period", len(pending))
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
    # 关闭共享 LLM 连接池
    try:
        from pyagentforge.client import close_shared_llm_client
        await close_shared_llm_client()
    except Exception:  # pragma: no cover
        pass
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

    # === Middleware stack (executed in reverse order of registration) ===
    # CORS is outermost so that preflight works even when downstream middleware
    # rejects a request.
    _validate_cors_settings(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allowed_methods,
        allow_headers=settings.cors_allowed_headers,
    )
    # P0-5: RequestContext 注入 X-Request-ID + contextvars，贯穿整个请求链
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AuthMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    # ErrorHandler is innermost so it catches exceptions from routes/services.
    app.add_middleware(
        ErrorHandlerMiddleware,
        expose_error_details=settings.expose_error_details,
    )

    # === Register routes ===
    # All API routes are mounted under /api/v1. Health/root stay at the origin
    # so that probes and dashboards can reach them without the version prefix.
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
