"""Embeddings for clustering (stage 4) and near-duplicate detection (§4.4.5).

Table 23: theme extraction and clustering use EMBEDDINGS, NOT GENERATION —
"clustering is deterministic and reproducible; generation here would invent
structure".

The default backend is a local sentence-transformers model. That is deliberate:
it costs nothing per refresh, it is reproducible, and it keeps the sovereign
deployment option open (NFR-05) without a second provider dependency. A
hashing/TF-IDF fallback is provided so the pipeline runs on a machine with no
model download — with a loud warning, because cluster quality degrades.
"""

from __future__ import annotations

import logging

import numpy as np

log = logging.getLogger(__name__)

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder:
    """Encodes text to L2-normalised vectors.

    The multilingual default matters: FR-28 requires English and French source
    ingestion, and the bias risk in Table 36 is "anglophone and EU bias in
    sources", so an English-only encoder would bake that bias into clustering.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, allow_fallback: bool = True):
        self.model_name = model_name
        self._model = None
        self._fallback = None
        self.allow_fallback = allow_fallback

    def _ensure(self) -> None:
        if self._model is not None or self._fallback is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            log.info("Embedder: using %s", self.model_name)
        except Exception as exc:  # noqa: BLE001
            if not self.allow_fallback:
                raise
            log.warning(
                "sentence-transformers unavailable (%s). Falling back to TF-IDF+SVD; "
                "cluster quality will be materially worse. Install with: pip install sentence-transformers",
                exc,
            )
            self._fallback = "tfidf"

    def encode(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        self._ensure()
        if self._model is not None:
            vectors = self._model.encode(
                texts, batch_size=batch_size, show_progress_bar=False, normalize_embeddings=True
            )
            return np.asarray(vectors, dtype=np.float32)
        return self._encode_tfidf(texts)

    def _encode_tfidf(self, texts: list[str]) -> np.ndarray:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        n_components = max(2, min(128, len(texts) - 1))
        vec = TfidfVectorizer(max_features=20000, ngram_range=(1, 2), stop_words=None)
        matrix = vec.fit_transform(texts)
        if matrix.shape[1] <= n_components:
            dense = matrix.toarray().astype(np.float32)
        else:
            # random_state fixed: SC-11 requires identical inputs to yield identical output.
            dense = TruncatedSVD(n_components=n_components, random_state=0).fit_transform(matrix).astype(np.float32)
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return dense / norms

    @staticmethod
    def to_blob(vector: np.ndarray) -> bytes:
        return np.asarray(vector, dtype=np.float32).tobytes()

    @staticmethod
    def from_blob(blob: bytes | None) -> np.ndarray | None:
        if not blob:
            return None
        return np.frombuffer(blob, dtype=np.float32)


def cosine_matrix(vectors: np.ndarray) -> np.ndarray:
    """Pairwise cosine similarity for already-normalised vectors."""
    if vectors.size == 0:
        return np.zeros((0, 0), dtype=np.float32)
    return np.clip(vectors @ vectors.T, -1.0, 1.0)
