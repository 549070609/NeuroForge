from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Service.gateway.routes import proxy as proxy_route


def _workflow_payload(workflow_id: str = "wf-1") -> dict:
    return {
        "id": workflow_id,
        "session_id": "sess-1",
        "task": "demo-task",
        "workflow_type": "graph",
        "status": "created",
        "thread_id": f"thread-{workflow_id}",
        "result": None,
        "error": None,
        "trace_id": None,
        "steps": [],
        "elapsed_ms": 0,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "metadata": {},
    }


def test_execute_route_returns_trace_fields(monkeypatch):
    class FakeProxyService:
        async def execute(self, **kwargs):
            trace_id = kwargs.get("trace_id")
            return SimpleNamespace(
                success=True,
                output="ok",
                error=None,
                iterations=1,
                metadata={"trace_id": trace_id or "trace-1", "span_id": "span-1"},
            )

    monkeypatch.setattr(proxy_route, "get_proxy_service", lambda: FakeProxyService())

    app = FastAPI()
    app.include_router(proxy_route.router)
    client = TestClient(app)

    response = client.post(
        "/proxy/execute",
        json={"session_id": "sess-1", "prompt": "hello", "trace_id": "trace-upstream"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["trace_id"] == "trace-upstream"
    assert payload["span_id"] == "span-1"


def test_workflow_routes_and_trace_route(monkeypatch):
    class FakeProxyService:
        async def create_workflow(self, **kwargs):
            payload = _workflow_payload("wf-create")
            payload["task"] = kwargs["task"]
            payload["workflow_type"] = kwargs["workflow_type"]
            return payload

        async def get_workflow(self, workflow_id: str):
            payload = _workflow_payload(workflow_id)
            payload["status"] = "completed"
            payload["result"] = "done"
            payload["trace_id"] = "trace-2"
            return payload

        async def start_workflow(self, workflow_id: str, trace_id: str | None = None):
            payload = _workflow_payload(workflow_id)
            payload["status"] = "completed"
            payload["result"] = "done"
            payload["trace_id"] = trace_id or "trace-2"
            return payload

        async def pause_workflow(self, workflow_id: str):
            payload = _workflow_payload(workflow_id)
            payload["status"] = "paused"
            return payload

        async def resume_workflow(self, workflow_id: str, trace_id: str | None = None):
            payload = _workflow_payload(workflow_id)
            payload["status"] = "completed"
            payload["result"] = "done"
            payload["trace_id"] = trace_id or "trace-3"
            return payload

        async def get_trace(self, trace_id: str):
            return {
                "trace_id": trace_id,
                "scope": "workflow",
                "session_id": "sess-1",
                "workflow_id": "wf-1",
                "summary": {"total_spans": 3},
                "spans": [{"span_id": "span-1"}],
                "updated_at": "2026-01-01T00:00:10Z",
            }

    monkeypatch.setattr(proxy_route, "get_proxy_service", lambda: FakeProxyService())

    app = FastAPI()
    app.include_router(proxy_route.router)
    client = TestClient(app)

    created = client.post(
        "/proxy/workflows",
        json={"session_id": "sess-1", "task": "ship it", "workflow_type": "graph"},
    )
    assert created.status_code == 201
    assert created.json()["id"] == "wf-create"

    paused = client.post("/proxy/workflows/wf-create/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post("/proxy/workflows/wf-create/resume", params={"trace_id": "trace-resume"})
    assert resumed.status_code == 200
    assert resumed.json()["trace_id"] == "trace-resume"

    trace = client.get("/proxy/traces/trace-resume")
    assert trace.status_code == 200
    assert trace.json()["trace_id"] == "trace-resume"
