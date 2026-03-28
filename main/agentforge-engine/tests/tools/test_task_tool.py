"""Tests for TaskTool permission handling."""

from unittest.mock import patch

import pytest

from pyagentforge.tools.base import BaseTool
from pyagentforge.tools.builtin.task import TaskTool
from pyagentforge.tools.registry import ToolRegistry


class DummyProvider:
    """Minimal provider stub for TaskTool tests."""

    model = "dummy-model"


class AllowedTool(BaseTool):
    name = "allowed"
    description = "allowed tool"

    async def execute(self, **kwargs):
        return "ok"


class SecretTool(BaseTool):
    name = "secret"
    description = "secret tool"

    async def execute(self, **kwargs):
        return "secret"


@pytest.mark.asyncio
async def test_task_tool_keeps_filtered_tools_when_replacing_task():
    registry = ToolRegistry()
    registry.register(AllowedTool())
    registry.register(SecretTool())

    task_tool = TaskTool(provider=DummyProvider(), tool_registry=registry)
    registry.register(task_tool)

    captured = {}

    class FakeEngine:
        def __init__(self, provider, tool_registry, config, context, ask_callback):
            captured["tool_names"] = sorted(tool.name for tool in tool_registry)

        async def run(self, prompt: str) -> str:
            return "done"

    with patch(
        "pyagentforge.tools.builtin.task.get_agent_type_config",
        return_value={"system_prompt": "test", "tools": ["allowed", "Task"]},
    ), patch("pyagentforge.tools.builtin.task.AgentEngine", FakeEngine):
        result = await task_tool.execute("desc", "prompt", subagent_type="explore")

    assert "done" in result
    assert captured["tool_names"] == ["Task", "allowed"]
