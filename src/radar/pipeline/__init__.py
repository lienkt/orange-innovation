"""Pipeline stages (Table 16).

  1 Collect      -> connectors                (ingest.Ingestor.collect)
  2 Normalise    -> signal records            (ingest.Ingestor._store)
  3 Classify     -> typed, tiered signals     (ingest.Ingestor.classify)
  4 Extract      -> theme clusters            (themes.ThemeExtractor)
  5 Synthesise   -> candidate opportunities   (synthesis.Synthesiser)
  6 Curate/score -> ranked opportunity spaces (synthesis + graph + scoring)
  7 Serve        -> radar, briefs, API        (readmodel.ReadModel)

"Each stage has a defined input and output contract, which allows stages to be
developed, tested and replaced independently" (§4.2).

Nothing is imported eagerly here. `radar.scoring` needs `pipeline.prompts` for
the strategic-relevance rubric, while `pipeline.run` needs `radar.scoring` to
execute the scoring stage; importing either from this module's body would close
that loop. Import the submodule you need directly:

    from radar.pipeline.run import RefreshRunner, STAGES
    from radar.pipeline import prompts
"""

from __future__ import annotations

__all__ = ["STAGES", "RefreshRunner"]


def __getattr__(name: str):
    """Lazily expose the orchestrator without creating an import cycle."""
    if name in ("STAGES", "RefreshRunner"):
        from . import run

        return getattr(run, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
