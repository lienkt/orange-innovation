"""Long-form topic description and solution diagram (FR-14, FR-18, §4.9).

The topic detail already answers "what is this and why now" in fragments: a
statement, cited claims, a link list, a score breakdown. What it does not do is
say the thing out loud, in the order a salesperson preparing a meeting needs it,
with the competitive picture and the questions to ask. That is what this stage
generates, and it is the same content the PDF brief renders.

Generation is the risky part of the system, so every defence used in synthesis
(§4.4.4) is reused here, in the same order of effectiveness:

  1. Evidence binding      the factual sections must cite signal ids that are
                           actually attached to this topic. Uncited factual
                           sections are STRIPPED, not rewritten.
  2. Closed vocabularies    the diagram's `provider` values are enumerated, and
                           a box claiming to be an Orange asset must name one
                           that was supplied.
  3. No model numbers       a regex over every generated sentence. The brief's
                           figures come from the sizing engine, and a model
                           sentence that contradicts them is worse than absent.
  4. Named-entity check     no customer, partner or competitor beyond the lists
                           supplied — the failure most likely to be repeated in
                           a meeting as though it were a known Orange fact.

The diagram deserves a note. The model does not draw anything: it emits a
STRUCTURE — layers, boxes, flows — which `radar.brief` renders with the same
geometry every time. A model asked for SVG or drawing code produces something
that looks plausible and overlaps its own labels; a model asked for structure
produces something a renderer can guarantee.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..competition import CompetitionAnalyser, competition_for_topic
from ..config import Config
from ..db import Database, js, unjs
from ..llm import LLMClient
from . import prompts
from .synthesis import _NUMERIC_CLAIM_RE

log = logging.getLogger(__name__)

PROVIDERS = ("orange", "partner", "customer", "third_party")
MAX_LAYERS = 5
MAX_NODES_PER_LAYER = 4
MAX_FLOWS = 8


class DescriptionGenerator:
    def __init__(self, cfg: Config, db: Database, llm: LLMClient):
        self.cfg = cfg
        self.db = db
        self.llm = llm

    # ------------------------------------------------------------------

    def run(self, states: tuple[str, ...] = ("active", "watchlist", "fading"),
            topic_ids: list[str] | None = None, limit: int | None = None,
            force: bool = False, max_workers: int = 4) -> dict[str, Any]:
        """Generate descriptions for topics that need one.

        A description is regenerated when the topic's version has moved on:
        §4.1's "design for the refresh" applies to prose as much as to scores —
        a brief describing evidence the topic no longer rests on is worse than
        no brief.
        """
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
                f"SELECT * FROM opportunity_spaces WHERE merged_into IS NULL AND state IN ({placeholders}) "
                f"ORDER BY id", states,
            )
        stale = [dict(r) for r in rows if force or self._is_stale(r["id"], r["version"])]
        pending = stale[:limit] if limit else stale
        deferred = len(stale) - len(pending)
        if deferred:
            # §4.12: a silent cap reads as "we covered everything". Say what was
            # left, and how to ask for it.
            log.warning(
                "%d topic(s) still need a description and were left for the next run "
                "(cap %d). Run `radar describe --limit N` to write more now.",
                deferred, limit,
            )

        stats = {"considered": len(rows), "generated": 0, "failed": 0,
                 "sections_stripped": 0, "diagrams": 0,
                 "skipped_fresh": len(rows) - len(stale), "deferred_by_cap": deferred}
        if not pending:
            return stats

        def work(topic: dict[str, Any]) -> None:
            try:
                result = self.generate(topic)
            except Exception as exc:  # noqa: BLE001 — one bad topic must not stop the stage
                log.warning("Description generation failed for %s: %s", topic["id"], exc)
                stats["failed"] += 1
                return
            stats["generated"] += 1
            stats["sections_stripped"] += len(result["stripped"])
            stats["diagrams"] += 1 if result["sections"].get("diagram") else 0

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="describe") as pool:
            list(pool.map(work, pending))
        return stats

    def _is_stale(self, topic_id: str, version: int) -> bool:
        row = self.db.query_one(
            "SELECT topic_version FROM topic_descriptions WHERE opportunity_id = ?", (topic_id,)
        )
        return row is None or row["topic_version"] != version

    # ------------------------------------------------------------------

    def generate(self, topic: dict[str, Any]) -> dict[str, Any]:
        """One topic: prompt, validate, persist."""
        signals = self._signals(topic["id"])
        assets = self._named_assets(topic["id"])
        competition = competition_for_topic(self.db, topic["id"])
        if competition is None:
            # The narrative names competitors, so it cannot run before they are
            # known. Computing it here is cheap and keeps the stages orderable
            # in any sequence.
            competition = CompetitionAnalyser(self.cfg, self.db).assess(topic)

        payload = self.llm.complete_json(
            prompts.description_system_prompt(self.cfg),
            prompts.format_topic_for_description(
                dict(topic) | {"why_hot": unjs(topic["why_hot"], []) or []},
                signals, assets, competition,
                {
                    "vertical": self.cfg.verticals.label(topic["vertical"]),
                    "use_case": self.cfg.use_cases.label(topic["use_case"]),
                    "technology": self.cfg.technologies.label(topic["technology"]),
                },
            ),
            strong=True, temperature=0.35, max_tokens=3000,
        )

        allowed_names = self._allowed_names(assets, competition)
        sections, stripped = self._validate_sections(payload, {s["id"] for s in signals}, allowed_names)
        sections["qualifying_questions"] = self._validate_list(
            payload.get("qualifying_questions"), stripped, "qualifying_questions", limit=6
        )
        sections["objection_handling"] = self._validate_objections(payload, stripped)
        diagram = self._validate_diagram(payload.get("diagram"), assets, stripped)
        if diagram:
            sections["diagram"] = diagram

        self._store(topic, sections, stripped)
        return {"sections": sections, "stripped": stripped}

    # -- validation --------------------------------------------------------

    def _validate_sections(self, payload: dict[str, Any], valid_signal_ids: set[str],
                           allowed_names: list[str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
        stripped: list[dict[str, str]] = []
        out: dict[str, Any] = {}
        raw = payload.get("sections") or {}
        declared = payload.get("entities_named")
        unverified = self._unverified_names(declared, allowed_names)

        for name in prompts.DESCRIPTION_SECTIONS:
            entry = raw.get(name)
            if not isinstance(entry, dict):
                stripped.append({"section": name, "reason": "missing from the model output"})
                continue
            text = str(entry.get("text", "")).strip()
            if len(text) < 40:
                stripped.append({"section": name, "reason": "empty or too short to be useful"})
                continue
            # Defence 3, applied to prose exactly as it is applied to claims.
            if _NUMERIC_CLAIM_RE.search(text):
                stripped.append({"section": name, "reason": "contained a generated quantity"})
                continue
            cited = [s for s in entry.get("signals") or [] if s in valid_signal_ids]
            if name in prompts.CITED_SECTIONS and not cited:
                stripped.append({"section": name, "reason": "no claim survived evidence binding"})
                continue
            if unverified and self._names_in(text, unverified):
                stripped.append({
                    "section": name,
                    "reason": f"named entities that were never supplied: {', '.join(unverified[:4])}",
                })
                continue
            out[name] = {"text": text, "signals": cited}
        return out, stripped

    def _validate_list(self, values: Any, stripped: list[dict[str, str]], name: str,
                       limit: int) -> list[str]:
        if not isinstance(values, list):
            stripped.append({"section": name, "reason": "missing from the model output"})
            return []
        kept = []
        for value in values:
            text = str(value).strip()
            if len(text) < 12:
                continue
            if _NUMERIC_CLAIM_RE.search(text):
                stripped.append({"section": name, "reason": "an entry contained a generated quantity"})
                continue
            kept.append(text)
        return kept[:limit]

    def _validate_objections(self, payload: dict[str, Any],
                             stripped: list[dict[str, str]]) -> list[dict[str, str]]:
        entries = payload.get("objection_handling")
        if not isinstance(entries, list):
            stripped.append({"section": "objection_handling", "reason": "missing from the model output"})
            return []
        kept = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            objection = str(entry.get("objection", "")).strip()
            response = str(entry.get("response", "")).strip()
            if len(objection) < 8 or len(response) < 20:
                continue
            if _NUMERIC_CLAIM_RE.search(objection + " " + response):
                stripped.append({"section": "objection_handling",
                                 "reason": "an entry contained a generated quantity"})
                continue
            kept.append({"objection": objection, "response": response})
        return kept[:4]

    def _validate_diagram(self, diagram: Any, assets: dict[str, list[str]],
                          stripped: list[dict[str, str]]) -> dict[str, Any] | None:
        """Closed-vocabulary validation on the diagram structure.

        The rule that matters is the `orange` provider: a box claiming to be an
        Orange asset must name one that was supplied, otherwise the picture
        asserts a capability nobody can check — the visual equivalent of the
        invented account name the next-action prompt exists to prevent. Such a
        box is not dropped (the architecture still needs that component), it is
        demoted to third_party and the picture stays honest.
        """
        if not isinstance(diagram, dict):
            stripped.append({"section": "diagram", "reason": "missing from the model output"})
            return None
        supplied = [a.split(" (")[0].strip().lower() for values in assets.values() for a in values]

        layers: list[dict[str, Any]] = []
        node_labels: set[str] = set()
        demoted = 0
        for layer in (diagram.get("layers") or [])[:MAX_LAYERS]:
            if not isinstance(layer, dict):
                continue
            nodes = []
            for node in (layer.get("nodes") or [])[:MAX_NODES_PER_LAYER]:
                if not isinstance(node, dict):
                    continue
                label = str(node.get("label", "")).strip()[:42]
                if not label:
                    continue
                provider = str(node.get("provider", "third_party")).strip().lower()
                if provider not in PROVIDERS:
                    provider = "third_party"
                if provider == "orange":
                    needle = label.lower()
                    if not any(needle in item or item in needle for item in supplied if len(item) > 3):
                        provider = "third_party"
                        demoted += 1
                nodes.append({"label": label, "provider": provider})
                node_labels.add(label)
            if nodes:
                layers.append({"label": str(layer.get("label", "")).strip()[:34], "nodes": nodes})

        if len(layers) < 2:
            stripped.append({"section": "diagram", "reason": "fewer than two usable layers"})
            return None

        flows = []
        for flow in (diagram.get("flows") or [])[:MAX_FLOWS]:
            if not isinstance(flow, dict):
                continue
            source, target = str(flow.get("from", "")).strip(), str(flow.get("to", "")).strip()
            # A flow between boxes that do not exist would draw an arrow to
            # nowhere, so unresolvable flows are dropped rather than guessed.
            if source in node_labels and target in node_labels and source != target:
                flows.append({"from": source, "to": target, "label": str(flow.get("label", "")).strip()[:26]})

        if demoted:
            stripped.append({
                "section": "diagram",
                "reason": f"{demoted} box(es) claimed to be an Orange asset that was not supplied — "
                          f"shown as third-party instead",
            })
        return {
            "title": str(diagram.get("title", "")).strip()[:70],
            "caption": str(diagram.get("caption", "")).strip()[:220],
            "layers": layers,
            "flows": flows,
        }

    # -- named-entity guard ------------------------------------------------

    def _allowed_names(self, assets: dict[str, list[str]],
                       competition: dict[str, Any] | None) -> list[str]:
        allowed = [a.split(" (")[0].strip().lower() for values in assets.values() for a in values]
        allowed += [o["label"].lower() for o in self.cfg.offers.get("offers", [])]
        allowed += [r["label"].lower() for r in self.cfg.references.get("named", [])]
        allowed += [p["label"].lower() for p in self.cfg.assets.get("partners", [])]
        allowed += [c["label"].lower() for c in self.cfg.assets.get("certifications", [])]
        allowed += [p["label"].lower() for p in self.cfg.assets.get("capability_pools", [])]
        allowed += [c["label"].lower() for c in (competition or {}).get("competitors", [])]
        allowed += ["orange", "orange business", "orange cyberdefense", "orange group", "eurostat", "ted"]
        return [a for a in allowed if a]

    def _unverified_names(self, declared: Any, allowed: list[str]) -> list[str]:
        if not isinstance(declared, list):
            return []
        unverified = []
        for name in declared:
            needle = str(name).split(" (")[0].strip().lower()
            if len(needle) < 3:
                continue
            if any(needle in item or item in needle for item in allowed):
                continue
            unverified.append(str(name))
        return unverified

    @staticmethod
    def _names_in(text: str, names: list[str]) -> bool:
        lowered = text.lower()
        return any(re.search(rf"(?<![\w-]){re.escape(n.lower())}(?![\w-])", lowered) for n in names)

    # -- inputs ------------------------------------------------------------

    def _signals(self, topic_id: str) -> list[dict[str, Any]]:
        rows = self.db.query(
            """SELECT s.id, s.title, s.extract, s.publisher, s.published_at, s.tier, s.url
               FROM signals s JOIN opportunity_signals os ON os.signal_id = s.id
               WHERE os.opportunity_id = ? ORDER BY s.tier ASC, s.published_at DESC""",
            (topic_id,),
        )
        return [dict(r) for r in rows]

    def _named_assets(self, topic_id: str) -> dict[str, list[str]]:
        rows = self.db.query(
            """SELECT l.node_id, l.link_type, n.label FROM opportunity_links l
               JOIN graph_nodes n ON n.id = l.node_id
               WHERE l.opportunity_id = ? AND l.rejected = 0""",
            (topic_id,),
        )
        assets: dict[str, list[str]] = {}
        for row in rows:
            kind = row["node_id"].split(":", 1)[0]
            assets.setdefault(kind, []).append(f"{row['label']} ({row['link_type']})")
        return assets

    # -- persistence -------------------------------------------------------

    def _store(self, topic: dict[str, Any], sections: dict[str, Any],
               stripped: list[dict[str, str]]) -> None:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO topic_descriptions
                       (opportunity_id, generated_at, topic_version, sections, stripped,
                        prompt_version, model_version, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(opportunity_id) DO UPDATE SET
                       generated_at=excluded.generated_at, topic_version=excluded.topic_version,
                       sections=excluded.sections, stripped=excluded.stripped,
                       prompt_version=excluded.prompt_version, model_version=excluded.model_version,
                       pipeline_version=excluded.pipeline_version""",
                (topic["id"], now, topic["version"], js(sections), js(stripped),
                 prompts.PROMPT_VERSION_DESCRIPTION, self.llm.strong_model, self.cfg.pipeline_version),
            )


