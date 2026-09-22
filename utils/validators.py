"""
utils/validators.py — Input validation helpers for Pixhare.

All validation functions return (is_valid: bool, error_message: str).
They never raise exceptions — callers decide how to handle failures.
"""

import os
import re
from pathlib import Path
from typing import Tuple

from config import Config
from utils.logger import get_logger

log = get_logger(__name__)


def validate_image_extension(filename: str) -> Tuple[bool, str]:
    """
    Check that a filename has an allowed image extension.

    Args:
        filename: Original filename from the upload.

    Returns:
        (True, "") if valid.
        (False, error_message) if invalid.
    """
    if not filename or "." not in filename:
        return False, "Filename has no extension."

    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in Config.ALLOWED_EXTENSIONS:
        return False, (
            f"Extension '.{ext}' is not allowed. "
            f"Accepted: {', '.join(sorted(Config.ALLOWED_EXTENSIONS))}"
        )
    return True, ""


def validate_image_size(file_size_bytes: int) -> Tuple[bool, str]:
    """
    Check that an upload does not exceed the configured size limit.

    Args:
        file_size_bytes: Size of the uploaded file in bytes.

    Returns:
        (True, "") if within limit.
        (False, error_message) if too large.
    """
    if file_size_bytes > Config.MAX_UPLOAD_BYTES:
        limit_mb = Config.MAX_UPLOAD_BYTES / (1024 * 1024)
        actual_mb = file_size_bytes / (1024 * 1024)
        return False, (
            f"File is {actual_mb:.1f} MB — exceeds the {limit_mb:.0f} MB limit."
        )
    return True, ""


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Basic email format check.

    Args:
        email: Email string to validate.

    Returns:
        (True, "") if format looks valid.
        (False, error_message) otherwise.
    """
    if not email or not email.strip():
        return False, "Email address is required."

    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email.strip()):
        return False, f"'{email}' is not a valid email address."

    return True, ""


def validate_event_name(name: str) -> Tuple[bool, str]:
    """
    Validate an event name — must be non-empty and reasonably sized.

    Args:
        name: Event name string.

    Returns:
        (True, "") if valid.
        (False, error_message) otherwise.
    """
    if not name or not name.strip():
        return False, "Event name is required."
    if len(name.strip()) > 120:
        return False, "Event name must be 120 characters or fewer."
    return True, ""


def safe_path(base_dir: Path, filename: str) -> Tuple[bool, Path]:
    """
    Resolve a filename relative to base_dir and verify there is no
    path traversal attack (e.g. '../../etc/passwd').

    Args:
        base_dir: The trusted directory.
        filename: Filename (should already be secure_filename'd).

    Returns:
        (True, resolved_path) if safe.
        (False, base_dir) if traversal detected (caller should reject).
    """
    resolved = (base_dir / filename).resolve()
    if not str(resolved).startswith(str(base_dir.resolve())):
        log.warning("Path traversal attempt detected: %s", filename)
        return False, base_dir
    return True, resolved


def validate_password(password: str, min_length: int = 8) -> str:
    """
    Validate a password and return an error string, or "" if valid.

    Rules:
        - At least `min_length` characters (default 8)
        - At least one letter
        - At least one digit

    Args:
        password:   Raw password string.
        min_length: Minimum required length.

    Returns:
        Error message string, or "" if the password is acceptable.
    """
    if not password:
        return "Password is required."
    if len(password) < min_length:
        return f"Password must be at least {min_length} characters."
    if not re.search(r"[A-Za-z]", password):
        return "Password must contain at least one letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one digit."
    return ""
