"""
api/chat_routes.py — AI chat endpoint for guests.

Endpoints:
    POST /api/chat — Ask a question about your event photos (public)
"""

from flask import Blueprint, jsonify, request

from services import rag_engine
from utils.logger import get_logger
from utils.validators import validate_email

log = get_logger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


@chat_bp.route("", methods=["POST"])
def chat():
    """
    Ask Pixhare AI a question about an event.

    Request JSON:
        event_name  (str, required) — The event name
        guest_name  (str, required) — The guest's name
        question    (str, required) — Natural language question

    Response 200:
        { success: true, answer: "..." }

    Response 400:
        { success: false, error: { code: "VALIDATION_ERROR", details: {...} } }
    """
    data = request.get_json(silent=True) or {}

    event_name = (data.get("event_name") or "").strip()
    guest_name = (data.get("guest_name") or "").strip()
    question   = (data.get("question") or "").strip()

    errors = {}
    if not event_name:
        errors["event_name"] = "event_name is required."
    if not guest_name:
        errors["guest_name"] = "guest_name is required."
    if not question:
        errors["question"] = "question is required."
    if len(question) > 500:
        errors["question"] = "Question must be 500 characters or fewer."

    if errors:
        return jsonify({
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "details": errors},
        }), 400

    log.info("Chat: guest='%s' event='%s' q='%s'", guest_name, event_name, question[:80])

    answer = rag_engine.ask(event_name, guest_name, question)

    return jsonify({
        "success": True,
        "answer":  answer,
    }), 200
