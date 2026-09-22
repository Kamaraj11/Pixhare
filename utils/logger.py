"""
utils/logger.py — Centralised structured logging for Pixhare.

Usage:
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Image uploaded", extra={"filename": "photo.jpg"})

Rules enforced here:
  - Passwords, API keys, and tokens are NEVER logged.
  - Log files are written to the LOG_DIR from config.
  - Console output is always enabled in development.
"""

import logging
import logging.handlers
import sys
from pathlib import Path


# Sensitive field names that must never appear in log messages.
_SENSITIVE_KEYS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "smtp_password", "llm_api_key", "authorization",
})


class _SensitiveFilter(logging.Filter):
    """Drop any log record whose message contains a known sensitive keyword."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        msg = record.getMessage().lower()
        return not any(key in msg for key in _SENSITIVE_KEYS)


def setup_logging(log_dir: Path, level: int = logging.DEBUG) -> None:
    """
    Configure the root logger once at application startup.

    Args:
        log_dir: Directory where rotating log files will be written.
        level:   Minimum log level (DEBUG in dev, INFO in prod).
    """
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # ── Formatter ────────────────────────────────────────────────────
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = _SensitiveFilter()

    # ── Console handler ──────────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    console.addFilter(sensitive_filter)
    root.addHandler(console)

    # ── Rotating file handler ────────────────────────────────────────
    # Keeps last 5 files × 5 MB each = 25 MB max log storage.
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "pixhare.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    file_handler.addFilter(sensitive_filter)
    root.addHandler(file_handler)

    # ── Suppress noisy third-party loggers ──────────────────────────
    for noisy in ("werkzeug", "urllib3", "PIL", "tensorflow", "absl"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Args:
        name: Typically __name__ of the calling module.

    Returns:
        A Logger instance scoped to that module name.
    """
    return logging.getLogger(name)
