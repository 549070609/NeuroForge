"""Persistence module - Storage backends for sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SessionStore(ABC):
    """
    Abstract base class for session storage.

    Implementations:
        - MemoryStore: Default, in-memory storage
        - RedisStore: Redis-backed storage for production
    """

    @abstractmethod
    async def get(self, key: str) -> dict[str, Any] | None:
        """
        Get session data by key.

        Args:
            key: Session key

        Returns:
            Session data or None if not found
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        """
        Set session data.

        Args:
            key: Session key
            value: Session data
            ttl: Time-to-live in seconds (optional)
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete session data.

        Args:
            key: Session key
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if session exists.

        Args:
            key: Session key

        Returns:
            True if session exists
        """
        pass


class MemoryStore(SessionStore):
    """
    In-memory session storage.

    Suitable for single-instance development and testing.
    Not suitable for production with multiple instances.
    """

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    async def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> None:
        # Note: TTL is not implemented for memory store
        self._data[key] = value

    async def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]

    async def exists(self, key: str) -> bool:
        return key in self._data

    def clear(self) -> None:
        """Clear all sessions (for testing)."""
        self._data.clear()


def create_store(settings: Any) -> SessionStore:
    """
    Factory function to create appropriate store.

    Args:
        settings: ServiceSettings instance

    Returns:
        SessionStore instance (MemoryStore or RedisStore)
    """
    if settings.redis_url and settings.redis_enabled:
        try:
            from .redis_store import RedisStore

            return RedisStore(settings.redis_url)
        except ImportError:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("Redis not installed, falling back to MemoryStore")
            return MemoryStore()

    return MemoryStore()
