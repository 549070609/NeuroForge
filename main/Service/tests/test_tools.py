"""Tests for tool endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_list_tools(client: TestClient):
    """Test tools listing returns core tools from ToolRegistry."""
    response = client.get("/api/v1/tools")
    assert response.status_code == 200
    tools = response.json()
    assert isinstance(tools, list)
    assert len(tools) >= 6

    tool_names = {t["name"] for t in tools}
    for expected in ("bash", "read", "write", "edit", "glob", "grep"):
        assert expected in tool_names, f"Missing core tool: {expected}"

    tool = tools[0]
    assert "name" in tool
    assert "description" in tool
    assert "parameters" in tool


def test_execute_tool_not_found(client: TestClient):
    """Test executing a non-existent tool returns 404."""
    response = client.post(
        "/api/v1/tools/nonexistent_tool/execute",
        json={"tool_name": "nonexistent_tool", "parameters": {}},
    )
    assert response.status_code == 404
