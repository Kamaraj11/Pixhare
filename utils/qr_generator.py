"""
utils/qr_generator.py — QR code generation for Pixhare.

Generates a QR code PNG image for a given URL and saves it to disk.
"""

import qrcode
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)


def generate_qr_png(url: str, save_path: Path) -> bool:
    """
    Generate a QR code PNG and save it to save_path.

    Args:
        url:       The URL to encode in the QR code.
        save_path: Absolute path where the PNG will be written.

    Returns:
        True on success, False on failure.
    """
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color="#8b5cf6",    # purple dots
            back_color="#0f0f14",   # dark background
        )
        img.save(str(save_path))
        log.info("QR code saved: %s", save_path)
        return True
    except Exception as exc:
        log.error("Failed to generate QR code: %s", exc)
        return False
