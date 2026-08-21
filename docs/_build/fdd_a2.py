import sys, textwrap; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(12.4, 6.6)
c.title("Figure 2 — Functional capability map",
        "Six capability groups and the functions inside each. All six are delivered; the exclusions are listed at the foot.")

groups = [
    ("EVIDENCE ACQUISITION", GREEN, [
        "Source catalogue & licence position", "Taxonomy-derived query expansion",
        "Scheduled, parallel collection", "Publication-date gating (replay safe)",
        "Deduplication & syndication collapse", "Raw archive retention",
        "Source tiering (1–4)", "Internal signal intake + moderation"]),
    ("SENSE-MAKING", TEAL, [
        "Relevance gate", "Signal-type classification (6 types)",
        "Geography & language tagging", "Theme clustering",
        "Candidate synthesis (5 lenses)", "Adversarial critic pass",
        "Evidence enrichment", "On-demand constrained generation"]),
    ("QUALIFICATION", ORANGE_D, [
        "Attractiveness (5 components)", "Right to win (7 components)",
        "Market size — two methods", "Competitive intensity",
        "Time-horizon derivation", "Lifecycle state machine"]),
    ("COMPETITOR INTELLIGENCE", RED, [
        "Robots-aware site crawling", "Structured competitor profiles",
        "Per-topic competitor join", "Differentiation angle per competitor",
        "Competitor-seeded generation", "Profiling-coverage reporting"]),
    ("PORTFOLIO JOIN", BLUE, [
        "Orange Business Graph build", "Link generation & typing L0–L4",
        "Supporting-evidence links (SUP)", "Portfolio distance",
        "Curator confirmation of patterns", "White space & orphan offers"]),
    ("DECISION SUPPORT", PURPLE, [
        "Role-mode ranking & filtering", "Radar, list and analytics views",
        "Score explanation surface", "Long-form description",
        "PDF sales brief + completeness", "Stage gate & team conviction",
        "Divergence review queue", "Coverage & gap reporting"]),
]
TOP, HDR, ROW = 84.0, 7.4, 7.4
W, GAP = 15.6, 1.0
x = 0.8
for name, col, items in groups:
    body = len(items) * ROW + 2.6
    y0 = TOP - HDR - body
    c.zone(x, y0, W, HDR + body, None, fc="#FFFFFF", ec=col, ls="-", lw=1.3, radius=0.9)
    c.ax.add_patch(FancyBboxPatch((x, TOP - HDR), W, HDR,
                                  boxstyle="round,pad=0,rounding_size=0.9", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, TOP - HDR), W, 1.4, fc=col, ec="none", zorder=4))
    c.ax.text(x + W / 2, TOP - HDR / 2 + 0.4, "\n".join(textwrap.wrap(name, 15)),
              fontsize=7.4, color="#FFFFFF", ha="center", va="center", weight="bold",
              zorder=6, linespacing=1.3)
    yy = TOP - HDR - 3.0
    for it in items:
        c.box(x + 0.9, yy - 6.5, W - 1.8, 6.5, "", None, fc=GREY_LL, ec=GREY_L, lw=0.8, radius=0.5)
        c.ax.text(x + 1.6, yy - 1.6, "\n".join(textwrap.wrap(it, 22)), fontsize=6.4,
                  color=INK, ha="left", va="top", zorder=6, linespacing=1.5)
        yy -= ROW
    x += W + GAP

c.rule(15.0)
c.text(0.8, 12.0, "Deferred by scope, with the reason:", fs=7.6, color=INK, weight="bold")
c.text(0.8, 8.6, "CRM integration — public assets give a sufficient right-to-win proxy   ·   Learned scoring and learned per-role ranking — no labels exist on day one; the capture and replay "
                 "harness ships instead   ·   Patent connector — needs EPO OPS registration", fs=6.9, color=GREY_D)
c.text(0.8, 5.2, "PowerPoint export — the PDF brief is built instead   ·   Backtest evaluation metrics — the replay harness exists, the metrics do not   ·   "
                 "Headless-browser rendering — three competitor sites are client-side only", fs=6.9, color=GREY_D)
c.save(OUT + "fdd-02-capability.png")
