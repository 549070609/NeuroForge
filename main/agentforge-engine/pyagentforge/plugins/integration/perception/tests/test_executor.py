"""
单元测试 — executor.DecisionExecutor / _default_find_user
"""

import asyncio
from typing import Any

import pytest

from pyagentforge.plugins.integration.perception.executor import (
    DecisionExecutor,
    ExecutionResult,
    execute_decision,
)
from pyagentforge.plugins.integration.perception.perception import (
    DecisionType,
    PerceptionResult,
)


def _make_result(decision: DecisionType, **kw) -> PerceptionResult:
    return PerceptionResult(decision=decision, reason="test", data={}, **kw)


# ---------------------------------------------------------------------------
# DecisionType.NONE
# ---------------------------------------------------------------------------

class TestExecutorNoneDecision:
    @pytest.mark.asyncio
    async def test_none_returns_success(self):
        ex = DecisionExecutor()
        er = await ex.execute(_make_result(DecisionType.NONE))
        assert er.success is True
        assert er.details["decision"] == "none"


# ---------------------------------------------------------------------------
# find_user — EventBus
# ---------------------------------------------------------------------------

class TestFindUserEventBus:
    @pytest.mark.asyncio
    async def test_sync_event_bus_success(self):
        published: list = []

        class SyncBus:
            def publish(self, event: str, payload: Any) -> None:
                published.append((event, payload))

        ex = DecisionExecutor(event_bus=SyncBus())
        er = await ex.execute(_make_result(DecisionType.FIND_USER))
        assert er.success is True
        assert "EventBus" in er.message
        assert len(published) == 1
        assert published[0][0] == "perception.alert"

    @pytest.mark.asyncio
    async def test_async_event_bus_success(self):
        published: list = []

        class AsyncBus:
            async def publish(self, event: str, payload: Any) -> None:
                published.append(event)

        ex = DecisionExecutor(event_bus=AsyncBus())
        er = await ex.execute(_make_result(DecisionType.FIND_USER))
        assert er.success is True
        assert len(published) == 1

    @pytest.mark.asyncio
    async def test_event_bus_failure_returns_false_no_callback(self):
        """C-2 修复验证：EventBus 失败且无 callback 时应返回 False"""

        class BrokenBus:
            def publish(self, event: str, payload: Any) -> None:
                raise RuntimeError("Bus down")

        ex = DecisionExecutor(event_bus=BrokenBus())
        er = await ex.execute(_make_result(DecisionType.FIND_USER))
        assert er.success is False
        assert "EventBus error" in er.message
        assert "Bus down" in er.message

    @pytest.mark.asyncio
    async def test_event_bus_failure_fallback_to_callback(self):
        """EventBus 失败后应继续尝试 callback，成功则报 True"""
        called: list = []

        class BrokenBus:
            def publish(self, event: str, payload: Any) -> None:
                raise RuntimeError("Bus down")

        def cb(result: PerceptionResult, content: str) -> None:
            called.append(content)

        ex = DecisionExecutor(event_bus=BrokenBus(), notify_callback=cb)
        er = await ex.execute(_make_result(DecisionType.FIND_USER))
        assert er.success is True
        assert "callback" in er.message.lower()
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_no_channel_logs_and_returns_true(self):
        """无任何通知渠道时降级为日志，视为预期行为返回 True"""
        ex = DecisionExecutor()
        er = await ex.execute(_make_result(DecisionType.FIND_USER))
        assert er.success is True
        assert "no notification channel" in er.message.lower()

    @pytest.mark.asyncio
    async def test_callback_failure_returns_false(self):
        def bad_cb(result: PerceptionResult, content: str) -> None:
            raise ValueError("callback exploded")

        ex = DecisionExecutor(notify_callback=bad_cb)
        er = await ex.execute(_make_result(DecisionType.FIND_USER))
        assert er.success is False
        assert "Callback failed" in er.message


# ---------------------------------------------------------------------------
# find_user — json.dumps default=str（H-2 修复验证）
# ---------------------------------------------------------------------------

class TestFindUserNonSerializable:
    @pytest.mark.asyncio
    async def test_non_serializable_data_does_not_crash(self):
        """data 含不可序列化对象时不应崩溃（default=str 覆盖）"""
        import datetime

        result = PerceptionResult(
            decision=DecisionType.FIND_USER,
            reason="test",
            data={"ts": datetime.datetime(2026, 1, 1), "obj": object()},
        )
        ex = DecisionExecutor()
        er = await ex.execute(result)
        assert er.success is True


# ---------------------------------------------------------------------------
# execute 动作路径
# ---------------------------------------------------------------------------

class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_no_action_configured_returns_false(self):
        ex = DecisionExecutor(execute_actions={})
        er = await ex.execute(_make_result(DecisionType.EXECUTE))
        assert er.success is False
        assert "No execute action configured" in er.message

    @pytest.mark.asyncio
    async def test_unknown_action_type_returns_false(self):
        ex = DecisionExecutor(execute_actions={"default": {"type": "ftp"}})
        er = await ex.execute(_make_result(DecisionType.EXECUTE))
        assert er.success is False
        assert "Unknown action type" in er.message


# ---------------------------------------------------------------------------
# call_agent 路径
# ---------------------------------------------------------------------------

class TestCallAgent:
    @pytest.mark.asyncio
    async def test_no_engine_returns_false(self):
        ex = DecisionExecutor()
        er = await ex.execute(_make_result(DecisionType.CALL_AGENT))
        assert er.success is False
        assert "engine" in er.message.lower()

    @pytest.mark.asyncio
    async def test_engine_run_called(self):
        class FakeEngine:
            async def run(self, prompt: str) -> str:
                return f"handled: {prompt[:20]}"

        ex = DecisionExecutor(engine=FakeEngine())
        er = await ex.execute(_make_result(DecisionType.CALL_AGENT))
        assert er.success is True
        assert "handled" in er.message


# ---------------------------------------------------------------------------
# execute_decision 便捷函数
# ---------------------------------------------------------------------------

class TestExecuteDecisionHelper:
    @pytest.mark.asyncio
    async def test_with_executor(self):
        ex = DecisionExecutor()
        result = _make_result(DecisionType.NONE)
        er = await execute_decision(result, executor=ex)
        assert er.success is True

    @pytest.mark.asyncio
    async def test_without_executor_creates_default(self):
        result = _make_result(DecisionType.NONE)
        er = await execute_decision(result)
        assert er.success is True
