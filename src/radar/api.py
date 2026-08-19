"""Read API (FR-27, pipeline stage 7).

FR-27: "Expose a read API so that topic data can be consumed by other Orange
tools." It is priority C in the requirements, but the React frontend needs it,
so it is built now and serves both.

The API is READ-ONLY except for the two write paths the requirements demand:
feedback capture (FR-23, FR-34, DR-15) and curator link confirmation (LK-06).
Nothing here mutates a score or a topic — that is the pipeline's job, and
keeping the boundary sharp is what makes SC-11 reproducibility checkable.
"""

from __future__ import annotations

import datetime as dt
import logging
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import bootstrap
from .brief import BriefBuilder, brief_for_topic, brief_path
from .competition import CompetitionAnalyser, LEVEL_MEANING, competition_for_topic
from .config import get_config
from .db import Database, js
from .graph import LINK_MEANING, Linker
from .llm import LLMClient
from .pipeline.describe import DescriptionGenerator, description_for_topic
from .reference import ReferenceDataFetcher, reference_status
from .sizing import MarketSizer, sizes_for_topic
from .workflow import (AXIS_ANCHORS, AXIS_LABELS, ROLE_AXIS, STAGE_LABELS,
                       STAGE_OWNER_ROLE, STAGES, WorkflowService)
from .readmodel import SORTS, ReadModel

log = logging.getLogger(__name__)

app = FastAPI(
    title="Orange Business Innovation Radar",
    description="Read API for the Opportunity Spaces / Innovation Radar MVP.",
    version="0.1.0",
)

# The React dev server runs on a different origin. In production the built
# bundle is served from THIS app (see the static mount at the bottom of this
# file), so the deployed origin needs no CORS entry at all — the list stays
# scoped to the local dev servers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_cfg = get_config()
# Prepare persistent storage BEFORE opening the database. On App Service the
# database lives on an SMB share that cannot host a WAL journal, and the file
# has to be seeded from the deployment package on first boot — see
# radar.bootstrap for why both of those are done here rather than in a shell
# script wrapped around the process.
bootstrap.prepare(Path(_cfg.db_path), Path(__file__).resolve().parents[2])

try:
    _db = Database(_cfg.db_path)
except Exception as exc:  # noqa: BLE001 — an unusable path must not kill the import
    bootstrap.STARTUP_ERROR = f"{type(exc).__name__}: {exc}"
    log.error("Database path unusable (%s); serving in a degraded state", exc)
    _db = Database(Path(tempfile.gettempdir()) / "radar-unavailable.db")

try:
    # Idempotent, and it means a database created before the sizing, competition
    # and brief tables existed still serves those endpoints rather than 500ing
    # on a missing table.
    _db.init_schema()
except Exception as exc:  # noqa: BLE001
    # NOT fatal. A process that raises at import is restarted by the platform,
    # and enough restarts exhaust a Free plan's quota — which also disables the
    # log endpoints, so the failure hides its own cause. Recording it and
    # answering 503 with the reason is strictly more useful than dying.
    bootstrap.STARTUP_ERROR = f"{type(exc).__name__}: {exc}"
    log.error("Database initialisation failed: %s", exc)

_read = ReadModel(_cfg, _db)
_workflow = WorkflowService(_cfg, _db)


def _llm() -> LLMClient:
    """Built per request rather than at import: a missing API key should fail
    the one call that needs a model, not the whole read API."""
    return LLMClient(max_retries=_cfg.settings["llm"]["max_retries"])


def _vocab_payload(vocab) -> list[dict[str, Any]]:
    return [
        {"id": item.id, "label": item.label, "definition": item.definition}
        for item in vocab
    ]


