"""
api/email_routes.py — Email delivery management endpoints.

Endpoints:
    POST /api/email/resend-gallery — Resend gallery email to a guest (JWT required)
"""

from flask import Blueprint, g, jsonify, request

from models.database import db
from models.event import Event
from models.user import Guest, GuestFaceEmbedding
from utils.email_sender import send_gallery_email, send_new_photos_email
from utils.jwt_helper import jwt_required
from utils.logger import get_logger

log = get_logger(__name__)

email_bp = Blueprint("email", __name__, url_prefix="/api/email")


@email_bp.route("/resend-gallery", methods=["POST"])
@jwt_required
def resend_gallery():
    """
    Resend a gallery email to a specific guest.

    JWT required (photographer must own the event).

    Request JSON:
        gallery_token (str, required) — Guest's gallery token

    Response 200:
        { success: true, message: "Gallery email resent to <email>" }
    """
    data          = request.get_json(silent=True) or {}
    gallery_token = (data.get("gallery_token") or "").strip()

    if not gallery_token:
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "gallery_token is required."},
        }), 400

    guest = Guest.query.filter_by(gallery_token=gallery_token).first()
    if not guest:
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": "Guest not found."},
        }), 404

    # ── Verify photographer owns the event ────────────────────
    event = Event.query.filter_by(
        name=guest.event_name, photographer_id=g.photographer_id
    ).first()
    if not event:
        return jsonify({
            "success": False,
            "error": {"code": "FORBIDDEN", "message": "You do not own this event."},
        }), 403

    # ── Recompute matched count via stored embedding ───────────
    from config import Config              # noqa: PLC0415
    from services import faiss_store       # noqa: PLC0415
    import json, numpy as np               # noqa: E401, PLC0415

    matched_count  = guest.last_emailed_photo_count or 0
    emb_row = GuestFaceEmbedding.query.filter_by(guest_id=guest.id, phase="upload").first()

    if emb_row:
        embedding     = np.array(json.loads(emb_row.embedding), dtype=np.float32)
        hits          = faiss_store.search(guest.event_name, embedding, top_k=Config.FAISS_TOP_K)
        matched_count = len({h["photo_id"] for h in hits})

    gallery_url = f"{Config.BASE_URL}/gallery/{gallery_token}"
    new_count   = matched_count - (guest.last_emailed_photo_count or 0)

    if new_count > 0:
        send_new_photos_email(
            to          = guest.email,
            guest_name  = guest.name,
            gallery_url = gallery_url,
            new_count   = new_count,
            event_name  = guest.event_name,
        )
    else:
        send_gallery_email(
            to          = guest.email,
            guest_name  = guest.name,
            gallery_url = gallery_url,
            photo_count = matched_count,
            event_name  = guest.event_name,
        )

    # Update count
    guest.last_emailed_photo_count = matched_count
    from datetime import datetime, timezone  # noqa: PLC0415
    guest.gallery_sent_at = datetime.now(timezone.utc)
    db.session.commit()

    log.info("Gallery email resent for guest '%s' (%s)", guest.name, guest.email)
    return jsonify({
        "success": True,
        "message": f"Gallery email resent to {guest.email} ({matched_count} photos).",
    }), 200


@email_bp.route("/guests", methods=["GET"])
@jwt_required
def list_guests():
    """
    List all guests for an event (photographer view).

    Query params:
        event_name (str, required)

    Response 200:
        { success: true, guests: [...] }
    """
    event_name = (request.args.get("event_name") or "").strip()
    if not event_name:
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "event_name query param is required."},
        }), 400

    event = Event.query.filter_by(name=event_name, photographer_id=g.photographer_id).first()
    if not event:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    guests = Guest.query.filter_by(event_name=event_name)\
                  .order_by(Guest.registered_at.desc()).all()

    return jsonify({
        "success": True,
        "count":   len(guests),
        "guests":  [_serialize_guest(g_) for g_ in guests],
    }), 200


def _serialize_guest(guest: Guest) -> dict:
    from config import Config  # noqa: PLC0415
    return {
        "id":            guest.id,
        "name":          guest.name,
        "email":         guest.email,
        "event_name":    guest.event_name,
        "matched_count": guest.last_emailed_photo_count,
        "gallery_url":   f"{Config.BASE_URL}/gallery/{guest.gallery_token}",
        "gallery_token": guest.gallery_token,
        "registered_at": guest.registered_at.isoformat() if guest.registered_at else None,
        "gallery_sent_at": guest.gallery_sent_at.isoformat() if guest.gallery_sent_at else None,
    }
