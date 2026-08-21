import sys, textwrap; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 6.6)
c.title("Figure 1 — Layered architecture",
        "Two runtimes over one SQLite file: a batch discovery pipeline that writes, and a read-mostly API that serves. Nothing in the serving path imports the pipeline's heavy dependencies.")

layers = [
    ("PRESENTATION", "frontend/\nReact 18 · Vite · TypeScript\nno chart library",
     ["App.tsx — view state, deep links, pane sizing", "RadarChart — hand-drawn SVG polar plot",
      "Charts — grid, funnel, divergence, timeline", "TopicDetail · ScoreExplain · Brief · MarketSize",
      "Filters · Workflow · Help · Announcer"], 74.0, PURPLE, PURPLE_L),
    ("API", "src/radar/api.py\nFastAPI · ~40 endpoints\nsame-origin static mount",
     ["/api/view — role-ranked, faceted, capped at 24", "/api/topics/{id} + /history + /evidence-timeline",
      "/api/workflow/* · /api/divergence", "/api/analytics/* · /api/coverage · /api/whitespace",
      "POST description | brief | market-size | competition"], 57.0, BLUE, BLUE_L),
    ("READ MODEL", "src/radar/readmodel.py\nrole modes, ranking, facets",
     ["one bulk fetch per table, indexed in memory", "_assemble() shared by the list and detail paths",
      "randomised exploration slot (§4.7.6)", "coverage, white space and orphan-offer reports"],
     40.0, TEAL, TEAL_L),
    ("DOMAIN SERVICES", "scoring · graph · sizing\ncompetition · workflow\nbrief · describe",
     ["AttractivenessScorer — 5 components", "RightToWinScorer — 7 components, graph lookup",
      "Linker — L0–L4 typing + portfolio distance", "SizingEngine — two methods, factor by factor",
      "CompetitionAssessor · WorkflowService", "BriefRenderer — reportlab, no browser"], 21.0, ORANGE_D, ORANGE_L),
    ("STORAGE & INTEGRATION", "db.py · connectors/\nllm.py · embeddings.py\nconfig.py",
     ["SQLite + WAL, foreign keys on", "13 connectors behind one registry",
      "LLMClient — deepseek | openai | ollama | mock", "sentence-transformers, TF-IDF fallback",
      "YAML + CSV config, validated at load"], 4.0, GREY_D, GREY_LL),
]
for name, sub, items, y, col, fill in layers:
    c.box(1.0, y, 98.0, 15.0, "", None, fc=fill, ec=col, lw=1.3)
    c.ax.add_patch(FancyBboxPatch((1.0, y), 24.0, 15.0,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((23.0, y), 2.0, 15.0, fc=col, ec="none", zorder=4))
    c.text(2.6, y + 11.6, name, fs=8.6, color="#FFFFFF", weight="bold", z=6)
    c.ax.text(2.6, y + 8.8, sub, fontsize=6.3, color="#FFFFFFDD", ha="left", va="top",
              zorder=6, linespacing=1.7)
    n = len(items)
    w = (98.0 - 26.4) / n - 1.0
    wrap_at = max(16, int((w - 2.2) * 2.45))
    x = 26.4
    for it in items:
        c.box(x, y + 2.0, w, 11.0, "", None, fc="#FFFFFF", ec="#00000018", lw=0.8, radius=0.5)
        c.ax.text(x + 1.1, y + 11.6, "\n".join(textwrap.wrap(it, wrap_at)), fontsize=6.4,
                  color=INK, ha="left", va="top", zorder=6, linespacing=1.65)
        x += w + 1.0
for y in (72.0, 55.0, 38.0, 19.0):
    for x in (13.0, 50.0, 86.0):
        c.arrow((x, y + 2.0), (x, y), color=GREY_D, lw=1.2)
c.save(OUT + "ta-01-layers.png")
