"""
api/health.py — Health check endpoint.

GET /api/health

Returns application status, version, and service availability.
Used by monitoring tools and as a startup verification step.
"""

import platform
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from utils.logger import get_logger

log = get_logger(__name__)

health_bp = Blueprint("health", __name__)

_START_TIME = datetime.now(timezone.utc)


@health_bp.route("/api/health", methods=["GET"])
def health_check():
    """
    Return application health status.

    Response:
        200 OK — always (application is running).
        {
            "success": true,
            "data": {
                "status": "ok",
                "uptime_seconds": 42,
                "python": "3.11.0",
                "timestamp": "2025-01-01T00:00:00Z"
            }
        }
    """
    uptime = (datetime.now(timezone.utc) - _START_TIME).total_seconds()

    log.debug("Health check requested")

    return jsonify({
        "success": True,
        "message": "Pixhare is running.",
        "data": {
            "status": "ok",
            "uptime_seconds": round(uptime, 1),
            "python_version": platform.python_version(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }), 200
