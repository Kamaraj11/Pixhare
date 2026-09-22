"""
app.py — Pixhare Flask application factory.

PHASE 1: Minimal working app with:
  - Configuration loading
  - Directory creation
  - Database initialisation
  - Logging setup
  - Health endpoint
  - Centralised error handlers
  - 413 (file too large) handler

Later phases will register additional blueprints here.
"""

import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

from config import Config
from models.database import db
from utils.logger import setup_logging, get_logger

log = get_logger(__name__)


def create_app(config_class: type = Config) -> Flask:
    """
    Flask application factory.

    Args:
        config_class: Configuration class (default: Config from config.py).

    Returns:
        Configured Flask application instance.
    """
    # ── Create directories early so logger can write its file ────────
    config_class.ensure_directories()

    # ── Logging ──────────────────────────────────────────────────────
    log_level = logging.DEBUG if config_class.DEBUG else logging.INFO
    setup_logging(config_class.LOG_DIR, level=log_level)

    log.info("=" * 60)
    log.info("Starting Pixhare — AI-Powered Event Photo Sharing")
    log.info("Environment : %s", config_class.ENV)
    log.info("Database    : %s", config_class.SQLALCHEMY_DATABASE_URI)
    log.info("=" * 60)

    # ── Flask app ─────────────────────────────────────────────────────
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)

    # ── CORS (needed if frontend is served separately) ────────────────
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # ── Database ──────────────────────────────────────────────────────
    db.init_app(app)
    with app.app_context():
        # Import all models so SQLAlchemy sees them before create_all()
        from models.user import Photographer, Guest, GuestFaceEmbedding  # noqa: F401
        from models.event import Event                                     # noqa: F401
        from models.photo import EventPhoto, PhotoFaceEmbedding           # noqa: F401
        db.create_all()
        log.info("Database tables created / verified.")

    # ── Blueprints ────────────────────────────────────────────
    from api.health import health_bp
    app.register_blueprint(health_bp)

    from api.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

    # Future phases will add:
    #   from api.event_routes  import event_bp
    #   from api.photo_routes  import photo_bp
    #   from api.guest_routes  import guest_bp
    #   from api.chat_routes   import chat_bp
    #   from api.voice_routes  import voice_bp
    #   from api.email_routes  import email_bp
    log.info("Blueprints registered.")

    # ── Error handlers ────────────────────────────────────────────────
    _register_error_handlers(app)

    # ── Startup validation ────────────────────────────────────────────
    config_class.validate_startup()

    log.info("Pixhare application ready.")
    return app


def _register_error_handlers(app: Flask) -> None:
    """Register centralised JSON error responses for common HTTP errors."""

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"success": False, "error": {"code": "BAD_REQUEST", "message": str(e)}}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication required."}}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"success": False, "error": {"code": "FORBIDDEN", "message": "Access denied."}}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": {"code": "NOT_FOUND", "message": str(e)}}), 404

    @app.errorhandler(413)
    def request_too_large(e):
        limit_mb = Config.MAX_UPLOAD_BYTES // (1024 * 1024)
        return jsonify({
            "success": False,
            "error": {
                "code": "FILE_TOO_LARGE",
                "message": f"Upload exceeds the {limit_mb} MB limit.",
            },
        }), 413

    @app.errorhandler(500)
    def internal_error(e):
        log.exception("Internal server error: %s", e)
        return jsonify({"success": False, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}}), 500


# ── Entry point ───────────────────────────────────────────────────────
app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    port  = int(os.environ.get("PORT", 5000))
    log.info("Running on http://0.0.0.0:%d  (debug=%s)", port, debug)
    app.run(debug=debug, host="0.0.0.0", port=port)
