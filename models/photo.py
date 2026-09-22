"""
models/photo.py — EventPhoto and PhotoFaceEmbedding models.

EventPhoto: One row per uploaded photo in an event.
PhotoFaceEmbedding: One row per detected face in a photo
                    (a photo with N faces = N rows).
Face: Detailed face record with bounding box and FAISS vector ID.
"""

from datetime import datetime, timezone
from models.database import db


class EventPhoto(db.Model):
    """
    A single photo uploaded to an event.

    Fields:
        id              — Primary key.
        event_name      — Name of the event this photo belongs to.
        filename        — Stored filename (safe, no path components).
        storage_path    — Full path/key in storage (local or cloud).
        upload_status   — 'uploaded' | 'processing' | 'processed' | 'failed'.
        matched         — True after face embeddings have been computed.
        uploaded_at     — Upload timestamp (UTC).
    """
    __tablename__ = "event_photo"
    __table_args__ = (
        db.UniqueConstraint("event_name", "filename", name="uq_event_photo_filename"),
    )

    id           = db.Column(db.Integer, primary_key=True)
    event_name   = db.Column(db.String(120), nullable=False, index=True)
    filename     = db.Column(db.String(300), nullable=False)
    storage_path = db.Column(db.String(512))
    upload_status= db.Column(db.String(20), default="uploaded", nullable=False)
    matched      = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_at  = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    face_embeddings = db.relationship(
        "PhotoFaceEmbedding", backref="photo", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<EventPhoto id={self.id} filename={self.filename!r}>"


class PhotoFaceEmbedding(db.Model):
    """
    One ArcFace embedding per detected face per event photo.

    A photo with 3 faces → 3 PhotoFaceEmbedding rows.
    The faiss_vector_id links this row to a position in the FAISS index.

    Fields:
        id              — Primary key.
        event_name      — Denormalised for fast per-event queries.
        photo_id        — FK → EventPhoto.
        filename        — Denormalised filename for direct lookup.
        face_index      — 0-based index of this face within the photo.
        bbox_x, bbox_y,
        bbox_w, bbox_h  — Bounding box of the detected face (pixels).
        faiss_vector_id — Row index in the FAISS index (for lookup).
        embedding       — JSON-serialised float32 list (ArcFace 512-dim).
        confidence      — RetinaFace detection confidence [0–1].
    """
    __tablename__ = "photo_face_embedding"

    id              = db.Column(db.Integer, primary_key=True)
    event_name      = db.Column(db.String(120), nullable=False, index=True)
    photo_id        = db.Column(db.Integer, db.ForeignKey("event_photo.id"), nullable=False, index=True)
    filename        = db.Column(db.String(300), nullable=False)
    face_index      = db.Column(db.Integer, nullable=False, default=0)
    bbox_x          = db.Column(db.Integer)
    bbox_y          = db.Column(db.Integer)
    bbox_w          = db.Column(db.Integer)
    bbox_h          = db.Column(db.Integer)
    faiss_vector_id = db.Column(db.Integer, index=True)   # position in FAISS index
    embedding       = db.Column(db.Text, nullable=False)  # JSON list of floats
    confidence      = db.Column(db.Float)

    def __repr__(self) -> str:
        return (
            f"<PhotoFaceEmbedding id={self.id} "
            f"photo_id={self.photo_id} face_index={self.face_index}>"
        )
