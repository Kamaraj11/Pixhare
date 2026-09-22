"""
utils/security.py — Security helpers for Pixhare.

Covers:
  - Safe filename generation
  - Secure random token generation
  - Session token verification helpers
"""

import os
import secrets
import string
from pathlib import Path

from werkzeug.utils import secure_filename as _werkzeug_secure

from utils.logger import get_logger

log = get_logger(__name__)


def make_safe_filename(original_filename: str) -> str:
    """
    Generate a safe, unique filename from an uploaded file's original name.

    Strategy:
      1. Strip directory components and dangerous characters via Werkzeug.
      2. Prepend a 16-character random hex token so filenames never collide.

    Args:
        original_filename: The raw filename from the upload.

    Returns:
        A safe filename string, e.g. "a3f9b2c1d4e5f678_photo.jpg"
    """
    safe = _werkzeug_secure(original_filename)
    if not safe:
        # Werkzeug returns "" for filenames that are entirely unsafe
        safe = "upload"
    token = secrets.token_hex(8)   # 16 hex characters
    return f"{token}_{safe}"


def generate_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure URL-safe token.

    Used for:
      - QR verification tokens
      - Gallery access tokens
      - Session identifiers

    Args:
        length: Number of bytes of randomness (output will be 2× longer in hex).

    Returns:
        A hex string of length*2 characters.
    """
    return secrets.token_hex(length)


def generate_otp(digits: int = 6) -> str:
    """
    Generate a numeric OTP for email verification.

    Args:
        digits: Number of digits (default 6).

    Returns:
        A zero-padded numeric string, e.g. "048271".
    """
    return "".join(secrets.choice(string.digits) for _ in range(digits))


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.

    Use this when comparing OTPs, tokens, etc.

    Args:
        a, b: Strings to compare.

    Returns:
        True if equal, False otherwise.
    """
    return secrets.compare_digest(a.encode(), b.encode())