@app.get("/api/meta")
def meta() -> dict[str, Any]:
    """Controlled vocabularies, role modes and filter dimensions (AC-04, FR-12)."""
    last = _db.query_one(
        "SELECT id, started_at, finished_at, reference_date, is_replay, weight_set "
        "FROM refreshes ORDER BY started_at DESC LIMIT 1"
    )
    return {
        "verticals": _vocab_payload(_cfg.verticals),
        "use_cases": _vocab_payload(_cfg.use_cases),
        "technologies": _vocab_payload(_cfg.technologies),
        "domains": _vocab_payload(_cfg.domains),
        "personas": _vocab_payload(_cfg.personas),
        "signal_types": _vocab_payload(_cfg.signal_types),
        "horizons": ["now", "next", "later"],
        "states": ["candidate", "watchlist", "active", "fading", "dormant", "rejected"],
        "link_types": [
            {"id": key, "meaning": value[0], "definition": value[1], "owner": value[2], "action": value[3]}
            for key, value in LINK_MEANING.items()
        ],
        "roles": [
            {
                "id": mode["id"],
                "label": mode["label"],
                "description": mode["description"],
                "primary_action": mode["primary_action"],
                "link_types": mode["link_types"],
                "acceptance": mode.get("acceptance"),
                "ranking": mode["ranking"],
            }
            for mode in _cfg.role_modes_raw["modes"]
        ],
        "sorts": [{"id": key, "label": label} for key, label in SORTS.items()],
        "competition_levels": [
            {"id": level, "meaning": meaning} for level, meaning in LEVEL_MEANING.items()
        ],
        "sizing_version": _cfg.sizing_version,
        "competitor_register_version": _cfg.competitor_version,
        "weight_set": _cfg.weight_set,
        "attractiveness_weights": _cfg.attractiveness_weights,
        "right_to_win_weights": _cfg.right_to_win_weights,
        "pipeline_version": _cfg.pipeline_version,
        "last_refresh": dict(last) if last else None,
        "strategy": {
            "plan": _cfg.strategy["plan"],
            "period": _cfg.strategy["period"],
            "ambitions": [
                {"id": a["id"], "label": a["label"], "implication": a["radar_implication"]}
                for a in _cfg.strategy["ambitions"]
            ],
            "privileged_verticals": _cfg.strategy.get("privileged_verticals", {}),
        },
    }


@app.get("/api/view")
def view(
    role: str = Query("strategist"),
    vertical: list[str] | None = Query(None),
    domain: list[str] | None = Query(None),
    persona: list[str] | None = Query(None),
    geography: list[str] | None = Query(None),
    horizon: list[str] | None = Query(None),
    state: list[str] | None = Query(None),
    competition: list[str] | None = Query(None),
    has_brief: bool = Query(False),
    q: str | None = Query(None),
    limit: int | None = Query(None),
    sort: str = Query("rank"),
) -> dict[str, Any]:
    """The capped, filtered, role-ranked radar view (FR-13, FR-21, FR-22, AC-05)."""
    if role not in _cfg.role_ids:
        raise HTTPException(400, f"Unknown role {role!r}. Known: {_cfg.role_ids}")
    if sort not in SORTS:
        raise HTTPException(400, f"Unknown sort {sort!r}. Known: {list(SORTS)}")
    filters = {
        key: value
        for key, value in (
            ("vertical", vertical), ("domain", domain), ("persona", persona),
            ("geography", geography), ("horizon", horizon), ("state", state),
            ("competition", competition), ("has_brief", has_brief or None), ("q", q),
        )
        if value
    }
    return _read.view(role, filters, limit, sort=sort)


@app.get("/api/topics/{topic_id}")
def topic(topic_id: str) -> dict[str, Any]:
    """Topic detail with the full score decomposition (NFR-01, NFR-02, NFR-03)."""
    result = _read.topic(topic_id)
    if result is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return result


@app.get("/api/topics/{topic_id}/history")
def history(topic_id: str) -> dict[str, Any]:
    """Score trajectory with the weight-set comparability warning (FR-20, §4.6)."""
    return _read.history(topic_id)


