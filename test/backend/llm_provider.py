"""
LLM Provider Bridge

Creates real LLM provider instances. Tries pyagentforge first, falls back
to direct SDK usage so the demo works standalone.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ENGINE_PATH = str(Path(__file__).resolve().parents[2] / "main" / "agentforge-engine")

_engine_import_failed = False


def _ensure_engine_path() -> bool:
    """Add engine path and return True if pyagentforge is usable."""
    global _engine_import_failed
    if _engine_import_failed:
        return False
    if ENGINE_PATH not in sys.path:
        sys.path.insert(0, ENGINE_PATH)
    return True


class LLMBridge:
    """Unified interface to create and call LLM providers."""

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str = "",
        temperature: float = 0.4,
        max_tokens: int = 4096,
        api_type: str = "openai-completions",
        auth_header_type: str = "bearer",
    ) -> None:
        self.provider_name = provider
        self.api_key = (api_key or "").strip()
        self.model = model
        self.base_url = (base_url or "").strip()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_type = api_type
        self.auth_header_type = auth_header_type or "bearer"
        self._provider: Any = None

    async def _get_provider(self) -> Any:
        if self._provider is not None:
            return self._provider

        if self.provider_name == "anthropic":
            self._provider = await self._create_anthropic()
        elif self.provider_name == "openai":
            self._provider = await self._create_openai()
        elif self.provider_name == "custom":
            # Route by api_type: Anthropic Messages API or OpenAI-compatible
            if self.api_type == "anthropic-messages":
                self._provider = await self._create_anthropic()
            else:
                self._provider = await self._create_openai()
        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")

        return self._provider

    async def _create_anthropic(self) -> Any:
        global _engine_import_failed
        if _ensure_engine_path():
            try:
                from pyagentforge.providers.anthropic_provider import AnthropicProvider
                from anthropic import AsyncAnthropic
                client_kwargs: dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    client_kwargs["base_url"] = self.base_url
                provider = AnthropicProvider(
                    api_key=self.api_key,
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                if self.base_url:
                    provider.client = AsyncAnthropic(**client_kwargs)
                return provider
            except ImportError:
                _engine_import_failed = True
                logger.info("pyagentforge not available, using anthropic SDK directly")

        return _DirectAnthropicProvider(
            api_key=self.api_key,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            base_url=self.base_url or None,
        )

    async def _create_openai(self) -> Any:
        # Custom auth headers (api-key/x-api-key) require _DirectOpenAIProvider; pyagentforge doesn't support them
        use_custom_auth = self.auth_header_type in ("api-key", "x-api-key")
        if not use_custom_auth and _ensure_engine_path():
            try:
                from pyagentforge.providers.openai_provider import OpenAIProvider
                kwargs: dict[str, Any] = {
                    "api_key": self.api_key,
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                }
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                return OpenAIProvider(**kwargs)
            except ImportError:
                pass
            _engine_import_failed = True
            logger.info("pyagentforge not available, using openai SDK directly")

        return _DirectOpenAIProvider(
            api_key=self.api_key,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            base_url=self.base_url or None,
            auth_header_type=self.auth_header_type,
        )

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """
        Send a chat request and return structured result.

        Returns:
            {
                "text": str,           # Agent reply text
                "tool_calls": [...],   # Any tool calls made
                "usage": {...},        # Token usage
            }
        """
        provider = await self._get_provider()

        try:
            if hasattr(provider, "create_message"):
                response = await asyncio.wait_for(
                    provider.create_message(
                        system=system_prompt,
                        messages=messages,
                        tools=tools or [],
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                    ),
                    timeout=timeout,
                )
                return {
                    "text": response.text if hasattr(response, "text") else str(response),
                    "tool_calls": [
                        {"name": tc.name, "input": tc.input}
                        for tc in (response.tool_calls if hasattr(response, "tool_calls") else [])
                    ],
                    "usage": response.usage if hasattr(response, "usage") else {},
                }
            else:
                result = await asyncio.wait_for(
                    provider.call(system_prompt, messages),
                    timeout=timeout,
                )
                return {"text": result, "tool_calls": [], "usage": {}}

        except asyncio.TimeoutError:
            logger.error("LLM call timed out after %.1fs", timeout)
            raise TimeoutError(f"LLM 调用超时 ({timeout}s)，请检查网络或 API 状态")
        except Exception as e:
            logger.error("LLM call failed: %s", e)
            raise

    async def test_connection(self) -> dict[str, Any]:
        """Test the connection with a minimal request."""
        try:
            result = await self.chat(
                system_prompt="Reply with exactly: CONNECTION_OK",
                messages=[{"role": "user", "content": "ping"}],
            )
            return {
                "success": True,
                "response": result["text"][:200],
                "usage": result.get("usage", {}),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class _DirectAnthropicProvider:
    """Fallback: use anthropic SDK directly without pyagentforge."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float,
        base_url: str | None = None,
    ):
        from anthropic import AsyncAnthropic
        client_kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": httpx.Timeout(120.0, connect=10.0),
        }
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**client_kwargs)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def create_message(self, system: str, messages: list, tools: list, **kwargs):
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "system": system,
            "messages": messages,
        }
        if tools:
            params["tools"] = tools
        if self.temperature != 1.0:
            params["temperature"] = kwargs.get("temperature", self.temperature)

        response = await self.client.messages.create(**params)
        return _ProviderResponseAdapter(response)


