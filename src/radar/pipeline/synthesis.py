"""Pipeline stages 5-6a: Synthesise and curate (Table 16).

Theme clusters + taxonomy -> candidate opportunity spaces -> curated topics.

This module implements the four hallucination defences of §4.4.4 in the order
the document ranks them by effectiveness:

  1. Evidence binding      — every claim references signal ids that must exist
                             in the cluster that produced the candidate.
                             Uncited claims are STRIPPED, not rewritten.
  2. Closed-vocabulary out — taxonomy values validated against the enumerations.
  3. No numbers            — enforced in the prompt (llm.NO_NUMBERS_RULE) and
                             detected here as a critic test.
  4. Entailment check      — a cheap second pass on the "why hot" claims.

and the identity rules of §4.4.5, which are what make momentum measurable:
canonical identity is the taxonomy triple; a recurring topic is UPDATED, not
recreated (DR-03).
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from concurrent.futures import ThreadPoolExecutor

from ..config import Config
from ..db import Database, js, unjs
from ..embeddings import Embedder
from ..llm import LLMClient
from . import prompts

log = logging.getLogger(__name__)

#: Used when a helper is called outside the parallel path.
_NULL_LOCK = threading.Lock()

# Numbers the model must never invent (§4.4.4 defence 3). Years and small
# ordinals are allowed through — "2027" in a claim usually comes from a cited
# regulatory deadline, and the entailment check is the right tool for that.
_NUMERIC_CLAIM_RE = re.compile(
    r"(\d+\s*(?:%|percent|per cent))"
    r"|([€$£]\s*\d)"
    r"|(\d+(?:[.,]\d+)?\s*(?:bn|billion|m\b|million|k\b|thousand))"
    r"|(\d+(?:[.,]\d+)?\s*x\b)",
    re.I,
)


@dataclass
class Candidate:
    vertical: str
    use_case: str
    technology: str
    statement: str
    domains: list[str] = field(default_factory=list)
    personas: list[str] = field(default_factory=list)
    geographies: list[str] = field(default_factory=list)
    why_hot: list[dict[str, Any]] = field(default_factory=list)
    why_specific: str = ""
    cluster_id: int | None = None
    critic_score: int | None = None
    critic_notes: str = ""
    rejection: str | None = None

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.vertical, self.use_case, self.technology)

    @property
    def signal_ids(self) -> list[str]:
        out: list[str] = []
        for claim in self.why_hot:
            out.extend(claim.get("signals", []))
        return sorted(set(out))


@dataclass
class SynthesisStats:
    clusters_processed: int = 0
    raw_candidates: int = 0
    failed_vocabulary: int = 0
    failed_specificity: int = 0
    failed_evidence: int = 0
    failed_critic: int = 0
    merged_duplicates: int = 0
    accepted: int = 0
    entailment_stripped: int = 0
    rounds: int = 1
    rejections: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        data = {k: v for k, v in self.__dict__.items() if k != "rejections"}
        data["rejections_sample"] = self.rejections[:20]
        return data


class Synthesiser:
    def __init__(self, cfg: Config, db: Database, llm: LLMClient, embedder: Embedder | None = None):
        self.cfg = cfg
        self.db = db
        self.llm = llm
        self.embedder = embedder or Embedder()
        cur = cfg.settings["curation"]
        self.min_chars = int(cur["statement_min_chars"])
        self.max_chars = int(cur["statement_max_chars"])
        self.banned = {b.lower() for b in cur["banned_generic_statements"]}
        self.dup_threshold = float(cur["duplicate_similarity_threshold"])
        self.critic_min = int(cur["critic_min_score"])
        self.temperature = float(cfg.settings["llm"]["temperature_synthesis"])
        self.critic_temperature = float(cfg.settings["llm"]["temperature_critic"])

    # -- stage 5 -----------------------------------------------------------

    def run(self, refresh_id: str, max_clusters: int | None = None,
            run_critic: bool = True, run_entailment: bool = True,
            target_topics: int | None = None, max_rounds: int = 4) -> SynthesisStats:
        """Synthesise candidates, optionally looping until a topic target is met.

        §4.4.3's coverage-driven prompting is what makes a target sensible
        rather than arbitrary: each round recomputes which taxonomy cells have
        evidence but no candidate yet, so a second round explores the grid
        rather than re-elaborating what the first round already produced.

        The loop stops on whichever comes first — the target, the round cap, or
        a round that adds nothing. That last condition matters: without it, a
        target higher than the evidence can support would spin, and §4.1's whole
        posture is that an empty answer is a valid one.
        """
        overall = SynthesisStats()
        rounds = 0
        while True:
            rounds += 1
            stats = self._run_once(refresh_id, max_clusters, run_critic, run_entailment)
            for field_name in ("clusters_processed", "raw_candidates", "failed_vocabulary",
                              "failed_specificity", "failed_evidence", "failed_critic",
                              "merged_duplicates", "accepted", "entailment_stripped"):
                setattr(overall, field_name,
                        getattr(overall, field_name) + getattr(stats, field_name))
            overall.rejections.extend(stats.rejections)

            if target_topics is None:
                break
            live = self.db.query_one(
                "SELECT COUNT(*) n FROM opportunity_spaces WHERE merged_into IS NULL"
            )["n"]
            log.info("round %d: %d topics live (target %d)", rounds, live, target_topics)
            if live >= target_topics:
                log.info("target reached after %d round(s)", rounds)
                break
            if rounds >= max_rounds:
                log.warning("stopping at round cap %d with %d topics — the evidence did not "
                            "support the target", max_rounds, live)
                break
            if stats.accepted == 0:
                log.warning("round %d added nothing; the evidenced grid is covered. Stopping at %d "
                            "topics rather than manufacturing more.", rounds, live)
                break
        overall.rounds = rounds
        return overall

    def _run_once(self, refresh_id: str, max_clusters: int | None = None,
                  run_critic: bool = True, run_entailment: bool = True) -> SynthesisStats:
        stats = SynthesisStats()
        # Read the current cluster set rather than this refresh's, so that
        # stages can be run in separate invocations (`radar refresh --stages
        # themes` then `--stages synthesise`) without silently finding nothing.
        # The themes stage replaces the cluster table wholesale, so whatever is
        # present is by definition the latest clustering.
        clusters = self.db.query(
            "SELECT id FROM clusters ORDER BY size DESC" +
            (f" LIMIT {int(max_clusters)}" if max_clusters else "")
        )
        if not clusters:
            log.warning("No clusters present — run the `themes` stage first. Nothing to synthesise.")
            return stats

        target_cells = self._coverage_targets()

        # Clusters are independent until the deduplication step, and each one
        # spends most of its time waiting on the model (generation passes,
        # critic, entailment), so they are processed concurrently. Nothing is
        # written to the database until _persist below, so there is no write
        # contention to manage here — only the shared stats counters, which take
        # a lock.
        lock = threading.Lock()
        accepted: list[Candidate] = []

        def process(cluster_id: int) -> None:
            payload = self._cluster_payload(cluster_id)
            if not payload["signals"]:
                return
            candidates = self._generate(payload, target_cells)
            with lock:
                stats.clusters_processed += 1
                stats.raw_candidates += len(candidates)

            valid_ids = {s["id"] for s in payload["signals"]}
            survivors: list[Candidate] = []
            for candidate in candidates:
                candidate.cluster_id = cluster_id
                with lock:
                    ok = self._validate(candidate, valid_ids, stats)
                if not ok:
                    continue
                if run_critic:
                    # The critic compares against neighbouring candidates, so it
                    # reads the shared accepted list — a snapshot is enough and
                    # avoids holding the lock across a model call.
                    with lock:
                        neighbours = list(accepted[-8:])
                    if not self._criticise(candidate, payload, neighbours, stats, lock):
                        continue
                if run_entailment:
                    self._entailment_check(candidate, payload, stats, lock)
                    if not candidate.why_hot:
                        with lock:
                            stats.failed_evidence += 1
                            stats.rejections.append(
                                {"statement": candidate.statement, "reason": "all claims failed entailment"}
                            )
                        continue
                survivors.append(candidate)
                with lock:
                    accepted.append(candidate)
            log.info("cluster %s → %d candidates, %d survived", cluster_id, len(candidates), len(survivors))

        workers = max(1, int(self.cfg.settings["llm"].get("max_parallel_clusters", 4)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="cluster") as pool:
            list(pool.map(process, [row["id"] for row in clusters]))

        # Near-duplicate merge across the whole batch (§4.4.5).
        deduped = self._deduplicate(accepted, stats)
        self._persist(deduped, refresh_id, stats)
        stats.accepted = len(deduped)
        return stats

    def _cluster_payload(self, cluster_id: int) -> dict[str, Any]:
        cluster = self.db.query_one("SELECT * FROM clusters WHERE id = ?", (cluster_id,))
        signals = self.db.query(
            "SELECT id, title, extract, publisher, published_at, signal_type, tier, geographies, url "
            "FROM signals WHERE cluster_id = ? ORDER BY tier ASC, published_at DESC LIMIT 14",
            (cluster_id,),
        )
        return {
            "cluster_id": cluster_id,
            "label": cluster["label"] if cluster else "",
            "keyphrases": cluster["keyphrases"] if cluster else "[]",
            "signals": [dict(s) for s in signals],
        }

    def _coverage_targets(self) -> list[dict[str, str]]:
        """Grid cells with evidence but no candidate yet (§4.4.3).

        "This converts brainstorming from 'produce more ideas' into 'cover the
        evidenced grid', which terminates and is measurable."
        """
        existing = {
            (r["vertical"], r["use_case"], r["technology"])
            for r in self.db.query(
                "SELECT vertical, use_case, technology FROM opportunity_spaces WHERE merged_into IS NULL"
            )
        }
        targets: list[dict[str, str]] = []
        for use_case in self.cfg.use_cases:
            for domain_id in use_case.get("domains") or []:
                for vertical in self.cfg.verticals:
                    for tech_id in _technologies_for_domain(self.cfg, domain_id)[:2]:
                        cell = (vertical.id, use_case.id, tech_id)
                        if cell not in existing:
                            targets.append(
                                {"vertical": vertical.id, "use_case": use_case.id, "technology": tech_id}
                            )
        return targets

    #: §4.4.3 warns that an open-ended brainstorming loop "tends to produce
    #: volume rather than coverage: the model elaborates around whatever it
    #: produced first". Passes are therefore given DIFFERENT EVIDENCE LENSES
    #: rather than just a different random seed — each pass is told which kind
    #: of signal to reason from, so the passes explore genuinely different parts
    #: of the same cluster instead of paraphrasing one another.
    GENERATION_LENSES = (
        "Reason primarily from the REGULATORY and compliance evidence in this cluster. "
        "What becomes non-optional, for whom, and by when?",
        "Reason primarily from the PROCUREMENT and buying evidence in this cluster. "
        "Who is already spending, on what, and what would they buy next?",
        "Reason primarily from the TECHNOLOGY MATURITY and deployment evidence in this "
        "cluster. What has just become deployable that was not before?",
        "Reason from the CROSS-VERTICAL angle: this cluster's evidence may be concentrated "
        "in one sector, but the same problem may be more acute in another. Say which.",
    )

    def _generate(self, payload: dict[str, Any], target_cells: list[dict[str, str]]) -> list[Candidate]:
        """Over-produce candidates for one cluster (§4.4.3).

        "It is cheaper to generate forty candidates and keep eight than to coax
        eight good ones out of a single careful pass." So the cluster is passed
        over `candidates_per_cluster` times at high temperature, each pass under
        a different evidence lens, and the pool is deduplicated and critiqued
        afterwards. Passes are independent, so they run concurrently.
        """
        system = prompts.synthesis_system_prompt(self.cfg)
        passes = max(1, int(self.cfg.settings["curation"].get("candidates_per_cluster", 1)))

        def one_pass(index: int) -> list[Candidate]:
            lens = self.GENERATION_LENSES[index % len(self.GENERATION_LENSES)] if passes > 1 else None
            user = prompts.synthesis_user_prompt(payload, target_cells, lens=lens)
            try:
                data = self.llm.complete_json(
                    system, user, strong=True, temperature=self.temperature, max_tokens=4000
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Synthesis pass %d failed for cluster %s: %s", index, payload["cluster_id"], exc)
                return []
            return self._parse(data)

        out: list[Candidate] = []
        if passes == 1:
            return one_pass(0)
        with ThreadPoolExecutor(max_workers=passes, thread_name_prefix="synth") as pool:
            for result in pool.map(one_pass, range(passes)):
                out.extend(result)
        return out

    @staticmethod
    def _parse(data: dict[str, Any]) -> list[Candidate]:
        out: list[Candidate] = []
        for entry in data.get("candidates", []) or []:
            if not isinstance(entry, dict):
                continue
            try:
                out.append(
                    Candidate(
                        vertical=str(entry.get("vertical", "")).strip(),
                        use_case=str(entry.get("use_case", "")).strip(),
                        technology=str(entry.get("technology", "")).strip(),
                        statement=str(entry.get("statement", "")).strip(),
                        domains=[str(d) for d in entry.get("domains") or []],
                        personas=[str(p) for p in entry.get("personas") or []],
                        geographies=[str(g).upper() for g in entry.get("geographies") or []],
                        why_hot=[c for c in entry.get("why_hot") or [] if isinstance(c, dict)],
                        why_specific=str(entry.get("why_specific", "")).strip(),
                    )
                )
            except (TypeError, ValueError):
                continue
        return out

    # -- stage 6a: validation ---------------------------------------------

    def _validate(self, candidate: Candidate, valid_signal_ids: set[str], stats: SynthesisStats) -> bool:
        """Closed vocabulary, specificity and evidence binding (§4.4.4)."""
        # 2. Closed-vocabulary output. One retry via synonym resolution, then drop.
        for field_name, vocab in (
            ("vertical", self.cfg.verticals),
            ("use_case", self.cfg.use_cases),
            ("technology", self.cfg.technologies),
        ):
            value = getattr(candidate, field_name)
            if value not in vocab:
                repaired = vocab.resolve(value)
                if repaired is None:
                    stats.failed_vocabulary += 1
                    stats.rejections.append(
                        {"statement": candidate.statement, "reason": f"invalid {field_name}: {value!r}"}
                    )
                    return False
                setattr(candidate, field_name, repaired)

        candidate.domains = [d for d in candidate.domains if d in self.cfg.domains]
        candidate.personas = [p for p in candidate.personas if p in self.cfg.personas]
        if not candidate.domains:
            # Route via the use case's declared domains rather than dropping the
            # candidate: the domain is derivable, so a missing one is a prompt
            # miss, not a substantive failure.
            candidate.domains = list(self.cfg.use_cases[candidate.use_case].get("domains") or [])

        # Specificity validation (§4.4 principle 4, FR-06). "A candidate that
        # does not resolve to exactly one vertical, one use case and one
        # technology fails validation."
        statement = candidate.statement.strip()
        if not (self.min_chars <= len(statement) <= self.max_chars):
            stats.failed_specificity += 1
            stats.rejections.append(
                {"statement": statement, "reason": f"statement length {len(statement)} outside "
                                                   f"[{self.min_chars},{self.max_chars}]"}
            )
            return False
        if statement.lower().strip(" .") in self.banned:
            stats.failed_specificity += 1
            stats.rejections.append({"statement": statement, "reason": "banned generic statement"})
            return False

        # 1. Evidence binding. Every claim must cite ids that exist IN THIS
        # CLUSTER. Uncited claims are stripped, not rewritten.
        kept: list[dict[str, Any]] = []
        for claim in candidate.why_hot:
            text = str(claim.get("claim", "")).strip()
            cited = [s for s in claim.get("signals", []) if s in valid_signal_ids]
            if text and cited:
                kept.append({"claim": text, "signals": cited})
        candidate.why_hot = kept
        if not candidate.why_hot:
            stats.failed_evidence += 1
            stats.rejections.append({"statement": statement, "reason": "no claim survived evidence binding"})
            return False
        return True

    def _criticise(self, candidate: Candidate, payload: dict[str, Any],
                   accepted: list[Candidate], stats: SynthesisStats,
                   lock: "threading.Lock | None" = None) -> bool:
        """Adversarial critique pass (§4.4.3)."""
        guard = lock or _NULL_LOCK
        neighbours = [c.statement for c in accepted[-8:]]
        system = prompts.critic_system_prompt(self.cfg)
        user = prompts.format_candidate_for_critic(
            candidate.__dict__, payload["signals"], neighbours
        )
        try:
            verdict = self.llm.complete_json(
                system, user, strong=True, temperature=self.critic_temperature, max_tokens=900
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Critic pass failed, keeping candidate unjudged: %s", exc)
            return True

        score = int(verdict.get("score", 0) or 0)
        candidate.critic_score = score
        candidate.critic_notes = "; ".join(str(i) for i in verdict.get("issues", [])[:4])

        # Deterministic backstop for defence 3: the critic is asked about
        # invented numbers, but a regex is not subject to model judgement.
        for claim in candidate.why_hot:
            if _NUMERIC_CLAIM_RE.search(claim["claim"]):
                candidate.critic_notes = (candidate.critic_notes + "; quantitative claim in generated text").strip("; ")
                score = min(score, 2)
                candidate.critic_score = score

        if verdict.get("verdict") == "revise" and verdict.get("revised_statement"):
            revised = str(verdict["revised_statement"]).strip()
            if self.min_chars <= len(revised) <= self.max_chars:
                candidate.statement = revised

        if score < self.critic_min:
            with guard:
                stats.failed_critic += 1
                stats.rejections.append(
                    {"statement": candidate.statement, "reason": f"critic score {score} < {self.critic_min}"
                                                                 f" ({candidate.critic_notes})"}
                )
            return False
        return True

    def _entailment_check(self, candidate: Candidate, payload: dict[str, Any], stats: SynthesisStats,
                          lock: "threading.Lock | None" = None) -> None:
        """§4.4.4 defence 4 — verify each claim is entailed by its cited span."""
        by_id = {s["id"]: s for s in payload["signals"]}
        survivors: list[dict[str, Any]] = []
        for claim in candidate.why_hot:
            spans = [
                f"[{sid}] {by_id[sid]['title']} — {by_id[sid]['extract'][:400]}"
                for sid in claim["signals"] if sid in by_id
            ]
            if not spans:
                continue
            try:
                result = self.llm.complete_json(
                    prompts.entailment_prompt(),
                    f"CLAIM: {claim['claim']}\n\nEVIDENCE SPANS:\n" + "\n".join(spans),
                    temperature=0.0, max_tokens=200,
                )
            except Exception:  # noqa: BLE001 — a failed check must not delete evidence
                survivors.append(claim)
                continue
            if result.get("supported"):
                survivors.append(claim)
            else:
                with (lock or _NULL_LOCK):
                    stats.entailment_stripped += 1
        candidate.why_hot = survivors

    # -- stage 6b: identity, dedup, persistence ---------------------------

    def _deduplicate(self, candidates: list[Candidate], stats: SynthesisStats) -> list[Candidate]:
        """§4.4.5 — canonical identity is the triple; near-duplicates merge."""
        by_triple: dict[tuple[str, str, str], Candidate] = {}
        for candidate in candidates:
            existing = by_triple.get(candidate.triple)
            if existing is None:
                by_triple[candidate.triple] = candidate
                continue
            # Same triple = same topic. Merge evidence, keep the better statement.
            stats.merged_duplicates += 1
            existing.why_hot = _merge_claims(existing.why_hot, candidate.why_hot)
            existing.geographies = sorted(set(existing.geographies) | set(candidate.geographies))
            existing.personas = sorted(set(existing.personas) | set(candidate.personas))
            if (candidate.critic_score or 0) > (existing.critic_score or 0):
                existing.statement = candidate.statement
                existing.critic_score = candidate.critic_score

        survivors = list(by_triple.values())
        if len(survivors) < 2:
            return survivors

        # Near-duplicates with DIFFERENT triples, detected by embedding
        # similarity on the statement (§4.4.5). §4.4.5 asks for human review the
        # first time each merge rule fires — the merge is recorded as a
        # curator-reviewable event rather than applied silently.
        vectors = self.embedder.encode([c.statement for c in survivors])
        similarity = vectors @ vectors.T
        merged_away: set[int] = set()
        for i in range(len(survivors)):
            if i in merged_away:
                continue
            for j in range(i + 1, len(survivors)):
                if j in merged_away or similarity[i, j] < self.dup_threshold:
                    continue
                stats.merged_duplicates += 1
                survivors[i].why_hot = _merge_claims(survivors[i].why_hot, survivors[j].why_hot)
                survivors[i].critic_notes = (
                    f"{survivors[i].critic_notes}; merged near-duplicate "
                    f"'{survivors[j].statement}' (cos={similarity[i, j]:.3f}) — pending curator review"
                ).strip("; ")
                merged_away.add(j)
        return [c for idx, c in enumerate(survivors) if idx not in merged_away]

    def _persist(self, candidates: list[Candidate], refresh_id: str, stats: SynthesisStats) -> None:
        """DR-03: a topic that recurs is UPDATED, not recreated."""
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        today = now[:10]
        with self.db.cursor() as cur:
            for candidate in candidates:
                existing = cur.execute(
                    "SELECT id, version, why_hot FROM opportunity_spaces "
                    "WHERE vertical=? AND use_case=? AND technology=? AND merged_into IS NULL",
                    candidate.triple,
                ).fetchone()

                if existing:
                    # Refresh: new signals attach, score is recomputed later,
                    # previous score is retained in history (§4.4.5).
                    merged = _merge_claims(unjs(existing["why_hot"], []) or [], candidate.why_hot)
                    cur.execute(
                        """UPDATE opportunity_spaces
                           SET version = version + 1, statement = ?, why_hot = ?, last_refresh = ?,
                               critic_score = ?, critic_notes = ?, prompt_version = ?, model_version = ?
                           WHERE id = ?""",
                        (candidate.statement, js(merged), today, candidate.critic_score,
                         candidate.critic_notes, prompts.PROMPT_VERSION_SYNTHESIS,
                         self.llm.strong_model, existing["id"]),
                    )
                    topic_id = existing["id"]
                else:
                    topic_id = self._next_id(cur)
                    cur.execute(
                        """INSERT INTO opportunity_spaces
                           (id, version, vertical, use_case, technology, statement, domains, personas,
                            geographies, state, state_reason, state_changed_at, why_hot, critic_score,
                            critic_notes, first_seen, last_refresh, pipeline_version, prompt_version, model_version)
                           VALUES (?,1,?,?,?,?,?,?,?,'candidate','emitted by synthesis',?,?,?,?,?,?,?,?,?)""",
                        (topic_id, candidate.vertical, candidate.use_case, candidate.technology,
                         candidate.statement, js(candidate.domains), js(candidate.personas),
                         js(candidate.geographies), today, js(candidate.why_hot), candidate.critic_score,
                         candidate.critic_notes, today, today, self.cfg.pipeline_version,
                         prompts.PROMPT_VERSION_SYNTHESIS, self.llm.strong_model),
                    )

                for signal_id in candidate.signal_ids:
                    cur.execute(
                        "INSERT OR IGNORE INTO opportunity_signals "
                        "(opportunity_id, signal_id, attached_at, refresh_id) VALUES (?,?,?,?)",
                        (topic_id, signal_id, now, refresh_id),
                    )

    @staticmethod
    def _next_id(cur) -> str:
        row = cur.execute(
            "SELECT id FROM opportunity_spaces WHERE id LIKE 'OS%' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return "OS001"
        try:
            return f"OS{int(row['id'][2:]) + 1:03d}"
        except ValueError:
            return f"OS{dt.datetime.now().strftime('%H%M%S')}"


def _merge_claims(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union claims by text, unioning their cited signal ids."""
    merged: dict[str, set[str]] = {}
    order: list[str] = []
    for claim in list(a) + list(b):
        text = str(claim.get("claim", "")).strip()
        if not text:
            continue
        if text not in merged:
            merged[text] = set()
            order.append(text)
        merged[text].update(claim.get("signals", []))
    return [{"claim": text, "signals": sorted(merged[text])} for text in order]


def _technologies_for_domain(cfg: Config, domain_id: str) -> list[str]:
    """Technologies plausibly serving a domain, for coverage targeting."""
    out = []
    for offer in cfg.offers.get("offers", []):
        if domain_id in (offer.get("domains") or []):
            out.extend(offer.get("technologies") or [])
    for partner in cfg.assets.get("partners", []):
        if domain_id in (partner.get("domains") or []):
            out.extend(partner.get("provides_technologies") or [])
    seen: list[str] = []
    for tech in out:
        if tech not in seen and tech in cfg.technologies:
            seen.append(tech)
    return seen
