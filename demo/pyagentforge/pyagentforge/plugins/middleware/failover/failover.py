"""
Provider 故障转移系统

支持多 Provider 配置、自动故障转移和负载均衡
"""

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

import logging

logger = logging.getLogger(__name__)


class FailoverCondition(Enum):
    """故障转移触发条件"""
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    AUTH_ERROR = "auth_error"
    NETWORK_ERROR = "network_error"
    ANY_ERROR = "any_error"


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"
    LEAST_LATENCY = "least_latency"
    RANDOM = "random"
    PRIORITY = "priority"


@dataclass
class ProviderHealth:
    """Provider 健康状态"""
    provider: Any
    name: str
    priority: int = 0
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    average_latency_ms: float = 0
    total_requests: int = 0
    total_failures: int = 0
    max_consecutive_failures: int = 3
    recovery_timeout_seconds: float = 60

    def record_success(self, latency_ms: float) -> None:
        self.consecutive_failures = 0
        self.is_healthy = True
        self.last_success_time = time.time()
        self.total_requests += 1
        if self.average_latency_ms == 0:
            self.average_latency_ms = latency_ms
        else:
            self.average_latency_ms = self.average_latency_ms * 0.8 + latency_ms * 0.2

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_requests += 1
        self.last_failure_time = time.time()
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.is_healthy = False
            logger.warning(f"Provider {self.name} marked unhealthy")

    def check_recovery(self) -> bool:
        if self.is_healthy:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout_seconds


@dataclass
class FailoverConfig:
    """故障转移配置"""
    enabled: bool = True
    max_retries: int = 3
    retry_delay_ms: float = 1000
    retry_backoff_multiplier: float = 2.0
    max_retry_delay_ms: float = 30000
    conditions: list = field(default_factory=lambda: [
        FailoverCondition.RATE_LIMIT,
        FailoverCondition.TIMEOUT,
        FailoverCondition.SERVER_ERROR,
    ])
    load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.PRIORITY


class ProviderPool:
    """Provider 池"""

    def __init__(self, config: FailoverConfig | None = None):
        self.config = config or FailoverConfig()
        self._providers: dict[str, ProviderHealth] = {}
        self._provider_list: list[ProviderHealth] = []
        self._round_robin_index = 0

    def add_provider(self, name: str, provider: Any, priority: int = 0, **kwargs) -> None:
        health = ProviderHealth(provider=provider, name=name, priority=priority, **kwargs)
        self._providers[name] = health
        self._provider_list.append(health)
        self._provider_list.sort(key=lambda h: h.priority)
        logger.info(f"Added provider {name} to pool")

    def remove_provider(self, name: str) -> None:
        if name in self._providers:
            health = self._providers.pop(name)
            self._provider_list.remove(health)

    def get_provider(self, name: str) -> Any | None:
        health = self._providers.get(name)
        return health.provider if health else None

    def _select_provider(self) -> ProviderHealth | None:
        available = [h for h in self._provider_list if h.is_healthy or h.check_recovery()]
        if not available:
            return None

        if self.config.load_balance_strategy == LoadBalanceStrategy.PRIORITY:
            return available[0]
        elif self.config.load_balance_strategy == LoadBalanceStrategy.ROUND_ROBIN:
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
            return available[self._round_robin_index]
        elif self.config.load_balance_strategy == LoadBalanceStrategy.LEAST_LATENCY:
            return min(available, key=lambda h: h.average_latency_ms or float("inf"))
        elif self.config.load_balance_strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(available)
        return available[0]

    def _should_failover(self, error: Exception) -> bool:
        error_str = str(error).lower()
        for condition in self.config.conditions:
            if condition == FailoverCondition.RATE_LIMIT:
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    return True
            elif condition == FailoverCondition.TIMEOUT:
                if "timeout" in error_str:
                    return True
            elif condition == FailoverCondition.SERVER_ERROR:
                if "500" in error_str or "502" in error_str or "503" in error_str:
                    return True
            elif condition == FailoverCondition.ANY_ERROR:
                return True
        return False

    async def create_message(
        self, system: str, messages: list, tools: list, **kwargs
    ) -> Any:
        if not self.config.enabled:
            health = self._select_provider()
            if not health:
                raise RuntimeError("No provider available")
            return await health.provider.create_message(system, messages, tools, **kwargs)

        last_error = None
        retry_delay = self.config.retry_delay_ms

        for attempt in range(self.config.max_retries):
            health = self._select_provider()
            if not health:
                raise RuntimeError("No healthy providers available")

            try:
                start_time = time.time()
                response = await health.provider.create_message(system, messages, tools, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                health.record_success(latency_ms)
                return response
            except Exception as e:
                last_error = e
                health.record_failure()
                logger.warning(f"Provider {health.name} failed: {e}")

                if not self._should_failover(e):
                    raise

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(retry_delay / 1000)
                    retry_delay = min(
                        retry_delay * self.config.retry_backoff_multiplier,
                        self.config.max_retry_delay_ms,
                    )

        raise RuntimeError(f"All providers failed") from last_error

    def get_health_status(self) -> dict:
        return {
            name: {
                "is_healthy": h.is_healthy,
                "consecutive_failures": h.consecutive_failures,
                "total_requests": h.total_requests,
            }
            for name, h in self._providers.items()
        }
