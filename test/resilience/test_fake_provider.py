"""P1-12 FakeProvider 基础行为验证 + AgentEngine 故障注入集成测试。"""

from __future__ import annotations

import asyncio

import pytest

from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.executor import ToolRegistry

from .fake_provider import FakeAction, FakeProvider


pytestmark = pytest.mark.asyncio


class TestFakeProviderUnit:
    async def test_default_returns_text(self):
        p = FakeProvider()
        resp = await p.create_message(system="", messages=[])
        assert resp.text == "fake response"
        assert p.call_count == 1

    async def test_sequence_actions(self):
        p = FakeProvider(actions=[
            FakeAction(text="a"),
            FakeAction(text="b"),
        ])
        r1 = await p.create_message(system="", messages=[])
        r2 = await p.create_message(system="", messages=[])
        assert r1.text == "a"
        assert r2.text == "b"
        assert p.call_count == 2

    async def test_raise_exception(self):
        p = FakeProvider(actions=[FakeAction(raise_exc=TimeoutError("boom"))])
        with pytest.raises(TimeoutError, match="boom"):
            await p.create_message(system="", messages=[])

    async def test_delay(self):
        p = FakeProvider(actions=[FakeAction(text="ok", delay=0.05)])
        resp = await p.create_message(system="", messages=[])
        assert resp.text == "ok"

    async def test_stream(self):
        p = FakeProvider(actions=[FakeAction(text="streamed")])
        chunks = []
        async for chunk in p.create_message_stream(system="", messages=[]):
            chunks.append(chunk)
        assert any(c.get("text") == "streamed" for c in chunks)


class TestEngineWithFakeProvider:
    """验证 AgentEngine 在各种 Provider 故障下的行为。"""

    def _make_engine(self, provider: FakeProvider, **kw) -> AgentEngine:
        config = AgentConfig(max_iterations=5, timeout=2, **kw)
        return AgentEngine(
            provider=provider,
            tool_registry=ToolRegistry(),
            config=config,
        )

    async def test_normal_completion(self):
        engine = self._make_engine(FakeProvider(actions=[
            FakeAction(text="done"),
        ]))
        result = await engine.run("hello")
        assert "done" in result

    async def test_provider_timeout_raises_agent_timeout(self):
        from pyagentforge.kernel.errors import AgentTimeoutError

        engine = self._make_engine(FakeProvider(actions=[
            FakeAction(delay=10),
        ]))
        with pytest.raises(AgentTimeoutError):
            await engine.run("hello")

    async def test_provider_error_propagated(self):
        engine = self._make_engine(FakeProvider(actions=[
            FakeAction(raise_exc=ConnectionError("network down")),
        ]))
        with pytest.raises(ConnectionError, match="network down"):
            await engine.run("hello")

    async def test_cancel_event_stops_engine(self):
        from pyagentforge.kernel.errors import AgentCancelledError

        cancel = asyncio.Event()
        cancel.set()
        engine = self._make_engine(FakeProvider())
        with pytest.raises(AgentCancelledError):
            await engine.run("hello", cancel_event=cancel)
