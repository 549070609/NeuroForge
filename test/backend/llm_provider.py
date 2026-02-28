"""
LLM Provider Factory

Creates pyagentforge BaseProvider instances from ConfigStore settings.
Replaces the old LLMBridge wrapper — AgentEngine now handles the full
execution loop, so this module only needs to build provider objects.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ENGINE_PATH = str(Path(__file__).resolve().parents[2] / "main" / "agentforge-engine")


def _ensure_engine_path() -> None:
    if ENGINE_PATH not in sys.path:
        sys.path.insert(0, ENGINE_PATH)


def create_provider(
    provider_name: str,
    api_key: str,
    model: str,
    base_url: str = "",
    temperature: float = 0.4,
    max_tokens: int = 4096,
    api_type: str = "openai-completions",
) -> Any:
    """
    Instantiate a pyagentforge BaseProvider from explicit parameters.

    Returns an AnthropicProvider or OpenAIProvider depending on provider_name.
    Returns None if provider_name is unrecognised or api_key is missing.
    """
    _ensure_engine_path()
    api_key = (api_key or "").strip()
    if not api_key:
        return None

    if provider_name == "anthropic" or (
        provider_name == "custom" and api_type == "anthropic-messages"
    ):
        from pyagentforge.providers.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if base_url:
            from anthropic import AsyncAnthropic
            provider.client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        return provider

    if provider_name in ("openai", "custom"):
        from pyagentforge.providers.openai_provider import OpenAIProvider

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAIProvider(**kwargs)

    return None


def get_provider_from_config() -> Any:
    """
    Create a provider using the current ConfigStore settings.

    Returns None when api_key is not set.
    """
    from config_store import ConfigStore

    store = ConfigStore.get()
    return create_provider(
        provider_name=store.provider,
        api_key=store.api_key,
        model=store.model,
        base_url=store.base_url,
        temperature=store.temperature,
        max_tokens=store.max_tokens,
        api_type=store.api_type,
    )
