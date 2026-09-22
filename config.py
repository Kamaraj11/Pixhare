"""
config.py — Centralised configuration for Pixhare.

All application settings live here.
Secrets are loaded from the .env file via python-dotenv.
No credential is ever hardcoded.
"""

import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


# ─────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────
def _require(key: str) -> str:
    """Return an env var value, or raise at startup if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ─────────────────────────────────────────────
# Flask
# ─────────────────────────────────────────────
class Config:
    # Application
    ENV: str = _optional("FLASK_ENV", "development")
    DEBUG: bool = ENV == "development"

    # Secret key — must be set in production
    _raw_secret = os.getenv("SECRET_KEY")
    if not _raw_secret:
        warnings.warn(
            "SECRET_KEY is not set in .env — using insecure default. "
            "Set a strong random value for any deployed environment.",
            stacklevel=1,
        )
        _raw_secret = "pixhare-dev-insecure-key-change-this"
    SECRET_KEY: str = _raw_secret

    # ── Directories ──────────────────────────
    UPLOAD_DIR:    Path = BASE_DIR / "data" / "uploads"
    PROCESSED_DIR: Path = BASE_DIR / "data" / "processed"
    RESULTS_DIR:   Path = BASE_DIR / "data" / "results"
    EMBEDDINGS_DIR:Path = BASE_DIR / "data" / "embeddings"
    FAISS_DIR:     Path = BASE_DIR / "faiss_index"
    LOG_DIR:       Path = BASE_DIR / "logs"

    # ── Upload limits ────────────────────────
    MAX_UPLOAD_BYTES: int = 16 * 1024 * 1024          # 16 MB
    ALLOWED_EXTENSIONS: set = {"jpg", "jpeg", "png"}

    # ── Face / embedding settings ─────────────
    FACE_DETECTION_BACKEND: str = _optional("FACE_DETECTION_BACKEND", "retinaface")
    FACE_RECOGNITION_MODEL: str = _optional("FACE_RECOGNITION_MODEL", "ArcFace")
    FACE_CONFIDENCE_THRESHOLD: float = float(_optional("FACE_CONFIDENCE_THRESHOLD", "0.85"))
    EMBEDDING_DIM: int = 512          # ArcFace output — validated at runtime
    FAISS_TOP_K: int   = int(_optional("FAISS_TOP_K", "10"))
    SIMILARITY_THRESHOLD: float = float(_optional("SIMILARITY_THRESHOLD", "0.40"))

    # ── Database ─────────────────────────────
    _db_url = os.getenv("DATABASE_URL", "")
    if _db_url:
        _db_url = _db_url.replace("postgres://", "postgresql://")
    SQLALCHEMY_DATABASE_URI: str = _db_url or f"sqlite:///{BASE_DIR / 'pixhare.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # ── SMTP ─────────────────────────────────
    SMTP_HOST:       str = _optional("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT:       int = int(_optional("SMTP_PORT", "465"))
    SMTP_USERNAME:   str = _optional("SMTP_USERNAME")
    SMTP_PASSWORD:   str = _optional("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = _optional("SMTP_FROM_EMAIL")
    SMTP_USE_SSL:    bool = _optional("SMTP_USE_SSL", "true").lower() == "true"

    # ── LLM / RAG ────────────────────────────
    LLM_PROVIDER:  str = _optional("LLM_PROVIDER", "groq")   # groq | openai | none
    LLM_MODEL:     str = _optional("LLM_MODEL", "llama-3.3-70b-versatile")
    LLM_API_KEY:   str = _optional("LLM_API_KEY")
    LLM_MAX_TOKENS:int = int(_optional("LLM_MAX_TOKENS", "512"))
    LLM_TEMPERATURE:float = float(_optional("LLM_TEMPERATURE", "0.2"))

    # ── Voice / STT ──────────────────────────
    STT_PROVIDER: str = _optional("STT_PROVIDER", "groq_whisper")  # groq_whisper | none

    # ── QR / Session ─────────────────────────
    SESSION_LIFETIME_MINUTES: int = int(_optional("SESSION_LIFETIME_MINUTES", "60"))

    # ── Application base URL (for email links) ─
    BASE_URL: str = _optional("BASE_URL", "http://127.0.0.1:5000")

    @classmethod
    def ensure_directories(cls) -> None:
        """Create all required local directories if they do not exist."""
        dirs = [
            cls.UPLOAD_DIR, cls.PROCESSED_DIR, cls.RESULTS_DIR,
            cls.EMBEDDINGS_DIR, cls.FAISS_DIR, cls.LOG_DIR,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def validate_startup(cls) -> None:
        """Log a warning for each optional-but-important missing value."""
        import logging
        log = logging.getLogger("pixhare.config")

        if cls.BASE_URL == "http://127.0.0.1:5000":
            log.warning("BASE_URL not set — email gallery links will point to localhost.")
        if not cls.LLM_API_KEY:
            log.info("LLM_API_KEY not set — RAG will run in retrieval-only mode.")
        if not cls.SMTP_USERNAME:
            log.info("SMTP_USERNAME not set — email delivery is disabled.")
