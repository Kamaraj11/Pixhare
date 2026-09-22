"""
models/user.py — Photographer (admin user) and Guest data models.

Photographer: registers, creates events, uploads photos.
Guest: scans QR, uploads selfie, receives gallery link.
"""

from datetime import datetime, timezone
from models.database import db


class Photographer(db.Model):
    """
    A photographer who owns an account and manages events.

    Fields:
        id           — Primary key.
        name         — Full name.
        studio_name  — Studio or business name.
        email        — Unique login email.
        password     — Bcrypt/Werkzeug password hash (never plain text).
        is_verified  — True after OTP email verification.
        otp          — Temporary OTP stored during registration.
        otp_expiry   — When the OTP expires (UTC).
        scan_token   — Random token embedded in QR code URL.
        qr_url       — Public URL of the generated QR code image.
        registered_on — Account creation timestamp (UTC).
        events        — Relationship to this photographer's events.
    """
    __tablename__ = "photographer"

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    studio_name   = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password      = db.Column(db.String(256), nullable=False)
    is_verified   = db.Column(db.Boolean, default=False, nullable=False)
    otp           = db.Column(db.String(6))
    otp_expiry    = db.Column(db.DateTime)
    scan_token    = db.Column(db.String(64), unique=True, index=True)
    qr_url        = db.Column(db.String(512))
    registered_on = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    events = db.relationship("Event", backref="photographer", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Photographer id={self.id} email={self.email!r}>"


class Guest(db.Model):
    """
    A guest who scans the photographer's QR code and registers at an event.

    Fields:
        id                     — Primary key.
        name                   — Guest's full name.
        email                  — Guest's email (gallery sent here).
        event_name             — Name of the event they attended.
        selfie_path            — Storage path for their selfie image/video.
        selfie_is_video        — True if the selfie is a video file.
        gallery_token          — Unique UUID that forms the gallery URL.
        gallery_sent_at        — When the gallery email was first sent (UTC).
        last_emailed_photo_count — Photo count at last email, for delta emails.
        registered_at          — Registration timestamp (UTC).
    """
    __tablename__ = "guest"

    id                       = db.Column(db.Integer, primary_key=True)
    name                     = db.Column(db.String(120), nullable=False)
    email                    = db.Column(db.String(120), nullable=False)
    event_name               = db.Column(db.String(120), nullable=False, index=True)
    selfie_path              = db.Column(db.String(512))
    selfie_is_video          = db.Column(db.Boolean, default=False)
    gallery_token            = db.Column(db.String(64), unique=True, nullable=False, index=True)
    gallery_sent_at          = db.Column(db.DateTime)
    last_emailed_photo_count = db.Column(db.Integer, default=0)
    registered_at            = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    face_embeddings = db.relationship("GuestFaceEmbedding", backref="guest", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Guest id={self.id} name={self.name!r} event={self.event_name!r}>"


class GuestFaceEmbedding(db.Model):
    """
    Cached ArcFace embedding vectors for a guest's selfie.

    One row per captured angle (center / left / right for video selfies,
    or a single 'upload' row for static image selfies).
    Embeddings are cached here so they are never re-computed on repeat runs.

    Fields:
        id         — Primary key.
        guest_id   — FK → Guest.
        phase      — Capture angle: 'center', 'left', 'right', or 'upload'.
        embedding  — JSON-serialised float32 list (ArcFace 512-dim vector).
        confidence — RetinaFace detection confidence for this frame.
    """
    __tablename__ = "guest_face_embedding"
    __table_args__ = (
        db.UniqueConstraint("guest_id", "phase", name="uq_guest_phase"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    guest_id   = db.Column(db.Integer, db.ForeignKey("guest.id"), nullable=False, index=True)
    phase      = db.Column(db.String(20), nullable=False)
    embedding  = db.Column(db.Text, nullable=False)   # JSON list of floats
    confidence = db.Column(db.Float)

    def __repr__(self) -> str:
        return f"<GuestFaceEmbedding guest_id={self.guest_id} phase={self.phase!r}>"
