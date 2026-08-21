import sys, textwrap; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

# ------------------------------------------------------- 5. DEPLOYMENT
c = Canvas(11.8, 6.8)
c.title("Figure 5 — Deployment topology",
        "One Azure App Service serves the read API and the built React bundle from the same origin. Discovery is not deployed: it is a batch job against the same SQLite file.")

c.zone(1.0, 40.0, 30.0, 46.0, None, fc=GREY_LL, ec=GREY, ls="-")
c.text(16.0, 83.0, "DEVELOPER / CI  —  the write path", fs=7.8, color=GREY_D, ha="center", weight="bold")
c.box(3.0, 68.0, 26.0, 12.0, "radar refresh", "collect · classify · themes · synthesise\nenrich · graph · link · score · describe",
      fc="#FFFFFF", ec=ORANGE_D, tc=ORANGE_D, fs=8.2, subfs=6.3, shadow=True)
c.box(3.0, 54.0, 26.0, 12.0, "Heavy dependencies", "scikit-learn · sentence-transformers\ntorch · openai client",
      fc="#FFFFFF", ec=GREY_D, tc=GREY_D, fs=8.0, subfs=6.3)
c.cylinder(6.0, 42.0, 20.0, 10.0, "data/radar.db", "SQLite + WAL", fc=GREEN_L, ec=GREEN, fs=8.0, subfs=6.3)
c.arrow((16.0, 68.0), (16.0, 66.0), color=GREY_D)
c.arrow((16.0, 54.0), (16.0, 52.4), color=GREY_D)

c.path([(31.0, 47.0), (36.0, 47.0), (36.0, 62.0), (40.0, 62.0)], color=ORANGE_D, lw=1.6)
c.text(36.0, 50.0, "deploy-azure.sh\nbuilds, packages,\nprovisions, pushes", fs=6.5, color=ORANGE_D, ha="center", ls_=1.6)

c.zone(40.0, 28.0, 59.0, 58.0, None, fc=BLUE_L, ec=BLUE, ls="-", alpha=0.3)
c.text(69.5, 83.0, "AZURE  —  France Central  ·  rg-railpulse-cloud", fs=7.8, color=BLUE, ha="center", weight="bold")
c.box(42.0, 66.0, 55.0, 14.0, "", None, fc="#FFFFFF", ec=BLUE, lw=1.3, shadow=True)
c.text(69.5, 76.4, "App Service Plan  ·  plan-railpulse-cdb4ce  ·  F1 Linux, shared", fs=7.6, color=BLUE, ha="center", weight="bold")
c.text(69.5, 71.6, "The Free tier allows ONE plan per SUBSCRIPTION, not per region. A second F1 plan is created\nwithout complaint and then sits at QuotaExceeded forever, in any region — so the radar joins the\nexisting plan and the two apps share its 60 CPU-minutes a day.",
       fs=6.4, color=INK, ha="center", ls_=1.65)

c.box(42.0, 41.0, 26.0, 22.0, "", None, fc="#FFFFFF", ec=BLUE, lw=1.3, shadow=True)
c.text(55.0, 59.6, "web-orange-radar-1521f5", fs=7.8, color=BLUE, ha="center", weight="bold")
c.text(55.0, 56.2, "Python 3.13  ·  bash startup.sh", fs=6.4, color=GREY_D, ha="center")
c.box(43.4, 49.0, 23.2, 5.4, "gunicorn + uvicorn worker", None, fc=GREY_LL, ec=GREY_L, fs=6.6, bold=False, radius=0.5)
c.text(55.0, 46.6, "1 worker · 4 threads · 180 s timeout", fs=6.2, color=GREY_D, ha="center")
c.text(55.0, 43.4, "one core, ~1 GB, and SQLite with WAL\nis happiest with a single writer", fs=6.0, color=GREY_D, ha="center", ls_=1.5)

