"""
api/guest_routes.py — Guest-facing endpoints (public, no JWT).

Flow:
    1. Guest scans photographer's QR code.
       GET  /api/scan/<scan_token>
       → Returns event info so the frontend can show the registration form.

    2. Guest submits name, email, and selfie.
       POST /api/scan/<scan_token>/register
       → Saves Guest row, computes face embedding, searches FAISS,
         sends gallery email, returns gallery_token.

    3. Guest views their matched photos.
       GET  /api/gallery/<gallery_token>
       → Returns list of matched photo URLs.

All endpoints are public (no JWT required).
"""

import json
import uuid
from pathlib import Path

from flask import Blueprint, jsonify, request

from config import Config
from models.database import db
from models.event import Event
from models.photo import EventPhoto, PhotoFaceEmbedding
from models.user import Guest, GuestFaceEmbedding, Photographer
from services import face_pipeline, faiss_store
from utils.email_sender import send_gallery_email
from utils.logger import get_logger
from utils.security import make_safe_filename
from utils.validators import validate_email, validate_image_extension

log = get_logger(__name__)

guest_bp = Blueprint("guests", __name__)


# ─────────────────────────────────────────────────────────────
# GET /api/scan/<scan_token>
# ─────────────────────────────────────────────────────────────
@guest_bp.route("/api/scan/<scan_token>", methods=["GET"])
def scan_info(scan_token: str):
    """
    Validate a QR scan token and return the associated event info.

    Query params:
        event (str, optional): Filter to a specific event name.

    Response 200:
        { success: true, photographer: {...}, events: [...] }
    """
    photographer = Photographer.query.filter_by(scan_token=scan_token).first()
    if not photographer:
        return jsonify({
            "success": False,
            "error": {"code": "INVALID_TOKEN", "message": "Invalid or expired QR code."},
        }), 404

    event_name = request.args.get("event")
    query      = Event.query.filter_by(photographer_id=photographer.id)
    if event_name:
        query = query.filter_by(name=event_name)

    events = query.order_by(Event.date.desc()).all()

    return jsonify({
        "success": True,
        "photographer": {
            "name":        photographer.name,
            "studio_name": photographer.studio_name,
        },
        "scan_token": scan_token,
        "events": [
            {
                "name":        e.name,
                "date":        e.date,
                "venue":       e.venue,
                "event_time":  e.event_time,
                "description": e.description,
                "photo_count": e.photo_count,
            }
            for e in events
        ],
    }), 200


