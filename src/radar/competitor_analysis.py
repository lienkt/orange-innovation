"""Per-topic competitor analysis (§4.3.3 extension).

`competition.py` answers "how crowded is this space" and returns a level over a
named list. That is the right quantity and it is not enough to walk into a
meeting with, because it says nothing about what those competitors are actually
doing here or what Orange would say when the customer names one of them.

This module answers those two questions, in two clearly separated registers:

  the join         Arithmetic. For each competitor already matched to the topic,
                   which of that competitor's own published claims touch this
                   vertical, use case or technology. No model, no cost, always
                   present, recomputed whenever the topic or a profile moves.

  the comparison   Generated. Per competitor: what they are doing here, cited to
                   their own pages; how Orange differentiates against THAT
                   competitor for THIS opportunity, anchored in an Orange asset
                   actually linked to the topic; and what that competitor
                   genuinely does better. Plus one paragraph on the field.

The separation matters for the same reason it matters everywhere else in this
codebase: the join is reproducible from stored inputs, the comparison is a model
writing prose, and a reader has to be able to tell which is which. The interface
labels them differently and the brief prints them in different type.

The differentiation paragraph carries one additional guard beyond the usual
four. It may only name Orange assets that are LINKED to this topic — so where
Orange has nothing linked, the honest paragraph says Orange would be competing
on price and delivery rather than on a structural advantage. An invented
advantage is not discovered in review; it is discovered in the meeting.
"""

from __future__ import annotations

import concurrent.futures as futures
import datetime as dt
import logging
from typing import Any, Iterable

from .competition import competition_for_topic
from .competitor_intel import profile_coverage, profile_from_row
from .config import Config
from .db import Database, js, unjs

log = logging.getLogger(__name__)

ANALYSIS_SCHEMA = "canalysis-1"