c.box(71.0, 41.0, 26.0, 22.0, "", None, fc="#FFFFFF", ec=GREEN, lw=1.3, shadow=True)
c.text(84.0, 59.6, "/home  —  the only persistent path", fs=7.4, color=GREEN, ha="center", weight="bold")
c.cylinder(73.0, 50.0, 22.0, 7.6, "/home/data/radar.db", None, fc=GREEN_L, ec=GREEN, fs=7.0)
c.box(73.0, 43.4, 22.0, 5.4, "/home/data/briefs/*.pdf", None, fc=GREEN_L, ec=GREEN, fs=6.6, bold=False, radius=0.5)
c.arrow((68.0, 52.5), (70.6, 52.5), color=GREY_D, lw=1.3)

c.box(42.0, 29.0, 55.0, 10.0, "", None, fc=GOLD_L, ec=GOLD, lw=1.1)
c.text(43.6, 36.2, "startup.sh seeds /home/data on FIRST boot only, then leaves it alone.", fs=7.0, color=GOLD, weight="bold")
c.text(43.6, 32.0, "Everything outside /home is replaced on each deploy, so a brief generated at 14:00 would vanish at the next\npush. Feedback, assessments, descriptions and briefs created in production are not thrown away by a deploy.",
       fs=6.4, color=INK, ls_=1.6)

c.box(1.0, 1.0, 47.0, 24.0, "", None, fc="#FFFFFF", ec=GREY_D, lw=1.1)
c.text(2.6, 22.0, "WHAT IS NOT IN THE SERVING PACKAGE", fs=7.6, color=INK, weight="bold")
c.ax.text(2.6, 19.0, "radar.api imports scikit-learn, sentence-transformers and the OpenAI client only\n"
                     "INSIDE the functions that need them, so a serving instance never loads torch.\n"
                     "28 MB instead of multiple gigabytes — on the Free tier that is the difference\n"
                     "between starting and not.\n\n"
                     "raw_items is dropped from the serving copy: it exists so the pipeline can be\n"
                     "re-run as of a past date, which the API never does, and it is half the file.\n"
                     "Every citation still resolves.",
          fontsize=6.3, color=GREY_D, ha="left", va="top", linespacing=1.65, zorder=8)

c.box(52.0, 1.0, 47.0, 24.0, "", None, fc=RED_L, ec=RED, lw=1.1)
c.text(53.6, 22.0, "BEFORE THIS GOES ANYWHERE REAL", fs=7.6, color=RED, weight="bold")
c.ax.text(53.6, 19.0, "The deployed app is PUBLIC and UNAUTHENTICATED — fine for a demonstration,\n"
                      "not fine for anything else:\n"
                      "·  the briefs are stamped Internal, and the business graph, the competitor\n"
                      "   register and the reference density are Orange's own material\n"
                      "·  POST /description and POST /brief call the model with the deployed key,\n"
                      "   so anyone with the URL can spend it\n\n"
                      "Either an IP access restriction or Entra sign-in closes it, in one command.",
          fontsize=6.3, color=INK, ha="left", va="top", linespacing=1.65, zorder=8)
c.save(OUT + "ta-05-deployment.png")


# ------------------------------------------------------- 6. SCORING DATAFLOW
c = Canvas(11.8, 6.6)
c.title("Figure 6 — How a score is computed, and how it is explained",
        "Table 23's division of labour, implemented literally. Every component returns a value AND the inputs that produced it, and both are persisted.")

