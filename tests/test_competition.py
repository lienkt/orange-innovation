"""Competitive intensity invariants (§4.3.3, Table 27).

The failure modes worth testing are the ones that would put something wrong in
front of a customer: a competitor asserted without evidence and not marked as
such, a partner quietly refiled as a pure competitor, an alias matching inside
an unrelated word, and a level that no longer distinguishes anything because a
long tail of weak matches saturates it.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.competition import CompetitionAnalyser, competition_for_topic
from radar.config import get_config
from radar.db import Database, js


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


def seed_topic(db, topic_id="OS001", *, vertical="manufacturing",
               use_case="predictive_maintenance", technology="zero_trust_architecture",
               domains=("cybersecurity",)):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
                 (id, version, vertical, use_case, technology, statement, domains, personas,
                  geographies, state, first_seen, last_refresh, pipeline_version)
               VALUES (?,1,?,?,?,?,?,'[]','[]','active','2026-01-01','2026-08-01','0.1.0')""",
            (topic_id, vertical, use_case, technology, "A specific statement", js(list(domains))),
        )
    return dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,)))


def attach_signal(db, topic_id, signal_id, title, extract="", published="2026-07-01"):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO signals
                 (id, source_id, publisher, title, url, published_at, ingested_at, tier, extract,
                  pipeline_version)
               VALUES (?, 'news', 'example.com', ?, 'https://example.invalid', ?, ?, 2, ?, '0.1.0')""",
            (signal_id, title, published, published, extract),
        )
        cur.execute(
            "INSERT INTO opportunity_signals (opportunity_id, signal_id, attached_at, refresh_id) "
            "VALUES (?,?,?, 'R-test')",
            (topic_id, signal_id, published),
        )


# ---------------------------------------------------------------------------
# Evidence versus structure
# ---------------------------------------------------------------------------

def test_a_competitor_named_in_the_evidence_is_marked_evidenced_and_cites_it(cfg, db):
    """LK-08's principle: a claim nobody can check will still reach a customer."""
    topic = seed_topic(db)
    attach_signal(db, topic["id"], "SIG-1",
                  "Zscaler zero trust reaches industrial networks",
                  "Zscaler extends zero trust network access into OT environments.")
    assessment = CompetitionAnalyser(cfg, db).assess(topic)

    zscaler = next(c for c in assessment["competitors"] if c["id"] == "zscaler_comp")
    assert zscaler["basis"] == "evidenced"
    assert zscaler["mentions"][0]["signal_id"] == "SIG-1"
    assert "Zscaler" in zscaler["mentions"][0]["quote"]


def test_structural_presence_is_listed_but_not_claimed_as_evidence(cfg, db):
    """The register knowing they sell this is not proof they are in the deal."""
    topic = seed_topic(db)
    assessment = CompetitionAnalyser(cfg, db).assess(topic)
    assert assessment["competitors"], "a zero-trust topic must match the security specialists"
    assert all(c["basis"] == "structural" for c in assessment["competitors"])
    assert assessment["counts"]["evidenced"] == 0


def test_evidence_outranks_structure_in_the_listing(cfg, db):
    """What the corpus has actually seen goes first — it is what a rep can quote."""
    topic = seed_topic(db)
    attach_signal(db, topic["id"], "SIG-1", "Bechtle wins zero trust rollout",
                  "Bechtle deploys zero trust for a manufacturer.")
    assessment = CompetitionAnalyser(cfg, db).assess(topic)
    # Bechtle is a regional integrator (low type weight) but it is evidenced,
    # so it must outrank the structurally-matched heavyweights.
    assert assessment["competitors"][0]["id"] == "bechtle"


def test_aliases_match_on_word_boundaries(cfg, db):
    """'Colt' inside 'Colten Industries' is not Colt Technology Services."""
    topic = seed_topic(db, technology="sd_wan", domains=("connectivity_solutions",))
    attach_signal(db, topic["id"], "SIG-1", "Colten Industries upgrades its network",
                  "Colten Industries selected an SD-WAN provider.")
    assessment = CompetitionAnalyser(cfg, db).assess(topic)
    colt = next((c for c in assessment["competitors"] if c["id"] == "colt_technology"), None)
    assert colt is None or colt["basis"] == "structural"


# ---------------------------------------------------------------------------
# Partner-and-competitor is a fact, not a category error
# ---------------------------------------------------------------------------

def test_a_partner_who_also_competes_keeps_both_labels(cfg, db):
    """Microsoft is a Gold partner and the default alternative in AI deals.

    A salesperson needs both halves; filing it under one hides the harder half.
    """
    topic = seed_topic(db, technology="generative_ai", use_case="document_intelligence",
                       domains=("cx_customer_experience",))
    assessment = CompetitionAnalyser(cfg, db).assess(topic)
    microsoft = next(c for c in assessment["competitors"] if c["id"] == "microsoft_azure")
    assert microsoft["relationship"] == "both"
    assert microsoft["partner_id"] == "microsoft"
    assert assessment["counts"]["partners_who_also_compete"] >= 1


# ---------------------------------------------------------------------------
# The level has to discriminate
# ---------------------------------------------------------------------------

def test_level_is_scored_over_the_listed_set_not_the_whole_register(cfg, db):
    """§4.6's score-compression guard, applied to competition.

    Summing a fifty-entry tail of weak domain matches would rate every security
    topic identically, and the level would stop meaning anything.
    """
    topic = seed_topic(db)
    analyser = CompetitionAnalyser(cfg, db)
    assessment = analyser.assess(topic)
    listed = assessment["competitors"]
    assert assessment["score"] == pytest.approx(sum(c["contribution"] for c in listed))
    assert len(listed) <= cfg.settings["competition"]["max_listed"]


def test_a_thin_field_scores_lower_than_a_crowded_one(cfg, db):
    """Two topics, two fields: the ordering must survive the weighting."""
    crowded = seed_topic(db, "OS001", technology="zero_trust_architecture",
                         domains=("cybersecurity",))
    thin = seed_topic(db, "OS002", technology="quantum_key_distribution",
                      use_case="post_quantum_migration", domains=("cybersecurity",))
    analyser = CompetitionAnalyser(cfg, db)
    assert analyser.assess(crowded)["score"] > analyser.assess(thin)["score"]


def test_level_bands_come_from_configuration(cfg, db):
    """NFR-11: a threshold is configuration, and the inputs travel with the result."""
    topic = seed_topic(db)
    assessment = CompetitionAnalyser(cfg, db).assess(topic)
    assert assessment["inputs"]["bands"] == cfg.settings["competition"]["bands"]
    assert assessment["level"] in ("none", "low", "medium", "high")


def test_assessment_is_stored_with_the_register_version(cfg, db):
    """A competitor list is only as good as the register it came from."""
    topic = seed_topic(db)
    CompetitionAnalyser(cfg, db).run(topic_ids=[topic["id"]])
    stored = competition_for_topic(db, topic["id"])
    assert stored["register_version"] == cfg.competitor_version
    assert stored["level"] and stored["competitors"]


def test_competition_never_touches_the_published_scores(cfg, db):
    """SC-12: a crowded field and a weak position are different facts.

    Competitive intensity is a fourth quantity; running it must not write a
    score row or alter a topic.
    """
    topic = seed_topic(db)
    CompetitionAnalyser(cfg, db).run(topic_ids=[topic["id"]])
    assert db.query_one("SELECT COUNT(*) n FROM scores")["n"] == 0
    assert db.query_one("SELECT version FROM opportunity_spaces WHERE id = ?",
                        (topic["id"],))["version"] == 1
