"""
api/photo_routes.py — Event photo upload and listing endpoints.

Endpoints:
    POST /api/events/<event_name>/photos  — Upload 1-50 photos (JWT required)
    GET  /api/events/<event_name>/photos  — List photos for an event (JWT required)
    GET  /api/events/<event_name>/photos/<filename> — Serve a photo file (JWT required)
"""

import threading
from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request, send_file

from config import Config
from models.database import db
from models.event import Event
from models.photo import EventPhoto
from utils.jwt_helper import jwt_required
from utils.logger import get_logger
from utils.security import make_safe_filename
from utils.validators import validate_image_extension, validate_image_size

log = get_logger(__name__)

photo_bp = Blueprint("photos", __name__, url_prefix="/api/events")

_MAX_FILES_PER_UPLOAD = 50


# ─────────────────────────────────────────────────────────────
# POST /api/events/<event_name>/photos
# ─────────────────────────────────────────────────────────────
@photo_bp.route("/<event_name>/photos", methods=["POST"])
@jwt_required
def upload_photos(event_name: str):
    """
    Upload one or more photos to an event.

    Multipart form:
        photos: one or more image files (jpg/jpeg/png)

    Response 202:
        { success: true, uploaded: N, queued_for_processing: N, photos: [...] }
    """
    event = Event.query.filter_by(name=event_name, photographer_id=g.photographer_id).first()
    if not event:
        return jsonify({
            "success": False,
            "error": {"code": "NOT_FOUND", "message": f"Event '{event_name}' not found."},
        }), 404

    files = request.files.getlist("photos")
    if not files or all(f.filename == "" for f in files):
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "No photo files provided."},
        }), 400

    if len(files) > _MAX_FILES_PER_UPLOAD:
        return jsonify({
            "success": False,
            "error": {"code": "TOO_MANY_FILES", "message": f"Max {_MAX_FILES_PER_UPLOAD} files per upload."},
        }), 400

    upload_dir = Config.UPLOAD_DIR / _safe_dir(event_name)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_photos = []
    errors       = []

    for f in files:
        if not f.filename:
            continue

        # ── Validate extension ────────────────────────────────
        ok, err = validate_image_extension(f.filename)
        if not ok:
            errors.append({"filename": f.filename, "error": err})
            continue

        # ── Validate size ─────────────────────────────────────
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        ok, err = validate_image_size(size)
        if not ok:
            errors.append({"filename": f.filename, "error": err})
            continue

        # ── Save file ─────────────────────────────────────────
        safe_name   = make_safe_filename(f.filename)
        save_path   = upload_dir / safe_name
        f.save(str(save_path))

        # ── DB row ────────────────────────────────────────────
        photo = EventPhoto(
            event_name    = event_name,
            filename      = safe_name,
            storage_path  = str(save_path),
            upload_status = "uploaded",
        )
        db.session.add(photo)
        db.session.flush()   # get photo.id

        saved_photos.append({"id": photo.id, "filename": safe_name, "path": str(save_path)})

    # ── Update event photo count ──────────────────────────────
    event.photo_count = (event.photo_count or 0) + len(saved_photos)
    db.session.commit()
    log.info("Uploaded %d photos to event '%s'", len(saved_photos), event_name)

    # ── Trigger face processing in background ─────────────────
    app = current_app._get_current_object()
    for p in saved_photos:
        t = threading.Thread(
            target=_run_pipeline,
            args=(app, p["path"], event_name, p["id"]),
            daemon=True,
        )
        t.start()

    return jsonify({
        "success":                True,
        "uploaded":               len(saved_photos),
        "queued_for_processing":  len(saved_photos),
        "errors":                 errors,
        "photos":                 saved_photos,
    }), 202


# ─────────────────────────────────────────────────────────────
# GET /api/events/<event_name>/photos
# ─────────────────────────────────────────────────────────────
@photo_bp.route("/<event_name>/photos", methods=["GET"])
@jwt_required
def list_photos(event_name: str):
    """
    List all photos for an event.

    Query params:
        status (str, optional): Filter by upload_status (uploaded|processing|processed|failed)

    Response 200:
        { success: true, count: N, photos: [ { id, filename, status, matched, url } ] }
    """
    event = Event.query.filter_by(name=event_name, photographer_id=g.photographer_id).first()
    if not event:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    status_filter = request.args.get("status")
    query = EventPhoto.query.filter_by(event_name=event_name)
    if status_filter:
        query = query.filter_by(upload_status=status_filter)

    photos = query.order_by(EventPhoto.uploaded_at.desc()).all()

    return jsonify({
        "success": True,
        "count":   len(photos),
        "photos":  [_serialize_photo(p) for p in photos],
    }), 200


# ─────────────────────────────────────────────────────────────
# GET /api/events/<event_name>/photos/<filename>
# ─────────────────────────────────────────────────────────────
@photo_bp.route("/<event_name>/photos/<filename>", methods=["GET"])
@jwt_required
def serve_photo(event_name: str, filename: str):
    """Serve a photo file directly (for dashboard preview)."""
    photo = EventPhoto.query.filter_by(event_name=event_name, filename=filename).first()
    if not photo or not photo.storage_path:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND"}}), 404

    path = Path(photo.storage_path)
    if not path.exists():
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "File not found on disk."}}), 404

    return send_file(str(path))


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _safe_dir(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _run_pipeline(app, photo_path: str, event_name: str, photo_id: int) -> None:
    """Run face detection pipeline inside an app context (background thread)."""
    with app.app_context():
        from services.face_pipeline import process_photo  # noqa: PLC0415
        process_photo(Path(photo_path), event_name, photo_id)


def _serialize_photo(photo: EventPhoto) -> dict:
    return {
        "id":          photo.id,
        "filename":    photo.filename,
        "status":      photo.upload_status,
        "matched":     photo.matched,
        "uploaded_at": photo.uploaded_at.isoformat() if photo.uploaded_at else None,
        "url":         f"{Config.BASE_URL}/api/events/{photo.event_name}/photos/{photo.filename}",
    }
