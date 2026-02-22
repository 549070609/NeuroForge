"""Tests for migrated legacy runtime API endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from Service.gateway.routes import legacy_runtime as legacy_routes


class StubLegacyRuntimeService:
    """Simple in-memory stub for legacy runtime endpoint tests."""

    def __init__(self) -> None:
        self._agent_counter = 0
        self._session_counter = 0
        self.agents: dict[str, dict[str, Any]] = {}
        self.sessions: dict[str, dict[str, Any]] = {}

    async def create_session(
        self,
        agent_id: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, str]:
        self._session_counter += 1
        session_id = f"session_{self._session_counter}"
        self.sessions[session_id] = {
            "status": "active",
            "messages": [],
        }
        return {"session_id": session_id, "status": "created"}

    async def get_session_detail(self, session_id: str) -> dict[str, Any]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)

        messages = session["messages"]
        return {
            "session_id": session_id,
            "status": session["status"],
            "message_count": len(messages),
            "messages": messages,
        }

    async def send_message(self, session_id: str, message: str) -> dict[str, str]:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)

        session["messages"].append({"role": "user", "content": message})
        content = f"echo:{message}"
        session["messages"].append({"role": "assistant", "content": content})
        return {"role": "assistant", "content": content}

    async def stream_message(self, session_id: str, message: str):
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)

        session["messages"].append({"role": "user", "content": message})
        yield {"type": "stream", "event": {"delta": "partial"}}
        final_text = f"stream:{message}"
        session["messages"].append({"role": "assistant", "content": final_text})
        yield {"type": "complete", "text": final_text}

    async def delete_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def list_sessions(self) -> list[dict[str, Any]]:
        return [
            {
                "id": session_id,
                "title": f"Session {session_id}",
                "model": "stub-model",
                "created_at": "",
                "updated_at": "",
                "message_count": len(data["messages"]),
            }
            for session_id, data in self.sessions.items()
        ]

    def create_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._agent_counter += 1
        agent_id = f"agent-{self._agent_counter}"
        self.agents[agent_id] = {
            "id": agent_id,
            "name": payload["name"],
            "description": payload.get("description"),
            "model": payload.get("model", "stub-model"),
            "is_active": True,
        }
        return self.agents[agent_id]

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        if agent_id not in self.agents:
            raise KeyError(agent_id)
        return self.agents[agent_id]

    def update_agent(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if agent_id not in self.agents:
            raise KeyError(agent_id)

        for field in ("description", "is_active"):
            if field in payload and payload[field] is not None:
                self.agents[agent_id][field] = payload[field]

        return self.agents[agent_id]

    def delete_agent(self, agent_id: str) -> None:
        self.agents.pop(agent_id, None)

    def list_agents(self) -> list[dict[str, Any]]:
        return list(self.agents.values())


@pytest.fixture
def legacy_runtime_stub(client: TestClient):
    """Override legacy runtime dependency with in-memory stub service."""
    stub = StubLegacyRuntimeService()
    client.app.dependency_overrides[legacy_routes.get_legacy_runtime_service] = lambda: stub
    try:
        yield stub
    finally:
        client.app.dependency_overrides.pop(legacy_routes.get_legacy_runtime_service, None)


def test_legacy_agent_crud(client: TestClient, legacy_runtime_stub: StubLegacyRuntimeService):
    """Legacy /api/agents CRUD should be mounted and functional."""
    response = client.post(
        "/api/agents",
        json={
            "name": "demo-agent",
            "description": "demo",
            "system_prompt": "You are demo",
            "allowed_tools": ["*"],
            "model": "claude-sonnet-4-20250514",
        },
    )
    assert response.status_code == 201
    agent_id = response.json()["id"]

    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()["agents"]
    assert any(agent["id"] == agent_id for agent in agents)

    response = client.get(f"/api/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "demo-agent"

    response = client.put(
        f"/api/agents/{agent_id}",
        json={"description": "updated", "is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "updated"
    assert response.json()["is_active"] is False

    response = client.delete(f"/api/agents/{agent_id}")
    assert response.status_code == 204


def test_legacy_session_message_flow(
    client: TestClient,
    legacy_runtime_stub: StubLegacyRuntimeService,
):
    """Legacy /api/sessions message flow should work through Service gateway."""
    response = client.post("/api/sessions", json={})
    assert response.status_code == 201
    session_id = response.json()["session_id"]

    response = client.post(
        f"/api/sessions/{session_id}/messages",
        json={"message": "hello"},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "echo:hello"

    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["message_count"] == 2

    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert any(item["id"] == session_id for item in response.json()["sessions"])

    response = client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 204

    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 404


def test_legacy_websocket_stream(
    client: TestClient,
    legacy_runtime_stub: StubLegacyRuntimeService,
):
    """Legacy websocket endpoint should be mounted at /ws/{session_id}."""
    session_id = client.post("/api/sessions", json={}).json()["session_id"]

    with client.websocket_connect(f"/ws/{session_id}") as websocket:
        websocket.send_json({"message": "ping"})

        start_event = websocket.receive_json()
        assert start_event["type"] == "start"
        assert start_event["session_id"] == session_id

        stream_event = websocket.receive_json()
        assert stream_event["type"] == "stream"

        complete_event = websocket.receive_json()
        assert complete_event["type"] == "complete"
        assert complete_event["text"] == "stream:ping"