@app.get("/api/whitespace")
def whitespace(
    min_attractiveness: float = Query(55.0),
    vertical: list[str] | None = Query(None),
    domain: list[str] | None = Query(None),
    persona: list[str] | None = Query(None),
    geography: list[str] | None = Query(None),
    horizon: list[str] | None = Query(None),
    competition: list[str] | None = Query(None),
    q: str | None = Query(None),
) -> dict[str, Any]:
    """High attractiveness, no path from the portfolio (FR-32, §4.5.5).

    Takes the same filters as the radar view: the rail is on screen on this tab
    too, and a control that is offered has to work.
    """
    filters = {
        key: value
        for key, value in (
            ("vertical", vertical), ("domain", domain), ("persona", persona),
            ("geography", geography), ("horizon", horizon), ("competition", competition), ("q", q),
        )
        if value
    }
    unfiltered = _read.white_space(min_attractiveness)
    rows = _read.white_space_filtered(min_attractiveness, filters)
    return {"min_attractiveness": min_attractiveness, "count": len(rows),
            "total_unfiltered": len(unfiltered), "topics": rows}


@app.get("/api/orphan-offers")
def orphan_offers() -> dict[str, Any]:
    """Offers with no live opportunity space — a portfolio-decay signal (FR-33)."""
    rows = Linker(_cfg, _db).offers_without_topics()
    return {"count": len(rows), "offers": rows}


@app.get("/api/coverage")
def coverage() -> dict[str, Any]:
    """Language, geography, tier and source coverage as a reported metric (NFR-08)."""
    return _read.coverage()


@app.get("/api/refreshes")
def refreshes(limit: int = Query(20)) -> dict[str, Any]:
    """Refresh log (FR-19, NFR-04, NFR-10)."""
    rows = _db.query(
        "SELECT id, started_at, finished_at, reference_date, is_replay, pipeline_version, weight_set "
        "FROM refreshes ORDER BY started_at DESC LIMIT ?", (limit,)
    )
    return {"refreshes": [dict(r) for r in rows]}


@app.get("/api/graph/node/{node_id:path}")
def graph_node(node_id: str) -> dict[str, Any]:
    """Reverse query: which topics attach to this asset (LK-09)."""
    node = _db.query_one("SELECT * FROM graph_nodes WHERE id = ?", (node_id,))
    if node is None:
        raise HTTPException(404, f"No such node: {node_id}")
    rows = _db.query(
        """SELECT o.id, o.statement, o.state, l.link_type, l.confidence
           FROM opportunity_links l JOIN opportunity_spaces o ON o.id = l.opportunity_id
           WHERE l.node_id = ? AND l.rejected = 0 AND o.merged_into IS NULL""",
        (node_id,),
    )
    return {"node": dict(node), "topics": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Write paths — feedback and curation only
# ---------------------------------------------------------------------------


class FeedbackIn(BaseModel):
    role: str
    kind: str = Field(description="rating | comparison | override | engagement")
    opportunity_id: str | None = None
    other_opportunity_id: str | None = None
    verdict: str | None = Field(None, description="useful|not_useful|wrong for ratings; left|right for comparisons")
    reason: str | None = None
    exposure_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Rank shown, view, filters, exploration slot. Required by DR-15 so engagement "
                    "can be inverse-propensity weighted against exposure bias (§4.7.6).",
    )


@app.post("/api/feedback")
def submit_feedback(payload: FeedbackIn) -> dict[str, Any]:
    """FR-23 / FR-34 / DR-15.

    §4.7.4: "ask for comparisons, not scores. People are unreliable at rating a
    topic 73 out of 100 and reliable at saying which of two topics they would
    rather take into a meeting." Both shapes are accepted; the comparison shape
    is the one that produces usable ranking labels.
    """
    if payload.role not in _cfg.role_ids:
        raise HTTPException(400, f"Unknown role {payload.role!r}")
    if payload.kind not in ("rating", "comparison", "override", "engagement"):
        raise HTTPException(400, f"Unknown feedback kind {payload.kind!r}")
    if payload.kind == "comparison" and not payload.other_opportunity_id:
        raise HTTPException(400, "A comparison needs other_opportunity_id")

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with _db.cursor() as cur:
        cur.execute(
            """INSERT INTO feedback (created_at, role, kind, opportunity_id, other_opportunity_id,
                                     verdict, reason, exposure_context)
               VALUES (?,?,?,?,?,?,?,?)""",
            (now, payload.role, payload.kind, payload.opportunity_id, payload.other_opportunity_id,
             payload.verdict, payload.reason, js(payload.exposure_context)),
        )
    return {"stored": True, "at": now}


