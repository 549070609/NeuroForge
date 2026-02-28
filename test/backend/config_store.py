"""
Runtime Configuration Store

Manages LLM provider configuration with JSON persistence.
Stores API keys, model selection, and provider settings.
"""

from __future__ import annotations

import json
import os
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "mock",  # "mock" | "llm"
    "provider": "anthropic",  # "anthropic" | "openai" | "custom"
    "api_type": "openai-completions",  # "openai-completions" | "anthropic-messages"
    "auth_header_type": "bearer",  # "bearer" | "api-key" | "x-api-key" (custom only)
    "api_key": "",
    "base_url": "",
    "model": "claude-sonnet-4-20250514",
    "temperature": 0.4,
    "max_tokens": 4096,
    "passive_system_prompt": "",
    "active_system_prompt": "",
}

PROVIDER_MODELS: dict[str, list[dict[str, str]]] = {
    "anthropic": [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4"},
    ],
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini"},
        {"id": "o3-mini", "name": "o3-mini"},
    ],
    "custom": [],
}


class ConfigStore:
    _instance: ConfigStore | None = None

    def __init__(self) -> None:
        self._config: dict[str, Any] = {**DEFAULT_CONFIG}
        self._load()

    @classmethod
    def get(cls) -> ConfigStore:
        if cls._instance is None:
            cls._instance = ConfigStore()
        return cls._instance

    def _load(self) -> None:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved.get("api_key"), str):
                    saved["api_key"] = saved["api_key"].strip()
                self._config.update(saved)
                logger.info("Loaded config from %s", CONFIG_PATH)
            except Exception as e:
                logger.warning("Failed to load config: %s", e)

    def _save(self) -> None:
        safe = {k: v for k, v in self._config.items() if k != "api_key"}
        safe["api_key"] = "***" if self._config.get("api_key") else ""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info("Saved config to %s", CONFIG_PATH)
        except Exception as e:
            logger.warning("Failed to save config: %s", e)

    @property
    def config(self) -> dict[str, Any]:
        return {**self._config}

    def get_safe_config(self) -> dict[str, Any]:
        """Return config with API key masked."""
        c = {**self._config}
        if c.get("api_key"):
            key = c["api_key"]
            c["api_key_preview"] = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
            c["api_key_set"] = True
        else:
            c["api_key_preview"] = ""
            c["api_key_set"] = False
        del c["api_key"]
        return c

    def update(self, updates: dict[str, Any]) -> dict[str, Any]:
        for k, v in updates.items():
            if k in DEFAULT_CONFIG:
                if k == "api_key" and isinstance(v, str):
                    v = v.strip()  # Remove accidental whitespace
                self._config[k] = v
        self._save()
        return self.get_safe_config()

    @property
    def is_llm_mode(self) -> bool:
        return self._config.get("mode") == "llm" and bool(self._config.get("api_key"))

    @property
    def api_key(self) -> str:
        return (self._config.get("api_key", "") or "").strip()

    @property
    def provider(self) -> str:
        return self._config.get("provider", "anthropic")

    @property
    def model(self) -> str:
        return self._config.get("model", "claude-sonnet-4-20250514")

    @property
    def api_type(self) -> str:
        return self._config.get("api_type", "openai-completions")

    @property
    def auth_header_type(self) -> str:
        return self._config.get("auth_header_type", "bearer")

    @property
    def base_url(self) -> str:
        return (self._config.get("base_url", "") or "").strip()

    @property
    def temperature(self) -> float:
        return self._config.get("temperature", 0.4)

    @property
    def max_tokens(self) -> int:
        return self._config.get("max_tokens", 4096)

    @staticmethod
    def get_models_for_provider(provider: str) -> list[dict[str, str]]:
        return PROVIDER_MODELS.get(provider, [])
