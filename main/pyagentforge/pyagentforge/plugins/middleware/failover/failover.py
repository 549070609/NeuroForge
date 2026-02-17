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

from pyagentforge.kernel.message import ProviderResponse
from pyagentforge.providers.base import BaseProvider
from pyagentforge.utils.logging import get_logger

logger = get_logger(__name__)


class FailoverCondition(Enum):
    """故障转移触发条件"""

    RATE_LIMIT = "rate_limit"  # 速率限制
    TIMEOUT = "timeout"  # 超时
    SERVER_ERROR = "server_error"  # 服务器错误 (5xx)
    AUTH_ERROR = "auth_error"  # 认证错误
    NETWORK_ERROR = "network_error"  # 网络错误
    ANY_ERROR = "any_error"  # 任何错误


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""

    ROUND_ROBIN = "round_robin"  # 轮询
    LEAST_LATENCY = "least_latency"  # 最低延迟
    RANDOM = "random"  # 随机
    PRIORITY = "priority"  # 按优先级
    WEIGHTED = "weighted"  # 按权重 (v3.0 新增)


class CircuitState(Enum):
    """熔断器状态 (v3.0 新增)"""

    CLOSED = "closed"  # 关闭 (正常)
    OPEN = "open"  # 打开 (拒绝请求)
    HALF_OPEN = "half_open"  # 半开 (允许一次尝试)


@dataclass
class ProviderHealth:
    """Provider 健康状态"""

    provider: BaseProvider
    name: str
    priority: int = 0
    weight: int = 100  # 权重 (v3.0 新增)，用于 WEIGHTED 调度
    is_healthy: bool = True
    consecutive_failures: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    average_latency_ms: float = 0
    total_requests: int = 0
    total_failures: int = 0

    # 配置
    max_consecutive_failures: int = 3
    recovery_timeout_seconds: float = 60

    # 熔断器状态 (v3.0 新增)
    circuit_state: CircuitState = field(default=CircuitState.CLOSED)
    circuit_open_until: float = 0  # 熔断器打开到这个时间

    def record_success(self, latency_ms: float) -> None:
        """记录成功请求"""
        self.consecutive_failures = 0
        self.is_healthy = True
        self.last_success_time = time.time()
        self.total_requests += 1

        # 熔断器：成功后恢复到 CLOSED
        if self.circuit_state == CircuitState.HALF_OPEN:
            self.circuit_state = CircuitState.CLOSED
            logger.info(
                "Circuit breaker recovered",
                extra_data={"provider": self.name},
            )

        # 更新平均延迟
        if self.average_latency_ms == 0:
            self.average_latency_ms = latency_ms
        else:
            self.average_latency_ms = (
                self.average_latency_ms * 0.8 + latency_ms * 0.2
            )

    def record_failure(self) -> None:
        """记录失败请求"""
        self.consecutive_failures += 1
        self.total_failures += 1
        self.total_requests += 1
        self.last_failure_time = time.time()

        if self.consecutive_failures >= self.max_consecutive_failures:
            self.is_healthy = False
            # 熔断器：打开
            self.circuit_state = CircuitState.OPEN
            self.circuit_open_until = time.time() + self.recovery_timeout_seconds
            logger.warning(
                "Provider marked unhealthy, circuit breaker OPEN",
                extra_data={
                    "provider": self.name,
                    "consecutive_failures": self.consecutive_failures,
                    "recovery_in_seconds": self.recovery_timeout_seconds,
                },
            )

    def check_recovery(self) -> bool:
        """
        检查是否可以恢复

        熔断器状态机:
        - CLOSED: 正常，返回 True
        - OPEN: 检查是否超时，超时则转为 HALF_OPEN
        - HALF_OPEN: 允许一次尝试

        Returns:
            是否可以接受请求
        """
        # CLOSED 状态，正常
        if self.circuit_state == CircuitState.CLOSED:
            return True

        # OPEN 状态，检查是否超时
        if self.circuit_state == CircuitState.OPEN:
            if time.time() >= self.circuit_open_until:
                # 转为 HALF_OPEN
                self.circuit_state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit breaker HALF_OPEN, allowing one attempt",
                    extra_data={"provider": self.name},
                )
                return True
            return False

        # HALF_OPEN 状态，允许一次尝试
        if self.circuit_state == CircuitState.HALF_OPEN:
            return True

        return self.is_healthy

    def get_metrics_snapshot(self) -> dict[str, Any]:
        """
        获取指标快照 (v3.0 新增)

        为 TelemetryCollector 提供统一接口。
        """
        return {
            "name": self.name,
            "is_healthy": self.is_healthy,
            "circuit_state": self.circuit_state.value,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "average_latency_ms": self.average_latency_ms,
        }


