"""
services/face_pipeline.py — Face detection and embedding pipeline.

Uses DeepFace (RetinaFace detector + ArcFace model) to:
  1. Detect all faces in an uploaded event photo.
  2. Compute a 512-dim ArcFace embedding per face.
  3. Save PhotoFaceEmbedding rows to the database.
  4. Add the embedding vectors to the per-event FAISS index.
  5. Mark the EventPhoto as 'processed'.

Public API:
    process_photo(photo_path, event_name, photo_id) → int  (faces found)
    compute_embedding(image_path)                   → np.ndarray | None
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np

from models.database import db
from models.photo import EventPhoto, PhotoFaceEmbedding
from services import faiss_store
from utils.logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────
# Lazy imports — DeepFace + TF load slowly; only import on use
# ─────────────────────────────────────────────────────────────
def _deepface():
    from deepface import DeepFace  # noqa: PLC0415
    return DeepFace


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def process_photo(
    photo_path: Path,
    event_name: str,
    photo_id: int,
) -> int:
    """
    Detect faces in a photo, embed them, and store results.

    Steps:
        1. Run DeepFace.represent() with RetinaFace + ArcFace.
        2. For each face: save a PhotoFaceEmbedding row.
        3. Batch-add all vectors to the FAISS index.
        4. Update EventPhoto.upload_status to 'processed'.

    Args:
        photo_path: Absolute path to the image file.
        event_name: Name of the event this photo belongs to.
        photo_id:   PK of the EventPhoto row.

    Returns:
        Number of faces detected (0 if none or on error).
    """
    photo: Optional[EventPhoto] = EventPhoto.query.get(photo_id)
    if not photo:
        log.error("process_photo: EventPhoto id=%s not found", photo_id)
        return 0

    photo.upload_status = "processing"
    db.session.commit()

    try:
        DeepFace = _deepface()
        from config import Config  # noqa: PLC0415

        representations = DeepFace.represent(
            img_path      = str(photo_path),
            model_name    = Config.FACE_RECOGNITION_MODEL,
            detector_backend = Config.FACE_DETECTION_BACKEND,
            enforce_detection = False,
            align         = True,
        )

        if not representations:
            log.info("No faces detected in photo id=%s ('%s')", photo_id, photo_path.name)
            photo.upload_status = "processed"
            db.session.commit()
            return 0

        vectors  = []
        ids      = []

        for face_index, rep in enumerate(representations):
            embedding  = rep.get("embedding", [])
            confidence = rep.get("face_confidence", 0.0)
            facial_area = rep.get("facial_area", {})

            if not embedding:
                continue

            vec = np.array(embedding, dtype=np.float32)

            # Persist embedding row
            face_emb = PhotoFaceEmbedding(
                event_name  = event_name,
                photo_id    = photo_id,
                filename    = photo.filename,
                face_index  = face_index,
                bbox_x      = facial_area.get("x"),
                bbox_y      = facial_area.get("y"),
                bbox_w      = facial_area.get("w"),
                bbox_h      = facial_area.get("h"),
                faiss_vector_id = None,   # will be back-filled below
                embedding   = json.dumps(embedding),
                confidence  = float(confidence),
            )
            db.session.add(face_emb)
            db.session.flush()   # get face_emb.id

            vectors.append(vec)
            ids.append(photo_id)

        if vectors:
            matrix = np.stack(vectors, axis=0)
            faiss_store.add_embeddings(event_name, matrix, ids)

        photo.upload_status = "processed"
        photo.matched       = True
        db.session.commit()

        log.info(
            "Processed photo id=%s: %d face(s) detected (event='%s')",
            photo_id, len(vectors), event_name,
        )
        return len(vectors)

    except Exception as exc:
        log.exception("face_pipeline error for photo id=%s: %s", photo_id, exc)
        photo.upload_status = "failed"
        db.session.commit()
        return 0


def compute_embedding(image_path: Path) -> Optional[np.ndarray]:
    """
    Compute a single face embedding for an image (e.g. a guest selfie).

    Returns the mean embedding if multiple faces are detected,
    or None if no face is found.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        numpy float32 array of shape (512,), or None.
    """
    try:
        DeepFace = _deepface()
        from config import Config  # noqa: PLC0415

        representations = DeepFace.represent(
            img_path         = str(image_path),
            model_name       = Config.FACE_RECOGNITION_MODEL,
            detector_backend = Config.FACE_DETECTION_BACKEND,
            enforce_detection = False,
            align             = True,
        )

        if not representations:
            log.warning("No face detected in image: %s", image_path.name)
            return None

        embeddings = [
            np.array(r["embedding"], dtype=np.float32)
            for r in representations
            if r.get("embedding")
        ]

        if not embeddings:
            return None

        # Use the mean of all detected face embeddings
        result = np.mean(embeddings, axis=0)
        log.debug("Embedding computed for %s (%d faces averaged)", image_path.name, len(embeddings))
        return result

    except Exception as exc:
        log.exception("compute_embedding error for %s: %s", image_path, exc)
        return None