# ─────────────────────────────────────────────────────────────
# POST /api/scan/<scan_token>/register
# ─────────────────────────────────────────────────────────────
@guest_bp.route("/api/scan/<scan_token>/register", methods=["POST"])
def guest_register(scan_token: str):
    """
    Register a guest and find their photos via face search.

    Multipart form:
        name       (str, required)
        email      (str, required)
        event_name (str, required)
        selfie     (image file, required)

    Response 200:
        {
          success: true,
          gallery_token: "...",
          gallery_url: "...",
          matched_count: N,
          message: "..."
        }
    """
    # ── Validate scan token ───────────────────────────────────
    photographer = Photographer.query.filter_by(scan_token=scan_token).first()
    if not photographer:
        return jsonify({"success": False, "error": {"code": "INVALID_TOKEN"}}), 404

    # ── Parse form data ───────────────────────────────────────
    name       = (request.form.get("name") or "").strip()
    email      = (request.form.get("email") or "").strip().lower()
    event_name = (request.form.get("event_name") or "").strip()
    selfie     = request.files.get("selfie")

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    ok, err = validate_email(email)
    if not ok:
        errors["email"] = err
    if not event_name:
        errors["event_name"] = "Event name is required."
    if not selfie or selfie.filename == "":
        errors["selfie"] = "Selfie photo is required."
    else:
        ok, err = validate_image_extension(selfie.filename)
        if not ok:
            errors["selfie"] = err

    if errors:
        return jsonify({"success": False, "error": {"code": "VALIDATION_ERROR", "details": errors}}), 400

    # ── Validate event exists ─────────────────────────────────
    event = Event.query.filter_by(name=event_name, photographer_id=photographer.id).first()
    if not event:
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": f"Event '{event_name}' not found."},
        }), 404

    # ── Save selfie ───────────────────────────────────────────
    selfie_dir  = Config.UPLOAD_DIR / "selfies"
    selfie_dir.mkdir(parents=True, exist_ok=True)
    safe_name   = make_safe_filename(selfie.filename)
    selfie_path = selfie_dir / safe_name
    selfie.save(str(selfie_path))

    # ── Compute guest face embedding ──────────────────────────
    embedding = face_pipeline.compute_embedding(selfie_path)

    # ── Create Guest row ──────────────────────────────────────
    gallery_token = str(uuid.uuid4()).replace("-", "")
    guest = Guest(
        name         = name,
        email        = email,
        event_name   = event_name,
        selfie_path  = str(selfie_path),
        gallery_token = gallery_token,
    )
    db.session.add(guest)
    db.session.flush()   # get guest.id

    # ── Save guest face embedding ─────────────────────────────
    if embedding is not None:
        guest_emb = GuestFaceEmbedding(
            guest_id  = guest.id,
            phase     = "upload",
            embedding = json.dumps(embedding.tolist()),
            confidence = 1.0,
        )
        db.session.add(guest_emb)

    db.session.commit()

    # ── FAISS search for matching photos ──────────────────────
    matched_filenames = []
    if embedding is not None:
        hits = faiss_store.search(event_name, embedding, top_k=Config.FAISS_TOP_K)
        if hits:
            photo_ids = list({h["photo_id"] for h in hits})
            photos    = EventPhoto.query.filter(EventPhoto.id.in_(photo_ids)).all()
            matched_filenames = [p.filename for p in photos]

    matched_count = len(matched_filenames)
    gallery_url   = f"{Config.BASE_URL}/gallery/{gallery_token}"

    # ── Send gallery email ────────────────────────────────────
    send_gallery_email(
        to          = email,
        guest_name  = name,
        gallery_url = gallery_url,
        photo_count = matched_count,
        event_name  = event_name,
    )

    # ── Update guest last email count ─────────────────────────
    guest.last_emailed_photo_count = matched_count
    from datetime import datetime, timezone
    guest.gallery_sent_at = datetime.now(timezone.utc)
    db.session.commit()

    log.info(
        "Guest '%s' registered for event '%s': %d photos matched",
        name, event_name, matched_count,
    )

    msg = (
        f"Welcome {name}! We found {matched_count} photo(s) of you. "
        "Check your email for your personal gallery link!"
        if matched_count > 0
        else f"Welcome {name}! No photos of you yet — we'll email you when the photographer uploads more!"
    )

    return jsonify({
        "success":       True,
        "gallery_token": gallery_token,
        "gallery_url":   gallery_url,
        "matched_count": matched_count,
        "message":       msg,
    }), 200


# ─────────────────────────────────────────────────────────────
# GET /api/gallery/<gallery_token>
# ─────────────────────────────────────────────────────────────
@guest_bp.route("/api/gallery/<gallery_token>", methods=["GET"])
def view_gallery(gallery_token: str):
    """
    Return all matched photos for a guest's gallery.

    Response 200:
        {
          success: true,
          guest: { name, event_name },
          photos: [ { filename, url } ],
          total: N
        }
    """
    guest = Guest.query.filter_by(gallery_token=gallery_token).first()
    if not guest:
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": "Gallery not found."},
        }), 404

    # Re-run FAISS search using stored embedding to get latest matches
    emb_row = GuestFaceEmbedding.query.filter_by(guest_id=guest.id, phase="upload").first()
    photos  = []

    if emb_row:
        import numpy as np  # noqa: PLC0415
        embedding = np.array(json.loads(emb_row.embedding), dtype=np.float32)
        hits      = faiss_store.search(guest.event_name, embedding, top_k=Config.FAISS_TOP_K)
        if hits:
            photo_ids    = list({h["photo_id"] for h in hits})
            photo_rows   = EventPhoto.query.filter(EventPhoto.id.in_(photo_ids)).all()
            photos = [
                {
                    "filename": p.filename,
                    "url":      f"{Config.BASE_URL}/api/gallery/{gallery_token}/photo/{p.filename}",
                }
                for p in photo_rows
            ]

    return jsonify({
        "success": True,
        "guest": {
            "name":       guest.name,
            "event_name": guest.event_name,
        },
        "photos": photos,
        "total":  len(photos),
    }), 200


# ─────────────────────────────────────────────────────────────
# GET /api/gallery/<gallery_token>/photo/<filename>
# ─────────────────────────────────────────────────────────────
@guest_bp.route("/api/gallery/<gallery_token>/photo/<filename>", methods=["GET"])
def serve_gallery_photo(gallery_token: str, filename: str):
    """Serve a matched photo file to the guest."""
    from flask import send_file  # noqa: PLC0415

    guest = Guest.query.filter_by(gallery_token=gallery_token).first()
    if not guest:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    photo = EventPhoto.query.filter_by(
        event_name=guest.event_name, filename=filename
    ).first()
    if not photo or not photo.storage_path:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    path = Path(photo.storage_path)
    if not path.exists():
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    return send_file(str(path))
