"""Mistral embedding calls (L2 normalisation for cosine / pgvector search)."""

from __future__ import annotations

from typing import List, Sequence

import numpy as np
from mistralai import Mistral

from . import config as cfg


def get_client() -> Mistral:
    if not cfg.MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY is not set. Add it to your .env file.")
    return Mistral(api_key=cfg.MISTRAL_API_KEY)


def _normalise(vecs: np.ndarray) -> np.ndarray:
    """L2-normalise each row; keeps inner product equal to cosine similarity."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return (vecs / norms).astype("float32")


def embed_texts(
    client: Mistral, texts: Sequence[str], normalise: bool = True
) -> np.ndarray:
    """
    Return a (n, d) float32 array of embeddings for the given strings.
    Batches according to EMBED_BATCH_SIZE.
    """
    if not texts:
        return np.zeros((0, 0), dtype="float32")
    all_rows: list[np.ndarray] = []
    batch: list[str] = []
    for t in texts:
        batch.append(t)
        if len(batch) >= cfg.EMBED_BATCH_SIZE:
            all_rows.append(_one_batch(client, batch, normalise))
            batch = []
    if batch:
        all_rows.append(_one_batch(client, batch, normalise))
    mat = np.vstack(all_rows)
    if mat.size and mat.shape[1] != cfg.EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"Expected embedding dimension {cfg.EMBEDDING_DIMENSION}, "
            f"got {mat.shape[1]}. Set EMBEDDING_DIMENSION in .env if needed."
        )
    return mat


def _one_batch(
    client: Mistral, batch: List[str], normalise: bool
) -> np.ndarray:
    res = client.embeddings.create(
        model=cfg.MISTRAL_EMBED_MODEL,
        inputs=batch,
    )
    if not res or not res.data:
        raise RuntimeError("Mistral embeddings response had no data.")

    def _ord(d) -> int:
        i = getattr(d, "index", None)
        return int(i) if i is not None else 0

    items = sorted(res.data, key=_ord)  # type: ignore[union-attr]
    arrs: list[Sequence[float]] = []
    for d in items:
        e = d.embedding
        if e is None:
            raise RuntimeError("Mistral embedding entry had no vector.")
        arrs.append(e)  # type: ignore[union-attr, arg-type]
    mat = np.array(arrs, dtype="float32")
    if normalise:
        mat = _normalise(mat)
    return mat


def embed_query(client: Mistral, text: str) -> np.ndarray:
    """Single query vector, shape (1, d), L2-normalised."""
    return embed_texts(client, [text], normalise=True)
