import sys, textwrap; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

def lifelines(c, actors, top=84.0, bottom=10.0, head_h=6.0):
    xs = {}
    for name, sub, x, w, col in actors:
        c.box(x, top - head_h, w, head_h, "", None, fc=col, ec=col, radius=0.7)
        c.text(x + w / 2, top - head_h / 2 + 1.0, name, fs=7.4, color="#FFFFFF", ha="center", weight="bold")
        if sub:
            c.text(x + w / 2, top - head_h / 2 - 1.8, sub, fs=5.9, color="#FFFFFFCC", ha="center")
        cx = x + w / 2
        c.ax.add_line(Line2D([cx, cx], [bottom, top - head_h], color=GREY, lw=1.0,
                             ls=(0, (2, 3)), zorder=2))
        xs[name] = cx
    return xs

def msg(c, x0, x1, y, label, color=GREY_D, ls="-", fs=6.5, above=True, ret=False):
    c.ax.add_patch(FancyArrowPatch((x0, y), (x1, y), arrowstyle="-|>" if not ret else "-|>",
                                   mutation_scale=10, color=color, lw=1.2,
                                   linestyle=(0, (4, 3)) if ret else ls, zorder=6,
                                   shrinkA=0, shrinkB=0))
    t = c.ax.text((x0 + x1) / 2, y + (1.5 if above else -1.9), label, fontsize=fs, color=color,
                  ha="center", va="center", zorder=7)
    t.set_bbox(dict(fc="#FFFFFF", ec="none", pad=1.0))

def band(c, x, y0, y1, color, w=1.6):
    c.ax.add_patch(Rectangle((x - w / 2, y0), w, y1 - y0, fc=color, ec=INK, lw=0.6, zorder=4))

# ------------------------------------------------------- 3. REFRESH SEQUENCE
c = Canvas(11.8, 6.4)
c.title("Figure 3 — Sequence: one refresh run",
        "`radar refresh --since-days 60`. Collection is parallel and network-bound; synthesis is parallel and model-bound; everything that writes is serial.")

actors = [
    ("CLI", "cli.py", 1.0, 12.0, GREY_D),
    ("RefreshRunner", "pipeline/run.py", 17.0, 15.0, ORANGE_D),
    ("Connectors", "13 sources", 36.0, 13.0, BLUE),
    ("LLMClient", "deepseek | ollama", 53.0, 14.0, PURPLE),
    ("Embeddings", "local model", 71.0, 12.0, TEAL),
    ("SQLite", "data/radar.db", 87.0, 12.0, GREEN),
]
xs = lifelines(c, actors, top=84.0, bottom=8.0)
CLI, RUN, CON, LLM, EMB, DB = (xs[k] for k in ("CLI", "RefreshRunner", "Connectors", "LLMClient", "Embeddings", "SQLite"))

band(c, RUN, 10.0, 76.0, ORANGE_L)
msg(c, CLI, RUN, 74.0, "run(reference_date, stages)", ORANGE_D)
msg(c, RUN, DB, 70.0, "open refresh row", GREEN)
band(c, CON, 62.0, 67.0, BLUE_L)
msg(c, RUN, CON, 66.0, "collect()  —  thread pool, 8 at a time, publication-date gated", BLUE)
msg(c, CON, DB, 62.5, "raw_items + signals  (URL dedup, serial writes)", GREEN, ret=True)
band(c, LLM, 46.0, 59.0, PURPLE_L)
msg(c, RUN, LLM, 58.0, "classify — signal type, relevance, batched 12 at a time", PURPLE)
band(c, EMB, 52.0, 55.0, TEAL_L)
msg(c, RUN, EMB, 54.0, "embed signal spans", TEAL)
msg(c, EMB, RUN, 51.0, "vectors  →  agglomerative clustering, deterministic", TEAL, ret=True)
msg(c, RUN, LLM, 47.5, "synthesise — 3 lensed passes per cluster, 4 clusters concurrent", PURPLE)
msg(c, LLM, RUN, 44.0, "candidates  →  vocabulary · evidence binding · critic · entailment", PURPLE, ret=True)
msg(c, RUN, DB, 40.5, "upsert opportunity_spaces on the canonical triple", GREEN)
msg(c, RUN, EMB, 37.0, "enrich — similarity + independent taxonomy corroboration", TEAL)
msg(c, RUN, DB, 33.5, "build graph, generate and type links L0–L4 / SUP", GREEN)
msg(c, RUN, DB, 30.0, "score — arithmetic components, then one rubric call per topic", GREEN)
msg(c, RUN, LLM, 26.5, "strategic relevance rubric  ·  next actions per role", PURPLE)
msg(c, RUN, DB, 23.0, "size (two methods) · competition · descriptions · briefs", GREEN)
msg(c, RUN, DB, 19.5, "close refresh row with per-stage stats and errors", GREEN)
msg(c, RUN, CLI, 16.0, "summary: counts, timings, sources that failed", ORANGE_D, ret=True)