@dataclass
class FailoverConfig:
    """故障转移配置"""

    enabled: bool = True
    max_retries: int = 3
    retry_delay_ms: float = 1000
    retry_backoff_multiplier: float = 2.0
    max_retry_delay_ms: float = 30000
    conditions: list[FailoverCondition] = field(
        default_factory=lambda: [
            FailoverCondition.RATE_LIMIT,
            FailoverCondition.TIMEOUT,
            FailoverCondition.SERVER_ERROR,
        ]
    )
    load_balance_strategy: LoadBalanceStrategy = LoadBalanceStrategy.PRIORITY


class ProviderPool:
    """
    Provider 池

    管理多个 Provider 并支持故障转移和负载均衡
    """

    def __init__(
        self,
        config: FailoverConfig | None = None,
    ) -> None:
        """
        初始化 Provider 池

        Args:
            config: 故障转移配置
        """
        self.config = config or FailoverConfig()
        self._providers: dict[str, ProviderHealth] = {}
        self._provider_list: list[ProviderHealth] = []
        self._round_robin_index = 0

    def add_provider(
        self,
        name: str,
        provider: BaseProvider,
        priority: int = 0,
        **health_config: Any,
    ) -> None:
        """
        添加 Provider

        Args:
            name: Provider 名称
            provider: Provider 实例
            priority: 优先级 (越小越优先)
            **health_config: 健康检查配置
        """
        health = ProviderHealth(
            provider=provider,
            name=name,
            priority=priority,
            **health_config,
        )
        self._providers[name] = health
        self._provider_list.append(health)

        # 按优先级排序
        self._provider_list.sort(key=lambda h: h.priority)

        logger.info(
            "Added provider to pool",
            extra_data={"name": name, "priority": priority, "total": len(self._providers)},
        )

    def remove_provider(self, name: str) -> None:
        """移除 Provider"""
        if name in self._providers:
            health = self._providers.pop(name)
            self._provider_list.remove(health)
            logger.info(
                "Removed provider from pool",
                extra_data={"name": name},
            )

    def get_provider(self, name: str) -> BaseProvider | None:
        """获取指定 Provider"""
        health = self._providers.get(name)
        return health.provider if health else None

    def _select_provider(self) -> ProviderHealth | None:
        """
        选择一个可用的 Provider

        Returns:
            ProviderHealth 或 None
        """
        available = [h for h in self._provider_list if h.is_healthy or h.check_recovery()]

        if not available:
            logger.error("No healthy providers available")
            return None

        strategy = self.config.load_balance_strategy

        if strategy == LoadBalanceStrategy.PRIORITY:
            return available[0]  # 已按优先级排序

        elif strategy == LoadBalanceStrategy.ROUND_ROBIN:
            self._round_robin_index = (self._round_robin_index + 1) % len(available)
            return available[self._round_robin_index]

        elif strategy == LoadBalanceStrategy.LEAST_LATENCY:
            return min(available, key=lambda h: h.average_latency_ms or float("inf"))

        elif strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(available)

        elif strategy == LoadBalanceStrategy.WEIGHTED:
            # 按权重随机选择 (v3.0 新增)
            import random
            total_weight = sum(h.weight for h in available)
            if total_weight <= 0:
                return available[0]
            r = random.uniform(0, total_weight)
            cumulative = 0
            for h in available:
                cumulative += h.weight
                if r <= cumulative:
                    return h
            return available[-1]

        return available[0]

    def _should_failover(self, error: Exception) -> bool:
        """
        判断是否应该故障转移

        Args:
            error: 发生的异常

        Returns:
            是否应该故障转移
        """
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

            elif condition == FailoverCondition.AUTH_ERROR:
                if "401" in error_str or "403" in error_str or "auth" in error_str:
                    return True

            elif condition == FailoverCondition.NETWORK_ERROR:
                if "network" in error_str or "connection" in error_str:
                    return True

            elif condition == FailoverCondition.ANY_ERROR:
                return True

        return False

    async def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ProviderResponse:
        """
        创建消息（带故障转移）

        Args:
            system: 系统提示词
            messages: 消息历史
            tools: 工具列表
            **kwargs: 额外参数

        Returns:
            Provider 响应
        """
        if not self.config.enabled:
            # 不启用故障转移，直接使用第一个 Provider
            health = self._select_provider()
            if not health:
                raise RuntimeError("No provider available")
            return await health.provider.create_message(system, messages, tools, **kwargs)

        last_error: Exception | None = None
        retry_delay = self.config.retry_delay_ms

        for attempt in range(self.config.max_retries):
            health = self._select_provider()

            if not health:
                raise RuntimeError("No healthy providers available")

            try:
                start_time = time.time()
                response = await health.provider.create_message(
                    system, messages, tools, **kwargs
                )
                latency_ms = (time.time() - start_time) * 1000
                health.record_success(latency_ms)

                return response

            except Exception as e:
                last_error = e
                health.record_failure()

                logger.warning(
                    "Provider request failed",
                    extra_data={
                        "provider": health.name,
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

                # 检查是否应该故障转移
                if not self._should_failover(e):
                    raise

                # 等待后重试
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(retry_delay / 1000)
                    retry_delay = min(
                        retry_delay * self.config.retry_backoff_multiplier,
                        self.config.max_retry_delay_ms,
                    )

        raise RuntimeError(
            f"All providers failed after {self.config.max_retries} attempts"
        ) from last_error

    async def stream_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """
        流式创建消息（带故障转移）

        Args:
            system: 系统提示词
            messages: 消息历史
            tools: 工具列表
            **kwargs: 额外参数

        Yields:
            流式响应块
        """
        if not self.config.enabled:
            health = self._select_provider()
            if not health:
                raise RuntimeError("No provider available")
            async for chunk in health.provider.stream_message(
                system, messages, tools, **kwargs
            ):
                yield chunk
            return

        last_error: Exception | None = None
        retry_delay = self.config.retry_delay_ms

        for attempt in range(self.config.max_retries):
            health = self._select_provider()

            if not health:
                raise RuntimeError("No healthy providers available")

            try:
                start_time = time.time()
                chunks = []
                async for chunk in health.provider.stream_message(
                    system, messages, tools, **kwargs
                ):
                    chunks.append(chunk)
                    yield chunk

                latency_ms = (time.time() - start_time) * 1000
                health.record_success(latency_ms)
                return

            except Exception as e:
                last_error = e
                health.record_failure()

                logger.warning(
                    "Provider streaming failed",
                    extra_data={
                        "provider": health.name,
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )

                if not self._should_failover(e):
                    raise

                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(retry_delay / 1000)
                    retry_delay = min(
                        retry_delay * self.config.retry_backoff_multiplier,
                        self.config.max_retry_delay_ms,
                    )

        raise RuntimeError(
            f"All providers failed after {self.config.max_retries} attempts"
        ) from last_error

    def get_health_status(self) -> dict[str, Any]:
        """
        获取所有 Provider 的健康状态

        Returns:
            健康状态字典
        """
        return {
            name: {
                "is_healthy": health.is_healthy,
                "consecutive_failures": health.consecutive_failures,
                "total_requests": health.total_requests,
                "total_failures": health.total_failures,
                "average_latency_ms": health.average_latency_ms,
            }
            for name, health in self._providers.items()
        }


def create_provider_pool_from_config(
    config: dict[str, Any],
    provider_factory: Any,
) -> ProviderPool:
    """
    从配置创建 Provider 池

    Args:
        config: 配置字典
        provider_factory: Provider 工厂函数

    Returns:
        ProviderPool 实例
    """
    failover_config = FailoverConfig(
        enabled=config.get("failover", {}).get("enabled", True),
        max_retries=config.get("failover", {}).get("max_retries", 3),
        retry_delay_ms=config.get("failover", {}).get("retry_delay_ms", 1000),
        retry_backoff_multiplier=config.get("failover", {}).get(
            "retry_backoff_multiplier", 2.0
        ),
        max_retry_delay_ms=config.get("failover", {}).get("max_retry_delay_ms", 30000),
        load_balance_strategy=LoadBalanceStrategy(
            config.get("load_balancing", {}).get("strategy", "priority")
        ),
    )

    pool = ProviderPool(failover_config)

    providers_config = config.get("providers", {})
    for name, provider_config in providers_config.items():
        provider = provider_factory(
            provider_type=provider_config["type"],
            model=provider_config["model"],
            **provider_config.get("options", {}),
        )
        pool.add_provider(
            name=name,
            provider=provider,
            priority=provider_config.get("priority", 0),
        )

    return pool
