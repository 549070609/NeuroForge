"""Gateway regression tests for /agents/{id}/execute."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Service.gateway.routes import agents as agents_route


def test_execute_route_response_fields_and_time_format(monkeypatch):
    class FakeAgentService:
        def get_agent(self, agent_id: str):
            return object()

        async def execute_agent(self, agent_id: str, task: str, context=None, options=None):
            return {
                "agent_id": agent_id,
                "status": "completed",
                "result": "done",
                "error": None,
                "plan_id": None,
                "started_at": "2026-01-01T00:00:00Z",
                "completed_at": "2026-01-01T00:00:01Z",
            }

    monkeypatch.setattr(agents_route, "get_agent_service", lambda: FakeAgentService())

    app = FastAPI()
    app.include_router(agents_route.router)
    client = TestClient(app)

    response = client.post(
        "/agents/demo-agent/execute",
        json={"task": "hello", "context": {"a": 1}, "options": {"max_iterations": 2}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_id"] == "demo-agent"
    assert payload["status"] == "completed"
    assert payload["result"] == "done"
    assert payload["error"] is None
    assert payload["plan_id"] is None

    datetime.fromisoformat(payload["started_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(payload["completed_at"].replace("Z", "+00:00"))
