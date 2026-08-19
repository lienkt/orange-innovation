"""Pipeline stage 4: Extract themes (Table 16).

Signals -> theme clusters. Embedding of signal spans; density-based clustering;
per-cluster keyphrase extraction; cluster tracking across refreshes.

Table 23 assigns this stage to EMBEDDINGS, NOT GENERATION: "clustering is
deterministic and reproducible; generation here would invent structure."

Agglomerative clustering with a distance threshold is used rather than k-means
or HDBSCAN because it needs no k, no random initialisation and no minimum
cluster count — SC-11 requires that identical inputs and identical
configuration yield identical output, and any randomised initialisation breaks
that guarantee.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections import Counter
from typing import Any

import numpy as np

from ..config import Config
from ..db import Database, js
from ..embeddings import Embedder

log = logging.getLogger(__name__)

# Stopwords for keyphrase extraction. English plus the French closed-class words
# that survive FR-28's French ingestion.
_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "will", "have", "has", "are", "was",
    "its", "their", "new", "more", "than", "into", "over", "about", "after", "under", "been",
    "which", "when", "what", "where", "how", "why", "who", "can", "could", "would", "should",
    "les", "des", "une", "pour", "avec", "dans", "sur", "est", "sont", "aux", "par", "leur",
    "cette", "nous", "vous", "plus", "tout", "tous", "être", "avoir", "fait",
    "said", "says", "year", "years", "week", "month", "day", "today", "news", "report",
    "market", "global", "company", "business", "service", "services", "solution", "solutions",
}
_TOKEN_RE = re.compile(r"[a-zà-ÿ][a-zà-ÿ0-9\-]{2,}", re.I)


class ThemeExtractor:
    def __init__(self, cfg: Config, db: Database, embedder: Embedder | None = None):
        self.cfg = cfg
        self.db = db
        self.embedder = embedder or Embedder()
        clustering = cfg.settings["clustering"]
        self.distance_threshold = float(clustering["distance_threshold"])
        self.min_cluster_size = int(clustering["min_cluster_size"])
        self.max_clusters = int(clustering["max_clusters"])

    def run(self, refresh_id: str, min_relevance: float = 0.3) -> dict[str, Any]:
        rows = self.db.query(
            "SELECT id, title, extract, publisher, signal_type, tier, published_at "
            "FROM signals WHERE relevance >= ? ORDER BY published_at DESC",
            (min_relevance,),
        )
        if len(rows) < self.min_cluster_size:
            log.warning("Only %d relevant signals — below min_cluster_size %d, no clusters formed.",
                        len(rows), self.min_cluster_size)
            return {"signals": len(rows), "clusters": 0}

        texts = [f"{r['title']}. {r['extract']}" for r in rows]
        log.info("Embedding %d signals…", len(texts))
        vectors = self.embedder.encode(texts)

        labels = self._cluster(vectors)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        # Persist embeddings so near-duplicate detection (§4.4.5) and the
        # backtest harness can reuse them without re-encoding.
        with self.db.cursor() as cur:
            for row, vector, label in zip(rows, vectors, labels):
                cur.execute(
                    "UPDATE signals SET embedding = ?, cluster_id = ? WHERE id = ?",
                    (Embedder.to_blob(vector), int(label) if label >= 0 else None, row["id"]),
                )

            # Cluster ids are re-assigned from scratch by every clustering run
            # and signals.cluster_id above was just overwritten for the whole
            # corpus, so the previous cluster set is stale in its entirety.
            # Deleting only this refresh's rows would leave orphaned clusters
            # pointing at signals that now belong elsewhere.
            cur.execute("DELETE FROM clusters")
            kept = 0
            for cluster_id in sorted(set(int(l) for l in labels if l >= 0)):
                members = [r for r, l in zip(rows, labels) if l == cluster_id]
                if len(members) < self.min_cluster_size:
                    # Below-threshold groups are left unclustered rather than
                    # forced together: a two-article "theme" is noise, and
                    # feeding it to synthesis produces exactly the one-off
                    # signal SC-09 says must score low.
                    for member in members:
                        cur.execute("UPDATE signals SET cluster_id = NULL WHERE id = ?", (member["id"],))
                    continue
                keyphrases = self._keyphrases(members)
                cur.execute(
                    "INSERT INTO clusters (id, label, keyphrases, size, created_at, refresh_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (cluster_id, ", ".join(keyphrases[:4]), js(keyphrases), len(members), now, refresh_id),
                )
                kept += 1

        log.info("Formed %d clusters from %d signals.", kept, len(rows))
        return {"signals": len(rows), "clusters": kept}

    def _cluster(self, vectors: np.ndarray) -> np.ndarray:
        from sklearn.cluster import AgglomerativeClustering

        if len(vectors) < 2:
            return np.array([-1] * len(vectors))
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            metric="cosine",
            linkage="average",
        )
        labels = model.fit_predict(vectors)
        # Cap the cluster count by keeping the largest; the tail is long and
        # thin, and synthesis cost scales with cluster count.
        counts = Counter(labels.tolist())
        if len(counts) > self.max_clusters:
            keep = {label for label, _ in counts.most_common(self.max_clusters)}
            labels = np.array([l if l in keep else -1 for l in labels])
        return labels

    def _keyphrases(self, members: list[Any], top_n: int = 10) -> list[str]:
        """Per-cluster keyphrase extraction (Table 16 stage 4).

        Frequency over unigrams and bigrams, with vocabulary terms boosted so
        that the phrases handed to synthesis are the ones the taxonomy can
        actually act on.
        """
        vocab_terms = set()
        for vocabulary in (self.cfg.use_cases, self.cfg.technologies):
            for item in vocabulary:
                vocab_terms.add(item.label.lower())
                vocab_terms.update(s.lower() for s in item.synonyms)

        unigrams: Counter[str] = Counter()
        bigrams: Counter[str] = Counter()
        for member in members:
            tokens = [
                t.lower() for t in _TOKEN_RE.findall(f"{member['title']} {member['extract']}")
                if t.lower() not in _STOPWORDS
            ]
            unigrams.update(tokens)
            bigrams.update(f"{a} {b}" for a, b in zip(tokens, tokens[1:]))

        scored: dict[str, float] = {}
        for phrase, count in list(bigrams.items()) + list(unigrams.items()):
            if count < 2:
                continue
            weight = 1.0 + (len(phrase.split()) - 1) * 0.6      # prefer bigrams
            if phrase in vocab_terms:
                weight *= 2.5                                    # prefer actionable vocabulary
            scored[phrase] = count * weight

        ranked = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
        out: list[str] = []
        for phrase, _ in ranked:
            # Suppress unigrams already covered by a kept bigram.
            if any(phrase != kept and phrase in kept for kept in out):
                continue
            out.append(phrase)
            if len(out) >= top_n:
                break
        return out

    def cluster_payload(self, cluster_id: int, max_signals: int = 14) -> dict[str, Any]:
        """Assemble the evidence block handed to synthesis (§4.4.2).

        Signals are ordered by tier then recency, so the highest-authority
        evidence is what the model sees first and the tier-4 tail is what gets
        truncated when the block is capped.
        """
        cluster = self.db.query_one("SELECT * FROM clusters WHERE id = ?", (cluster_id,))
        signals = self.db.query(
            "SELECT id, title, extract, publisher, published_at, signal_type, tier, geographies, "
            "url, attributes FROM signals WHERE cluster_id = ? ORDER BY tier ASC, published_at DESC LIMIT ?",
            (cluster_id, max_signals),
        )
        return {
            "cluster_id": cluster_id,
            "label": cluster["label"] if cluster else "",
            "keyphrases": cluster["keyphrases"] if cluster else "[]",
            "signals": [dict(s) for s in signals],
        }
