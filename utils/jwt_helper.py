"""
utils/jwt_helper.py — JWT helpers for Pixhare.

Covers:
  - generate_jwt(photographer_id) → signed token string
  - decode_jwt(token) → payload dict
  - jwt_required decorator → protects Flask routes
"""

import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, g, jsonify, request

from utils.logger import get_logger

log = get_logger(__name__)

_ALGORITHM = "HS256"
_TOKEN_LIFETIME_HOURS = 72   # 3 days


# ─────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────

def generate_jwt(photographer_id: int) -> str:
    """
    Create a signed JWT for the given photographer.

    Args:
        photographer_id: PK of the Photographer row.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(photographer_id),
        "iat": now,
        "exp": now + timedelta(hours=_TOKEN_LIFETIME_HOURS),
    }
    secret = current_app.config["SECRET_KEY"]
    token = jwt.encode(payload, secret, algorithm=_ALGORITHM)
    log.debug("JWT issued for photographer_id=%s", photographer_id)
    return token


def decode_jwt(token: str) -> dict:
    """
    Decode and verify a JWT.

    Args:
        token: Raw JWT string.

    Returns:
        Payload dict (contains 'sub' = photographer_id).

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is invalid.
    """
    secret = current_app.config["SECRET_KEY"]
    payload = jwt.decode(token, secret, algorithms=[_ALGORITHM], options={"verify_sub": False})
    if "sub" in payload:
        try:
            payload["sub"] = int(payload["sub"])
        except (ValueError, TypeError):
            pass
    return payload


# ─────────────────────────────────────────────────────────────
# Route decorator
# ─────────────────────────────────────────────────────────────

def jwt_required(fn):
    """
    Flask route decorator that enforces a valid Bearer JWT.

    On success:
        Sets g.photographer_id to the authenticated user's PK.
    On failure:
        Returns JSON 401 response.

    Usage:
        @app.route("/api/protected")
        @jwt_required
        def protected():
            return jsonify({"id": g.photographer_id})
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "success": False,
                "error": {"code": "UNAUTHORIZED", "message": "Bearer token required."},
            }), 401

        token = auth_header[len("Bearer "):]
        try:
            payload = decode_jwt(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": {"code": "TOKEN_EXPIRED", "message": "Token has expired. Please log in again."},
            }), 401
        except jwt.InvalidTokenError as exc:
            log.warning("Invalid JWT: %s", exc)
            return jsonify({
                "success": False,
                "error": {"code": "INVALID_TOKEN", "message": "Invalid or malformed token."},
            }), 401

        g.photographer_id = payload["sub"]
        return fn(*args, **kwargs)

    return wrapper
