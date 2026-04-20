"""
Rate Limiting Middleware.

Implements a simple in-memory rate limiter using sliding window.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from ..config.settings import ServiceSettings


class RateLimiter:
    """
    In-memory rate limiter using sliding window.

    Tracks requests per client IP within a time window.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, client_id: str) -> tuple[bool, int]:
        """
        Check if request is allowed.

        Args:
            client_id: Client identifier (usually IP address)

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Clean old requests
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]

            # Check limit
            current_count = len(self._requests[client_id])
            if current_count >= self.max_requests:
                return False, 0

            # Record request
            self._requests[client_id].append(now)
            return True, self.max_requests - current_count - 1


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Adds rate limiting based on client IP address.
    """

    def __init__(self, app, settings: ServiceSettings):
        super().__init__(app)
        self.settings = settings
        self.enabled = settings.rate_limit_enabled

        if self.enabled:
            self.limiter = RateLimiter(
                max_requests=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window,
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit
        allowed, remaining = await self.limiter.is_allowed(client_ip)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(self.settings.rate_limit_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(self.settings.rate_limit_window),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(self.settings.rate_limit_window)

        return response
