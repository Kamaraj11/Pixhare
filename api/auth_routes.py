"""
api/auth_routes.py — Photographer authentication endpoints.

Endpoints:
    POST /api/auth/register      — Create account, send OTP
    POST /api/auth/verify-otp    — Verify OTP → issue JWT
    POST /api/auth/login         — Login → issue JWT
    GET  /api/auth/me            — Return current photographer (JWT required)
"""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from models.database import db
from models.user import Photographer
from utils.email_sender import send_otp_email
from utils.jwt_helper import generate_jwt, jwt_required
from utils.logger import get_logger
from utils.security import generate_otp, generate_token
from utils.validators import validate_email, validate_password

log = get_logger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_OTP_TTL_MINUTES = 10


# ─────────────────────────────────────────────────────────────
# POST /api/auth/register
# ─────────────────────────────────────────────────────────────
@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Register a new photographer account.

    Request JSON:
        name        (str, required)
        studio_name (str, required)
        email       (str, required, unique)
        password    (str, required, ≥8 chars)

    Response 201:
        { success: true, message: "OTP sent to email" }

    Response 400 / 409:
        { success: false, error: { code, message } }
    """
    data = request.get_json(silent=True) or {}

    # ── Validate required fields ──────────────────────────────
    name        = (data.get("name") or "").strip()
    studio_name = (data.get("studio_name") or "").strip()
    email       = (data.get("email") or "").strip().lower()
    password    = data.get("password", "")

    errors = {}
    if not name:
        errors["name"] = "Name is required."
    if not studio_name:
        errors["studio_name"] = "Studio name is required."
    email_ok, email_err = validate_email(email)
    if not email_ok:
        errors["email"] = email_err
    pwd_err = validate_password(password)
    if pwd_err:
        errors["password"] = pwd_err

    if errors:
        return jsonify({"success": False, "error": {"code": "VALIDATION_ERROR", "details": errors}}), 400

    # ── Duplicate check ───────────────────────────────────────
    if Photographer.query.filter_by(email=email).first():
        return jsonify({
            "success": False,
            "error": {"code": "CONFLICT", "message": "An account with this email already exists."},
        }), 409

    # ── Create photographer row ───────────────────────────────
    otp        = generate_otp()
    otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=_OTP_TTL_MINUTES)
    scan_token = generate_token(32)

    photographer = Photographer(
        name        = name,
        studio_name = studio_name,
        email       = email,
        password    = generate_password_hash(password),
        otp         = otp,
        otp_expiry  = otp_expiry,
        scan_token  = scan_token,
    )
    db.session.add(photographer)
    db.session.commit()
    log.info("Photographer registered: %s (id=%s)", email, photographer.id)

    # ── Send OTP ──────────────────────────────────────────────
    send_otp_email(email, otp, name)

    return jsonify({
        "success": True,
        "message": f"Account created. A 6-digit OTP has been sent to {email}.",
    }), 201


# ─────────────────────────────────────────────────────────────
# POST /api/auth/verify-otp
# ─────────────────────────────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify the OTP sent during registration.

    Request JSON:
        email (str)
        otp   (str, 6 digits)

    Response 200:
        { success: true, token: "<jwt>", photographer: { id, name, email, studio_name } }
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    otp   = (data.get("otp") or "").strip()

    if not email or not otp:
        return jsonify({"success": False, "error": {"code": "BAD_REQUEST", "message": "email and otp are required."}}), 400

    photographer = Photographer.query.filter_by(email=email).first()
    if not photographer:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Account not found."}}), 404

    if photographer.is_verified:
        return jsonify({"success": False, "error": {"code": "ALREADY_VERIFIED", "message": "Account is already verified."}}), 400

    # ── OTP checks ────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    expiry = photographer.otp_expiry
    # Make expiry timezone-aware if stored as naive datetime
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if not photographer.otp or photographer.otp != otp:
        return jsonify({"success": False, "error": {"code": "INVALID_OTP", "message": "Incorrect OTP."}}), 400

    if not expiry or now > expiry:
        return jsonify({"success": False, "error": {"code": "OTP_EXPIRED", "message": "OTP has expired. Please register again or request a new code."}}), 400

    # ── Mark verified ─────────────────────────────────────────
    photographer.is_verified = True
    photographer.otp         = None
    photographer.otp_expiry  = None
    db.session.commit()
    log.info("Photographer verified: %s", email)

    token = generate_jwt(photographer.id)
    return jsonify({
        "success":      True,
        "token":        token,
        "photographer": _serialize(photographer),
    }), 200


# ─────────────────────────────────────────────────────────────
# POST /api/auth/login
# ─────────────────────────────────────────────────────────────
@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login with email + password.

    Request JSON:
        email    (str)
        password (str)

    Response 200:
        { success: true, token: "<jwt>", photographer: { id, name, email, studio_name } }
    """
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"success": False, "error": {"code": "BAD_REQUEST", "message": "email and password are required."}}), 400

    photographer = Photographer.query.filter_by(email=email).first()

    # Generic error to avoid email enumeration
    if not photographer or not check_password_hash(photographer.password, password):
        return jsonify({"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}}), 401

    if not photographer.is_verified:
        return jsonify({"success": False, "error": {"code": "NOT_VERIFIED", "message": "Please verify your email before logging in."}}), 403

    token = generate_jwt(photographer.id)
    log.info("Photographer logged in: %s", email)
    return jsonify({
        "success":      True,
        "token":        token,
        "photographer": _serialize(photographer),
    }), 200


# ─────────────────────────────────────────────────────────────
# POST /api/auth/resend-otp
# ─────────────────────────────────────────────────────────────
@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    """
    Resend OTP to unverified photographer.

    Request JSON:
        email (str)
    """
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()

    if not email:
        return jsonify({"success": False, "error": {"code": "BAD_REQUEST", "message": "email is required."}}), 400

    photographer = Photographer.query.filter_by(email=email).first()
    if not photographer:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Account not found."}}), 404

    if photographer.is_verified:
        return jsonify({"success": False, "error": {"code": "ALREADY_VERIFIED", "message": "Account is already verified."}}), 400

    otp = generate_otp()
    photographer.otp        = otp
    photographer.otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=_OTP_TTL_MINUTES)
    db.session.commit()
    send_otp_email(email, otp, photographer.name)
    return jsonify({"success": True, "message": "New OTP sent."}), 200


# ─────────────────────────────────────────────────────────────
# GET /api/auth/me
# ─────────────────────────────────────────────────────────────
@auth_bp.route("/me", methods=["GET"])
@jwt_required
def me():
    """
    Return the currently authenticated photographer.

    Headers:
        Authorization: Bearer <token>

    Response 200:
        { success: true, photographer: { id, name, email, studio_name, scan_token, qr_url } }
    """
    photographer = Photographer.query.get(g.photographer_id)
    if not photographer:
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": "Photographer not found."}}), 404

    return jsonify({"success": True, "photographer": _serialize(photographer, full=True)}), 200


# ─────────────────────────────────────────────────────────────
# Serialiser
# ─────────────────────────────────────────────────────────────
def _serialize(p: Photographer, full: bool = False) -> dict:
    base = {
        "id":           p.id,
        "name":         p.name,
        "studio_name":  p.studio_name,
        "email":        p.email,
        "registered_on": p.registered_on.isoformat() if p.registered_on else None,
    }
    if full:
        base["scan_token"] = p.scan_token
        base["qr_url"]     = p.qr_url
    return base
