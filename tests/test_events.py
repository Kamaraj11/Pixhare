"""
tests/test_events.py — Event API tests (create, list, get, delete, QR).

Uses a verified photographer JWT obtained via a helper fixture.
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app import create_app
from config import Config
from models.database import db
from models.user import Photographer
from werkzeug.security import generate_password_hash


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "event-test-secret"
    DEBUG = False


@pytest.fixture(scope="module")
def app():
    application = create_app(TestConfig)
    with application.app_context():
        yield application


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def auth_headers(app):
    """Create a verified photographer and return Bearer token headers."""
    with app.app_context():
        from utils.security import generate_token
        p = Photographer(
            name="Event Tester",
            studio_name="Test Studio",
            email="events@pixhare.io",
            password=generate_password_hash("Pass1234"),
            is_verified=True,
            scan_token=generate_token(),
        )
        db.session.add(p)
        db.session.commit()
        pid = p.id

    # Generate JWT manually
    now = datetime.now(timezone.utc)
    token = pyjwt.encode(
        {"sub": pid, "iat": now, "exp": now + timedelta(hours=1)},
        "event-test-secret",
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


# ── Create Event ──────────────────────────────────────────────────────

def test_create_event_success(client, auth_headers):
    resp = client.post("/api/events", json={
        "name":  "Test Wedding 2026",
        "date":  "2026-12-25",
        "venue": "Grand Hall",
    }, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["event"]["name"] == "Test Wedding 2026"


def test_create_event_missing_name(client, auth_headers):
    resp = client.post("/api/events", json={"date": "2026-01-01"}, headers=auth_headers)
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_event_missing_date(client, auth_headers):
    resp = client.post("/api/events", json={"name": "No Date Event"}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_duplicate_event(client, auth_headers):
    client.post("/api/events", json={"name": "Dup Event", "date": "2026-01-01"}, headers=auth_headers)
    resp = client.post("/api/events", json={"name": "Dup Event", "date": "2026-01-01"}, headers=auth_headers)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"


def test_create_event_no_auth(client):
    resp = client.post("/api/events", json={"name": "Unauth Event", "date": "2026-01-01"})
    assert resp.status_code == 401


# ── List Events ───────────────────────────────────────────────────────

def test_list_events(client, auth_headers):
    resp = client.get("/api/events", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert isinstance(data["events"], list)
    assert data["count"] >= 1


def test_list_events_no_auth(client):
    resp = client.get("/api/events")
    assert resp.status_code == 401


# ── Get Event ─────────────────────────────────────────────────────────

def test_get_event_not_found(client, auth_headers):
    resp = client.get("/api/events/99999", headers=auth_headers)
    assert resp.status_code == 404


def test_get_event_success(client, auth_headers):
    # List events, grab the first id
    events = client.get("/api/events", headers=auth_headers).get_json()["events"]
    if events:
        eid = events[0]["id"]
        resp = client.get(f"/api/events/{eid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


# ── Delete Event ──────────────────────────────────────────────────────

def test_delete_nonexistent_event(client, auth_headers):
    resp = client.delete("/api/events/99999", headers=auth_headers)
    assert resp.status_code == 404
