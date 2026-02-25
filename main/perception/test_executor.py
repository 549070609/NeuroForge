"""
Epic 4 决策执行器测试

运行: cd Agent-Learn/main && python -m perception.test_executor
"""

import asyncio
import sys
from pathlib import Path

# 兼容从 Agent-Learn/main 或 perception 目录运行
_main = Path(__file__).resolve().parent.parent
if str(_main) not in sys.path:
    sys.path.insert(0, str(_main))

try:
    from perception.perception import perceive, PerceptionResult, DecisionType
    from perception.executor import DecisionExecutor, execute_decision, ExecutionResult
except ImportError:
    from perception import perceive, PerceptionResult, DecisionType
    from executor import DecisionExecutor, execute_decision, ExecutionResult


async def test_executor_find_user():
    """Story 4.1: find_user 通知路径"""
    notified = []

    async def mock_notify(result, content):
        notified.append({"result": result, "content": content})

    r = PerceptionResult(DecisionType.FIND_USER, "Test alert", {"message": "error"})
    ex = DecisionExecutor(notify_callback=mock_notify)
    res = await ex.execute(r)
    assert res.success
    assert len(notified) == 1
    assert "Test alert" in notified[0]["content"]
    print("[OK] find_user (callback) passed")


async def test_executor_find_user_log_fallback():
    """find_user 无通道时 fallback 到 log"""
    r = PerceptionResult(DecisionType.FIND_USER, "Alert", {"x": 1})
    ex = DecisionExecutor()
    res = await ex.execute(r)
    assert res.success
    assert "log" in res.message.lower() or "no" in res.message.lower()
    print("[OK] find_user (log fallback) passed")


async def test_executor_execute_shell():
    """Story 4.2: execute shell 动作"""
    r = PerceptionResult(DecisionType.EXECUTE, "Trigger", {"action_key": "default"})
    ex = DecisionExecutor(
        execute_actions={"default": {"type": "shell", "cmd": "echo ok"}},
    )
    res = await ex.execute(r)
    assert res.success
    assert "ok" in res.message
    print("[OK] execute (shell) passed")


async def test_executor_none():
    """decision=none 不执行"""
    r = PerceptionResult(DecisionType.NONE, "No action", {})
    ex = DecisionExecutor(engine=object())
    res = await ex.execute(r)
    assert res.success
    assert "no action" in res.message.lower() or "none" in res.message.lower()
    print("[OK] none passed")


async def test_executor_call_agent_mock():
    """Story 4.3: call_agent 委派（mock engine）"""
    results = []

    class MockEngine:
        async def run(self, prompt):
            results.append(prompt)
            return "Handled"

    r = PerceptionResult(DecisionType.CALL_AGENT, "Need help", {"detail": "x"})
    ex = DecisionExecutor(engine=MockEngine())
    res = await ex.execute(r)
    assert res.success
    assert len(results) == 1
    assert "Need help" in results[0]
    assert "detail" in results[0] or "x" in results[0]
    print("[OK] call_agent (mock engine) passed")


async def main():
    print("Epic 4 Executor tests...\n")
    await test_executor_find_user()
    await test_executor_find_user_log_fallback()
    await test_executor_execute_shell()
    await test_executor_none()
    await test_executor_call_agent_mock()
    print("\n[PASS] All executor tests passed")


if __name__ == "__main__":
    asyncio.run(main())
