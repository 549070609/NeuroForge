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


def test_governance_routes(monkeypatch):
    class FakeProxyService:
        async def list_approvals(self, status: str | None = None):
            if status == "approved":
                return []
            return [
                {
                    "approval_id": "apr-1",
                    "kind": "execute",
                    "reason": "needs review",
                    "payload_hash": "hash",
                    "payload": {"prompt": "x"},
                    "status": "pending",
                    "created_at": "2026-01-01T00:00:00Z",
                    "expires_at": 1893456000,
                    "resolved_at": None,
                    "reviewer": None,
                    "comment": None,
                }
            ]

        async def get_approval(self, approval_id: str):
            if approval_id != "apr-1":
                return None
            return {
                "approval_id": approval_id,
                "kind": "execute",
                "reason": "needs review",
                "payload_hash": "hash",
                "payload": {"prompt": "x"},
                "status": "pending",
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": 1893456000,
                "resolved_at": None,
                "reviewer": None,
                "comment": None,
            }

        async def approve_approval(self, approval_id: str, *, reviewer: str, comment: str | None = None):
            return {
                "approval_id": approval_id,
                "kind": "execute",
                "reason": "needs review",
                "payload_hash": "hash",
                "payload": {"prompt": "x"},
                "status": "approved",
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": 1893456000,
                "resolved_at": "2026-01-01T00:00:10Z",
                "reviewer": reviewer,
                "comment": comment,
            }

        async def reject_approval(self, approval_id: str, *, reviewer: str, comment: str | None = None):
            return {
                "approval_id": approval_id,
                "kind": "execute",
                "reason": "needs review",
                "payload_hash": "hash",
                "payload": {"prompt": "x"},
                "status": "rejected",
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": 1893456000,
                "resolved_at": "2026-01-01T00:00:10Z",
                "reviewer": reviewer,
                "comment": comment,
            }

        async def get_slo_dashboard(self):
            return {
                "timestamp": "2026-01-01T00:00:00Z",
                "targets": {"success_rate": 0.995, "p95_latency_ms": 30000},
                "by_scope": {"execute:agent-1": {"total": 10}},
                "alerts": [],
            }

        def parse_handoff_payload(self, payload: str):
            if not payload:
                raise ValueError("handoff payload is empty")
            return {
                "version": "1.0",
                "source_agent": "a",
                "target_agent": "b",
                "task": "t",
                "context": {},
                "artifacts": [],
                "error": None,
                "trace_id": None,
                "timestamp": "2026-01-01T00:00:00Z",
            }

    monkeypatch.setattr(proxy_route, "get_proxy_service", lambda: FakeProxyService())

    app = FastAPI()
    app.include_router(proxy_route.router)
    client = TestClient(app)

    listed = client.get("/proxy/approvals")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    found = client.get("/proxy/approvals/apr-1")
    assert found.status_code == 200
    assert found.json()["approval_id"] == "apr-1"

    approved = client.post(
        "/proxy/approvals/apr-1/approve",
        json={"reviewer": "qa", "comment": "ok"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    rejected = client.post(
        "/proxy/approvals/apr-1/reject",
        json={"reviewer": "qa", "comment": "no"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    slo = client.get("/proxy/slo")
    assert slo.status_code == 200
    assert "by_scope" in slo.json()

    handoff = client.post("/proxy/handoff/parse", json={"payload": "{\"source_agent\":\"a\",\"target_agent\":\"b\"}"})
    assert handoff.status_code == 200
    assert handoff.json()["envelope"]["source_agent"] == "a"
