from __future__ import annotations

from typing import Any

import pytest

from Service.core.registry import ServiceRegistry
from Service.persistence import MemoryStore
from Service.services.proxy.agent_executor import ExecutionResult
from Service.services.proxy.agent_proxy_service import AgentProxyService
from Service.services.proxy.session_manager import SessionManager
from Service.services.proxy.workspace_manager import WorkspaceManager


class FakeExecutor:
    def __init__(self) -> None:
        self._initialized = True
        self._collector = None

    def set_trace_collector(self, collector) -> None:
        self._collector = collector

    async def execute(self, prompt: str, _context: dict[str, Any] | None = None) -> ExecutionResult:
        return ExecutionResult(success=True, output=f"echo:{prompt}", metadata={})

    async def execute_stream(self, prompt: str, _context: dict[str, Any] | None = None):
        yield {"type": "complete", "text": f"stream:{prompt}"}

    def create_engine_factory(self):
        return object()

    def reset(self) -> None:
        return None


@pytest.mark.asyncio
async def test_proxy_execute_persists_trace(monkeypatch, tmp_path) -> None:
    registry = ServiceRegistry()
    service = AgentProxyService(registry)
    service._workspace_manager = WorkspaceManager()
    service._store = MemoryStore()
    service._session_manager = SessionManager(store=service._store, session_ttl=3600, max_sessions=20)
    service._session_ttl = 3600

    async def fake_create_executor(*args, **kwargs):
        return FakeExecutor()

    monkeypatch.setattr(service, "_create_executor", fake_create_executor)

    workspace = service.create_workspace("ws-1", str(tmp_path), namespace="ns")
    assert workspace["workspace_id"] == "ws-1"

    session = await service.create_session("ws-1", "agent-1")
    result = await service.execute(session.session_id, "hello", trace_id="trace-fixed")

    assert result.success is True
    assert result.metadata["trace_id"] == "trace-fixed"
    assert result.metadata["span_id"]

    trace = await service.get_trace("trace-fixed")
    assert trace is not None
    assert trace["scope"] == "execute"
    assert trace["session_id"] == session.session_id


@pytest.mark.asyncio
async def test_workflow_lifecycle_create_pause_resume_start(monkeypatch, tmp_path) -> None:
    registry = ServiceRegistry()
    service = AgentProxyService(registry)
    service._workspace_manager = WorkspaceManager()
    service._store = MemoryStore()
    service._session_manager = SessionManager(store=service._store, session_ttl=3600, max_sessions=20)
    service._session_ttl = 3600
    service._workflow_checkpointer = None

    async def fake_create_executor(*args, **kwargs):
        return FakeExecutor()

    async def fake_execute_workflow_runtime(workflow, session, *, trace_id):
        return {
            "result": f"done:{workflow['task']}",
            "steps": [{"node": "analysis", "elapsed_ms": 1}],
            "elapsed_ms": 10,
            "trace_id": trace_id or "trace-generated",
        }

    monkeypatch.setattr(service, "_create_executor", fake_create_executor)
    monkeypatch.setattr(service, "_execute_workflow_runtime", fake_execute_workflow_runtime)

    service.create_workspace("ws-1", str(tmp_path), namespace="ns")
    session = await service.create_session("ws-1", "agent-1")

    workflow = await service.create_workflow(session.session_id, "task-a", workflow_type="graph")
    assert workflow["status"] == "created"

    paused = await service.pause_workflow(workflow["id"])
    assert paused["status"] == "paused"

    resumed = await service.resume_workflow(workflow["id"], trace_id="trace-resume")
    assert resumed["status"] == "completed"
    assert resumed["result"] == "done:task-a"
    assert resumed["trace_id"] == "trace-resume"

    workflow2 = await service.create_workflow(session.session_id, "task-b", workflow_type="team")
    started = await service.start_workflow(workflow2["id"], trace_id="trace-start")
    assert started["status"] == "completed"
    assert started["trace_id"] == "trace-start"
