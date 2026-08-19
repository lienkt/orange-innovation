"""Refresh orchestration — the seven stages of Table 16, end to end.

FR-19: refresh the radar on a defined cadence, incrementally, and display the
last refresh date per topic and globally.

FR-35 / §4.7.2: the same entry point runs a HISTORICAL REPLAY. Passing a past
`reference_date` reconstructs the state of the world as of that date, with every
connector and every feature restricted to data published before it. §4.7.2 calls
this "the single most persuasive demonstration available to this project" —
showing that the radar, run on 2024 data, would have surfaced something that
subsequently became obvious.

§4.1 principle 6 governs the design: "Design for the refresh, not the first run.
Any pipeline can produce an impressive first output. The hard requirement is
that the second run six weeks later updates the same topics rather than
producing a new, incomparable list."
"""

from __future__ import annotations

import datetime as dt
import logging
import time
import uuid
from typing import Any

from ..competition import CompetitionAnalyser
from ..config import Config, get_config
from ..db import Database, js
from ..embeddings import Embedder
from ..graph import Linker, build_graph
from ..llm import LLMClient
from ..reference import ReferenceDataFetcher
from ..scoring import ScoringEngine
from ..sizing import MarketSizer
from .actions import NextActionGenerator
from .describe import DescriptionGenerator
from .enrich import Enricher
from .ingest import Ingestor
from .synthesis import Synthesiser
from .themes import ThemeExtractor

log = logging.getLogger(__name__)

STAGES = ("collect", "classify", "themes", "synthesise", "enrich", "graph", "link", "score",
          "actions", "reference", "size", "competition", "describe")


class RefreshRunner:
    def __init__(self, cfg: Config | None = None, db: Database | None = None,
                 llm: LLMClient | None = None, embedder: Embedder | None = None):
        self.cfg = cfg or get_config()
        self.db = db or Database(self.cfg.db_path)
        self.llm = llm
        self.embedder = embedder or Embedder()

    def _ensure_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient(max_retries=self.cfg.settings["llm"]["max_retries"])
        return self.llm

    def run(
        self,
        reference_date: dt.date | None = None,
        since_days: int = 30,
        stages: tuple[str, ...] = STAGES,
        source_ids: list[str] | None = None,
        max_clusters: int | None = None,
        target_topics: int | None = None,
        use_llm: bool = True,
        run_critic: bool = True,
        run_entailment: bool = True,
    ) -> dict[str, Any]:
        reference_date = reference_date or dt.date.today()
        is_replay = reference_date < dt.date.today()
        refresh_id = f"R-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

        self.db.init_schema()
        with self.db.cursor() as cur:
            cur.execute(
                "INSERT INTO refreshes (id, started_at, reference_date, is_replay, pipeline_version, weight_set) "
                "VALUES (?,?,?,?,?,?)",
                (refresh_id, started, reference_date.isoformat(), int(is_replay),
                 self.cfg.pipeline_version, self.cfg.weight_set),
            )

        log.info("Refresh %s (reference_date=%s, replay=%s, stages=%s)",
                 refresh_id, reference_date, is_replay, ",".join(stages))
        stats: dict[str, Any] = {
            "refresh_id": refresh_id,
            "reference_date": reference_date.isoformat(),
            "is_replay": is_replay,
            "stages_run": list(stages),
        }
        clock: dict[str, float] = {}

        def timed(name: str, fn):
            start = time.monotonic()
            try:
                return fn()
            finally:
                clock[name] = round(time.monotonic() - start, 2)

        ingestor = Ingestor(self.cfg, self.db, self.llm if use_llm else None)

        if "collect" in stages:
            if use_llm:
                ingestor.llm = self._ensure_llm()
            stats["collect"] = timed(
                "collect",
                lambda: ingestor.collect(reference_date, refresh_id, since_days, source_ids).as_dict(),
            )

        if "classify" in stages:
            if use_llm:
                ingestor.llm = self._ensure_llm()
            stats["classify"] = timed("classify", lambda: ingestor.classify(refresh_id, use_llm=use_llm))

        if "themes" in stages:
            extractor = ThemeExtractor(self.cfg, self.db, self.embedder)
            stats["themes"] = timed("themes", lambda: extractor.run(refresh_id))

        if "synthesise" in stages:
            if not use_llm:
                log.warning("Skipping synthesis: it requires a model (Table 23 — the core creative step).")
                stats["synthesise"] = {"skipped": "requires LLM"}
            else:
                synth = Synthesiser(self.cfg, self.db, self._ensure_llm(), self.embedder)
                stats["synthesise"] = timed(
                    "synthesise",
                    lambda: synth.run(refresh_id, max_clusters, run_critic, run_entailment,
                                     target_topics).as_dict(),
                )

        if "enrich" in stages:
            enricher = Enricher(self.cfg, self.db, self.embedder)
            stats["enrich"] = timed("enrich", lambda: enricher.run(refresh_id, reference_date))

        if "graph" in stages:
            # The internal asset catalogue runs on a slower cadence than
            # discovery (§4.2), but rebuilding is cheap and keeps the graph
            # consistent with config on every run.
            stats["graph"] = timed("graph", lambda: build_graph(self.cfg, self.db))

        if "link" in stages:
            linker = Linker(self.cfg, self.db)
            stats["link"] = timed("link", linker.run)

        if "score" in stages:
            engine = ScoringEngine(self.cfg, self.db, self.llm if use_llm else None)
            stats["score"] = timed("score", lambda: engine.run(refresh_id, reference_date))

        if "actions" in stages and use_llm:
            generator = NextActionGenerator(self.cfg, self.db, self._ensure_llm())
            stats["actions"] = timed("actions", generator.run)
        elif "actions" in stages:
            stats["actions"] = {"skipped": "requires LLM"}

        # §4.3.4 sizing runs after scoring, because the obtainable-share
        # assumption reads right-to-win, and after link, because it reads
        # portfolio distance. Reference data comes first and is skipped when it
        # is already fresh — these are annual statistics, not a feed.
        if "reference" in stages:
            fetcher = ReferenceDataFetcher(self.cfg, self.db)
            stats["reference"] = timed("reference", fetcher.run)

        if "size" in stages:
            sizer = MarketSizer(self.cfg, self.db)
            stats["size"] = timed("size", sizer.run)

        if "competition" in stages:
            analyser = CompetitionAnalyser(self.cfg, self.db)
            stats["competition"] = timed("competition", analyser.run)

        if "describe" in stages and use_llm:
            # Descriptions are regenerated only where the topic's version moved,
            # so a routine refresh rewrites the prose that actually changed
            # rather than all of it (§4.1 principle 6) — and never more than the
            # configured ceiling, so the cost of a refresh stays predictable.
            describe_cfg = self.cfg.settings.get("description", {})
            describer = DescriptionGenerator(self.cfg, self.db, self._ensure_llm())
            stats["describe"] = timed(
                "describe",
                lambda: describer.run(
                    limit=describe_cfg.get("max_per_refresh", 40),
                    max_workers=describe_cfg.get("max_parallel", 4),
                ),
            )
        elif "describe" in stages:
            stats["describe"] = {"skipped": "requires LLM"}

        stats["timings_seconds"] = clock
        if self.llm is not None:
            # NFR-10: per-refresh compute and inference cost is measured and reported.
            stats["llm_usage"] = self.llm.usage_summary()

        finished = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE refreshes SET finished_at = ?, stats = ? WHERE id = ?",
                (finished, js(stats), refresh_id),
            )
        log.info("Refresh %s complete in %.1fs", refresh_id, sum(clock.values()))
        return stats
