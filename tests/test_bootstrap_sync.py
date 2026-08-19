"""The deployment must be able to ship new content without eating production.

`bootstrap.prepare` seeds the database once and then leaves it alone, so that a
redeploy cannot discard feedback or workflow state. That protection also stopped
new descriptions and briefs from ever arriving: the PDFs shipped, the rows did
not, and the UI reported that no brief existed. These tests pin both halves —
content moves forward, production state does not move at all.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3

import pytest

from radar import bootstrap


def _make(path, *, describe_for, feedback_note, when="2026-01-01T00:00:00+00:00",
          version=1, pdf=b"%PDF packaged", brief_path="/built/on/a/laptop.pdf"):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE opportunity_spaces (id TEXT PRIMARY KEY, merged_into TEXT, version INTEGER);
        CREATE TABLE topic_descriptions (opportunity_id TEXT PRIMARY KEY, generated_at TEXT NOT NULL,
                                         sections TEXT NOT NULL);
        CREATE TABLE topic_briefs (opportunity_id TEXT PRIMARY KEY, generated_at TEXT NOT NULL,
                                   path TEXT NOT NULL, filename TEXT NOT NULL,
                                   content_hash TEXT NOT NULL);
        CREATE TABLE topic_competition (opportunity_id TEXT PRIMARY KEY, computed_at TEXT NOT NULL,
                                        level TEXT NOT NULL);
        CREATE TABLE market_sizes (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                   opportunity_id TEXT NOT NULL, computed_at TEXT NOT NULL,
                                   method TEXT NOT NULL, tam_base REAL);
        CREATE TABLE feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, note TEXT);
        CREATE TABLE workflow_state (opportunity_id TEXT PRIMARY KEY, stage TEXT);
        """
    )
    for topic in ("OS001", "OS002"):
        conn.execute("INSERT INTO opportunity_spaces VALUES (?, NULL, ?)", (topic, version))
    for topic in describe_for:
        name = f"{topic}-opportunity-brief.pdf"
        conn.execute("INSERT INTO topic_descriptions VALUES (?, ?, ?)",
                     (topic, when, f"text for {topic}"))
        conn.execute("INSERT INTO topic_briefs VALUES (?, ?, ?, ?, ?)",
                     (topic, when, brief_path, name, hashlib.sha256(pdf).hexdigest()))
        conn.execute("INSERT INTO topic_competition VALUES (?, ?, 'high')", (topic, when))
        conn.execute("INSERT INTO market_sizes (opportunity_id, computed_at, method, tam_base) "
                     "VALUES (?, ?, 'bottom_up_adoption', 1.0)", (topic, when))
    conn.execute("INSERT INTO feedback (note) VALUES (?)", (feedback_note,))
    conn.execute("INSERT INTO workflow_state VALUES ('OS001', 'assessing')")
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def _clean_module_state():
    """STARTUP_ERROR and the notes are module globals, so one test's failure
    would otherwise be another test's assertion."""
    bootstrap.STARTUP_ERROR = None
    bootstrap.STARTUP_NOTES.clear()
    yield


@pytest.fixture
def deployment(tmp_path):
    """A live database seeded from an older package, plus the package that follows."""
    live = tmp_path / "home" / "radar.db"
    live.parent.mkdir()
    package = tmp_path / "package" / "data"
    package.mkdir(parents=True)
    (package / "briefs").mkdir()

    _make(live, describe_for=["OS001"], feedback_note="written in production")
    # Production then edits its own state: a stage move the package knows nothing of.
    conn = sqlite3.connect(live)
    conn.execute("UPDATE workflow_state SET stage = 'committed' WHERE opportunity_id = 'OS001'")
    conn.commit()
    conn.close()

    _make(package / "radar.db", describe_for=["OS001", "OS002"], feedback_note="dev artefact")
    return live, package


def test_new_content_arrives(deployment, monkeypatch):
    live, package = deployment
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)

    conn = sqlite3.connect(live)
    briefs = {row[0] for row in conn.execute("SELECT opportunity_id FROM topic_briefs")}
    assert briefs == {"OS001", "OS002"}, "the brief the package added must become visible"
    assert conn.execute("SELECT COUNT(*) FROM topic_descriptions").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM market_sizes").fetchone()[0] == 2, \
        "a surrogate-keyed table must be replaced per topic, not duplicated"
    conn.close()
    assert bootstrap.STARTUP_ERROR is None


def test_production_state_survives(deployment, monkeypatch):
    live, package = deployment
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)

    conn = sqlite3.connect(live)
    assert conn.execute("SELECT stage FROM workflow_state WHERE opportunity_id='OS001'") \
        .fetchone()[0] == "committed", "a deployment must not roll back a stage decision"
    notes = [row[0] for row in conn.execute("SELECT note FROM feedback")]
    assert notes == ["written in production"], "feedback is production's, never the package's"
    conn.close()


def test_second_start_is_a_no_op(deployment, monkeypatch):
    """The container restarts far more often than it is deployed."""
    live, package = deployment
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)
    bootstrap.STARTUP_NOTES.clear()
    bootstrap.prepare(live, package.parent)
    assert not [n for n in bootstrap.STARTUP_NOTES if "content sync:" in n], \
        "an unchanged package must not re-sync on every cold start"


