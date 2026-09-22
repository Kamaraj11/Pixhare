"""
services/faiss_store.py — Per-event FAISS vector index management.

Each event gets its own IndexFlatIP (inner-product) index stored at:
    <FAISS_DIR>/<event_name>/index.faiss
    <FAISS_DIR>/<event_name>/meta.json   ← maps vector row → photo_id

Public API:
    load_index(event_name)                      → faiss.Index
    add_embeddings(event_name, vectors, ids)     → None
    search(event_name, query_vec, top_k)         → list[dict]
    get_vector_count(event_name)                 → int
"""

import json
from pathlib import Path
from typing import List, Dict, Any

import faiss
import numpy as np

from config import Config
from utils.logger import get_logger

log = get_logger(__name__)

_DIM = Config.EMBEDDING_DIM   # 512 for ArcFace


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _index_dir(event_name: str) -> Path:
    d = Config.FAISS_DIR / _safe(event_name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe(name: str) -> str:
    """Convert event name to a filesystem-safe folder name."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)


def _index_path(event_name: str) -> Path:
    return _index_dir(event_name) / "index.faiss"


def _meta_path(event_name: str) -> Path:
    return _index_dir(event_name) / "meta.json"


def _load_meta(event_name: str) -> List[int]:
    """Return list of photo_ids ordered by FAISS vector row index."""
    p = _meta_path(event_name)
    if p.exists():
        return json.loads(p.read_text())
    return []


def _save_meta(event_name: str, photo_ids: List[int]) -> None:
    _meta_path(event_name).write_text(json.dumps(photo_ids))


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def load_index(event_name: str) -> faiss.IndexFlatIP:
    """
    Load an existing FAISS index for the event, or create a new one.

    Args:
        event_name: Name of the event.

    Returns:
        A FAISS IndexFlatIP (inner-product) index.
    """
    p = _index_path(event_name)
    if p.exists():
        index = faiss.read_index(str(p))
        log.debug("FAISS index loaded for '%s': %d vectors", event_name, index.ntotal)
    else:
        index = faiss.IndexFlatIP(_DIM)
        log.debug("FAISS index created for '%s'", event_name)
    return index


def add_embeddings(
    event_name: str,
    vectors: np.ndarray,
    photo_ids: List[int],
) -> None:
    """
    Add face embedding vectors to the event's FAISS index.

    Args:
        event_name: Name of the event.
        vectors:    numpy float32 array of shape (N, 512).
        photo_ids:  List of N photo_ids — one per vector row.
    """
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)

    vectors = vectors.astype(np.float32)
    # L2-normalise so inner product == cosine similarity
    faiss.normalize_L2(vectors)

    index   = load_index(event_name)
    meta    = _load_meta(event_name)

    index.add(vectors)
    meta.extend(photo_ids)

    faiss.write_index(index, str(_index_path(event_name)))
    _save_meta(event_name, meta)
    log.info(
        "FAISS '%s': added %d vectors, total=%d",
        event_name, len(photo_ids), index.ntotal,
    )


def search(
    event_name: str,
    query_vector: np.ndarray,
    top_k: int = None,
) -> List[Dict[str, Any]]:
    """
    Search the event's FAISS index for the closest faces.

    Args:
        event_name:   Name of the event.
        query_vector: 1-D numpy float32 array of shape (512,).
        top_k:        Number of results to return (default: Config.FAISS_TOP_K).

    Returns:
        List of dicts sorted by score desc:
            [{ "photo_id": int, "score": float }, ...]
        Only results with score >= Config.SIMILARITY_THRESHOLD are returned.
    """
    if top_k is None:
        top_k = Config.FAISS_TOP_K

    p = _index_path(event_name)
    if not p.exists():
        log.warning("FAISS index not found for event '%s'", event_name)
        return []

    index = load_index(event_name)
    if index.ntotal == 0:
        return []

    meta = _load_meta(event_name)
    q    = query_vector.astype(np.float32).reshape(1, -1)
    faiss.normalize_L2(q)

    actual_k = min(top_k, index.ntotal)
    scores, indices = index.search(q, actual_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        if float(score) < Config.SIMILARITY_THRESHOLD:
            continue
        photo_id = meta[idx] if idx < len(meta) else None
        if photo_id is not None:
            results.append({"photo_id": photo_id, "score": float(score)})

    log.debug(
        "FAISS search '%s': top_k=%d, hits=%d (threshold=%.2f)",
        event_name, top_k, len(results), Config.SIMILARITY_THRESHOLD,
    )
    return results


def get_vector_count(event_name: str) -> int:
    """Return the total number of face vectors indexed for the event."""
    p = _index_path(event_name)
    if not p.exists():
        return 0
    return load_index(event_name).ntotal
