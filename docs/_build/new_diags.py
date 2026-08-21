import sys, textwrap; sys.path.insert(0, ".")
from dg import *
from erd import Entity, rel
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

# ============================================ FDD 11 — COMPETITOR INTELLIGENCE
c = Canvas(11.8, 7.0)
c.title("Figure 11 — Competitor intelligence: from their website to your meeting",
        "The register says what a competitor sells. A profile says what they say they sell, with the page that said it. The two are different kinds of evidence and are treated differently.")

stages = [
    ("1  CRAWL", "competitor_intel.py", ["robots.txt obeyed per URL", "sitemap-guided selection",
      "locale duplicates collapsed", "bounded extract, never a mirror"],
     "1,745 pages  ·  53 of 65 sites", 1.0, TEAL),
    ("2  PROFILE", "one model call each", ["every claim cites its page",
      "closed vocabulary + corroboration", "no generated numbers", "their own offer names only"],
     "53 profiles  ·  12 refused or unreadable", 25.5, GREEN),
    ("3  JOIN", "competitor_analysis.py", ["competitor × this topic's triple",
      "claims filtered to the cell", "arithmetic — no model, no cost", "always present, always current"],
     "177 topics joined", 50.0, BLUE),
    ("4  COMPARE", "one model call per topic", ["what they do here, cited",
      "how Orange differentiates", "what they do better", "only linked Orange assets nameable"],
     "177 written comparisons", 74.5, PURPLE),
]
for title, sub, bullets, foot, x, col in stages:
    c.box(x, 30.0, 23.0, 52.0, "", None, fc="#FFFFFF", ec=col, lw=1.3, shadow=True)
    c.ax.add_patch(FancyBboxPatch((x, 74.0), 23.0, 8.0,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, 74.0), 23.0, 1.6, fc=col, ec="none", zorder=4))
    c.text(x + 11.5, 79.2, title, fs=9.4, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(x + 11.5, 76.0, sub, fs=6.6, color="#FFFFFFDD", ha="center", z=6, style="italic")
    yy = 69.0
    for b in bullets:
        c.ax.text(x + 1.4, yy, "\n".join(textwrap.wrap("· " + b, 30)), fontsize=6.7,
                  color=INK, ha="left", va="top", zorder=6, linespacing=1.6)
        yy -= 7.4
    c.chip(x + 1.4, 31.5, 20.2, 4.4, foot, fc=col, tc="#FFFFFF", fs=6.3)
    if x < 74.5:
        c.arrow((x + 23.0, 56.0), (x + 25.3, 56.0), color=GREY_D, lw=1.7)

c.box(1.0, 11.0, 47.5, 16.0, "", None, fc=RED_L, ec=RED, lw=1.2)
c.text(2.4, 24.4, "WHAT A PROFILE MAY NOT DO", fs=7.6, color=RED, weight="bold")
c.ax.text(2.4, 21.4, "A vendor's own site is TIER 4 — interested party — everywhere it is scored.\n"
                     "A profile never lifts attractiveness, and SC-09's guarantee that vendor-only\n"
                     "evidence scores low is untouched. It may EXPLAIN a competitor already matched\n"
                     "to a topic, and it may SEED generation. Nothing else.",
          fontsize=6.7, color=INK, ha="left", va="top", zorder=8, linespacing=1.65)

c.box(51.0, 11.0, 48.0, 16.0, "", None, fc=GREEN_L, ec=GREEN, lw=1.2)
c.text(52.4, 24.4, "WHAT IT MAY DO — SEED GENERATION", fs=7.6, color=GREEN, weight="bold")
c.ax.text(52.4, 21.4, "Where two or more profiled competitors sell into a taxonomy cell the radar has\n"
                      "no topic for, that cell is promoted to the front of the synthesis target list and\n"
                      "reasoned over through a competitor-move lens. The candidate still has to bind to\n"
                      "independent, non-vendor evidence to be accepted — so an unsupported one dies.",
          fontsize=6.7, color=INK, ha="left", va="top", zorder=8, linespacing=1.65)

c.rule(8.0)
c.text(1.0, 5.4, "Six competitors answer 403 to a declared automated client and one disallows crawling in robots.txt. Spoofing a browser agent would work and is not done: they are recorded as", fs=6.9, color=GREY_D)
c.text(1.0, 2.4, "blocked with the reason, named individually in the Coverage view, and counted per topic — so a competitive field built from seven of eight competitors says so rather than reading as complete.", fs=6.9, color=GREY_D)
c.save(OUT + "fdd-11-competitor.png")


# ============================================ TA 12 — COMPETITOR ERD
c = Canvas(11.8, 6.2); ax = c.ax
c.title("Figure 12 — Physical data model, part 5:  competitor intelligence",
        "Three tables added for competitor profiling. DR-08 applies unchanged: a page is stored as its URL plus a bounded extract, never as a mirror.")

pages = Entity(ax, 1.0, 84.0, 22.0, "competitor_pages", [
    ("id", "pk"), ("competitor_id", "idx"), ("url", "idx"), ("kind", ""), ("title", ""),
    ("extract", ""), ("lang", ""), ("content_hash", ""), ("fetched_at", ""),
    ("http_status", ""), ("pipeline_version", "")],
    header_fc=TEAL, row_h=2.3, fs=6.5,
    note="UNIQUE(competitor_id, url) · kind ∈ home | solution |\nindustry | product | customer_story | other")

prof = Entity(ax, 29.0, 84.0, 23.0, "competitor_profiles", [
    ("competitor_id", "pk"), ("generated_at", ""), ("status", ""), ("status_reason", ""),
    ("positioning", ""), ("claims", ""), ("verticals", ""), ("technologies", ""),
    ("use_cases", ""), ("named_offers", ""), ("stripped", ""), ("pages_used", ""),
    ("corpus_hash", ""), ("register_version", ""), ("prompt_version", ""),
    ("model_version", ""), ("pipeline_version", "")],
    header_fc=GREEN, row_h=2.3, fs=6.5,
    note="status ∈ profiled | blocked | unreachable | no_pages\nA refused competitor still gets a row, saying so")

analysis = Entity(ax, 58.0, 84.0, 23.0, "topic_competitor_analysis", [
    ("opportunity_id", "pkfk"), ("computed_at", ""), ("topic_version", ""), ("entries", ""),
    ("narrative", ""), ("stripped", ""), ("coverage", ""), ("register_version", ""),
    ("prompt_version", ""), ("model_version", ""), ("pipeline_version", "")],
    header_fc=PURPLE, row_h=2.3, fs=6.5,
    note="entries = the join (always present)\nnarrative = the comparison (NULL until asked for)")

stub = Entity(ax, 84.0, 84.0, 15.0, "opportunity_spaces", [("id", "pk"), ("… Figure 7", "")],
              header_fc=ORANGE, row_h=2.3, fs=6.2, body_fc="#FFFDF8")

rel(ax, [(23.0, 66.0), (26.0, 66.0), (26.0, 66.0), (29.0, 66.0)], "many", "one",
    color=GREEN, label="profiled from", labelat=(26.0, 66.0), labeldy=1.7)
rel(ax, [(52.0, 66.0), (55.0, 66.0), (55.0, 66.0), (58.0, 66.0)], "many", "many",
    color=BLUE, ls=(0, (3, 2)), label="read by the join", labelat=(55.0, 66.0), labeldy=1.7)
rel(ax, [(81.0, 80.0), (84.0, 80.0)], "one", "one", color=ORANGE, label="", labelat=None)

c.text(1.0, 24.0, "THE TWO REGISTERS, KEPT APART IN THE SCHEMA ITSELF", fs=8.0, color=INK, weight="bold")
c.box(1.0, 3.0, 48.0, 19.0, "", None, fc=BLUE_L, ec=BLUE, lw=1.1)
c.text(2.4, 19.0, "entries — the join", fs=7.6, color=BLUE, weight="bold")
c.ax.text(2.4, 16.0, "Arithmetic over stored data: which of a competitor's own claims touch\n"
                     "this topic's vertical, use case or technology, plus the register overlap\n"
                     "and the profiling status. Free, reproducible, recomputed whenever the\n"
                     "topic or a profile moves. Present on every analysed topic.",
          fontsize=6.7, color=INK, ha="left", va="top", zorder=8, linespacing=1.65)
c.box(51.0, 3.0, 48.0, 19.0, "", None, fc=PURPLE_L, ec=PURPLE, lw=1.1)
c.text(52.4, 19.0, "narrative — the comparison", fs=7.6, color=PURPLE, weight="bold")
c.ax.text(52.4, 16.0, "A model comparing two companies: activity cited to their pages, the\n"
                      "differentiation angle anchored on a LINKED Orange asset, and the\n"
                      "concession. Costs one call, so it is NULL until asked for — and re-running\n"
                      "the cheap join must never discard an expensive comparison that still holds.",
          fontsize=6.7, color=INK, ha="left", va="top", zorder=8, linespacing=1.65)
c.save(OUT + "ta-12-erd-competitor.png")
