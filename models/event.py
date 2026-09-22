"""
models/event.py — Event model.

An Event belongs to a Photographer and groups uploaded photos.
"""

from datetime import datetime, timezone
from models.database import db


class Event(db.Model):
    """
    An event created by a photographer.

    Fields:
        id              — Primary key.
        name            — Unique event name (e.g. "Raj Wedding 2025").
        date            — Event date string (YYYY-MM-DD).
        venue           — Optional venue name.
        event_time      — Optional time string (HH:MM).
        description     — Optional free-text description.
        photographer_id — FK → Photographer.
        photo_count     — Cached count of uploaded photos (avoids Storage list() calls).
        created_at      — Creation timestamp (UTC).
    """
    __tablename__ = "event"

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(120), unique=True, nullable=False, index=True)
    date            = db.Column(db.String(20), nullable=False)
    venue           = db.Column(db.String(200))
    event_time      = db.Column(db.String(20))
    description     = db.Column(db.Text)
    photographer_id = db.Column(db.Integer, db.ForeignKey("photographer.id"), nullable=False)
    photo_count     = db.Column(db.Integer, default=0, nullable=False)
    created_at      = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    photos = db.relationship(
        "EventPhoto",
        primaryjoin="Event.name == EventPhoto.event_name",
        foreign_keys="[EventPhoto.event_name]",
        backref="event",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} name={self.name!r}>"
