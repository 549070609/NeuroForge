"""统一 LLM 客户端。

支持重试、指数退避、故障转移和 fallback 模型。
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.kernel.model_registry import ModelConfig, ModelRegistry
from pyagentforge.protocols import PROTOCOL_ADAPTERS
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RetryConfig:
    """LLMClient 重试配置"""

    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_status_codes: set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )


@dataclass
class CallMetrics:
    """单次 LLM 调用的指标"""

    model_id: str
    attempt: int
    latency_ms: float
    success: bool
    status_code: int | None = None
    error: str | None = None


class LLMClient:
    """协议驱动的统一 LLM 客户端，内置重试和 fallback。"""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        retry_config: RetryConfig | None = None,
        fallback_model_ids: list[str] | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry(load_from_config=True)
        self.retry_config = retry_config or RetryConfig()
        self.fallback_model_ids = fallback_model_ids or []
        self._http_clients: dict[int, httpx.AsyncClient] = {}
        self._metrics: list[CallMetrics] = []
        logger.info(
            "Initialized LLMClient",
            extra_data={
                "max_retries": self.retry_config.max_retries,
                "fallbacks": self.fallback_model_ids,
            },
        )

    async def create_message(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ProviderResponse:
        models_to_try = [model_id] + [
            fid for fid in self.fallback_model_ids if fid != model_id
        ]

        last_error: Exception | None = None

        for model in models_to_try:
            try:
                return await self._call_with_retry(
                    model, messages, system, tools, **kwargs
                )
            except Exception as e:
                last_error = e
                if model != models_to_try[-1]:
                    logger.warning(
                        "Model failed, trying fallback",
                        extra_data={"failed_model": model, "error": str(e)},
                    )

        raise last_error  # type: ignore[misc]

    async def _call_with_retry(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> ProviderResponse:
        """带指数退避重试的 LLM 调用。"""
        model_candidates = self.registry.get_model_candidates(model_id)
        if not model_candidates:
            raise ValueError(f"Model configuration error: model '{model_id}' not found")

        last_error: Exception | None = None
        for candidate_index, model_config in enumerate(model_candidates):
            try:
                return await self._call_model_config_with_retry(
                    model_id=model_id,
                    model_config=model_config,
                    messages=messages,
                    system=system,
                    tools=tools,
                    **kwargs,
                )
            except Exception as exc:
                last_error = exc
                if candidate_index < len(model_candidates) - 1:
                    logger.warning(
                        "Primary model config failed, trying fallback config",
                        extra_data={
                            "model_id": model_id,
                            "failed_provider": model_config.provider,
                            "error": str(exc),
                        },
                    )
        raise last_error  # type: ignore[misc]

    async def _call_model_config_with_retry(
        self,
        model_id: str,
        model_config: ModelConfig,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> ProviderResponse:
        adapter = PROTOCOL_ADAPTERS.get(model_config.api_type)
        if not adapter:
            raise ValueError(f"Unsupported api_type: {model_config.api_type}")

        request_params = {
            "model": model_config.resolved_model_name,
            "messages": messages,
            "system": system,
            "tools": tools,
            "max_tokens": kwargs.pop("max_tokens", model_config.max_output_tokens),
            "temperature": kwargs.pop("temperature", 1.0),
            **kwargs,
        }

        payload = adapter.build_request(request_params, model_config)
        headers = adapter.build_headers(model_config)
        url = adapter.build_url(model_config)
        client = self._get_or_create_client(model_config.timeout)

        retry_cfg = self.retry_config
        delay = retry_cfg.initial_delay
        last_error: Exception | None = None

        for attempt in range(retry_cfg.max_retries + 1):
            start = time.monotonic()
            try:
                logger.debug(
                    "Calling LLM API",
                    extra_data={
                        "provider": model_config.provider,
                        "model": model_config.resolved_model_name,
                        "api_type": model_config.api_type,
                        "url": url,
                        "attempt": attempt + 1,
                    },
                )

                response = await client.post(url, headers=headers, json=payload)
                latency = (time.monotonic() - start) * 1000

                self._record_metric(
                    model_id, attempt + 1, latency, True, response.status_code
                )

                response.raise_for_status()
                return adapter.parse_response(response.json())

            except httpx.HTTPStatusError as e:
                latency = (time.monotonic() - start) * 1000
                status = e.response.status_code
                self._record_metric(
                    model_id, attempt + 1, latency, False, status, str(e)
                )
                last_error = e

                if status not in retry_cfg.retryable_status_codes:
                    raise

                if attempt >= retry_cfg.max_retries:
                    raise

                wait = self._compute_delay(delay, retry_cfg)
                logger.warning(
                    "Retrying after HTTP error",
                    extra_data={
                        "status": status,
                        "attempt": attempt + 1,
                        "wait_s": round(wait, 2),
                    },
                )
                await asyncio.sleep(wait)
                delay = min(delay * retry_cfg.backoff_multiplier, retry_cfg.max_delay)

            except (httpx.TransportError, httpx.TimeoutException) as e:
                latency = (time.monotonic() - start) * 1000
                self._record_metric(
                    model_id, attempt + 1, latency, False, error=str(e)
                )
                last_error = e

                if attempt >= retry_cfg.max_retries:
                    raise

                wait = self._compute_delay(delay, retry_cfg)
                logger.warning(
                    "Retrying after transport error",
                    extra_data={
                        "error": str(e),
                        "attempt": attempt + 1,
                        "wait_s": round(wait, 2),
                    },
                )
                await asyncio.sleep(wait)
                delay = min(delay * retry_cfg.backoff_multiplier, retry_cfg.max_delay)

        raise last_error  # type: ignore[misc]

    @staticmethod
    def _compute_delay(base_delay: float, cfg: RetryConfig) -> float:
        if cfg.jitter:
            return base_delay * (0.5 + random.random())
        return base_delay

    def _record_metric(
        self,
        model_id: str,
        attempt: int,
        latency_ms: float,
        success: bool,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        self._metrics.append(
            CallMetrics(
                model_id=model_id,
                attempt=attempt,
                latency_ms=latency_ms,
                success=success,
                status_code=status_code,
                error=error,
            )
        )
        if len(self._metrics) > 1000:
            self._metrics = self._metrics[-500:]

    def get_metrics(self) -> list[CallMetrics]:
        return list(self._metrics)

    async def stream_message(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        response = await self.create_message(
            model_id=model_id,
            messages=messages,
            system=system,
            tools=tools,
            **kwargs,
        )
        if response.text:
            yield {"type": "text_delta", "text": response.text}
        yield response

    async def count_tokens(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
    ) -> int:
        model_config = self.registry.get_model(model_id)
        if not model_config:
            raise ValueError(f"Model not found: {model_id}")

        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total += len(block.get("text", "")) // 4
        return total

    async def aclose(self) -> None:
        for client in self._http_clients.values():
            await client.aclose()
        self._http_clients.clear()

    def _get_or_create_client(self, timeout: int) -> httpx.AsyncClient:
        if timeout not in self._http_clients:
            self._http_clients[timeout] = httpx.AsyncClient(timeout=timeout)
        return self._http_clients[timeout]

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        """获取模型配置（供外部组件使用）。"""
        return self.registry.get_model(model_id)