class _StripAuthTransport(httpx.AsyncBaseTransport):
    """httpx transport that removes the auto-generated Authorization header and
    injects a custom auth header instead (e.g. api-key, x-api-key).

    Used when the upstream proxy authenticates via a non-Bearer header.  Without
    this, the OpenAI SDK sends *both* ``Authorization: Bearer <key>`` AND the
    custom header; many proxy back-ends forward the Bearer token to the real LLM
    which rejects it with 401 "令牌已过期或验证不正确".
    """

    def __init__(
        self,
        auth_header: str,
        api_key: str,
        wrapped: httpx.AsyncBaseTransport,
    ) -> None:
        self._auth_header = auth_header
        self._api_key = api_key
        self._wrapped = wrapped

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Remove the Bearer token the OpenAI SDK injected, then set the real header.
        request.headers.pop("authorization", None)
        request.headers[self._auth_header] = self._api_key
        return await self._wrapped.handle_async_request(request)


class _DirectOpenAIProvider:
    """Fallback: use openai SDK directly without pyagentforge."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float,
        base_url: str | None = None,
        auth_header_type: str = "bearer",
    ):
        from openai import AsyncOpenAI

        timeout = httpx.Timeout(120.0, connect=10.0)

        if auth_header_type == "bearer":
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
        else:
            # Some APIs (Azure, proxies, etc.) authenticate via a custom header
            # (api-key / x-api-key) instead of Bearer.  We wrap the default
            # httpx transport to strip the SDK-injected Authorization header and
            # replace it with the correct custom header so only ONE auth header
            # reaches the server.
            inner_transport = httpx.AsyncHTTPTransport()
            transport = _StripAuthTransport(
                auth_header=auth_header_type,
                api_key=api_key,
                wrapped=inner_transport,
            )
            http_client = httpx.AsyncClient(
                transport=transport,
                timeout=timeout,
            )
            self.client = AsyncOpenAI(
                api_key="placeholder",  # required by SDK; overridden by transport
                base_url=base_url,
                http_client=http_client,
            )

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def create_message(self, system: str, messages: list, tools: list, **kwargs):
        oai_messages = [{"role": "system", "content": system}]
        for m in messages:
            oai_messages.append({"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else str(m["content"])})

        params: dict[str, Any] = {
            "model": self.model,
            "messages": oai_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        response = await self.client.chat.completions.create(**params)
        return _OpenAIResponseAdapter(response)


class _ProviderResponseAdapter:
    """Adapts raw Anthropic response to match ProviderResponse interface."""

    def __init__(self, raw: Any):
        self._raw = raw

    @property
    def text(self) -> str:
        texts = []
        for block in self._raw.content:
            if hasattr(block, "text"):
                texts.append(block.text)
        return "\n".join(texts)

    @property
    def tool_calls(self) -> list:
        calls = []
        for block in self._raw.content:
            if hasattr(block, "type") and block.type == "tool_use":
                calls.append(block)
        return calls

    @property
    def usage(self) -> dict:
        return {
            "input_tokens": self._raw.usage.input_tokens,
            "output_tokens": self._raw.usage.output_tokens,
        }


class _OpenAIResponseAdapter:
    """Adapts raw OpenAI response to match ProviderResponse interface."""

    def __init__(self, raw: Any):
        self._raw = raw

    @property
    def text(self) -> str:
        choice = self._raw.choices[0] if self._raw.choices else None
        return choice.message.content or "" if choice else ""

    @property
    def tool_calls(self) -> list:
        return []

    @property
    def usage(self) -> dict:
        u = self._raw.usage
        return {
            "input_tokens": u.prompt_tokens if u else 0,
            "output_tokens": u.completion_tokens if u else 0,
        }


_bridge_instance: LLMBridge | None = None


def get_bridge(
    provider: str,
    api_key: str,
    model: str,
    base_url: str = "",
    temperature: float = 0.4,
    max_tokens: int = 4096,
    api_type: str = "openai-completions",
    auth_header_type: str = "bearer",
) -> LLMBridge:
    """Get or create a cached LLM bridge instance."""
    global _bridge_instance
    if (
        _bridge_instance is not None
        and _bridge_instance.api_key == (api_key or "").strip()
        and _bridge_instance.model == model
        and _bridge_instance.provider_name == provider
        and _bridge_instance.base_url == (base_url or "").strip()
        and _bridge_instance.api_type == api_type
        and _bridge_instance.auth_header_type == auth_header_type
    ):
        return _bridge_instance

    _bridge_instance = LLMBridge(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        api_type=api_type,
        auth_header_type=auth_header_type,
    )
    return _bridge_instance


def get_bridge_from_config() -> LLMBridge | None:
    """Create a bridge from the current config store settings."""
    from config_store import ConfigStore
    store = ConfigStore.get()
    if not store.is_llm_mode:
        return None
    return get_bridge(
        provider=store.provider,
        api_key=store.api_key,
        model=store.model,
        base_url=store.base_url,
        temperature=store.temperature,
        max_tokens=store.max_tokens,
        api_type=store.api_type,
        auth_header_type=store.auth_header_type,
    )