@app.get("/api/feedback/stats")
def feedback_stats() -> dict[str, Any]:
    """How close the learned-ranking model is to being trainable (§4.7.4).

    "Roughly three to six hundred comparisons per role is enough to fit a ranker
    over the feature set above."
    """
    rows = _db.query(
        "SELECT role, kind, COUNT(*) AS n FROM feedback GROUP BY role, kind"
    )
    by_role: dict[str, dict[str, int]] = {}
    for row in rows:
        by_role.setdefault(row["role"], {})[row["kind"]] = row["n"]
    return {
        "by_role": by_role,
        "comparisons_needed_per_role": {"min": 300, "max": 600},
        "note": "Problem A (relevance ranking) needs human labels; Problem B "
                "(emergence forecasting) is self-supervised from historical replay (§4.7.2).",
    }


class LinkDecisionIn(BaseModel):
    pattern: str
    decision: str = Field(description="confirmed | rejected")
    curator: str
    reason: str | None = None


@app.post("/api/links/decision")
def link_decision(payload: LinkDecisionIn) -> dict[str, Any]:
    """LK-06 — curator confirmation of a link pattern.

    "Confirmations and rejections are stored and become training data" (§4.5.4).
    The decision takes effect on the next `link` stage run.
    """
    if payload.decision not in ("confirmed", "rejected"):
        raise HTTPException(400, "decision must be 'confirmed' or 'rejected'")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with _db.cursor() as cur:
        cur.execute(
            "INSERT OR REPLACE INTO link_pattern_decisions (pattern, decision, curator, reason, decided_at) "
            "VALUES (?,?,?,?,?)",
            (payload.pattern, payload.decision, payload.curator, payload.reason, now),
        )
    return {"stored": True, "applies_on": "next `radar refresh --stages link` run"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    counts = {}
    for table in ("signals", "opportunity_spaces", "graph_nodes", "opportunity_links", "feedback"):
        row = _db.query_one(f"SELECT COUNT(*) AS n FROM {table}")
        counts[table] = row["n"] if row else 0
    return {"ok": True, "counts": counts, "weight_set": _cfg.weight_set}


# ---------------------------------------------------------------------------
# Collaboration workflow (FR-25, §4.10)
# ---------------------------------------------------------------------------


@app.get("/api/workflow/board")
def workflow_board(role: str | None = Query(None)) -> dict[str, Any]:
    """Stage-gate board (§4.10 model A).

    Optionally ranked for a role, so a stage owner sees their column in their
    own priority order rather than an arbitrary one.
    """
    topics = _read.topics(states=("active", "watchlist", "fading", "candidate"))
    if role:
        if role not in _cfg.role_ids:
            raise HTTPException(400, f"Unknown role {role!r}")
        # Order for the role, but do NOT filter: the board is a workflow view,
        # and a stage owner has to see everything in their column.
        topics = _read.rank(topics, role, apply_role_filter=False)
    return _workflow.board(topics)


@app.get("/api/workflow/meta")
def workflow_meta() -> dict[str, Any]:
    """Stages, per-role axes and the rating anchors the UI renders."""
    return {
        "stages": [
            {"id": s, "label": STAGE_LABELS[s], "owner_role": STAGE_OWNER_ROLE.get(s)}
            for s in STAGES
        ],
        "terminal_stages": [
            {"id": s, "label": STAGE_LABELS[s]} for s in ("parked", "rejected")
        ],
        "role_axis": ROLE_AXIS,
        "axis_labels": AXIS_LABELS,
        "anchors": AXIS_ANCHORS,
        "divergence_threshold": _cfg.settings["workflow"]["divergence_threshold"],
        "conviction_ranking_weight": _cfg.settings["workflow"]["conviction_ranking_weight"],
    }


class AssessmentIn(BaseModel):
    role: str = Field(description="strategist | sales | presales")
    rating: int = Field(ge=0, le=5)
    author: str
    confidence: int = Field(3, ge=1, le=5)
    rationale: str | None = None


@app.post("/api/topics/{topic_id}/assessment")
def submit_assessment(topic_id: str, payload: AssessmentIn) -> dict[str, Any]:
    """§4.10 model C — each role rates its own axis.

    §4.7.4: "ask for comparisons, not scores ... People are unreliable at rating
    a topic 73 out of 100". Hence a 0-5 scale with written anchors, and a
    separate confidence, rather than a free percentage.
    """
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    try:
        conviction = _workflow.record_assessment(
            topic_id, payload.role, payload.rating, payload.author,
            payload.confidence, payload.rationale,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    topic = _read.topic(topic_id)
    return {
        "conviction": conviction,
        "divergence": topic.get("divergence"),
        "attractiveness": (topic.get("attractiveness") or {}).get("score"),
        "right_to_win": (topic.get("right_to_win") or {}).get("score"),
    }


class TransitionIn(BaseModel):
    to_stage: str
    actor: str
    actor_role: str
    reason: str | None = None
    owner: str | None = None


@app.post("/api/topics/{topic_id}/stage")
def move_stage(topic_id: str, payload: TransitionIn) -> dict[str, Any]:
    """Advance, park or reject a topic in the stage gate (§4.10 model A)."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    try:
        return _workflow.transition(
            topic_id, payload.to_stage, payload.actor, payload.actor_role,
            payload.reason, payload.owner,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/topics/{topic_id}/transitions")
def transitions(topic_id: str) -> dict[str, Any]:
    rows = _db.query(
        "SELECT * FROM workflow_transitions WHERE opportunity_id = ? ORDER BY created_at DESC",
        (topic_id,),
    )
    return {"transitions": [dict(r) for r in rows]}


@app.get("/api/divergence")
def divergence_review() -> dict[str, Any]:
    """§4.10 model C: "disagreement becomes information rather than friction".

    The review queue — topics where the team and the evidence disagree enough to
    be worth a human looking.
    """
    out = []
    for topic in _read.topics(states=("active", "watchlist", "fading", "candidate")):
        if topic.get("divergence"):
            out.append({
                "id": topic["id"],
                "statement": topic["statement"],
                "attractiveness": (topic.get("attractiveness") or {}).get("score"),
                "right_to_win": (topic.get("right_to_win") or {}).get("score"),
                "conviction": topic.get("conviction"),
                "divergence": topic["divergence"],
                "workflow": topic.get("workflow"),
            })
    out.sort(key=lambda t: max(abs(f["delta"]) for f in t["divergence"]["flags"]), reverse=True)
    return {"count": len(out), "topics": out}


# ---------------------------------------------------------------------------
# Aggregates for the charts
# ---------------------------------------------------------------------------


@app.get("/api/analytics/grid")
def analytics_grid() -> dict[str, Any]:
    """Vertical x domain occupancy, with reference density per vertical.

    This is the white-space map §4.5.5 asks for, as a grid rather than a
    document: where topics exist, and where Orange has proof points to sell them.
    """
    topics = _read.topics(states=("active", "watchlist", "fading", "candidate"))
    verticals = [v.id for v in _cfg.verticals]
    domains = [d.id for d in _cfg.domains]
    cells: dict[str, dict[str, Any]] = {}
    for topic in topics:
        for domain in topic["domains"]:
            key = f"{topic['triple']['vertical']}|{domain}"
            cell = cells.setdefault(key, {"count": 0, "best_attractiveness": 0.0, "gap": False})
            cell["count"] += 1
            cell["best_attractiveness"] = max(
                cell["best_attractiveness"], (topic.get("attractiveness") or {}).get("score", 0.0)
            )
            cell["gap"] = cell["gap"] or topic["evidence_gap_warning"]
    return {
        "verticals": [{"id": v.id, "label": v.label} for v in _cfg.verticals],
        "domains": [{"id": d.id, "label": d.label} for d in _cfg.domains],
        "cells": cells,
        "max_count": max([c["count"] for c in cells.values()], default=0),
    }


@app.get("/api/analytics/summary")
def analytics_summary() -> dict[str, Any]:
    """Headline counts for the KPI row, plus the distributions the charts use."""
    def counts(sql: str) -> dict[str, int]:
        return {str(r[0]): r[1] for r in _db.query(sql)}

    topics = _read.topics(states=("active", "watchlist", "fading", "candidate"))
    distance = {}
    for topic in topics:
        key = f"L{topic['portfolio_distance']}"
        distance[key] = distance.get(key, 0) + 1

    signal_ages = _db.query(
        "SELECT published_at, COUNT(*) n FROM signals WHERE relevance > 0 "
        "GROUP BY published_at ORDER BY published_at"
    )
    stages = _db.query("SELECT stage, COUNT(*) n FROM workflow_state GROUP BY stage")
    assessed = _db.query_one(
        "SELECT COUNT(DISTINCT opportunity_id) n FROM assessments WHERE superseded = 0"
    )
    return {
        "topics": len(topics),
        "signals": _db.query_one("SELECT COUNT(*) n FROM signals")["n"],
        "relevant_signals": _db.query_one("SELECT COUNT(*) n FROM signals WHERE relevance > 0")["n"],
        "sources": _db.query_one("SELECT COUNT(DISTINCT source_id) n FROM signals")["n"],
        "links": _db.query_one("SELECT COUNT(*) n FROM opportunity_links WHERE rejected = 0")["n"],
        "topics_assessed": assessed["n"] if assessed else 0,
        "by_state": counts("SELECT state, COUNT(*) FROM opportunity_spaces GROUP BY state"),
        "by_horizon": counts("SELECT horizon, COUNT(*) FROM opportunity_spaces WHERE horizon IS NOT NULL GROUP BY horizon"),
        "by_distance": distance,
        "by_stage": {r["stage"]: r["n"] for r in stages},
        "by_tier": counts("SELECT tier, COUNT(*) FROM signals GROUP BY tier"),
        "by_signal_type": counts(
            "SELECT COALESCE(signal_type,'unclassified'), COUNT(*) FROM signals WHERE relevance > 0 GROUP BY 1"
        ),
        "by_language": counts("SELECT language, COUNT(*) FROM signals GROUP BY language"),
        "by_source": counts("SELECT source_id, COUNT(*) FROM signals GROUP BY source_id"),
        "signal_timeline": [{"date": r["published_at"], "n": r["n"]} for r in signal_ages],
    }


@app.get("/api/topics/{topic_id}/evidence-timeline")
def evidence_timeline(topic_id: str) -> dict[str, Any]:
    """Signal accretion over time — momentum made visible (§4.6, §4.4.5).

    "Momentum is simply the trajectory of signal accretion, which is honest and
    explainable." This endpoint is that trajectory, so the UI can show the shape
    the momentum component actually measured rather than only its output number.
    """
    rows = _db.query(
        """SELECT s.published_at, s.tier, s.signal_type, s.publisher
           FROM signals s JOIN opportunity_signals os ON os.signal_id = s.id
           WHERE os.opportunity_id = ? ORDER BY s.published_at""",
        (topic_id,),
    )
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        month = (row["published_at"] or "")[:7]
        if not month:
            continue
        bucket = buckets.setdefault(month, {"month": month, "n": 0, "by_type": {}})
        bucket["n"] += 1
        stype = row["signal_type"] or "unclassified"
        bucket["by_type"][stype] = bucket["by_type"].get(stype, 0) + 1
    return {
        "topic_id": topic_id,
        "total": len(rows),
        "distinct_publishers": len({r["publisher"] for r in rows}),
        "months": [buckets[k] for k in sorted(buckets)],
    }


# ---------------------------------------------------------------------------
# Market size, competition, description and the PDF brief
# (§4.3.4, §4.3.3, FR-18)
#
# These are generation endpoints, so they are POSTs, and they are the only
# writes in the API besides feedback and curation. They write derived artefacts
# — a size, an assessment, a description, a PDF — and never a score or a topic,
# so the boundary that makes SC-11 reproducibility checkable still holds.
# ---------------------------------------------------------------------------


@app.get("/api/topics/{topic_id}/market-size")
def market_size(topic_id: str) -> dict[str, Any]:
    """Every stored estimate for a topic, factor by factor (§4.3.4)."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return {"topic_id": topic_id, "estimates": sizes_for_topic(_db, topic_id)}


@app.post("/api/topics/{topic_id}/market-size")
def recompute_market_size(topic_id: str) -> dict[str, Any]:
    """Recompute from the reference data currently in the store."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    MarketSizer(_cfg, _db).run(topic_ids=[topic_id])
    return {"topic_id": topic_id, "estimates": sizes_for_topic(_db, topic_id)}


@app.get("/api/reference-data")
def reference_data() -> dict[str, Any]:
    """What the sizing engine has to work with, and how old it is (NFR-08)."""
    return reference_status(_db)


@app.post("/api/reference-data/refresh")
def refresh_reference_data(force: bool = Query(False)) -> dict[str, Any]:
    """Refetch Eurostat. Annual statistics, so this is rarely needed."""
    return ReferenceDataFetcher(_cfg, _db).run(force=force)


@app.get("/api/topics/{topic_id}/competition")
def competition(topic_id: str) -> dict[str, Any]:
    """Named competitors and the computed intensity level (§4.3.3)."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    stored = competition_for_topic(_db, topic_id)
    if stored is None:
        CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
        stored = competition_for_topic(_db, topic_id)
    return stored or {}


@app.post("/api/topics/{topic_id}/competition")
def recompute_competition(topic_id: str) -> dict[str, Any]:
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
    return competition_for_topic(_db, topic_id) or {}


@app.get("/api/topics/{topic_id}/description")
def description(topic_id: str) -> dict[str, Any]:
    """The generated long-form description, or 404 if none exists yet."""
    stored = description_for_topic(_db, topic_id)
    if stored is None:
        raise HTTPException(404, f"No description generated for {topic_id} yet")
    return stored


@app.post("/api/topics/{topic_id}/description")
def generate_description(topic_id: str, force: bool = Query(False)) -> dict[str, Any]:
    """Generate (or regenerate) the description for one topic.

    Synchronous on purpose: it is one model call, the caller is a person who
    just pressed a button, and a background job would need a status endpoint to
    tell them the same thing.
    """
    row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
    if row is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    existing = description_for_topic(_db, topic_id)
    if existing and not force and not existing["stale"]:
        return existing
    try:
        DescriptionGenerator(_cfg, _db, _llm()).generate(dict(row))
    except Exception as exc:  # noqa: BLE001 — surfaced to the user, not swallowed
        raise HTTPException(502, f"Description generation failed: {exc}") from exc
    return description_for_topic(_db, topic_id) or {}


@app.get("/api/topics/{topic_id}/brief")
def brief_meta(topic_id: str) -> dict[str, Any]:
    """Whether a brief exists, when it was made and whether it has gone stale."""
    if _read.topic(topic_id) is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    return brief_for_topic(_db, topic_id) or {"topic_id": topic_id, "exists": False}


@app.post("/api/topics/{topic_id}/brief")
def generate_brief(topic_id: str, force: bool = Query(False)) -> dict[str, Any]:
    """Build the PDF brief, generating its inputs if they are missing.

    The brief is an assembly of computed, curated and generated content, so it
    makes sure all three exist before rendering: sizing and competition are
    cheap and deterministic; the description costs one model call and is only
    made when absent or stale.
    """
    row = _db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
    if row is None:
        raise HTTPException(404, f"No such topic: {topic_id}")
    existing = brief_for_topic(_db, topic_id)
    if existing and existing["exists"] and not existing["stale"] and not force:
        return existing

    if not sizes_for_topic(_db, topic_id):
        MarketSizer(_cfg, _db).run(topic_ids=[topic_id])
    if competition_for_topic(_db, topic_id) is None:
        CompetitionAnalyser(_cfg, _db).run(topic_ids=[topic_id])
    stored_description = description_for_topic(_db, topic_id)
    if stored_description is None or stored_description["stale"] or force:
        try:
            DescriptionGenerator(_cfg, _db, _llm()).generate(dict(row))
        except Exception as exc:  # noqa: BLE001
            # A brief without the narrative is still worth having — it carries
            # the evidence, the assets, the sizing and the competitors — so the
            # failure is reported in the payload rather than as a dead end.
            log.warning("Brief for %s built without a fresh description: %s", topic_id, exc)

    try:
        meta = BriefBuilder(_cfg, _db).build(topic_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Brief generation failed: {exc}") from exc
    meta["description_available"] = description_for_topic(_db, topic_id) is not None
    return meta


@app.get("/api/topics/{topic_id}/brief.pdf")
def brief_pdf(topic_id: str, download: bool = Query(False)) -> FileResponse:
    """The PDF itself.

    Served inline by default so it can be embedded in the radar, and as an
    attachment with ?download=1 — the same file either way, so what a
    salesperson forwards is byte-identical to what they read.
    """
    path = brief_path(_db, topic_id)
    if path is None:
        raise HTTPException(404, f"No brief generated for {topic_id}. POST to this path first.")
    meta = brief_for_topic(_db, topic_id) or {}
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path, media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{meta.get("filename", path.name)}"',
            # The brief is regenerated in place, so a cached copy would show a
            # stale document at the same URL.
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/analytics/market-size")
def analytics_market_size() -> dict[str, Any]:
    """Sized opportunity by vertical, for the analytics view."""
    rows = _db.query(
        """SELECT o.vertical, m.method, m.confidence, m.tam_base, m.sam_base, m.som_base
           FROM market_sizes m JOIN opportunity_spaces o ON o.id = m.opportunity_id
           WHERE o.merged_into IS NULL AND m.method = 'bottom_up_adoption'"""
    )
    by_vertical: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = by_vertical.setdefault(
            row["vertical"],
            {"vertical": row["vertical"],
             "label": _cfg.verticals.label(row["vertical"]),
             "topics": 0, "sam_base": 0.0, "som_base": 0.0},
        )
        entry["topics"] += 1
        entry["sam_base"] += row["sam_base"] or 0.0
        entry["som_base"] += row["som_base"] or 0.0
    confidence = {}
    for row in rows:
        confidence[row["confidence"]] = confidence.get(row["confidence"], 0) + 1
    levels = _db.query("SELECT level, COUNT(*) n FROM topic_competition GROUP BY level")
    return {
        # Summing SAM across topics double counts: two topics in the same
        # vertical address overlapping budgets. Reported as "sized opportunity",
        # never as a portfolio total, and the note travels with the payload so a
        # chart cannot lose it.
        "note": "Sizes are per topic and overlap within a vertical; this is a comparison of where "
                "sized opportunity concentrates, not a total addressable figure for Orange.",
        "by_vertical": sorted(by_vertical.values(), key=lambda v: -v["sam_base"]),
        "by_confidence": confidence,
        "competition_by_level": {r["level"]: r["n"] for r in levels},
        "sizing_version": _cfg.sizing_version,
    }


# ---------------------------------------------------------------------------
# Serving the frontend (production)
#
# One process, one origin: the API and the built React bundle are the same
# deployment. That is what makes the CORS list above a dev-only concern, and it
# means a deployed radar has no second thing to keep in step.
#
# Mounted LAST so every /api route above wins. Everything else falls through to
# the bundle, and unknown paths return index.html rather than a 404 — the app
# owns its own routing (?topic=OS012&tab=brief must survive a refresh).
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/healthz", include_in_schema=False)
def healthz() -> Any:
    """Liveness for the platform, distinct from /api/health's data counts.

    Reports a failed start rather than the process disappearing: 503 with the
    reason, and the startup notes alongside it, is what makes a bad deployment
    diagnosable from outside.
    """
    payload = {
        "ok": bootstrap.STARTUP_ERROR is None,
        "frontend": _FRONTEND_DIST.is_dir(),
        "database": str(_cfg.db_path),
        "startup": bootstrap.STARTUP_NOTES[-8:],
    }
    if bootstrap.STARTUP_ERROR:
        payload["error"] = bootstrap.STARTUP_ERROR
        return JSONResponse(payload, status_code=503)
    return payload


if _FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        candidate = (_FRONTEND_DIST / full_path).resolve()
        # Only serve real files from inside the bundle; anything else is a
        # client-side route and gets the app shell.
        if full_path and candidate.is_file() and _FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")
else:
    log.warning("No built frontend at %s — serving the API only. "
                "Run `npm --prefix frontend run build` before deploying.", _FRONTEND_DIST)
