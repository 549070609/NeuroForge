"""
Configuration settings for Service Layer.

Environment variables:
    SERVICE_REDIS_URL: Redis connection URL (optional)
    SERVICE_REDIS_ENABLED: Enable Redis storage (default: false)
    SERVICE_API_KEY: API key for authentication (optional)
    SERVICE_LOG_LEVEL: Logging level (default: INFO)
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """
    Service Layer configuration.

    Uses pydantic-settings for environment variable loading.
    All settings can be overridden via environment variables with prefix SERVICE_.
    """

    model_config = SettingsConfigDict(
        env_prefix="SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Server Configuration ===
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # === Redis Configuration (Optional) ===
    redis_url: str | None = None
    redis_enabled: bool = False

    # === SQLite Configuration ===
    sqlite_path: str = "data/service.db"

    # === Authentication ===
    api_key: str | None = None
    api_key_header: str = "X-API-Key"

    # === Rate Limiting ===
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # === Session Configuration ===
    session_ttl: int = 3600  # 1 hour default
    max_sessions: int = 100
    legacy_sessions_dir: str = "data/legacy_sessions"

    # === SSE Configuration ===
    sse_heartbeat: int = 30  # seconds
    sse_retry_timeout: int = 3000  # milliseconds

    # === Governance / P2 ===
    guardrails_enabled: bool = True
    hitl_enabled: bool = True
    approval_ttl: int = 900
    approval_auto_approve: bool = False
    slo_window_size: int = 1000
    slo_target_success_rate: float = 0.995
    slo_target_p95_ms: int = 30000
    circuit_failure_threshold: int = 5
    circuit_open_seconds: int = 60


# Global settings instance
_settings: ServiceSettings | None = None


def get_settings() -> ServiceSettings:
    """Get global settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = ServiceSettings()
    return _settings


def configure_logging(settings: ServiceSettings | None = None) -> None:
    """Configure logging based on settings."""
    if settings is None:
        settings = get_settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
