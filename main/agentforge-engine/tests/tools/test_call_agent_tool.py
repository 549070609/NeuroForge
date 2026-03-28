"""Tests for CallAgentTool execution flow."""

import asyncio

import pytest

from pyagentforge.plugins.tools.call_agent import CallAgentTool


class TaskRecord:
    def __init__(self, task_id: str):
        self.id = task_id


class StubBackgroundManager:
    def __init__(self):
        self.calls = []

    async def launch(self, **kwargs):
        self.calls.append(kwargs)
        return TaskRecord("bg-123")


class SlowEngine:
    async def run(self, prompt: str) -> str:
        await asyncio.sleep(0.05)
        return "slow-result"


class FastEngine:
    async def run(self, prompt: str) -> str:
        return f"echo:{prompt}"


@pytest.mark.asyncio
async def test_call_agent_tool_times_out_waiting_for_completion():
    tool = CallAgentTool()

    result = await tool.execute(
        agent_type="explore",
        prompt="hello",
        timeout=0.01,
        engine_factory=lambda agent_type: SlowEngine(),
    )

    assert "timed out" in result


@pytest.mark.asyncio
async def test_call_agent_tool_uses_background_manager_for_detached_execution():
    tool = CallAgentTool()
    background_manager = StubBackgroundManager()

    result = await tool.execute(
        agent_type="explore",
        prompt="hello",
        wait_for_completion=False,
        background_manager=background_manager,
        session_id="session-1",
    )

    assert "bg-123" in result
    assert background_manager.calls[0]["agent_type"] == "explore"
    assert background_manager.calls[0]["metadata"]["mode"] == "detached"


@pytest.mark.asyncio
async def test_call_agent_tool_returns_result_when_run_completes():
    tool = CallAgentTool()

    result = await tool.execute(
        agent_type="explore",
        prompt="hello",
        timeout=1,
        engine_factory=lambda agent_type: FastEngine(),
    )

    assert "completed successfully" in result
    assert "echo:hello" in result
