"""Collaboration workflow and distributed assessment (FR-25, §4.10).

§4.10 evaluates four collaboration models and recommends "A + B + D, with C as a
fast follower". This module implements A and C, which are the two that touch
scoring:

  Model A — sequential stage-gate. Shortlisted -> Demand-tested -> Packaged ->
  Live, with an owner per stage. Its named weakness is latency: "a topic can die
  waiting for a stage owner", so `age_in_stage_days` is computed and surfaced
  rather than left for someone to notice.

  Model C — distributed assessment. "All three roles rate topics on their own
  axis (strategy: attractiveness; sales: demand; presales: deliverability).
  Divergence between the external score and internal ratings is surfaced as a
  review trigger."

HOW ASSESSMENT AFFECTS SCORING, and the line it must not cross.

SC-14 is explicit that internal data "adjusts but does not replace external
discovery", and SC-12 forbids collapsing attractiveness and right-to-win into
one number. So conviction is deliberately NOT folded into either published
score. It is a THIRD, separately displayed quantity:

  attractiveness   is the world moving          (external evidence)
  right to win     can we play, can we win      (internal assets)
  conviction       do our own people believe it (internal judgement)

Conviction enters only the per-role RANKING function, which already exists to
order a list and is never displayed as a score. That keeps every published
number reproducible from evidence alone (SC-11) while still letting the people
closest to customers change what surfaces first.

DIVERGENCE IS THE PRODUCT. §4.10 model C: "disagreement becomes information
rather than friction". A topic the evidence rates highly and the sales team
rates low is the single most interesting row in the system — either the radar is
wrong about the market, or the market is ahead of the sales conversation. Either
way a human should look, so it is flagged, not averaged away.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from .config import Config
from .db import Database

log = logging.getLogger(__name__)

# Model A stage gate (§4.10). Order matters: it defines "forward".
STAGES = ["shortlisted", "demand_tested", "packaged", "live"]
STAGE_LABELS = {
    "shortlisted": "Shortlisted",
    "demand_tested": "Demand-tested",
    "packaged": "Packaged",
    "live": "Live",
    "parked": "Parked",
    "rejected": "Rejected",
}
TERMINAL_STAGES = ["parked", "rejected"]

#: Which role owns which stage, and therefore who is accountable for the delay.
STAGE_OWNER_ROLE = {
    "shortlisted": "strategist",
    "demand_tested": "sales",
    "packaged": "presales",
    "live": "presales",
}

#: Each role rates its OWN axis only. A salesperson is authoritative about
#: whether customers are asking and is not being asked to re-judge the evidence.
ROLE_AXIS = {
    "strategist": "strategic_fit",
    "sales": "customer_demand",
    "presales": "deliverability",
}
AXIS_LABELS = {
    "strategic_fit": "Strategic fit",
    "customer_demand": "Customer demand",
    "deliverability": "Deliverability",
}

#: Discrete anchors, for the score-compression reason in §4.6 and §4.7.4's
#: finding that people are unreliable at fine-grained absolute ratings.
AXIS_ANCHORS = {
    "strategic_fit": {
        0: "Not strategically relevant — connects to no Trust the future ambition",
        1: "Weak: a distraction from the plan",
        2: "Adjacent: sellable but advances no stated ambition",
        3: "Plausible, but the connection needs an argument",
        4: "Clearly serves an ambition with a credible delivery story",
        5: "Squarely inside Innovative growth — trusted B2B, cyberdefence or trusted AI",
    },
    "customer_demand": {
        0: "No customer has ever raised this",
        1: "Raised once, in passing",
        2: "Occasional interest, no budget attached",
        3: "Several accounts asking; budget unclear",
        4: "Named accounts asking with budget in view",
        5: "Customers are actively buying this now — we are being asked for it",
    },
    "deliverability": {
        0: "We could not deliver this at all",
        1: "Would need a capability we do not have and cannot source",
        2: "Deliverable only with significant build or a new partner",
        3: "Deliverable with integration work across existing offers",
        4: "Deliverable now with minor packaging work",
        5: "Deliverable today from the shelf, with proof points to show",
    },
}


class WorkflowService:
    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        wf = cfg.settings.get("workflow", {})
        self.divergence_threshold = float(wf.get("divergence_threshold", 30.0))
        self.min_assessments_for_conviction = int(wf.get("min_assessments_for_conviction", 1))
        self.stale_after_days = int(wf.get("stale_in_stage_days", 30))

    # -- stage gate ---------------------------------------------------------

    def ensure_state(self, topic_id: str) -> dict[str, Any]:
        row = self.db.query_one("SELECT * FROM workflow_state WHERE opportunity_id = ?", (topic_id,))
        if row:
            return dict(row)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT OR IGNORE INTO workflow_state "
                "(opportunity_id, stage, owner_role, entered_stage_at, updated_at) VALUES (?,?,?,?,?)",
                (topic_id, "shortlisted", STAGE_OWNER_ROLE["shortlisted"], now, now),
            )
        return dict(self.db.query_one("SELECT * FROM workflow_state WHERE opportunity_id = ?", (topic_id,)))

    def transition(self, topic_id: str, to_stage: str, actor: str, actor_role: str,
                   reason: str | None = None, owner: str | None = None) -> dict[str, Any]:
        if to_stage not in STAGES + TERMINAL_STAGES:
            raise ValueError(f"Unknown stage {to_stage!r}. Known: {STAGES + TERMINAL_STAGES}")
        current = self.ensure_state(topic_id)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO workflow_transitions "
                "(opportunity_id, from_stage, to_stage, actor, actor_role, reason, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (topic_id, current["stage"], to_stage, actor, actor_role, reason, now),
            )
            cur.execute(
                "UPDATE workflow_state SET stage = ?, owner_role = ?, owner = ?, "
                "entered_stage_at = ?, updated_at = ?, note = ? WHERE opportunity_id = ?",
                (to_stage, STAGE_OWNER_ROLE.get(to_stage), owner, now, now, reason, topic_id),
            )
        return self.state_for(topic_id)

    def prefetch(self, topic_ids: list[str]) -> dict[str, Any]:
        """Load the workflow rows for many topics in two queries instead of 3n.

        The read model assembles up to two hundred topics for a single view, and
        every one of them asked this service three separate questions. That is
        several hundred round trips to answer one screen — see
        `ReadModel._bulk` for why that mattered enough to fix.
        """
        if not topic_ids:
            return {"state": {}, "assessments": {}}
        placeholders = ",".join("?" * len(topic_ids))
        params = tuple(topic_ids)
        state = {
            row["opportunity_id"]: dict(row)
            for row in self.db.query(
                f"SELECT * FROM workflow_state WHERE opportunity_id IN ({placeholders})", params
            )
        }
        # A topic that has never been through the stage gate has no row, and
        # `ensure_state` creates one — a write on read, which is deliberate:
        # §4.10 model A wants every live topic to sit in a column with an owner.
        # Done one topic at a time it was two extra queries and a transaction per
        # topic on the first view after a refresh, which is precisely when the
        # radar has the most new topics and the least patience for a slow screen.
        missing = [topic_id for topic_id in topic_ids if topic_id not in state]
        if missing:
            now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            with self.db.cursor() as cur:
                cur.executemany(
                    "INSERT OR IGNORE INTO workflow_state "
                    "(opportunity_id, stage, owner_role, entered_stage_at, updated_at) "
                    "VALUES (?,?,?,?,?)",
                    [(topic_id, "shortlisted", STAGE_OWNER_ROLE["shortlisted"], now, now)
                     for topic_id in missing],
                )
            for topic_id in missing:
                state[topic_id] = {
                    "opportunity_id": topic_id, "stage": "shortlisted",
                    "owner_role": STAGE_OWNER_ROLE["shortlisted"], "owner": None,
                    "entered_stage_at": now, "updated_at": now, "note": None,
                }
        assessments: dict[str, list[dict[str, Any]]] = {}
        for row in self.db.query(
            f"""SELECT opportunity_id, role, axis, rating, confidence, rationale, author, created_at
                FROM assessments WHERE opportunity_id IN ({placeholders}) AND superseded = 0
                ORDER BY created_at DESC""",
            params,
        ):
            assessments.setdefault(row["opportunity_id"], []).append(dict(row))
        return {"state": state, "assessments": assessments}

    def state_for(self, topic_id: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
        # `ensure_state` writes a default row when none exists, so it is still
        # called when the prefetch found nothing — a topic that has never been
        # touched by the workflow needs its row created exactly once.
        state = state or self.ensure_state(topic_id)
        entered = state.get("entered_stage_at")
        age_days = 0
        if entered:
            try:
                age_days = (dt.datetime.now(dt.timezone.utc)
                            - dt.datetime.fromisoformat(entered)).days
            except (ValueError, TypeError):
                age_days = 0
        stage = state["stage"]
        return {
            "stage": stage,
            "stage_label": STAGE_LABELS.get(stage, stage),
            "owner_role": state.get("owner_role"),
            "owner": state.get("owner"),
            "entered_stage_at": entered,
            "age_in_stage_days": age_days,
            # §4.10's named weakness of the stage gate is latency. Surfacing it
            # is the cheapest possible mitigation.
            "stalled": stage in STAGES and age_days >= self.stale_after_days,
            "note": state.get("note"),
            "next_stage": (STAGES[STAGES.index(stage) + 1]
                           if stage in STAGES and STAGES.index(stage) + 1 < len(STAGES) else None),
        }

    # -- distributed assessment --------------------------------------------

    def record_assessment(self, topic_id: str, role: str, rating: int, author: str,
                          confidence: int = 3, rationale: str | None = None) -> dict[str, Any]:
        if role not in ROLE_AXIS:
            raise ValueError(f"Unknown role {role!r}. Known: {list(ROLE_AXIS)}")
        if not 0 <= int(rating) <= 5:
            raise ValueError("rating must be 0-5")
        if not 1 <= int(confidence) <= 5:
            raise ValueError("confidence must be 1-5")
        axis = ROLE_AXIS[role]
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            # One live assessment per author per role per topic; older ones are
            # superseded rather than deleted, because a changed mind is itself a
            # label worth keeping (§4.7.7).
            cur.execute(
                "UPDATE assessments SET superseded = 1 "
                "WHERE opportunity_id = ? AND role = ? AND author = ? AND superseded = 0",
                (topic_id, role, author),
            )
            cur.execute(
                "INSERT INTO assessments (opportunity_id, role, axis, rating, confidence, "
                "rationale, author, created_at, weight_set) VALUES (?,?,?,?,?,?,?,?,?)",
                (topic_id, role, axis, int(rating), int(confidence), rationale, author,
                 now, self.cfg.weight_set),
            )
        return self.conviction_for(topic_id)

    def conviction_for(self, topic_id: str,
                       rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """Aggregate live assessments into a conviction block.

        Ratings are confidence-weighted: someone who says "4, but I am not sure"
        should move the aggregate less than someone who is certain. Each axis is
        reported separately as well as blended, because the axes answer
        different questions and averaging them alone would repeat exactly the
        mistake SC-12 warns about.
        """
        if rows is None:
            rows = self.db.query(
                "SELECT role, axis, rating, confidence, rationale, author, created_at "
                "FROM assessments WHERE opportunity_id = ? AND superseded = 0 ORDER BY created_at DESC",
                (topic_id,),
            )
        by_axis: dict[str, dict[str, Any]] = {}
        for row in rows:
            entry = by_axis.setdefault(row["axis"], {"ratings": [], "weights": [], "voices": []})
            entry["ratings"].append(row["rating"])
            entry["weights"].append(row["confidence"])
            entry["voices"].append({
                "role": row["role"], "rating": row["rating"], "confidence": row["confidence"],
                "rationale": row["rationale"], "author": row["author"], "at": row["created_at"],
            })

        axes: dict[str, Any] = {}
        for axis, entry in by_axis.items():
            total_weight = sum(entry["weights"]) or 1
            weighted = sum(r * w for r, w in zip(entry["ratings"], entry["weights"])) / total_weight
            spread = (max(entry["ratings"]) - min(entry["ratings"])) if len(entry["ratings"]) > 1 else 0
            axes[axis] = {
                "label": AXIS_LABELS.get(axis, axis),
                "score": round(weighted * 20.0, 1),      # 0-5 -> 0-100
                "raw_mean": round(weighted, 2),
                "n": len(entry["ratings"]),
                # §4.7.6: "persistently low agreement on a criterion means the
                # criterion is ill-defined, not that the model is failing".
                "rater_spread": spread,
                "contested": spread >= 3,
                "voices": entry["voices"],
            }

        assessed = len(rows)
        overall = (round(sum(a["score"] for a in axes.values()) / len(axes), 1) if axes else None)
        return {
            "assessed": assessed,
            "axes": axes,
            "score": overall,
            "roles_responded": sorted({r["role"] for r in rows}),
            "roles_missing": [r for r in ROLE_AXIS if r not in {row["role"] for row in rows}],
            "sufficient": assessed >= self.min_assessments_for_conviction,
        }

    def divergence_for(self, topic_id: str, attractiveness: float | None,
                       right_to_win: float | None,
                       conviction: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """§4.10 model C — surface disagreement as a review trigger.

        Two comparisons, each between a published score and the role whose job
        it is to know better:

          attractiveness vs customer_demand   — the market says one thing, the
                                                people talking to customers say another
          right_to_win   vs deliverability    — the asset graph says we can, the
                                                people who would build it disagree
        """
        # The caller has usually just computed this; recomputing it here cost a
        # second assessments query for every topic on every screen.
        conviction = conviction if conviction is not None else self.conviction_for(topic_id)
        if not conviction["axes"]:
            return None
        flags = []
        for axis, external, external_label in (
            ("customer_demand", attractiveness, "attractiveness"),
            ("deliverability", right_to_win, "right to win"),
        ):
            block = conviction["axes"].get(axis)
            if block is None or external is None:
                continue
            delta = block["score"] - external
            if abs(delta) >= self.divergence_threshold:
                flags.append({
                    "axis": axis,
                    "axis_label": AXIS_LABELS[axis],
                    "internal": block["score"],
                    "external": round(external, 1),
                    "external_label": external_label,
                    "delta": round(delta, 1),
                    "direction": "internal_higher" if delta > 0 else "internal_lower",
                    "reading": (
                        f"The team rates {AXIS_LABELS[axis].lower()} well above the evidence-derived "
                        f"{external_label} — either the radar is missing signal, or enthusiasm is "
                        f"running ahead of it."
                        if delta > 0 else
                        f"The team rates {AXIS_LABELS[axis].lower()} well below the evidence-derived "
                        f"{external_label} — either the market is moving before our conversations are, "
                        f"or the evidence is thinner than the score suggests."
                    ),
                })
        if not flags:
            return None
        return {"flags": flags, "review_trigger": True}

    # -- board --------------------------------------------------------------

    #: What a board card actually shows. Everything else a topic carries — its
    #: links, its score components, its rank explanation, its conviction voices —
    #: was being shipped for every card, which made the board a 2 MB response for
    #: a screen of forty-word summaries. Selecting a card loads the full topic in
    #: the detail pane, which is where the rest of it belongs.
    CARD_FIELDS = ("id", "statement", "labels", "triple", "horizon", "state",
                   "portfolio_distance", "evidence_gap_warning", "signal_count",
                   "workflow", "divergence", "market_size_summary", "has_brief")

    @staticmethod
    def _card(topic: dict[str, Any]) -> dict[str, Any]:
        card = {key: topic.get(key) for key in WorkflowService.CARD_FIELDS}
        # Scores are cut to the published number: a card compares topics, and the
        # decomposition belongs where it can be read properly (NFR-01).
        for kind in ("attractiveness", "right_to_win"):
            block = topic.get(kind) or {}
            card[kind] = {"score": block.get("score")} if block else None
        conviction = topic.get("conviction") or {}
        card["conviction"] = {"score": conviction.get("score"),
                              "assessed": conviction.get("assessed", 0)} if conviction else None
        competition = topic.get("competition") or {}
        card["competition"] = ({"level": competition.get("level"),
                                "level_label": competition.get("level_label")}
                               if competition else None)
        return card

    def board(self, topics: list[dict[str, Any]]) -> dict[str, Any]:
        """Group topics by stage for the visual workflow (FR-25)."""
        columns: dict[str, list[dict[str, Any]]] = {s: [] for s in STAGES}
        for extra in TERMINAL_STAGES:
            columns[extra] = []
        for topic in topics:
            stage = (topic.get("workflow") or {}).get("stage", "shortlisted")
            columns.setdefault(stage, []).append(self._card(topic))
        return {
            "stages": [
                {
                    "id": stage,
                    "label": STAGE_LABELS[stage],
                    "owner_role": STAGE_OWNER_ROLE.get(stage),
                    "count": len(columns.get(stage, [])),
                    "topics": columns.get(stage, []),
                }
                for stage in STAGES + TERMINAL_STAGES
            ],
            "axes": [{"id": a, "label": AXIS_LABELS[a], "anchors": AXIS_ANCHORS[a],
                      "role": r} for r, a in ROLE_AXIS.items()],
        }