def test_updated_brief_file_replaces_the_stale_one(deployment, monkeypatch, tmp_path):
    live, package = deployment
    served = tmp_path / "served"
    served.mkdir()
    (served / "OS001-opportunity-brief.pdf").write_bytes(b"%PDF old")
    (package / "briefs" / "OS001-opportunity-brief.pdf").write_bytes(b"%PDF packaged")
    monkeypatch.setenv("RADAR_BRIEF_DIR", str(served))
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")

    bootstrap.prepare(live, package.parent)
    assert (served / "OS001-opportunity-brief.pdf").read_bytes() == b"%PDF packaged", \
        "the row names the packaged PDF, so the packaged PDF belongs on disk"


def test_a_broken_package_does_not_break_startup(deployment, monkeypatch):
    live, package = deployment
    (package / "radar.db").write_bytes(b"this is not a database")
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)
    assert bootstrap.STARTUP_ERROR is None, "content is not worth a crash loop"
    conn = sqlite3.connect(live)
    assert conn.execute("SELECT COUNT(*) FROM topic_briefs").fetchone()[0] == 1
    conn.close()


def test_a_regeneration_in_production_is_not_rolled_back(deployment, monkeypatch, tmp_path):
    """The UI can regenerate any of these — each costs a paid model call.

    The allow-list once claimed nothing in the UI wrote them, which was false, so
    the sync would have reverted a curator's work on the next deploy and charged
    them for it twice.
    """
    live, package = deployment
    served = tmp_path / "served"
    served.mkdir()
    (package / "briefs" / "OS001-opportunity-brief.pdf").write_bytes(b"%PDF packaged")
    (served / "OS001-opportunity-brief.pdf").write_bytes(b"%PDF regenerated in production")

    later = "2099-01-01T00:00:00+00:00"
    conn = sqlite3.connect(live)
    conn.execute("UPDATE topic_descriptions SET generated_at=?, sections='the curator regenerated this' "
                 "WHERE opportunity_id='OS001'", (later,))
    conn.execute("UPDATE topic_briefs SET generated_at=?, content_hash=? WHERE opportunity_id='OS001'",
                 (later, hashlib.sha256(b"%PDF regenerated in production").hexdigest()))
    conn.execute("UPDATE topic_competition SET computed_at=?, level='low' WHERE opportunity_id='OS001'",
                 (later,))
    conn.execute("UPDATE market_sizes SET computed_at=?, tam_base=999.0 WHERE opportunity_id='OS001'",
                 (later,))
    conn.commit()
    conn.close()

    monkeypatch.setenv("RADAR_BRIEF_DIR", str(served))
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)

    conn = sqlite3.connect(live)
    assert conn.execute("SELECT sections FROM topic_descriptions WHERE opportunity_id='OS001'") \
        .fetchone()[0] == "the curator regenerated this"
    assert conn.execute("SELECT level FROM topic_competition WHERE opportunity_id='OS001'") \
        .fetchone()[0] == "low"
    assert conn.execute("SELECT tam_base FROM market_sizes WHERE opportunity_id='OS001'") \
        .fetchone()[0] == 999.0
    # ...while content the package alone carries still arrives.
    assert conn.execute("SELECT COUNT(*) FROM topic_briefs WHERE opportunity_id='OS002'") \
        .fetchone()[0] == 1
    conn.close()
    assert (served / "OS001-opportunity-brief.pdf").read_bytes() == b"%PDF regenerated in production", \
        "the row describes production's PDF, so production's PDF stays on disk"


def test_topics_travel_with_their_content(deployment, monkeypatch):
    """opportunity_spaces.version is what marks a brief stale.

    Shipping briefs while freezing the topics they describe flagged every one of
    them 'the topic has been refreshed since' the moment the pipeline bumped a
    version.
    """
    live, package = deployment
    conn = sqlite3.connect(package / "radar.db")
    conn.execute("UPDATE opportunity_spaces SET version = 7")
    conn.commit()
    conn.close()

    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)

    conn = sqlite3.connect(live)
    assert conn.execute("SELECT version FROM opportunity_spaces WHERE id='OS001'").fetchone()[0] == 7
    conn.close()


def test_a_partial_sync_is_retried_not_recorded(deployment, monkeypatch):
    """A marker written after a skipped table suppresses that table forever."""
    live, package = deployment
    conn = sqlite3.connect(package / "radar.db")
    conn.execute("DROP TABLE topic_competition")
    conn.commit()
    conn.close()

    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(live, package.parent)
    assert not (live.parent / ".content-fingerprint").exists(), \
        "an incomplete sync must not be recorded as done"


def test_a_checkout_is_left_alone(tmp_path, monkeypatch):
    """In a checkout the served database IS the packaged one."""
    package = tmp_path / "data"
    package.mkdir()
    db = package / "radar.db"
    _make(db, describe_for=["OS001"], feedback_note="local")
    monkeypatch.setenv("RADAR_SQLITE_JOURNAL_MODE", "DELETE")
    bootstrap.prepare(db, tmp_path)
    assert not [n for n in bootstrap.STARTUP_NOTES if "content sync" in n]
    assert not (package / ".content-fingerprint").exists()
