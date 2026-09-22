"""
tests/test_api.py — Phase 1: API health endpoint tests.

These tests verify:
  1. The Flask app can be created successfully.
  2. GET /api/health returns 200.
  3. Response JSON has the expected structure.
  4. No external services (DB, LLM, SMTP) are required.
"""

import pytest
from app import create_app
from config import Config


class TestConfig(Config):
    """Test configuration — uses in-memory SQLite, no real .env needed."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"
    DEBUG = False


@pytest.fixture(scope="module")
def client():
    """Create a test Flask client using an in-memory database."""
    app = create_app(TestConfig)
    with app.test_client() as c:
        yield c


# ── Health endpoint ───────────────────────────────────────────────────

def test_health_returns_200(client):
    """Health endpoint must return HTTP 200."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_response_structure(client):
    """Health response must include success=True and required fields."""
    response = client.get("/api/health")
    data = response.get_json()

    assert data["success"] is True
    assert "message" in data
    assert "data" in data
    assert data["data"]["status"] == "ok"
    assert "uptime_seconds" in data["data"]
    assert "python_version" in data["data"]
    assert "timestamp" in data["data"]


def test_health_content_type(client):
    """Health endpoint must return JSON content type."""
    response = client.get("/api/health")
    assert "application/json" in response.content_type


# ── Error handler tests ───────────────────────────────────────────────

def test_404_returns_json(client):
    """Unknown routes must return JSON 404, not HTML."""
    response = client.get("/api/nonexistent-route-xyz")
    assert response.status_code == 404
    data = response.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
