"""Tests for SpawnSubagentTool runtime execution."""

import json
from pathlib import Path
import sys

import pytest


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from main.Agent import get_tool_registry


@pytest.mark.asyncio
async def test_spawn_subagent_uses_injected_executor():
    tool = get_tool_registry(force_new=True).get("spawn_subagent")
    captured = {}

    async def executor(**kwargs):
        captured.update(kwargs)
        return "subagent-ok"

    result = await tool.execute(
        subagent_id="builder-agent",
        task="build agent",
        inputs={"agent_id": "demo"},
        context={"request_id": "req-1"},
        subagent_executor=executor,
    )

    payload = json.loads(result)

    assert payload["success"] is True
    assert payload["status"] == "completed"
    assert payload["output"] == "subagent-ok"
    assert captured["agent"].agent_id == "builder-agent"
    assert "build agent" in captured["prompt"]
    assert '"agent_id": "demo"' in captured["prompt"]


@pytest.mark.asyncio
async def test_spawn_subagent_fails_without_runtime_executor():
    tool = get_tool_registry(force_new=True).get("spawn_subagent")

    result = await tool.execute(
        subagent_id="builder-agent",
        task="build agent",
    )

    payload = json.loads(result)

    assert payload["success"] is False
    assert payload["status"] == "failed"
    assert "运行时不可用" in payload["error"]
