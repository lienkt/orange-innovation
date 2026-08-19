"""Evidence enrichment (§4.4.5 "new signals attach to the existing topic")."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from radar.config import get_config
from radar.db import Database, js
from radar.embeddings import Embedder
from radar.pipeline.enrich import Enricher

REF = dt.date(2026, 8, 18)


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "e.db")
    database.init_schema()
    with database.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
               (id, vertical, use_case, technology, statement, state, first_seen,
                last_refresh, pipeline_version)
               VALUES ('OS001','manufacturing','ot_ics_security','siem_soar',
                       'OT security monitoring for industrial control systems in manufacturing.',
                       'watchlist','2026-01-01','2026-08-18','0.1.0')"""
        )
    return database


def add_signal(db, sid: str, title: str, extract: str, vector, attributes=None,
               published: str = "2026-08-01"):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO signals (id, source_id, publisher, title, url, published_at,
               ingested_at, tier, extract, relevance, embedding, attributes, pipeline_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid, "test", "example.com", title, f"https://example.com/{sid}", published,
             "2026-08-18T00:00:00", 2, extract, 1.0,
             Embedder.to_blob(np.asarray(vector, dtype=np.float32)),
             js(attributes or {}), "0.1.0"),
        )


def test_a_corroborated_signal_is_attached(cfg, db):
    """The whole point: a topic created earlier must pick up new evidence."""
    enricher = Enricher(cfg, db, Embedder())
    vector = enricher.embedder.encode(
        ["OT security monitoring for industrial control systems in manufacturing."]
    )[0]
    add_signal(db, "SIG-1", "ICS security advisory for plant operators",
               "Industrial control system security monitoring guidance", vector)
    result = enricher.run("R-test", REF)
    assert result["attached"] == 1
    assert db.query_one("SELECT COUNT(*) n FROM opportunity_signals")["n"] == 1


def test_similarity_without_corroboration_is_refused(cfg, db):
    """Embeddings rate unrelated security items as close. Requiring a second,
    independent reason is what stops enrichment inflating every signal count —
    which would corrupt market signal strength, diversity and momentum."""
    enricher = Enricher(cfg, db, Embedder())
    # Same vector as the topic, so similarity is maximal, but the text shares no
    # vocabulary term and there is no CPV to fall back on.
    vector = enricher.embedder.encode(
        ["OT security monitoring for industrial control systems in manufacturing."]
    )[0]
    add_signal(db, "SIG-2", "Quarterly results announcement", "The company reported results.", vector)
    result = enricher.run("R-test", REF)
    assert result["attached"] == 0
    assert result["rejected_similarity_without_corroboration"] >= 1


def test_a_procurement_notice_corroborates_through_cpv(cfg, db):
    """A tender's prose is boilerplate; its CPV is the real evidence."""
    enricher = Enricher(cfg, db, Embedder())
    vector = enricher.embedder.encode(
        ["OT security monitoring for industrial control systems in manufacturing."]
    )[0]
    add_signal(db, "SIG-3", "Contract notice", "Framework agreement, lot 2, see annex.",
               vector, attributes={"cpv": ["35120000"]})
    result = enricher.run("R-test", REF)
    assert result["attached"] == 1


def test_future_signals_are_never_attached(cfg, db):
    """FR-35 leakage control applies to enrichment as much as to collection."""
    enricher = Enricher(cfg, db, Embedder())
    vector = enricher.embedder.encode(
        ["OT security monitoring for industrial control systems in manufacturing."]
    )[0]
    add_signal(db, "SIG-4", "ICS security monitoring for plants",
               "industrial control system security", vector, published="2027-01-01")
    result = enricher.run("R-test", REF)
    assert result["attached"] == 0


def test_attachment_is_idempotent(cfg, db):
    """A second refresh must not double-count evidence — signal volume feeds
    market signal strength directly."""
    enricher = Enricher(cfg, db, Embedder())
    vector = enricher.embedder.encode(
        ["OT security monitoring for industrial control systems in manufacturing."]
    )[0]
    add_signal(db, "SIG-5", "ICS security monitoring advisory",
               "industrial control system security monitoring", vector)
    first = enricher.run("R-1", REF)
    second = enricher.run("R-2", REF)
    assert first["attached"] == 1
    assert second["attached"] == 0
    assert db.query_one("SELECT COUNT(*) n FROM opportunity_signals")["n"] == 1


def test_enrichment_never_writes_a_claim(cfg, db):
    """§4.4.4: an uncited claim is forbidden, and only synthesis may write
    claims. Enrichment adds evidence, never prose."""
    enricher = Enricher(cfg, db, Embedder())
    vector = enricher.embedder.encode(
        ["OT security monitoring for industrial control systems in manufacturing."]
    )[0]
    add_signal(db, "SIG-6", "ICS security monitoring", "industrial control system security", vector)
    enricher.run("R-test", REF)
    row = db.query_one("SELECT why_hot FROM opportunity_spaces WHERE id='OS001'")
    assert row["why_hot"] in ("[]", None, "")
