"""P1-7 Checkpoint 重试与降级回归测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from pyagentforge.kernel.checkpoint import BaseCheckpointer, Checkpoint, MemoryCheckpointer
from pyagentforge.kernel.context import ContextManager
from pyagentforge.kernel.engine import AgentConfig, AgentEngine
from pyagentforge.kernel.executor import ToolRegistry


pytestmark = pytest.mark.asyncio


class FailNTimesCheckpointer(BaseCheckpointer):
    """前 N 次 save 抛 OSError，之后正常。"""

    def __init__(self, fail_count: int):
        self._fail_count = fail_count
        self._call_count = 0
        self._inner = MemoryCheckpointer()

    async def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        self._call_count += 1
        if self._call_count <= self._fail_count:
            raise OSError(f"disk error #{self._call_count}")
        await self._inner.save(session_id, checkpoint)

    async def load(self, session_id: str) -> Checkpoint | None:
        return await self._inner.load(session_id)

    async def delete(self, session_id: str) -> None:
        await self._inner.delete(session_id)

    async def list_sessions(self) -> list[str]:
        return await self._inner.list_sessions()


class AlwaysFailCheckpointer(BaseCheckpointer):
    """save 永远抛异常。"""

    async def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        raise OSError("permanent failure")

    async def load(self, session_id: str) -> Checkpoint | None:
        return None

    async def delete(self, session_id: str) -> None:
        pass

    async def list_sessions(self) -> list[str]:
        return []


class NonRetryableCheckpointer(BaseCheckpointer):
    """save 抛不可重试异常（如序列化错误）。"""

    async def save(self, session_id: str, checkpoint: Checkpoint) -> None:
        raise TypeError("cannot serialize")

    async def load(self, session_id: str) -> Checkpoint | None:
        return None

    async def delete(self, session_id: str) -> None:
        pass

    async def list_sessions(self) -> list[str]:
        return []


class _StubProvider:
    def __init__(self):
        self.model = "stub"


def _make_engine(checkpointer: BaseCheckpointer, plugin_manager=None) -> AgentEngine:
    engine = AgentEngine.__new__(AgentEngine)
    engine.provider = _StubProvider()
    engine.config = AgentConfig()
    engine.context = ContextManager(system_prompt="test")
    engine.checkpointer = checkpointer
    engine.plugin_manager = plugin_manager
    engine._session_id = "test-session"
    engine._checkpoint_consecutive_failures = 0
    engine._checkpoint_disabled = False
    return engine


class TestCheckpointRetry:
    async def test_retryable_error_retries_then_succeeds(self):
        cp = FailNTimesCheckpointer(fail_count=2)
        engine = _make_engine(cp)
        await engine._save_checkpoint(1)
        assert cp._call_count == 3
        assert engine._checkpoint_consecutive_failures == 0

    async def test_non_retryable_error_does_not_retry(self):
        cp = NonRetryableCheckpointer()
        engine = _make_engine(cp)
        await engine._save_checkpoint(1)
        assert engine._checkpoint_consecutive_failures == 1

    async def test_consecutive_failures_disable_checkpoint(self):
        cp = AlwaysFailCheckpointer()
        engine = _make_engine(cp)
        for i in range(AgentEngine._CHECKPOINT_FAIL_THRESHOLD):
            await engine._save_checkpoint(i)
        assert engine._checkpoint_disabled is True

    async def test_disabled_checkpoint_skips_save(self):
        cp = MemoryCheckpointer()
        engine = _make_engine(cp)
        engine._checkpoint_disabled = True
        await engine._save_checkpoint(1)
        stored = await cp.load("test-session")
        assert stored is None

    async def test_on_checkpoint_failed_hook_fired(self):
        mock_pm = AsyncMock()
        mock_pm.emit_hook = AsyncMock(return_value=None)
        cp = AlwaysFailCheckpointer()
        engine = _make_engine(cp, plugin_manager=mock_pm)
        await engine._save_checkpoint(1)
        mock_pm.emit_hook.assert_called_once()
        call_args = mock_pm.emit_hook.call_args
        assert call_args[0][0] == "on_checkpoint_failed"
        payload = call_args[0][1]
        assert payload["session_id"] == "test-session"
        assert payload["consecutive"] == 1