def description_for_topic(db: Database, topic_id: str) -> dict[str, Any] | None:
    """Stored description, shaped for the read model, the API and the brief."""
    row = db.query_one("SELECT * FROM topic_descriptions WHERE opportunity_id = ?", (topic_id,))
    if row is None:
        return None
    topic = db.query_one("SELECT version FROM opportunity_spaces WHERE id = ?", (topic_id,))
    sections = unjs(row["sections"], {}) or {}
    return {
        "sections": {k: v for k, v in sections.items()
                     if k not in ("diagram", "qualifying_questions", "objection_handling")},
        "section_order": [s for s in prompts.DESCRIPTION_SECTIONS if s in sections],
        "section_titles": {
            "summary": "In one paragraph",
            "what_is_changing": "What has changed",
            "who_buys_and_why": "Who buys, and why now",
            "what_orange_would_deliver": "What Orange would deliver",
            "why_orange_can_win": "Why Orange can win",
            "competitive_landscape": "Competitive landscape",
            "risks_and_unknowns": "Risks and unknowns",
        },
        "qualifying_questions": sections.get("qualifying_questions", []),
        "objection_handling": sections.get("objection_handling", []),
        "diagram": sections.get("diagram"),
        "stripped": unjs(row["stripped"], []) or [],
        "generated_at": row["generated_at"],
        "topic_version": row["topic_version"],
        # §4.1: a description of a topic that has since moved on is worse than
        # none, so staleness is reported rather than left for the reader to spot.
        "stale": bool(topic and topic["version"] != row["topic_version"]),
        "provenance": {
            "prompt_version": row["prompt_version"],
            "model_version": row["model_version"],
            "pipeline_version": row["pipeline_version"],
        },
    }
