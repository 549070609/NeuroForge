"""Tests for health and basic endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


def test_root_endpoint(client: TestClient):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data


def test_openapi_docs(client: TestClient):
    """Test OpenAPI docs endpoint."""
    response = client.get("/docs")
    assert response.status_code == 200
