"""Tests for tool endpoints."""

import pytest
from fastapi.testclient import TestClient


def test_list_tools(client: TestClient):
    """Test tools listing."""
    response = client.get("/api/v1/tools")
    assert response.status_code == 200
    tools = response.json()
    assert isinstance(tools, list)
    assert len(tools) > 0

    # Check tool structure
    tool = tools[0]
    assert "name" in tool
    assert "description" in tool
    assert "parameters" in tool


def test_execute_tool_not_implemented(client: TestClient):
    """Test tool execution (not yet implemented)."""
    response = client.post(
        "/api/v1/tools/bash/execute",
        json={"parameters": {"command": "echo test"}},
    )
    assert response.status_code == 501