class CompetitorAnalyst:
    def __init__(self, cfg: Config, db: Database, llm: Any | None = None):
        self.cfg = cfg
        self.db = db
        self.settings = cfg.settings["competitor_intel"]
        self.pipeline_version = cfg.settings["pipeline_version"]
        self._llm = llm

    @property
    def llm(self) -> Any:
        if self._llm is None:
            from .llm import LLMClient
            self._llm = LLMClient(max_retries=self.cfg.settings["llm"]["max_retries"])
        return self._llm

    # ------------------------------------------------------------------ run
    def run(self, topic_ids: Iterable[str] | None = None, limit: int | None = None,
            force: bool = False, use_llm: bool = True,
            states: tuple[str, ...] = ("active", "watchlist", "fading")) -> dict[str, Any]:
        if topic_ids:
            placeholders = ",".join("?" for _ in topic_ids)
            rows = self.db.query(
                f"SELECT * FROM opportunity_spaces WHERE id IN ({placeholders})", tuple(topic_ids))
        else:
            placeholders = ",".join("?" for _ in states)
            rows = self.db.query(
                f"""SELECT * FROM opportunity_spaces
                    WHERE state IN ({placeholders}) AND merged_into IS NULL
                    ORDER BY id""", tuple(states))
        topics = [dict(r) for r in rows]

        stats: dict[str, Any] = {
            "considered": len(topics), "joined": 0, "written": 0,
            "skipped_current": 0, "skipped_no_competitors": 0,
            "entries_stripped": 0, "errors": {},
        }

        pending: list[dict[str, Any]] = []
        for topic in topics:
            entries = self.join(topic["id"])
            if not entries:
                stats["skipped_no_competitors"] += 1
                continue
            self._store(topic, entries, narrative=None, keep_narrative=True)
            stats["joined"] += 1
            if not force and self._is_current(topic):
                stats["skipped_current"] += 1
                continue
            pending.append({"topic": topic, "entries": entries})

        if not use_llm:
            log.info("Competitor analysis (join only): %s", stats)
            return stats

        cap = limit or int(self.settings["max_analyses_per_run"])
        if len(pending) > cap:
            # §4.12: what a cap left undone is logged, never silently dropped.
            stats["deferred"] = [j["topic"]["id"] for j in pending[cap:]]
            log.info("Analysis cap: writing %d of %d; %d deferred",
                     cap, len(pending), len(pending) - cap)
            pending = pending[:cap]

        from .pipeline import prompts
        system = prompts.competitor_analysis_system_prompt(self.cfg)

        def work(job: dict[str, Any]) -> None:
            try:
                result = self.write(job["topic"], job["entries"], system)
            except Exception as exc:                          # pragma: no cover - defensive
                log.exception("Competitor analysis failed for %s", job["topic"]["id"])
                stats["errors"][job["topic"]["id"]] = f"{type(exc).__name__}: {exc}"
                return
            stats["written"] += 1
            stats["entries_stripped"] += len(result["stripped"])

        with futures.ThreadPoolExecutor(max_workers=int(self.settings["max_parallel_analyses"])) as pool:
            list(pool.map(work, pending))
        log.info("Competitor analysis: %s", stats)
        return stats

    # ----------------------------------------------------------------- join
    def join(self, topic_id: str) -> list[dict[str, Any]]:
        """The structural half: competitor × this topic's taxonomy cell.

        Arithmetic throughout. A claim is 'relevant' when the profile's own
        closed-vocabulary tags overlap this topic's triple, or when the claim
        text names the topic's technology or use case. That is a keyword join,
        it is stated as one, and it is why the model is asked to write the
        comparison rather than to decide what is relevant.
        """
        topic = self.db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))
        if topic is None:
            return []
        competition = competition_for_topic(self.db, topic_id)
        if not competition or not competition.get("competitors"):
            return []

        register = {e["id"]: e for e in self.cfg.competitors_raw["competitors"]}
        types = self.cfg.competitors_raw.get("types", {})
        cell = {
            "vertical": topic["vertical"],
            "use_case": topic["use_case"],
            "technology": topic["technology"],
        }
        labels = {
            "vertical": self._label(self.cfg.verticals, topic["vertical"]),
            "use_case": self._label(self.cfg.use_cases, topic["use_case"]),
            "technology": self._label(self.cfg.technologies, topic["technology"]),
        }

        out: list[dict[str, Any]] = []
        for listed in competition["competitors"]:
            cid = listed.get("id")
            entry = register.get(cid)
            if entry is None:
                continue
            row = self.db.query_one(
                "SELECT * FROM competitor_profiles WHERE competitor_id = ?", (cid,))
            profile = profile_from_row(row)
            item: dict[str, Any] = {
                "id": cid,
                "label": entry["label"],
                "type": entry.get("type"),
                "type_label": types.get(entry.get("type"), {}).get("label", entry.get("type")),
                "relationship": entry.get("relationship", "competitor"),
                "basis": listed.get("basis"),
                "mentions": listed.get("mentions", []),
                "website": entry.get("website"),
                "profile_status": (profile or {}).get("status", "unread"),
                "profile_reason": (profile or {}).get("status_reason"),
                "positioning": (profile or {}).get("positioning"),
                "register_overlap": self._overlap(entry, cell),
            }
            if profile and profile.get("status") == "profiled":
                item["relevant_claims"] = self._relevant_claims(profile, cell, labels)
                item["profile_overlap"] = self._overlap(profile, cell)
                item["named_offers"] = [o["name"] for o in profile.get("named_offers", [])]
                item["pages_used"] = profile.get("pages_used", 0)
            else:
                item["relevant_claims"] = []
                item["profile_overlap"] = {}
                item["named_offers"] = []
                item["pages_used"] = 0
            out.append(item)
        return out

    @staticmethod
    def _overlap(source: dict[str, Any], cell: dict[str, str]) -> dict[str, bool]:
        return {
            "vertical": cell["vertical"] in (source.get("verticals") or []),
            "use_case": cell["use_case"] in (source.get("use_cases") or []),
            "technology": cell["technology"] in (source.get("technologies") or []),
        }

    @staticmethod
    def _relevant_claims(profile: dict[str, Any], cell: dict[str, str],
                         labels: dict[str, str]) -> list[dict[str, Any]]:
        """Claims whose text touches this cell, most specific first."""
        needles = [w.lower() for w in labels.values() if w]
        needles += [cell["technology"].replace("_", " "), cell["use_case"].replace("_", " ")]
        scored = []
        for claim in profile.get("claims", []):
            text = (claim.get("claim") or "").lower()
            hits = sum(1 for n in needles if n and n in text)
            scored.append((hits, claim))
        scored.sort(key=lambda pair: -pair[0])
        # A profile with no textual hit still contributes its top claims: the
        # competitor is on this topic because the register put it there, and
        # showing nothing would read as "they do nothing here".
        return [claim for _, claim in scored[:8]]

    def _label(self, vocab: Any, value: str) -> str:
        try:
            item = vocab.get(value)
            return getattr(item, "label", None) or value
        except Exception:
            return value

    # ------------------------------------------------------------ narrative
    def write(self, topic: dict[str, Any], entries: list[dict[str, Any]],
              system: str | None = None) -> dict[str, Any]:
        from .pipeline import prompts
        from .pipeline.synthesis import _NUMERIC_CLAIM_RE

        system = system or prompts.competitor_analysis_system_prompt(self.cfg)
        labels = {
            "vertical": self._label(self.cfg.verticals, topic["vertical"]),
            "use_case": self._label(self.cfg.use_cases, topic["use_case"]),
            "technology": self._label(self.cfg.technologies, topic["technology"]),
        }
        assets = self._named_assets(topic["id"])
        signals = self._signals(topic["id"])
        user = prompts.format_topic_for_competitor_analysis(topic, labels, entries, assets, signals)
        # Eight competitors x (activity + differentiation + concession) is a long
        # structured answer, and the default completion budget truncates it
        # mid-string — which surfaces as invalid JSON and loses the whole topic
        # rather than its tail. 23 of 177 failed this way on the first full run.
        payload = self.llm.complete_json(
            system, user, max_tokens=8000,
            temperature=self.cfg.settings["llm"]["temperature_critic"])
        if not isinstance(payload, dict):
            payload = {}

        allowed_pages = {
            entry["id"]: {p for claim in entry.get("relevant_claims", []) for p in claim.get("pages", [])}
            for entry in entries
        }
        allowed_assets = [name for names in assets.values() for name in names]
        # Names arrive as "Live Objects (L0)"; the model is asked to spell them
        # exactly, but a paragraph that drops the link-type suffix is still
        # naming a supplied asset and should not be discarded for punctuation.
        allowed_bare = {a.split(" (")[0].strip().lower() for a in allowed_assets}

        by_id = {e["id"]: e for e in entries}
        stripped: list[dict[str, str]] = []
        written: dict[str, Any] = {}

        for raw in payload.get("competitors") or []:
            if not isinstance(raw, dict):
                continue
            cid = str(raw.get("id", "")).strip()
            if cid not in by_id:
                stripped.append({"competitor": cid or "?", "reason": "not a competitor on this topic"})
                continue

            activity = raw.get("activity") or {}
            text = str(activity.get("text", "")).strip()
            cited = [p for p in activity.get("pages") or [] if p in allowed_pages.get(cid, set())]
            if _NUMERIC_CLAIM_RE.search(text):
                stripped.append({"competitor": cid, "reason": "activity contained a generated quantity"})
                text = ""
            if text and by_id[cid]["profile_status"] == "profiled" and not cited:
                stripped.append({"competitor": cid, "reason": "activity cited no page of theirs"})
                text = ""

            diff = str(raw.get("differentiation", "")).strip()
            used = [a for a in raw.get("orange_assets") or [] if str(a).strip()]
            unverified = [a for a in used
                          if str(a).split(" (")[0].strip().lower() not in allowed_bare]
            if _NUMERIC_CLAIM_RE.search(diff):
                stripped.append({"competitor": cid, "reason": "differentiation contained a quantity"})
                diff = ""
            elif unverified:
                stripped.append({
                    "competitor": cid,
                    "reason": f"differentiation named unsupplied Orange assets: {', '.join(unverified[:3])}",
                })
                diff = ""
            elif len(diff) < 60:
                stripped.append({"competitor": cid, "reason": "differentiation too thin to use"})
                diff = ""

            concession = str(raw.get("concession", "")).strip()
            if _NUMERIC_CLAIM_RE.search(concession):
                concession = ""

            written[cid] = {
                "activity": {"text": text, "pages": cited},
                "differentiation": diff,
                "orange_assets": [a for a in used if a not in unverified],
                "concession": concession,
            }

        field = str(payload.get("field", "")).strip()
        if _NUMERIC_CLAIM_RE.search(field):
            stripped.append({"competitor": "field", "reason": "contained a generated quantity"})
            field = ""

        narrative = {"per_competitor": written, "field": field}
        self._store(topic, entries, narrative=narrative, stripped=stripped)
        return {"narrative": narrative, "stripped": stripped}

    # ------------------------------------------------------------- helpers
    def _signals(self, topic_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """SELECT s.id, s.title, s.publisher, s.published_at, s.tier
               FROM signals s JOIN opportunity_signals os ON os.signal_id = s.id
               WHERE os.opportunity_id = ? ORDER BY s.tier ASC, s.published_at DESC LIMIT 12""",
            (topic_id,))
        return [dict(r) for r in rows]

    def _named_assets(self, topic_id: str) -> dict[str, list[str]]:
        rows = self.db.query(
            """SELECT l.node_id, l.link_type, n.label FROM opportunity_links l
               JOIN graph_nodes n ON n.id = l.node_id
               WHERE l.opportunity_id = ? AND l.rejected = 0""",
            (topic_id,))
        assets: dict[str, list[str]] = {}
        for row in rows:
            kind = row["node_id"].split(":", 1)[0]
            assets.setdefault(kind, []).append(f"{row['label']} ({row['link_type']})")
        return assets

    def _is_current(self, topic: dict[str, Any]) -> bool:
        from .pipeline import prompts
        row = self.db.query_one(
            """SELECT topic_version, narrative, prompt_version, register_version
               FROM topic_competitor_analysis WHERE opportunity_id = ?""", (topic["id"],))
        if row is None or not row["narrative"]:
            return False
        return (row["topic_version"] == topic["version"]
                and row["prompt_version"] == prompts.PROMPT_VERSION_COMPETITOR_ANALYSIS
                and row["register_version"] == self.cfg.competitors_raw["version"])

    def _store(self, topic: dict[str, Any], entries: list[dict[str, Any]],
               narrative: dict[str, Any] | None, stripped: list[dict[str, str]] | None = None,
               keep_narrative: bool = False) -> None:
        from .pipeline import prompts
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        coverage = {
            "on_topic": len(entries),
            "profiled": sum(1 for e in entries if e["profile_status"] == "profiled"),
            "blocked": sum(1 for e in entries if e["profile_status"] in ("blocked", "unreachable")),
            "unread": sum(1 for e in entries if e["profile_status"] in ("unread", "no_pages")),
            "register": profile_coverage(self.db, self.cfg),
        }
        existing = self.db.query_one(
            "SELECT narrative, stripped FROM topic_competitor_analysis WHERE opportunity_id = ?",
            (topic["id"],))
        if narrative is None and keep_narrative and existing is not None:
            # Re-running the join must not throw away a comparison that is still
            # valid: the join is cheap and runs often, the writing is neither.
            narrative_json = existing["narrative"]
            stripped_json = existing["stripped"]
        else:
            narrative_json = js(narrative) if narrative else None
            stripped_json = js(stripped or [])

        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO topic_competitor_analysis
                       (opportunity_id, computed_at, topic_version, entries, narrative, stripped,
                        coverage, register_version, prompt_version, model_version, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(opportunity_id) DO UPDATE SET
                       computed_at=excluded.computed_at, topic_version=excluded.topic_version,
                       entries=excluded.entries, narrative=excluded.narrative,
                       stripped=excluded.stripped, coverage=excluded.coverage,
                       register_version=excluded.register_version,
                       prompt_version=excluded.prompt_version,
                       model_version=excluded.model_version""",
                (topic["id"], now, topic["version"], js(entries), narrative_json, stripped_json,
                 js(coverage), self.cfg.competitors_raw["version"],
                 prompts.PROMPT_VERSION_COMPETITOR_ANALYSIS if narrative_json else None,
                 getattr(self.llm if self._llm else None, "strong_model", None),
                 self.pipeline_version),
            )


def analysis_for_topic(db: Database, topic_id: str) -> dict[str, Any] | None:
    row = db.query_one(
        "SELECT * FROM topic_competitor_analysis WHERE opportunity_id = ?", (topic_id,))
    return analysis_from_row(row)


def analysis_from_row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["entries"] = unjs(data.get("entries"), [])
    data["coverage"] = unjs(data.get("coverage"), {})
    data["stripped"] = unjs(data.get("stripped"), [])
    data["narrative"] = unjs(data.get("narrative"), None)
    per = (data.get("narrative") or {}).get("per_competitor", {})
    # Merge the written half onto the structural half, so the interface and the
    # brief both read one list rather than joining two.
    for entry in data["entries"]:
        entry["written"] = per.get(entry["id"])
    data["has_narrative"] = bool(data.get("narrative"))
    return data
