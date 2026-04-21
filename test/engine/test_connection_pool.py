"""
P1-1 连接池回归测试

验证：
  1. ConnectionPoolConfig 默认值合理
  2. LLMClient._get_or_create_client 构建的 httpx.AsyncClient 带 Limits + Timeout
  3. get_shared_llm_client 返回同一实例（单例）
  4. close_shared_llm_client 正确清理单例
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from pyagentforge.client import (
    ConnectionPoolConfig,
    LLMClient,
    RetryConfig,
    close_shared_llm_client,
    get_shared_llm_client,
)
import pyagentforge.client as client_module


# ── ConnectionPoolConfig 默认值 ──────────────────────────────────

class TestConnectionPoolConfig:
    def test_defaults(self):
        cfg = ConnectionPoolConfig()
        assert cfg.max_connections == 100
        assert cfg.max_keepalive_connections == 20
        assert cfg.keepalive_expiry == 30.0
        assert cfg.connect_timeout == 10.0
        assert cfg.read_timeout == 120.0

    def test_custom(self):
        cfg = ConnectionPoolConfig(max_connections=50, connect_timeout=5.0)
        assert cfg.max_connections == 50
        assert cfg.connect_timeout == 5.0


# ── _get_or_create_client 带 Limits + Timeout ──────────────────

class TestClientPooling:
    @pytest.mark.asyncio
    async def test_client_has_limits_and_timeout(self):
        pool_cfg = ConnectionPoolConfig(
            max_connections=42,
            max_keepalive_connections=10,
            connect_timeout=3.0,
            read_timeout=60.0,
        )
        llm = LLMClient(
            pool_config=pool_cfg,
            retry_config=RetryConfig(max_retries=0),
        )
        try:
            client = llm._get_or_create_client(timeout=90)
            assert isinstance(client, httpx.AsyncClient)
            # read_timeout = max(timeout=90, pool.read_timeout=60) → 90
            assert client.timeout.read == 90.0
            assert client.timeout.connect == 3.0
            # 连接池参数通过 transport._pool 暴露
            transport = client._transport
            pool = getattr(transport, "_pool", None)
            if pool is not None:
                assert pool._max_connections == 42
                assert pool._max_keepalive_connections == 10
        finally:
            await llm.aclose()

    @pytest.mark.asyncio
    async def test_same_loop_same_timeout_reuses_client(self):
        llm = LLMClient(retry_config=RetryConfig(max_retries=0))
        try:
            c1 = llm._get_or_create_client(timeout=30)
            c2 = llm._get_or_create_client(timeout=30)
            assert c1 is c2
        finally:
            await llm.aclose()

    @pytest.mark.asyncio
    async def test_different_timeout_creates_new_client(self):
        llm = LLMClient(retry_config=RetryConfig(max_retries=0))
        try:
            c1 = llm._get_or_create_client(timeout=30)
            c2 = llm._get_or_create_client(timeout=60)
            assert c1 is not c2
        finally:
            await llm.aclose()


# ── 共享单例 ──────────────────────────────────────────────────

class TestSharedLLMClient:
    @pytest.fixture(autouse=True)
    def _reset_shared(self):
        """确保测试前后清理单例。"""
        client_module._shared_client = None
        yield
        client_module._shared_client = None

    def test_singleton(self):
        a = get_shared_llm_client()
        b = get_shared_llm_client()
        assert a is b

    @pytest.mark.asyncio
    async def test_close_resets_singleton(self):
        _ = get_shared_llm_client()
        assert client_module._shared_client is not None
        await close_shared_llm_client()
        assert client_module._shared_client is None
