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

    def print_masked_summary(self) -> None:
        """P1-8: 启动时打印脱敏配置摘要（mask key 中间段）。"""
        def _mask(value: str | None) -> str:
            if not value:
                return "<not set>"
            if len(value) <= 6:
                return "***"
            return value[:3] + "***" + value[-3:]

        lines = [
            f"  host={self.host}:{self.port}",
            f"  debug={self.debug}",
            f"  log_level={self.log_level}  log_json={self.log_json}",
            f"  api_key={_mask(self.api_key)}",
            f"  api_keys=[{', '.join(_mask(k) for k in self.api_keys)}]" if self.api_keys else "  api_keys=<none>",
            f"  redis_enabled={self.redis_enabled}  redis_url={_mask(self.redis_url)}",
            f"  rate_limit_enabled={self.rate_limit_enabled}  {self.rate_limit_requests}/{self.rate_limit_window}s",
            f"  cors_origins={self.cors_allowed_origins}",
            f"  shutdown_grace={self.shutdown_grace}s",
            f"  workspace_base={self.workspace_base or '<cwd>'}",
            f"  agent_dir={self.agent_dir or '<default>'}",
            f"  data_dir={self.data_dir}",
        ]
        logging.getLogger(__name__).info("ServiceSettings:\n%s", "\n".join(lines))

    # === Server Configuration ===
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    # P0-5: 启用 JSON 结构化日志（生产推荐 true；开发可保持 false 以便阅读）
    log_json: bool = False
    expose_error_details: bool = False

    # === Workspace Isolation ===
    workspace_base: str = ""

    # === CORS ===
    cors_allowed_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allowed_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allowed_headers: list[str] = ["Content-Type", "Authorization", "X-API-Key", "X-Request-ID"]

    # === Redis Configuration (Optional) ===
    redis_url: str | None = None
    redis_enabled: bool = False

    # === SQLite Configuration ===
    sqlite_path: str = "data/service.db"

    # === Authentication ===
    api_key: str | None = None
    api_key_header: str = "X-API-Key"
    # P0-8: 多 key 支持。key=客户端传入的 api key，value=client_id (用于限流 / 审计)
    api_keys: dict[str, str] = {}
    # 可信反向代理 IP 白名单；仅来自这些 IP 的 X-Forwarded-For 才被采信
    trusted_proxies: list[str] = []

    # === Rate Limiting ===
    rate_limit_enabled: bool = False
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # === Session Configuration ===
    session_ttl: int = 3600  # 1 hour default
    max_sessions: int = 100
    legacy_sessions_dir: str = "data/legacy_sessions"

    # === Graceful Shutdown (P1-5) ===
    shutdown_grace: int = 30  # seconds to wait for in-flight tasks before force cancel

    # === SSE Configuration ===
    sse_heartbeat: int = 30  # seconds
    sse_retry_timeout: int = 3000  # milliseconds

    # === Path Configuration (P1-9) ===
    agent_dir: str = ""  # Agent 目录，空则用默认 main/Agent
    data_dir: str = "data"  # 数据目录（session / checkpoint / plan）

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


class _JSONFormatter(logging.Formatter):
    """P0-5 结构化日志 formatter：输出 JSON 行，自动注入 request_id。"""

    _STANDARD = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        # 延迟导入，避免循环依赖
        try:
            from ..gateway.middleware.request_context import get_request_id
            request_id = get_request_id()
        except Exception:
            request_id = ""

        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        # 附加任何通过 `extra={...}` 传入的自定义字段
        for key, value in record.__dict__.items():
            if key not in self._STANDARD and not key.startswith("_"):
                try:
                    json.dumps(value)  # 可序列化检测
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: ServiceSettings | None = None) -> None:
    """Configure logging based on settings.

    P0-5: `log_json=True` 时使用 JSON formatter，日志行自动附带 request_id。
    """
    if settings is None:
        settings = get_settings()

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level))

    # 清理已有 handler，避免重复输出
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    if settings.log_json:
        handler.setFormatter(_JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    root.addHandler(handler)
