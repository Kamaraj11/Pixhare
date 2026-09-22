"""
utils/email_sender.py — SMTP email delivery for Pixhare.

Covers:
  - send_otp_email(to, otp) — OTP verification during registration
  - send_gallery_email(to, guest_name, gallery_url, photo_count) — Gallery delivery
  - Graceful fallback: logs the message if SMTP is not configured

No credentials are hardcoded; all values come from Config.
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Config
from utils.logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _smtp_ready() -> bool:
    """Return True if all required SMTP settings are present."""
    return bool(Config.SMTP_USERNAME and Config.SMTP_PASSWORD and Config.SMTP_FROM_EMAIL)


def _send(to: str, subject: str, html_body: str) -> bool:
    """
    Send a single HTML email.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        html_body: HTML content string.

    Returns:
        True on success, False on failure.
    """
    if not _smtp_ready():
        log.info(
            "[EMAIL STUB] To: %s | Subject: %s\n--- body preview ---\n%s\n---",
            to, subject, html_body[:500],
        )
        return True   # treat as success in dev mode

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = Config.SMTP_FROM_EMAIL
    msg["To"]      = to
    msg.attach(MIMEText(html_body, "html"))

    try:
        ctx = ssl.create_default_context()
        if Config.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=ctx) as server:
                server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_FROM_EMAIL, to, msg.as_string())
        else:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
                server.sendmail(Config.SMTP_FROM_EMAIL, to, msg.as_string())

        log.info("Email sent to %s | subject=%r", to, subject)
        return True
    except Exception as exc:                        # pragma: no cover
        log.error("Failed to send email to %s: %s", to, exc)
        return False


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def send_otp_email(to: str, otp: str, name: str = "") -> bool:
    """
    Send a 6-digit OTP for photographer email verification.

    Args:
        to:   Recipient email.
        otp:  6-digit OTP string.
        name: Recipient's name (optional, for personalisation).

    Returns:
        True if sent (or logged in dev mode), False on SMTP failure.
    """
    greeting = f"Hi {name}," if name else "Hi,"
    html = f"""
    <html><body style="font-family:sans-serif;background:#0f0f14;color:#e2e2f0;padding:40px;">
      <div style="max-width:480px;margin:auto;background:#1a1a2e;border-radius:16px;padding:40px;">
        <h2 style="color:#8b5cf6;margin-bottom:8px;">Pixhare</h2>
        <p style="color:#a0a0c0;">{greeting}</p>
        <p>Use the code below to verify your email address.</p>
        <div style="background:#0f0f14;border-radius:12px;padding:24px;text-align:center;margin:24px 0;">
          <span style="font-size:36px;font-weight:700;letter-spacing:12px;color:#8b5cf6;">{otp}</span>
        </div>
        <p style="color:#606080;font-size:14px;">This code expires in <strong>10 minutes</strong>.
        If you did not create a Pixhare account, you can safely ignore this email.</p>
      </div>
    </body></html>
    """
    return _send(to, "Pixhare — Your Verification Code", html)


def send_gallery_email(
    to: str,
    guest_name: str,
    gallery_url: str,
    photo_count: int,
    event_name: str = "",
) -> bool:
    """
    Send a gallery access link to a guest.

    Args:
        to:          Guest's email.
        guest_name:  Guest's name.
        gallery_url: Full URL to the guest's personal gallery.
        photo_count: Number of photos found.
        event_name:  Name of the event (optional).

    Returns:
        True on success / logged, False on failure.
    """
    event_line = f" from <strong>{event_name}</strong>" if event_name else ""
    plural = "photo" if photo_count == 1 else "photos"
    html = f"""
    <html><body style="font-family:sans-serif;background:#0f0f14;color:#e2e2f0;padding:40px;">
      <div style="max-width:520px;margin:auto;background:#1a1a2e;border-radius:16px;padding:40px;">
        <h2 style="color:#8b5cf6;margin-bottom:8px;">Pixhare 📸</h2>
        <p>Hi <strong>{guest_name}</strong>!</p>
        <p>We found <strong>{photo_count} {plural}</strong>{event_line} featuring you.</p>
        <a href="{gallery_url}"
           style="display:inline-block;margin:24px 0;padding:14px 32px;
                  background:linear-gradient(135deg,#8b5cf6,#6366f1);
                  color:#fff;border-radius:10px;text-decoration:none;
                  font-weight:600;font-size:16px;">
          View My Gallery →
        </a>
        <p style="color:#606080;font-size:13px;">
          This link is personal to you. New photos are added automatically as the
          photographer uploads them — you'll receive another email then!
        </p>
      </div>
    </body></html>
    """
    subject = f"Your photos from {event_name}" if event_name else "Your Pixhare gallery is ready!"
    return _send(to, subject, html)


def send_new_photos_email(
    to: str,
    guest_name: str,
    gallery_url: str,
    new_count: int,
    event_name: str = "",
) -> bool:
    """
    Notify a guest that new photos matching them have been added.

    Args:
        to:          Guest's email.
        guest_name:  Guest's name.
        gallery_url: Gallery URL.
        new_count:   Number of newly matched photos.
        event_name:  Event name.

    Returns:
        True on success / logged.
    """
    plural = "photo" if new_count == 1 else "photos"
    event_line = f" from {event_name}" if event_name else ""
    html = f"""
    <html><body style="font-family:sans-serif;background:#0f0f14;color:#e2e2f0;padding:40px;">
      <div style="max-width:520px;margin:auto;background:#1a1a2e;border-radius:16px;padding:40px;">
        <h2 style="color:#8b5cf6;margin-bottom:8px;">Pixhare 📸</h2>
        <p>Hi <strong>{guest_name}</strong>!</p>
        <p>The photographer just added <strong>{new_count} new {plural}</strong>{event_line} featuring you!</p>
        <a href="{gallery_url}"
           style="display:inline-block;margin:24px 0;padding:14px 32px;
                  background:linear-gradient(135deg,#8b5cf6,#6366f1);
                  color:#fff;border-radius:10px;text-decoration:none;
                  font-weight:600;font-size:16px;">
          See New Photos →
        </a>
      </div>
    </body></html>
    """
    subject = f"New photos added to your gallery!"
    return _send(to, subject, html)
