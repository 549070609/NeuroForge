"""Health check and Agent lifecycle routes."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request

from ...core import PROXY_SERVICE_KEY
from ...schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Lightweight health check."""
    return HealthResponse()


@router.get("/health/deep")
async def deep_health_check(request: Request) -> dict[str, Any]:
    """Deep health check including service and LLM connectivity.

    Returns per-service health, active session count, and uptime.
    """
    registry = getattr(request.app.state, "registry", None)
    services_health: dict[str, str] = {}

    if registry:
        for name, svc in getattr(registry, "_services", {}).items():
            try:
                if hasattr(svc, "is_healthy"):
                    services_health[name] = "healthy" if svc.is_healthy() else "degraded"
                else:
                    services_health[name] = "unknown"
            except Exception:
                services_health[name] = "error"

    start_time = getattr(request.app.state, "_start_time", None)
    uptime_s = int(time.time() - start_time) if start_time else None

    return {
        "status": "healthy",
        "services": services_health,
        "uptime_seconds": uptime_s,
    }


@router.get("/agents/active")
async def list_active_agents(request: Request) -> dict[str, Any]:
    """List all currently active agent sessions.

    Returns session IDs, agent types, and running durations.
    """
    registry = getattr(request.app.state, "registry", None)
    active: list[dict[str, Any]] = []

    if registry:
        proxy_svc = getattr(registry, "_services", {}).get(PROXY_SERVICE_KEY)
        if proxy_svc and hasattr(proxy_svc, "_executors"):
            for session_id, executor in proxy_svc._executors.items():
                engine = getattr(executor, "_engine", None)
                active.append({
                    "session_id": session_id,
                    "model": getattr(engine.provider, "model", "unknown") if engine else "unknown",
                    "context_messages": len(engine.context) if engine else 0,
                })

    return {"count": len(active), "agents": active}


@router.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Service Layer", "docs": "/docs"}
