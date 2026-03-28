"""Tests for AgentService.execute_agent real execution path."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from Service.core.registry import ServiceRegistry
from Service.services.agent_service import AgentService


def _build_service(tmp_path: Path) -> tuple[AgentService, str]:
    registry = ServiceRegistry()
    service = AgentService(registry)

    agent_id = "demo-agent"
    prompt_path = tmp_path / "system_prompt.md"
    prompt_path.write_text("You are a demo agent.", encoding="utf-8")

    agent = SimpleNamespace(
        namespace="demo",
        metadata={
            "identity": {"name": "demo-agent"},
            "model": {"id": "mock-model", "max_tokens": 128, "temperature": 0.2},
            "limits": {"is_readonly": False, "max_iterations": 5},
            "capabilities": {"tools": ["read"], "denied_tools": []},
        },
        system_prompt_path=prompt_path,
    )

    service._directory = SimpleNamespace(
        get_agent=lambda current_id: agent if current_id == agent_id else None
    )
    service.get_agent = lambda current_id: object() if current_id == agent_id else None
    return service, agent_id


class _Result:
    def __init__(self, success: bool, output: str, error: str | None = None) -> None:
        self.success = success
        self.output = output
        self.error = error


@pytest.mark.asyncio
async def test_execute_agent_success_with_options_override(tmp_path: Path, monkeypatch):
    service, agent_id = _build_service(tmp_path)

    class RecordingExecutor:
        created = []
        init_calls = []
        execute_calls = []

        def __init__(self, workspace_context):
            self.workspace_context = workspace_context
            self.__class__.created.append(workspace_context)

        async def initialize(self, agent_definition, system_prompt, config_overrides):
            self.__class__.init_calls.append(
                {
                    "agent_definition": agent_definition,
                    "system_prompt": system_prompt,
                    "config_overrides": config_overrides,
                }
            )

        async def execute(self, prompt, context):
            self.__class__.execute_calls.append({"prompt": prompt, "context": context})
            return _Result(success=True, output="ok-result")

    from Service.services.proxy import agent_executor as executor_module

    monkeypatch.setattr(executor_module, "AgentExecutor", RecordingExecutor)

    options = {
        "workspace_root": str(tmp_path),
        "namespace": "custom-ns",
        "is_readonly": True,
        "max_iterations": 3,
        "model_id": "override-model",
    }
    result = await service.execute_agent(
        agent_id=agent_id,
        task="run task",
        context={"k": "v"},
        options=options,
    )

    assert result["status"] == "completed"
    assert result["result"] == "ok-result"
    assert result["error"] is None
    assert result["plan_id"] is None
    assert result["started_at"].endswith("Z")
    assert result["completed_at"].endswith("Z")

    workspace_context = RecordingExecutor.created[0]
    assert workspace_context.config.root_path == str(tmp_path)
    assert workspace_context.config.namespace == "custom-ns"
    assert workspace_context.config.is_readonly is True

    assert RecordingExecutor.init_calls[0]["config_overrides"]["max_iterations"] == 3
    assert RecordingExecutor.execute_calls[0]["context"] == {"k": "v"}


@pytest.mark.asyncio
async def test_execute_agent_not_found_returns_error(tmp_path: Path):
    registry = ServiceRegistry()
    service = AgentService(registry)
    service.get_agent = lambda agent_id: None

    result = await service.execute_agent(agent_id="missing", task="task")

    assert result["status"] == "error"
    assert "not found" in result["error"].lower()
    assert result["result"] is None
    assert result["plan_id"] is None
    assert result["started_at"].endswith("Z")
    assert result["completed_at"].endswith("Z")


@pytest.mark.asyncio
async def test_execute_agent_executor_exception_returns_error(tmp_path: Path, monkeypatch):
    service, agent_id = _build_service(tmp_path)

    class FailingExecutor:
        def __init__(self, workspace_context):
            self.workspace_context = workspace_context

        async def initialize(self, agent_definition, system_prompt, config_overrides):
            raise RuntimeError("executor failed")

        async def execute(self, prompt, context):
            return _Result(success=True, output="unused")

    from Service.services.proxy import agent_executor as executor_module

    monkeypatch.setattr(executor_module, "AgentExecutor", FailingExecutor)

    result = await service.execute_agent(agent_id=agent_id, task="task")

    assert result["status"] == "error"
    assert "executor failed" in result["error"]
    assert result["result"] is None
    assert result["plan_id"] is None
