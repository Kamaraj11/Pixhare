"""
api/event_routes.py — Event management endpoints.

Endpoints:
    POST   /api/events                 — Create event (JWT required)
    GET    /api/events                 — List photographer's events (JWT required)
    GET    /api/events/<event_id>      — Get single event (JWT required)
    DELETE /api/events/<event_id>      — Delete event (JWT required)
    GET    /api/events/<event_id>/qr   — Return QR image (JWT required)
"""

from pathlib import Path

from flask import Blueprint, g, jsonify, request, send_file

from config import Config
from models.database import db
from models.event import Event
from models.user import Photographer
from utils.jwt_helper import jwt_required
from utils.logger import get_logger
from utils.qr_generator import generate_qr_png
from utils.validators import validate_event_name

log = get_logger(__name__)

event_bp = Blueprint("events", __name__, url_prefix="/api/events")


# ─────────────────────────────────────────────────────────────
# POST /api/events
# ─────────────────────────────────────────────────────────────
@event_bp.route("", methods=["POST"])
@jwt_required
def create_event():
    """
    Create a new event under the authenticated photographer.

    Request JSON:
        name        (str, required, unique)
        date        (str, required, YYYY-MM-DD)
        venue       (str, optional)
        event_time  (str, optional, HH:MM)
        description (str, optional)

    Response 201:
        { success: true, event: { id, name, date, venue, qr_url, scan_token, ... } }
    """
    data = request.get_json(silent=True) or {}

    name        = (data.get("name") or "").strip()
    date        = (data.get("date") or "").strip()
    venue       = (data.get("venue") or "").strip()
    event_time  = (data.get("event_time") or "").strip()
    description = (data.get("description") or "").strip()

    # ── Validation ────────────────────────────────────────────
    errors = {}
    ok, err = validate_event_name(name)
    if not ok:
        errors["name"] = err
    if not date:
        errors["date"] = "Event date is required (YYYY-MM-DD)."

    if errors:
        return jsonify({"success": False, "error": {"code": "VALIDATION_ERROR", "details": errors}}), 400

    # ── Duplicate check ───────────────────────────────────────
    if Event.query.filter_by(name=name).first():
        return jsonify({
            "success": False,
            "error": {"code": "CONFLICT", "message": f"An event named '{name}' already exists."},
        }), 409

    # ── Get photographer scan_token ───────────────────────────
    photographer = Photographer.query.get(g.photographer_id)
    if not photographer:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Photographer not found."}}), 404

    # ── Create event ──────────────────────────────────────────
    event = Event(
        name            = name,
        date            = date,
        venue           = venue or None,
        event_time      = event_time or None,
        description     = description or None,
        photographer_id = g.photographer_id,
    )
    db.session.add(event)
    db.session.flush()   # get event.id before commit

    # ── Generate QR code ──────────────────────────────────────
    scan_url  = f"{Config.BASE_URL}/scan/{photographer.scan_token}?event={name}"
    qr_dir    = Config.UPLOAD_DIR / "qr_codes"
    qr_filename = f"qr_event_{event.id}.png"
    qr_path   = qr_dir / qr_filename

    generate_qr_png(scan_url, qr_path)
    qr_url = f"{Config.BASE_URL}/api/events/{event.id}/qr"

    db.session.commit()
    log.info("Event created: '%s' (id=%s) by photographer %s", name, event.id, g.photographer_id)

    return jsonify({
        "success": True,
        "event":   _serialize(event, photographer.scan_token, qr_url),
    }), 201


# ─────────────────────────────────────────────────────────────
# GET /api/events
# ─────────────────────────────────────────────────────────────
@event_bp.route("", methods=["GET"])
@jwt_required
def list_events():
    """
    List all events belonging to the authenticated photographer.

    Response 200:
        { success: true, events: [ { id, name, date, ... }, ... ] }
    """
    photographer = Photographer.query.get(g.photographer_id)
    if not photographer:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    events = Event.query.filter_by(photographer_id=g.photographer_id)\
                  .order_by(Event.created_at.desc()).all()

    return jsonify({
        "success": True,
        "count":   len(events),
        "events":  [_serialize(e, photographer.scan_token) for e in events],
    }), 200


# ─────────────────────────────────────────────────────────────
# GET /api/events/<event_id>
# ─────────────────────────────────────────────────────────────
@event_bp.route("/<int:event_id>", methods=["GET"])
@jwt_required
def get_event(event_id: int):
    """
    Get a single event by ID.

    Response 200:
        { success: true, event: { ... } }
    """
    event = Event.query.get(event_id)
    if not event or event.photographer_id != g.photographer_id:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Event not found."}}), 404

    photographer = Photographer.query.get(g.photographer_id)
    qr_url = f"{Config.BASE_URL}/api/events/{event.id}/qr"
    return jsonify({"success": True, "event": _serialize(event, photographer.scan_token, qr_url)}), 200


# ─────────────────────────────────────────────────────────────
# DELETE /api/events/<event_id>
# ─────────────────────────────────────────────────────────────
@event_bp.route("/<int:event_id>", methods=["DELETE"])
@jwt_required
def delete_event(event_id: int):
    """
    Delete an event and its associated QR code image.

    Response 200:
        { success: true, message: "Event deleted." }
    """
    event = Event.query.get(event_id)
    if not event or event.photographer_id != g.photographer_id:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Event not found."}}), 404

    # Remove QR file if it exists
    qr_path = Config.UPLOAD_DIR / "qr_codes" / f"qr_event_{event_id}.png"
    if qr_path.exists():
        qr_path.unlink(missing_ok=True)

    db.session.delete(event)
    db.session.commit()
    log.info("Event deleted: id=%s by photographer %s", event_id, g.photographer_id)
    return jsonify({"success": True, "message": "Event deleted."}), 200


# ─────────────────────────────────────────────────────────────
# GET /api/events/<event_id>/qr
# ─────────────────────────────────────────────────────────────
@event_bp.route("/<int:event_id>/qr", methods=["GET"])
@jwt_required
def get_qr(event_id: int):
    """
    Serve the QR code PNG for an event.

    Response 200: PNG image
    """
    event = Event.query.get(event_id)
    if not event or event.photographer_id != g.photographer_id:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    qr_path = Config.UPLOAD_DIR / "qr_codes" / f"qr_event_{event_id}.png"
    if not qr_path.exists():
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "QR image not found."}}), 404

    return send_file(str(qr_path), mimetype="image/png")


# ─────────────────────────────────────────────────────────────
# Serialiser
# ─────────────────────────────────────────────────────────────
def _serialize(event: Event, scan_token: str = None, qr_url: str = None) -> dict:
    d = {
        "id":          event.id,
        "name":        event.name,
        "date":        event.date,
        "venue":       event.venue,
        "event_time":  event.event_time,
        "description": event.description,
        "photo_count": event.photo_count,
        "created_at":  event.created_at.isoformat() if event.created_at else None,
    }
    if scan_token:
        d["scan_url"] = f"{Config.BASE_URL}/scan/{scan_token}?event={event.name}"
    if qr_url:
        d["qr_url"] = qr_url
    return d
