"""统一 LLM 客户端。

支持重试、指数退避、故障转移和 fallback 模型。
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from pyagentforge.kernel.hooks import (
    HookContext,
    RequestPayload,
    run_request_interceptors,
    run_response_transformers,
    run_stream_transformers,
)
from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.kernel.model_registry import ModelConfig, ModelRegistry
from pyagentforge.protocols import PROTOCOL_ADAPTERS, StreamEvent
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
    """协议驱动的统一 LLM 客户端，内置重试和 fallback。

    生命周期与 event loop
    ----------------------
    本类内部维护一个 ``httpx.AsyncClient`` 缓存。httpx 的 AsyncClient
    会把 socket 绑定到**创建它时的 event loop**；若在另一个 loop 上复用
    同一实例，会抛 ``RuntimeError: Event loop is closed``。

    为避免该陷阱（pytest-asyncio 默认为每个用例新建 loop、
    长期服务可能切换 loop），本类的 HTTP client 缓存以
    ``(id(running_loop), timeout)`` 为 key：
    - 同一 loop 下重复调用复用连接池；
    - 切换到新 loop 时自动创建新客户端，并清理已关闭 loop 的遗留条目；
    - ``aclose()`` 关闭当前仍存活 loop 上的所有客户端；
    - 支持 ``async with LLMClient() as client: ...`` 语义。
    """

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        retry_config: RetryConfig | None = None,
        fallback_model_ids: list[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry(load_from_config=True)
        self.retry_config = retry_config or RetryConfig()
        self.fallback_model_ids = fallback_model_ids or []
        # 可选的底层 httpx transport（主要用于测试注入 MockTransport）
        self._transport = transport
        # key: (id(loop), timeout) -> (loop_ref, httpx.AsyncClient)
        self._http_clients: dict[tuple[int, int], tuple[asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}
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

                # Hook point: 请求即将发送，运行所有匹配的 RequestInterceptor
                hook_ctx = HookContext(
                    model_id=model_id,
                    model_config=model_config,
                    attempt=attempt + 1,
                )
                request_obj = RequestPayload(url=url, headers=dict(headers), payload=payload)
                request_obj = await run_request_interceptors(hook_ctx, request_obj)

                response = await client.post(
                    request_obj.url,
                    headers=request_obj.headers,
                    json=request_obj.payload,
                )
                latency = (time.monotonic() - start) * 1000

                self._record_metric(
                    model_id, attempt + 1, latency, True, response.status_code
                )

                response.raise_for_status()
                provider_response = adapter.parse_response(response.json())
                # Hook point: 响应解析完成，运行所有匹配的 ResponseTransformer
                return await run_response_transformers(hook_ctx, provider_response)

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
        """通过 SSE 流式调用 LLM。

        Yields:
            - 中间 :class:`StreamEvent` 对象（经 StreamTransformer 过滤后）；
            - 最后一个 :class:`ProviderResponse`（由 adapter.aggregate_stream 合成，
              再经 ResponseTransformer 管线处理）。

        调用方可通过 ``async for chunk in client.stream_message(...)`` 消费，
        并用 ``isinstance(chunk, ProviderResponse)`` 判断终态。
        """
        model_candidates = self.registry.get_model_candidates(model_id)
        if not model_candidates:
            raise ValueError(f"Model configuration error: model '{model_id}' not found")

        last_error: Exception | None = None
        for candidate_index, model_config in enumerate(model_candidates):
            try:
                async for item in self._stream_model_config(
                    model_id=model_id,
                    model_config=model_config,
                    messages=messages,
                    system=system,
                    tools=tools,
                    **kwargs,
                ):
                    yield item
                return
            except Exception as exc:
                last_error = exc
                if candidate_index < len(model_candidates) - 1:
                    logger.warning(
                        "Stream model config failed, trying fallback config",
                        extra_data={
                            "model_id": model_id,
                            "failed_provider": model_config.provider,
                            "error": str(exc),
                        },
                    )
        assert last_error is not None
        raise last_error

    async def _stream_model_config(
        self,
        model_id: str,
        model_config: ModelConfig,
        messages: list[dict[str, Any]],
        system: str | None,
        tools: list[dict[str, Any]] | None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        adapter = PROTOCOL_ADAPTERS.get(model_config.api_type)
        if not adapter:
            raise ValueError(f"Unsupported api_type: {model_config.api_type}")
        if not adapter.supports_streaming():
            raise ValueError(
                f"Protocol {model_config.api_type!r} does not support streaming"
            )

        request_params = {
            "model": model_config.resolved_model_name,
            "messages": messages,
            "system": system,
            "tools": tools,
            "max_tokens": kwargs.pop("max_tokens", model_config.max_output_tokens),
            "temperature": kwargs.pop("temperature", 1.0),
            **kwargs,
        }

        payload = adapter.build_stream_request(request_params, model_config)
        headers = adapter.build_stream_headers(model_config)
        url = adapter.build_stream_url(model_config)
        http_client = self._get_or_create_client(model_config.timeout)

        hook_ctx = HookContext(model_id=model_id, model_config=model_config)
        request_obj = RequestPayload(url=url, headers=dict(headers), payload=payload)
        request_obj = await run_request_interceptors(hook_ctx, request_obj)

        start = time.monotonic()
        collected: list[StreamEvent] = []
        async with http_client.stream(
            "POST",
            request_obj.url,
            headers=request_obj.headers,
            json=request_obj.payload,
        ) as response:
            if response.status_code >= 400:
                # 读取错误正文后再抛，便于调试
                error_body = await response.aread()
                self._record_metric(
                    model_id, 1, (time.monotonic() - start) * 1000, False,
                    response.status_code, error_body[:500].decode("utf-8", errors="replace"),
                )
                response.raise_for_status()

            async for line in response.aiter_lines():
                event = adapter.parse_stream_line(line)
                if event is None:
                    continue
                collected.append(event)
                transformed = await run_stream_transformers(hook_ctx, event)
                if transformed is None:
                    continue
                yield transformed
                if event.type == "done":
                    break

        latency = (time.monotonic() - start) * 1000
        self._record_metric(model_id, 1, latency, True, 200)

        final = adapter.aggregate_stream(collected, model_config)
        final = await run_response_transformers(hook_ctx, final)
        yield final

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
        """关闭当前 event loop 上所有 httpx 客户端。

        对来自已关闭 loop 的遗留条目，只做丢弃（在已关闭 loop 上 await 会失败）。
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        remaining: dict[tuple[int, int], tuple[asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}
        for key, (loop, client) in self._http_clients.items():
            if loop.is_closed():
                # 对应 loop 已关闭，无法安全调用 aclose；直接丢弃
                continue
            if current_loop is not None and loop is current_loop:
                try:
                    await client.aclose()
                except Exception as exc:  # pragma: no cover - 清理尽力而为
                    logger.debug("Failed to close httpx client: %s", exc)
                continue
            # 其它仍存活的 loop 上的客户端：保留，由该 loop 的拥有者自行关闭
            remaining[key] = (loop, client)
        self._http_clients = remaining

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    def _get_or_create_client(self, timeout: int) -> httpx.AsyncClient:
        """按 (running_loop, timeout) 维度返回/创建 httpx client。

        调用方必须在 async 上下文中使用（已有 running loop）。
        """
        loop = asyncio.get_running_loop()
        key = (id(loop), timeout)

        cached = self._http_clients.get(key)
        if cached is not None:
            cached_loop, cached_client = cached
            if not cached_loop.is_closed() and cached_loop is loop:
                return cached_client
            # loop 已失效 -> 丢弃该条目（不 await，防止报错）
            self._http_clients.pop(key, None)

        # 机会性清理其它已关闭 loop 的遗留条目，防止缓存无限增长
        stale = [k for k, (l, _c) in self._http_clients.items() if l.is_closed()]
        for k in stale:
            self._http_clients.pop(k, None)

        client_kwargs: dict[str, Any] = {"timeout": timeout}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport
        client = httpx.AsyncClient(**client_kwargs)
        self._http_clients[key] = (loop, client)
        return client

    def get_model_config(self, model_id: str) -> ModelConfig | None:
        """获取模型配置（供外部组件使用）。"""
        return self.registry.get_model(model_id)
