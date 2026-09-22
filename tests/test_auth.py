"""
tests/test_auth.py — Auth API tests (register, OTP verify, login, /me).
"""

import pytest
from unittest.mock import patch
from app import create_app
from config import Config
from models.database import db as _db


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key-for-pixhare"
    DEBUG = False
    WTF_CSRF_ENABLED = False


@pytest.fixture(scope="module")
def app():
    application = create_app(TestConfig)
    with application.app_context():
        yield application


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def registered_photographer(client):
    """Register a photographer and return their email + OTP."""
    with patch("utils.email_sender._send", return_value=True):
        resp = client.post("/api/auth/register", json={
            "name":        "Test Photographer",
            "studio_name": "Test Studio",
            "email":       "test@pixhare.io",
            "password":    "TestPass123",
        })
    assert resp.status_code == 201
    return {"email": "test@pixhare.io", "password": "TestPass123"}


# ── Register ──────────────────────────────────────────────────────────

def test_register_success(client):
    with patch("utils.email_sender._send", return_value=True):
        resp = client.post("/api/auth/register", json={
            "name":        "New User",
            "studio_name": "My Studio",
            "email":       "newuser@pixhare.io",
            "password":    "MyPass456",
        })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert "OTP" in data["message"] or "otp" in data["message"].lower()


def test_register_duplicate_email(client):
    with patch("utils.email_sender._send", return_value=True):
        client.post("/api/auth/register", json={
            "name": "Dup", "studio_name": "S", "email": "dup@pixhare.io", "password": "Pass1234",
        })
        resp = client.post("/api/auth/register", json={
            "name": "Dup2", "studio_name": "S2", "email": "dup@pixhare.io", "password": "Pass1234",
        })
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "CONFLICT"


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"email": "x@y.com"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_register_weak_password(client):
    resp = client.post("/api/auth/register", json={
        "name": "A", "studio_name": "B", "email": "weak@pixhare.io", "password": "abc",
    })
    assert resp.status_code == 400


# ── OTP Verify ────────────────────────────────────────────────────────

def test_verify_otp_wrong(client, registered_photographer):
    resp = client.post("/api/auth/verify-otp", json={
        "email": registered_photographer["email"],
        "otp":   "000000",
    })
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "INVALID_OTP"


def test_verify_otp_missing_fields(client):
    resp = client.post("/api/auth/verify-otp", json={"email": "x@y.com"})
    assert resp.status_code == 400


# ── Login ─────────────────────────────────────────────────────────────

def test_login_unverified_account(client, registered_photographer):
    """Login should fail if OTP not yet verified."""
    resp = client.post("/api/auth/login", json={
        "email":    registered_photographer["email"],
        "password": registered_photographer["password"],
    })
    # Should fail: not verified yet
    assert resp.status_code in (401, 403)


def test_login_wrong_password(client, registered_photographer):
    resp = client.post("/api/auth/login", json={
        "email":    registered_photographer["email"],
        "password": "WrongPassword999",
    })
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"email": "x@y.com"})
    assert resp.status_code == 400


# ── /me endpoint ──────────────────────────────────────────────────────

def test_me_without_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
