import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

# ------------------------------------------------------- 1. LAYERED ARCHITECTURE
c = Canvas(11.8, 6.6)
c.title("Figure 1 — Layered architecture",
        "Two runtimes over one SQLite file: a batch discovery pipeline that writes, and a read-mostly API that serves. Nothing in the serving path imports the pipeline's heavy dependencies.")

layers = [
    ("PRESENTATION", "frontend/  ·  React 18 + Vite + TypeScript, no chart library",
     ["App.tsx — view state, deep links", "RadarChart — hand-drawn SVG polar plot",
      "Charts — grid, funnel, divergence, timeline", "TopicDetail · ScoreExplain · Brief",
      "Filters · Workflow · Help · Announcer"], 74.0, PURPLE, PURPLE_L),
    ("API", "src/radar/api.py  ·  FastAPI, 40 endpoints, same-origin static mount",
     ["/api/view — role-ranked, faceted", "/api/topics/{id} + /history + /evidence-timeline",
      "/api/workflow/* · /api/divergence", "/api/analytics/* · /api/coverage",
      "POST description | brief | market-size | competition"], 57.0, BLUE, BLUE_L),
    ("READ MODEL", "src/radar/readmodel.py  ·  role modes, ranking, facets, white space",
     ["one bulk fetch per table, indexed in memory", "_assemble() shared by list and detail paths",
      "exploration slot (§4.7.6)", "coverage and orphan-offer reports"], 40.0, TEAL, TEAL_L),
    ("DOMAIN SERVICES", "scoring · graph · sizing · competition · workflow · brief · describe",
     ["AttractivenessScorer  5 components", "RightToWinScorer  7 components, graph lookup",
      "Linker  L0–L4 typing + portfolio distance", "SizingEngine  two methods, factor by factor",
      "CompetitionAssessor  ·  WorkflowService", "BriefRenderer  reportlab, no browser"], 21.0, ORANGE_D, ORANGE_L),
    ("STORAGE & INTEGRATION", "db.py  ·  connectors/  ·  llm.py  ·  embeddings.py  ·  config.py",
     ["SQLite + WAL, foreign keys on", "13 connectors behind one registry",
      "LLMClient — deepseek | openai | ollama | mock", "sentence-transformers, TF-IDF fallback",
      "YAML/CSV config, validated at load"], 4.0, GREY_D, GREY_LL),
]
for name, sub, items, y, col, fill in layers:
    c.box(1.0, y, 98.0, 15.0, "", None, fc=fill, ec=col, lw=1.3)
    c.ax.add_patch(FancyBboxPatch((1.0, y), 26.0, 15.0,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((25.0, y), 2.0, 15.0, fc=col, ec="none", zorder=4))
    c.text(3.0, y + 10.4, name, fs=9.0, color="#FFFFFF", weight="bold", z=6)
    c.ax.text(3.0, y + 7.6, sub, fontsize=6.4, color="#FFFFFFE0", ha="left", va="top",
              zorder=6, linespacing=1.6, wrap=True)
    x = 28.4
    for it in items:
        w = (98.0 - 28.4) / len(items) - 1.0
        c.box(x, y + 2.0, w, 11.0, "", None, fc="#FFFFFF", ec="#00000018", lw=0.8, radius=0.5)
        c.ax.text(x + 1.0, y + 11.4, it, fontsize=6.4, color=INK, ha="left", va="top",
                  zorder=6, linespacing=1.6)
        x += w + 1.0
for y in (72.0, 55.0, 38.0, 19.0):
    for x in (14.0, 50.0, 86.0):
        c.arrow((x, y + 2.0), (x, y), color=GREY_D, lw=1.2)
c.save(OUT + "ta-01-layers.png")


# ------------------------------------------------------- 2. PIPELINE STAGES
c = Canvas(12.0, 6.6)
c.title("Figure 2 — The refresh pipeline: thirteen stages with declared input/output contracts",
        "Every stage can be run alone (`radar refresh --stages score,actions`), which is how the system is developed, tested and repaired.")

stages = [
    ("1", "collect", "connectors/", "source config +\nreference_date", "raw items", GREEN, 1.0),
    ("2", "normalise", "pipeline/ingest.py", "raw items", "signal records", GREEN, 15.0),
    ("3", "classify", "pipeline/ingest.py", "signals", "typed, tiered,\nrelevance-gated", GREEN, 29.0),
    ("4", "themes", "pipeline/themes.py", "signals + embeddings", "theme clusters", TEAL, 43.0),
    ("5", "synthesise", "pipeline/synthesis.py", "clusters + taxonomy", "candidate spaces", TEAL, 57.0),
    ("5b", "enrich", "pipeline/enrich.py", "topics + signals", "more evidence\nper topic", TEAL, 71.0),
    ("6", "graph", "graph.py", "business_graph/*.yaml", "nodes + edges", BLUE, 85.0),
]
for num, name, mod, inp, out, col, x in stages:
    c.box(x, 62.0, 13.0, 22.0, "", None, fc="#FFFFFF", ec=col, lw=1.3, shadow=True)
    c.ax.add_patch(FancyBboxPatch((x, 77.6), 13.0, 6.4,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, 77.6), 13.0, 1.4, fc=col, ec="none", zorder=4))
    c.text(x + 6.5, 80.8, f"{num}  {name}", fs=8.0, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(x + 6.5, 74.6, mod, fs=6.2, color=col, ha="center", z=6, style="italic")
    c.text(x + 6.5, 70.2, "in:  " + inp, fs=6.2, color=GREY_D, ha="center", z=6, ls_=1.5)
    c.text(x + 6.5, 65.0, "out:  " + out, fs=6.2, color=INK, ha="center", z=6, ls_=1.5)
    if x < 85.0:
        c.arrow((x + 13.0, 73.0), (x + 14.0, 73.0), color=GREY_D, lw=1.4)

stages2 = [
    ("6b", "link", "graph.py", "topics + nodes", "typed links +\nportfolio distance", BLUE, 1.0),
    ("6c", "score", "scoring.py", "topics + signals + links", "two scores,\nhorizon, state", ORANGE_D, 15.0),
    ("6d", "actions", "pipeline/actions.py", "scored topics", "next action per role", ORANGE_D, 29.0),
    ("6e", "reference", "reference.py", "Eurostat API", "reference series", GREEN, 43.0),
    ("6f", "size", "sizing.py", "topics + reference", "TAM/SAM/SOM,\ntwo methods", GREEN, 57.0),
    ("6g", "competition", "competition.py", "topics + register", "level + named list", TEAL, 71.0),
    ("7", "describe", "pipeline/describe.py", "topics + links + competitors", "narrative +\ndiagram spec", PURPLE, 85.0),
]
for num, name, mod, inp, out, col, x in stages2:
    c.box(x, 34.0, 13.0, 22.0, "", None, fc="#FFFFFF", ec=col, lw=1.3, shadow=True)
    c.ax.add_patch(FancyBboxPatch((x, 49.6), 13.0, 6.4,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, 49.6), 13.0, 1.4, fc=col, ec="none", zorder=4))
    c.text(x + 6.5, 52.8, f"{num}  {name}", fs=8.0, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(x + 6.5, 46.6, mod, fs=6.2, color=col, ha="center", z=6, style="italic")
    c.text(x + 6.5, 42.2, "in:  " + inp, fs=6.1, color=GREY_D, ha="center", z=6, ls_=1.5)
    c.text(x + 6.5, 37.0, "out:  " + out, fs=6.2, color=INK, ha="center", z=6, ls_=1.5)
    if x < 85.0:
        c.arrow((x + 13.0, 45.0), (x + 14.0, 45.0), color=GREY_D, lw=1.4)
c.path([(91.5, 62.0), (91.5, 59.0), (7.5, 59.0), (7.5, 56.0)], color=GREY_D, lw=1.4)

c.zone(1.0, 4.0, 31.0, 26.0, None, fc=GREEN_L, ec=GREEN)
c.text(2.4, 27.0, "CONCURRENCY", fs=8.0, color=GREEN, weight="bold")
c.ax.text(2.4, 24.0, "Sources are independent and network-bound, so collection\n"
                     "runs in a thread pool (max_parallel_sources = 8): twelve\n"
                     "sources in ~45 s. Database writes stay serial, because\n"
                     "dedup is a read-modify-write over the whole signal table.\n"
                     "Synthesis runs 4 clusters concurrently, each issuing 3\n"
                     "generation calls plus a critic and entailment call.",
          fontsize=6.6, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)

c.zone(34.0, 4.0, 31.0, 26.0, None, fc=RED_L, ec=RED)
c.text(35.4, 27.0, "FAILURE CONTAINMENT", fs=8.0, color=RED, weight="bold")
c.ax.text(35.4, 24.0, "Graceful degradation — a failing source is recorded in the\n"
                      "refresh stats and never aborts the run.\n\n"
                      "Circuit breaker — after two exhausted requests to a host,\n"
                      "the rest of that host's requests are skipped and the host\n"
                      "is named in collect.errors. Without it, ten blocked GDELT\n"
                      "queries cost eleven minutes for zero data.",
          fontsize=6.6, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)

c.zone(67.0, 4.0, 32.0, 26.0, None, fc=BLUE_L, ec=BLUE)
c.text(68.4, 27.0, "REPLAY AND LEAKAGE CONTROL", fs=8.0, color=BLUE, weight="bold")
c.ax.text(68.4, 24.0, "Every connector takes a reference_date and rejects anything\n"
                      "published after it — filtering on the PUBLICATION date, never\n"
                      "the ingestion date. §4.7.3 warns that leakage through late-\n"
                      "arriving documents is the standard way a forecasting model\n"
                      "produces excellent offline results and useless live ones.\n"
                      "raw_items is retained, so `radar replay --date 2024-06-01`\n"
                      "reconstructs a past state without re-fetching anything.",
          fontsize=6.6, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)
c.save(OUT + "ta-02-pipeline.png")
