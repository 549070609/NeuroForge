"""
FastAPI 应用入口

创建和配置 FastAPI 应用
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pyagentforge.api.routes.agent import router as agent_router
from pyagentforge.api.routes.session import router as session_router
from pyagentforge.api.websocket import websocket_router
from pyagentforge.config.settings import get_settings
from pyagentforge.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    settings = get_settings()

    # 启动时
    setup_logging()
    logger.info(
        "PyAgentForge starting",
        extra_data={
            "version": "1.0.0",
            "host": settings.host,
            "port": settings.port,
        },
    )

    yield

    # 关闭时
    logger.info("PyAgentForge shutting down")


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    settings = get_settings()

    app = FastAPI(
        title="PyAgentForge",
        description="通用型 AI Agent 服务底座",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(agent_router, prefix="/api/agents", tags=["agents"])
    app.include_router(websocket_router, prefix="/ws", tags=["websocket"])

    # 健康检查
    @app.get("/health")
    async def health_check() -> dict:
        return {"status": "healthy", "version": "1.0.0"}

    @app.get("/readiness")
    async def readiness_check() -> dict:
        return {"status": "ready", "version": "1.0.0"}

    # 根路径
    @app.get("/")
    async def root() -> dict:
        return {
            "name": "PyAgentForge",
            "version": "1.0.0",
            "docs": "/docs",
        }

    return app


# 默认应用实例
app = create_app()