c.text(1.0, 87.0, "ATTRACTIVENESS  —  five components, weights from settings.yaml", fs=8.0, color=ORANGE_D, weight="bold")
comps = [
    ("Market signal strength", "30%", "count of relevance-gated signals in the trailing 90 days, log-compressed base 2, normalised against the distribution across all live topics", "ARITHMETIC", 1.0, GREEN),
    ("Source diversity", "20%", "Shannon entropy over publishers, with tier-4 publishers discounted 0.35 on the EFFECTIVE COUNT — entropy is scale-invariant, so a flat discount cancels out entirely", "ARITHMETIC", 21.0, GREEN),
    ("Evidence quality", "20%", "tier-weighted mean, tier-4 contribution capped at 0.25, with a 0.45 floor penalty when no tier-1 or tier-2 evidence exists at all", "ARITHMETIC", 41.0, GREEN),
    ("Novelty & momentum", "15%", "slope of signal volume over 6 trailing periods, fitted on publication dates and never on ingestion dates", "ARITHMETIC", 61.0, GREEN),
    ("Strategic relevance", "15%", "rubric levels 0–5 with written anchors, mapped to 0–100. Discrete, because a free 0–100 ask compresses every answer into the middle of the scale", "MODEL, RUBRIC-SCORED", 81.0, PURPLE),
]
for name, w, body, kind, x, col in comps:
    c.box(x, 55.0, 18.0, 28.0, "", None, fc="#FFFFFF", ec=col, lw=1.2, shadow=True)
    c.ax.add_patch(FancyBboxPatch((x, 76.0), 18.0, 7.0,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, 76.0), 18.0, 1.4, fc=col, ec="none", zorder=4))
    c.text(x + 9.0, 80.8, name, fs=7.2, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(x + 9.0, 77.8, w, fs=7.6, color="#FFFFFFDD", ha="center", weight="bold", z=6)
    c.ax.text(x + 1.0, 73.6, "\n".join(textwrap.wrap(body, 37)), fontsize=6.2, color=INK, ha="left", va="top", zorder=6, linespacing=1.7)
    c.chip(x + 1.0, 56.4, 16.0, 4.0, kind, fc=col, tc="#FFFFFF", fs=5.8)

c.text(1.0, 49.0, "RIGHT TO WIN  —  seven components, a structured lookup against the Orange Business Graph. No language model touches this path.",
       fs=8.0, color=BLUE, weight="bold")
rtw = [("Offer match", "25%"), ("Reference density", "20%"), ("Partner coverage", "15%"),
       ("Compliance fit", "12%"), ("Capability depth", "12%"), ("External validation", "8%"),
       ("Technology ownership", "8%")]
x = 1.0
for name, w in rtw:
    c.box(x, 38.0, 13.4, 8.0, "", None, fc=BLUE_L, ec=BLUE, lw=1.0, radius=0.6)
    c.text(x + 6.7, 43.2, name, fs=6.6, color=BLUE, ha="center", weight="bold")
    c.text(x + 6.7, 40.0, w, fs=7.4, color=INK, ha="center", weight="bold")
    x += 14.0

c.zone(1.0, 3.0, 47.0, 31.0, None, fc=ORANGE_L, ec=ORANGE_D)
c.text(2.4, 31.0, "WHAT IS STORED, AND WHY IT IS STORED THAT WAY", fs=7.6, color=ORANGE_D, weight="bold")
c.ax.text(2.4, 28.0, "Each component returns a ComponentResult(value, inputs). The row in\n"
                     "`scores` keeps components AND inputs as JSON, so the UI can print the\n"
                     "publisher entropy alongside the publishers it counted, the tier\n"
                     "distribution, and the per-period buckets the momentum slope was\n"
                     "fitted to.\n\n"
                     "NFR-03 asks that a reviewer outside the project can reconstruct why\n"
                     "any topic holds its rank. A number you cannot re-derive is not\n"
                     "explained, only displayed.",
          fontsize=6.5, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)

c.zone(52.0, 3.0, 47.0, 31.0, None, fc=RED_L, ec=RED)
c.text(53.4, 31.0, "THE CALIBRATION-DRIFT GUARD", fs=7.6, color=RED, weight="bold")
c.ax.text(53.4, 28.0, "Every score row records the weight_set that produced it. Changing any\n"
                      "weight requires a NEW weight_set id, because scores across a version\n"
                      "boundary are not comparable — and the UI refuses to plot a trajectory\n"
                      "across the boundary silently.\n\n"
                      "The same rule extends outward: market_sizes carries sizing_version,\n"
                      "topic_competition carries register_version, and an assessment records\n"
                      "the weight_set the topic was scored under when it was rated. An opinion\n"
                      "formed against one calibration is never silently compared with another.",
          fontsize=6.5, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)
c.save(OUT + "ta-06-scoring.png")
