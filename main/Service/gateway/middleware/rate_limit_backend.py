"""
P1-3 可插拔限流后端（策略模式）

提供统一 RateLimitBackend 接口，内置 InMemory 和 Redis 两种实现。
InMemoryBackend 带后台清理，防止过期 key 泄漏内存；
RedisBackend 使用 Lua 脚本实现原子滑窗，支持多副本部署。
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RateLimitBackend(ABC):
    """限流后端抽象接口（策略模式）。"""

    @abstractmethod
    async def is_allowed(self, key: str) -> tuple[bool, int]:
        """检查请求是否允许，返回 (allowed, remaining)。"""

    async def cleanup(self) -> None:
        """可选：清理过期数据。"""

    async def close(self) -> None:
        """可选：关闭资源。"""


class InMemoryBackend(RateLimitBackend):
    """基于内存滑动窗口的限流后端，带后台过期清理。

    - 单进程场景使用
    - 后台 task 定期清理过期 key，防止内存泄漏
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: int,
        *,
        cleanup_interval: float = 60.0,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._cleanup_interval = cleanup_interval
        self._cleanup_task: asyncio.Task | None = None

    async def start_cleanup_loop(self) -> None:
        """启动后台清理循环（需在 async 上下文调用）。"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.ensure_future(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._cleanup_interval)
                await self.cleanup()
        except asyncio.CancelledError:
            pass

    async def cleanup(self) -> None:
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            stale_keys = [
                k for k, ts_list in self._requests.items()
                if not ts_list or ts_list[-1] <= cutoff
            ]
            for k in stale_keys:
                del self._requests[k]
            if stale_keys:
                logger.debug("InMemoryBackend cleanup: removed %d stale keys", len(stale_keys))

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        async with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            current = len(self._requests[key])
            if current >= self.max_requests:
                return False, 0
            self._requests[key].append(now)
            return True, self.max_requests - current - 1

    async def close(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._requests.clear()


class RedisBackend(RateLimitBackend):
    """基于 Redis Lua 脚本的原子滑动窗口限流后端。

    使用 sorted set 存储时间戳，Lua 脚本保证 ZREMRANGEBYSCORE + ZCARD + ZADD 原子执行。
    适合多副本部署。
    """

    _LUA_SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local max_req = tonumber(ARGV[3])
    local cutoff = now - window

    redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
    local current = redis.call('ZCARD', key)

    if current >= max_req then
        return {0, 0}
    end

    redis.call('ZADD', key, now, now .. ':' .. math.random(100000))
    redis.call('EXPIRE', key, window + 1)
    return {1, max_req - current - 1}
    """

    def __init__(
        self,
        redis_url: str,
        max_requests: int,
        window_seconds: int,
        *,
        key_prefix: str = "rl:",
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._key_prefix = key_prefix
        self._redis_url = redis_url
        self._redis = None
        self._script_sha: str | None = None

    async def _ensure_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    self._redis_url, decode_responses=False
                )
                self._script_sha = await self._redis.script_load(self._LUA_SCRIPT)
            except Exception:
                logger.exception("Failed to connect to Redis for rate limiting")
                raise

    async def is_allowed(self, key: str) -> tuple[bool, int]:
        await self._ensure_redis()
        redis_key = f"{self._key_prefix}{key}"
        now = time.time()
        try:
            result = await self._redis.evalsha(
                self._script_sha,
                1,
                redis_key,
                str(now),
                str(self.window_seconds),
                str(self.max_requests),
            )
            allowed = int(result[0])
            remaining = int(result[1])
            return bool(allowed), remaining
        except Exception:
            logger.warning("Redis rate limit check failed, allowing request")
            return True, self.max_requests

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
