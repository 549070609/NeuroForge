"""
Authentication Middleware.

Supports:
- API Key authentication (header-based)
- Session Token authentication (optional)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from fastapi import HTTPException, Request, Response, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from ..config.settings import ServiceSettings


# API Key header name
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware.

    Validates API key if configured.
    """

    def __init__(self, app, settings: ServiceSettings):
        super().__init__(app)
        self.settings = settings
        self.api_key = settings.api_key
        self.header_name = settings.api_key_header

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with authentication."""
        # Skip auth for health and docs
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Skip if no API key configured
        if not self.api_key:
            return await call_next(request)

        # Get API key from header
        provided_key = request.headers.get(self.header_name)

        # Validate
        if not provided_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": f'ApiKey realm="API"'},
            )

        if provided_key != self.api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key",
            )

        return await call_next(request)