c.zone(1.0, 1.0, 98.0, 12.0, None, fc=GREY_LL, ec=GREY)
c.text(2.4, 9.6, "WHAT IS ARITHMETIC AND WHAT IS A MODEL CALL", fs=7.6, color=INK, weight="bold")
c.text(2.4, 5.6, "Signal counting, publisher diversity, recency and momentum are arithmetic and never a model — \"a model asked to count will occasionally be wrong and always be\n"
                 "unverifiable\". Right-to-win is a structured lookup against the graph. Only two things call the model on the scoring path: the strategic-relevance rubric and the next action.",
       fs=6.7, color=GREY_D, ls_=1.7)
c.save(OUT + "ta-03-sequence-refresh.png")


# ------------------------------------------------------- 4. READ PATH SEQUENCE
c = Canvas(11.8, 6.2)
c.title("Figure 4 — Sequence: serving a view, and the N+1 that was removed",
        "The same request before and after the read-model rewrite. The fix was not caching — it was fetching each table once for the whole set and indexing it in memory.")

c.text(1.0, 87.0, "BEFORE  —  1.69 s · 343 kB · ~1,670 queries", fs=8.0, color=RED, weight="bold")
actors = [("Browser", "", 1.0, 13.0, GREY_D), ("FastAPI", "/api/view", 22.0, 14.0, BLUE),
          ("ReadModel", "", 45.0, 14.0, TEAL), ("SQLite", "", 68.0, 13.0, GREEN)]
xs = lifelines(c, actors, top=82.0, bottom=54.0, head_h=5.0)
B, F, R, D = (xs[k] for k in ("Browser", "FastAPI", "ReadModel", "SQLite"))
msg(c, B, F, 73.0, "GET /api/view?role=sales", BLUE)
msg(c, F, R, 69.5, "build_view(role, filters)", TEAL)
c.ax.add_patch(FancyBboxPatch((R - 2.0, 57.0), (D - R) + 4.0, 10.0,
                              boxstyle="round,pad=0,rounding_size=0.6", fc=RED_L, ec=RED,
                              lw=1.1, ls=(0, (4, 3)), zorder=3))
c.text((R + D) / 2 + 1.0, 64.0, "loop:  for each of 167 topics", fs=6.8, color=RED, ha="center", weight="bold")
c.text((R + D) / 2 + 1.0, 60.6, "11 queries — scores, links, node labels, competition, size,\nworkflow, assessments ×2, signal count, two artefact checks",
       fs=6.3, color=INK, ha="center", ls_=1.6)
c.text(85.0, 66.0, "1,670 round trips.\nInvisible in any\nfrontend profile,\nand 1.6 s of dead air\non every filter change.",
       fs=6.6, color=RED, ha="left", ls_=1.7)

c.rule(50.0)
c.text(1.0, 45.0, "AFTER  —  0.05 s · 84 kB · 11 queries", fs=8.0, color=GREEN, weight="bold")
xs = lifelines(c, actors, top=40.0, bottom=8.0, head_h=5.0)
B, F, R, D = (xs[k] for k in ("Browser", "FastAPI", "ReadModel", "SQLite"))
msg(c, B, F, 31.0, "GET /api/view?role=sales", BLUE)
msg(c, F, R, 27.5, "build_view(role, filters)", TEAL)
c.ax.add_patch(FancyBboxPatch((R - 2.0, 14.0), (D - R) + 4.0, 10.0,
                              boxstyle="round,pad=0,rounding_size=0.6", fc=GREEN_L, ec=GREEN, lw=1.1, zorder=3))
c.text((R + D) / 2 + 1.0, 21.2, "once:  one bulk SELECT per table", fs=6.8, color=GREEN, ha="center", weight="bold")
c.text((R + D) / 2 + 1.0, 17.4, "indexed in memory into a view context;  _assemble() reads\nfrom the context when given one, and queries when not",
       fs=6.3, color=INK, ha="center", ls_=1.6)
msg(c, R, B, 10.5, "24 topics, only the fields a list row renders", GREEN, ret=True)
c.text(85.0, 22.0, "A test asserts that the\nlist and detail paths\nproduce byte-identical\ntopics — two code paths\nfor one object is how\ntwo surfaces start\ndisagreeing.\n\nA second test guards the\nquery count against\ngrowing with the number\nof topics.",
       fs=6.5, color=GREEN, ha="left", ls_=1.7)
c.save(OUT + "ta-04-sequence-read.png")
