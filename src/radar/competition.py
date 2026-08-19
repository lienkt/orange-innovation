"""Competitive intensity per opportunity space (§4.3.3, Table 27).

§4.3.3 puts competition on the right-to-win side of the model: "contract award
notices additionally reveal who is winning, which feeds the competitive side of
right-to-win", and Table 27 lists "award concentration among competitors" as a
procurement feature.

The same rule as everywhere else in this codebase applies: a competitor is a
NAMED entity from a curated register, matched by a query, with the evidence that
justified it attached (LK-08's principle — "a link nobody can explain is worse
than no link, because it will eventually appear in front of a customer"). A
model may later write prose ABOUT this list; it may not add to it.

Two kinds of presence are distinguished, because they are worth different
things in a sales conversation:

  evidenced   The corpus actually mentions this competitor in the evidence
              attached to this topic. Cites the signal, dated and clickable.
  structural  The register says this competitor sells this technology into this
              vertical. True, useful, and not the same as proof.

The intensity level (NONE / LOW / MEDIUM / HIGH) is a band over a weighted
count, not a judgement: type weight x match specificity, doubled where the
presence is evidenced. Every input is stored, so the level can be re-derived
and disputed (NFR-01).

Competitive intensity is a FOURTH quantity, kept beside attractiveness, right to
win and conviction. It is never folded into any of them — SC-12 forbids
collapsing published scores, and a strong field is not the same fact as a weak
Orange position.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any

from .config import Config
from .db import Database, js, unjs

log = logging.getLogger(__name__)

LEVELS = ("none", "low", "medium", "high")
LEVEL_LABELS = {
    "none": "None",
    "low": "Low",
    "medium": "Medium",
    "high": "High",
}
LEVEL_MEANING = {
    "none": "No named competitor in the register plausibly plays in this space. "
            "Treat as unverified rather than empty: it may mean the register has a gap.",
    "low": "One or two adjacent players. Orange would be shaping the space rather than fighting for it.",
    "medium": "A real field, including at least one player the customer will already know. "
              "Expect to be compared.",
    "high": "Crowded, with heavyweight incumbents already visible in the evidence. "
            "Win on a specific differentiator or do not bid.",
}


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Word-boundary match, so 'Colt' never fires inside 'Colten'."""
    return re.compile(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", re.IGNORECASE)


class CompetitionAnalyser:
    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        self.settings = cfg.settings["competition"]
        self.types = cfg.competitors_raw["types"]
        self.register = cfg.competitors_raw["competitors"]
        self._patterns = {
            entry["id"]: [_alias_pattern(a) for a in entry.get("aliases", [])]
            for entry in self.register
        }

    # ------------------------------------------------------------------

    def run(self, states: tuple[str, ...] = ("active", "watchlist", "fading", "candidate"),
            topic_ids: list[str] | None = None) -> dict[str, Any]:
        self.db.init_schema()
        if topic_ids:
            placeholders = ",".join("?" * len(topic_ids))
            rows = self.db.query(
                f"SELECT * FROM opportunity_spaces WHERE id IN ({placeholders}) AND merged_into IS NULL",
                tuple(topic_ids),
            )
        else:
            placeholders = ",".join("?" * len(states))
            rows = self.db.query(
                f"SELECT * FROM opportunity_spaces WHERE merged_into IS NULL AND state IN ({placeholders})",
                states,
            )
        stats = {"topics": 0, "by_level": {}, "evidenced_competitors": 0}
        for row in rows:
            assessment = self.assess(dict(row))
            self._store(row["id"], assessment)
            stats["topics"] += 1
            stats["by_level"][assessment["level"]] = stats["by_level"].get(assessment["level"], 0) + 1
            stats["evidenced_competitors"] += sum(
                1 for c in assessment["competitors"] if c["basis"] == "evidenced"
            )
        return stats

    # ------------------------------------------------------------------

    def assess(self, topic: dict[str, Any]) -> dict[str, Any]:
        """Who competes here, how strongly, and what says so."""
        domains = set(unjs(topic["domains"], []) or [])
        technology = topic["technology"]
        vertical = topic["vertical"]
        signals = self._topic_signals(topic["id"])
        weights = self.settings["match_weights"]

        competitors: list[dict[str, Any]] = []
        for entry in self.register:
            reasons: list[str] = []
            match_weight = 0.0
            if technology in (entry.get("technologies") or []):
                match_weight = max(match_weight, float(weights["technology"]))
                reasons.append(f"sells {self.cfg.technologies.label(technology)}")
            if vertical in (entry.get("verticals") or []):
                match_weight = max(match_weight, float(weights["vertical"]))
                reasons.append(f"active in {self.cfg.verticals.label(vertical)}")
            if domains & set(entry.get("domains") or []):
                match_weight = max(match_weight, float(weights["domain"]))
                shared = sorted(domains & set(entry.get("domains") or []))
                reasons.append("competes in " + ", ".join(self.cfg.domains.label(d) for d in shared))

            mentions = self._mentions(entry, signals)
            if match_weight <= 0 and not mentions:
                continue
            if match_weight <= 0:
                # Named in this topic's own evidence but not registered against
                # its technology or vertical. Worth listing — the corpus knows
                # something the register does not — at the lowest match weight.
                match_weight = float(weights["domain"])
                reasons.append("named in this topic's evidence")

            type_weight = float(self.types[entry["type"]]["weight"])
            basis = "evidenced" if mentions else "structural"
            multiplier = float(self.settings["evidenced_multiplier"]) if mentions else 1.0
            contribution = type_weight * match_weight * multiplier

            competitors.append({
                "id": entry["id"],
                "label": entry["label"],
                "type": entry["type"],
                "type_label": self.types[entry["type"]]["label"],
                "relationship": entry.get("relationship", "competitor"),
                "partner_id": entry.get("partner_id"),
                "basis": basis,
                "why": "; ".join(reasons),
                "note": entry.get("note", ""),
                "mentions": mentions,
                "contribution": round(contribution, 3),
            })

        # Evidenced first, then by contribution: what the corpus has actually
        # seen outranks what the register merely implies.
        competitors.sort(key=lambda c: (c["basis"] != "evidenced", -c["contribution"], c["label"]))
        listed = competitors[: int(self.settings["max_listed"])]
        # Scored over the LISTED set, not the whole register. Competition is
        # experienced as "who will I be up against in this deal", not as a
        # vendor-directory size: summing a fifty-entry tail of weak domain
        # matches would rate every cybersecurity topic identically, which is the
        # same score-compression failure §4.6 warns about for the rubrics.
        score = round(sum(c["contribution"] for c in listed), 2)
        level = self._level(score)

        return {
            "level": level,
            "level_label": LEVEL_LABELS[level],
            "meaning": LEVEL_MEANING[level],
            "score": score,
            "competitors": listed,
            "counts": {
                "total": len(competitors),
                "listed": len(listed),
                "evidenced": sum(1 for c in competitors if c["basis"] == "evidenced"),
                "partners_who_also_compete": sum(1 for c in competitors if c["relationship"] == "both"),
            },
            "inputs": {
                "bands": self.settings["bands"],
                "match_weights": self.settings["match_weights"],
                "evidenced_multiplier": self.settings["evidenced_multiplier"],
                "type_weights": {k: v["weight"] for k, v in self.types.items()},
                "signals_scanned": len(signals),
                "scored_over": "the listed competitors only",
                "matched_but_not_listed": max(0, len(competitors) - len(listed)),
            },
            "register_version": self.cfg.competitor_version,
        }

    def _level(self, score: float) -> str:
        bands = self.settings["bands"]
        if score >= float(bands["high"]):
            return "high"
        if score >= float(bands["medium"]):
            return "medium"
        if score >= float(bands["low"]):
            return "low"
        return "none"

    def _topic_signals(self, topic_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """SELECT s.id, s.title, s.extract, s.publisher, s.published_at, s.url
               FROM signals s JOIN opportunity_signals os ON os.signal_id = s.id
               WHERE os.opportunity_id = ?""",
            (topic_id,),
        )
        return [dict(r) for r in rows]

    def _mentions(self, entry: dict[str, Any], signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Signals whose title or extract names this competitor.

        Cited rather than counted: a competitive claim in a customer meeting is
        only as good as the article behind it, so the signal id, publisher and
        date travel with every mention (NFR-02).
        """
        patterns = self._patterns[entry["id"]]
        found: list[dict[str, Any]] = []
        for signal in signals:
            haystack = f"{signal['title']} {signal['extract']}"
            for pattern in patterns:
                match = pattern.search(haystack)
                if match is None:
                    continue
                start = max(0, match.start() - 90)
                found.append({
                    "signal_id": signal["id"],
                    "publisher": signal["publisher"],
                    "published_at": signal["published_at"],
                    "url": signal["url"],
                    "title": signal["title"][:140],
                    "quote": haystack[start : match.end() + 90].strip(),
                })
                break
        found.sort(key=lambda m: m["published_at"], reverse=True)
        return found[:5]

    # ------------------------------------------------------------------

    def _store(self, topic_id: str, assessment: dict[str, Any]) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO topic_competition
                       (opportunity_id, computed_at, level, score, competitors, inputs,
                        register_version, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(opportunity_id) DO UPDATE SET
                       computed_at=excluded.computed_at, level=excluded.level, score=excluded.score,
                       competitors=excluded.competitors, inputs=excluded.inputs,
                       register_version=excluded.register_version,
                       pipeline_version=excluded.pipeline_version""",
                (topic_id, now, assessment["level"], assessment["score"],
                 js(assessment["competitors"]), js(assessment["inputs"]),
                 assessment["register_version"], self.cfg.pipeline_version),
            )


def competition_for_topic(db: Database, topic_id: str) -> dict[str, Any] | None:
    """Stored assessment, shaped for the read model and the API."""
    return competition_from_row(
        db.query_one("SELECT * FROM topic_competition WHERE opportunity_id = ?", (topic_id,))
    )


def competition_from_row(row: Any) -> dict[str, Any] | None:
    """The same shaping, from a row the caller already has.

    The read model fetches these in bulk for a whole view (see
    `ReadModel._bulk`), and shaping has to stay in one place: a competition
    block that looks different depending on which query loaded it is how two
    surfaces start disagreeing about the same topic.
    """
    if row is None:
        return None
    competitors = unjs(row["competitors"], []) or []
    return {
        "level": row["level"],
        "level_label": LEVEL_LABELS.get(row["level"], row["level"]),
        "meaning": LEVEL_MEANING.get(row["level"], ""),
        "score": row["score"],
        "competitors": competitors,
        "counts": {
            "listed": len(competitors),
            "evidenced": sum(1 for c in competitors if c.get("basis") == "evidenced"),
            "partners_who_also_compete": sum(1 for c in competitors if c.get("relationship") == "both"),
        },
        "inputs": unjs(row["inputs"], {}),
        "register_version": row["register_version"],
        "computed_at": row["computed_at"],
    }
