"""
Telemetry Middleware - 遥测中间件

作为中间件插入管道，自动追踪请求延迟和 Token 使用。
"""

import time
from typing import Any

from pyagentforge.middleware.base import BaseMiddleware, MiddlewareContext, NextMiddleware
from pyagentforge.middleware.telemetry.collector import TelemetryCollector


class TelemetryMiddleware(BaseMiddleware):
    """
    遥测中间件

    自动追踪:
    - 请求延迟
    - Token 使用量
    - 请求/错误计数

    Class Attributes:
        name: 中间件名称
        priority: 优先级 (200, 较后执行以确保捕获完整请求)

    Attributes:
        collector: 遥测收集器

    Examples:
        >>> from pyagentforge.middleware import MiddlewarePipeline
        >>> from pyagentforge.middleware.telemetry import TelemetryMiddleware, TelemetryCollector
        >>>
        >>> collector = TelemetryCollector()
        >>> telemetry = TelemetryMiddleware(collector)
        >>>
        >>> pipeline = MiddlewarePipeline()
        >>> pipeline.add(telemetry)
    """

    name = "telemetry"
    priority = 200  # 较后执行，确保捕获完整请求

    def __init__(self, collector: TelemetryCollector):
        """
        初始化遥测中间件

        Args:
            collector: 遥测收集器实例
        """
        self.collector = collector

    async def process(
        self,
        ctx: MiddlewareContext,
        next_middleware: NextMiddleware
    ) -> Any:
        """
        处理请求，追踪遥测数据

        Args:
            ctx: 中间件上下文
            next_middleware: 下一个中间件

        Returns:
            处理结果
        """
        start_time = time.time()
        success = True

        try:
            # 调用下一个中间件
            result = await next_middleware(ctx)

            # 提取 Token 使用量 (如果响应中包含)
            self._extract_tokens(ctx.session_key, result)

            return result

        except Exception as e:
            success = False
            raise

        finally:
            # 计算延迟
            latency_ms = (time.time() - start_time) * 1000

            # 记录请求
            self.collector.track_request(
                session_key=ctx.session_key,
                latency_ms=latency_ms,
                success=success
            )

    def _extract_tokens(self, session_key: str, result: Any) -> None:
        """
        从响应中提取 Token 使用量

        尝试从不同格式的响应中提取 input/output tokens。
        """
        if result is None:
            return

        # 尝试从字典中提取
        if isinstance(result, dict):
            usage = result.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            if input_tokens or output_tokens:
                self.collector.track_tokens(
                    session_key=session_key,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )

        # 尝试从对象属性中提取
        elif hasattr(result, "usage"):
            usage = result.usage
            input_tokens = getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "output_tokens", 0)

            if input_tokens or output_tokens:
                self.collector.track_tokens(
                    session_key=session_key,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens
                )

    def sync_event_bus(self, event_bus) -> None:
        """
        从 EventBus 同步数据

        Args:
            event_bus: EventBus 实例
        """
        if hasattr(event_bus, "get_stats"):
            stats = event_bus.get_stats()
            self.collector.sync_from_event_bus(stats)

    def sync_provider_pool(self, provider_pool) -> None:
        """
        从 ProviderPool 同步数据

        Args:
            provider_pool: ProviderPool 实例
        """
        if hasattr(provider_pool, "get_health_status"):
            health = provider_pool.get_health_status()
            self.collector.sync_from_provider_pool(health)
