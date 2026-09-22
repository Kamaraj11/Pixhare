"""
api/voice_routes.py — Speech-to-text transcription endpoint.

Uses Groq Whisper API to transcribe uploaded audio files.
Guests can speak their question; the frontend sends the audio here,
gets back a text transcription, then passes it to /api/chat.

Endpoints:
    POST /api/voice/transcribe — Transcribe audio → text
"""

import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request

from config import Config
from utils.logger import get_logger

log = get_logger(__name__)

voice_bp = Blueprint("voice", __name__, url_prefix="/api/voice")

_ALLOWED_AUDIO = {"webm", "wav", "mp3", "ogg", "m4a", "flac"}
_MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25 MB (Groq Whisper limit)


@voice_bp.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Transcribe an audio file to text using Groq Whisper.

    Multipart form:
        audio (file, required) — Audio recording (.webm, .wav, .mp3, etc.)

    Response 200:
        { success: true, text: "transcribed question..." }

    Response 400/503:
        { success: false, error: { code, message } }
    """
    audio_file = request.files.get("audio")
    if not audio_file or audio_file.filename == "":
        return jsonify({
            "success": False,
            "error": {"code": "BAD_REQUEST", "message": "No audio file provided."},
        }), 400

    # ── Extension check ───────────────────────────────────────
    ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else "webm"
    if ext not in _ALLOWED_AUDIO:
        return jsonify({
            "success": False,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": f"Unsupported audio format '.{ext}'. Accepted: {', '.join(sorted(_ALLOWED_AUDIO))}",
            },
        }), 400

    # ── Size check ────────────────────────────────────────────
    audio_file.seek(0, 2)
    size = audio_file.tell()
    audio_file.seek(0)
    if size > _MAX_AUDIO_BYTES:
        return jsonify({
            "success": False,
            "error": {"code": "FILE_TOO_LARGE", "message": "Audio file exceeds 25 MB limit."},
        }), 400

    if Config.STT_PROVIDER == "none" or not Config.LLM_API_KEY:
        return jsonify({
            "success": False,
            "error": {
                "code": "STT_DISABLED",
                "message": "Speech-to-text is disabled. Set LLM_API_KEY and STT_PROVIDER=groq_whisper.",
            },
        }), 503

    # ── Save to temp file and transcribe ──────────────────────
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = Path(tmp.name)

        text = _transcribe_groq(tmp_path, ext)
        tmp_path.unlink(missing_ok=True)

        log.info("STT transcription: '%s...'", text[:60])
        return jsonify({"success": True, "text": text}), 200

    except Exception as exc:
        log.exception("STT transcription failed: %s", exc)
        return jsonify({
            "success": False,
            "error": {"code": "TRANSCRIPTION_ERROR", "message": "Transcription failed. Please try again."},
        }), 500


def _transcribe_groq(audio_path: Path, ext: str) -> str:
    """Call Groq Whisper API and return the transcription text."""
    from groq import Groq  # noqa: PLC0415

    client = Groq(api_key=Config.LLM_API_KEY)
    with open(str(audio_path), "rb") as f:
        transcription = client.audio.transcriptions.create(
            file  = (audio_path.name, f),
            model = "whisper-large-v3",
        )
    return transcription.text.strip()
