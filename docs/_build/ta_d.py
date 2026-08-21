import sys, textwrap; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 6.8)
c.title("Figure 11 — Language-model integration and the guardrail chain",
        "The provider is an abstraction with a mock implementation, so every test runs without a network. Nothing a model produces reaches the database unvalidated.")

# ---- provider abstraction
c.zone(1.0, 62.0, 30.0, 24.0, None, fc=PURPLE_L, ec=PURPLE, ls="-", alpha=0.35)
c.text(16.0, 83.0, "PROVIDER ABSTRACTION  —  llm.py", fs=7.8, color=PURPLE, ha="center", weight="bold")
c.box(2.6, 72.0, 26.8, 8.0, "LLMClient", "one OpenAI-compatible interface",
      fc="#FFFFFF", ec=PURPLE, tc=PURPLE, fs=8.2, subfs=6.4)
for lbl, x in [("deepseek", 2.6), ("openai", 9.4), ("ollama", 16.2), ("mock", 23.0)]:
    c.box(x, 64.0, 6.2, 5.6, lbl, None, fc="#FFFFFF", ec=PURPLE, tc=PURPLE, fs=6.8)
    c.arrow((x + 3.1, 72.0), (x + 3.1, 69.8), color=PURPLE, lw=1.0)
c.text(16.0, 59.6, "NFR-05 — ollama keeps the sovereign deployment option open;\nmock keeps the test suite off the network entirely.",
       fs=6.4, color=PURPLE, ha="center", ls_=1.6)

# ---- where the model acts
c.zone(1.0, 20.0, 30.0, 36.0, None, fc=GREY_LL, ec=GREY)
c.text(16.0, 52.6, "WHERE THE MODEL IS ALLOWED TO ACT", fs=7.8, color=INK, ha="center", weight="bold")
rows = [("classify", "signal type + relevance, temp 0.0, batched 12"),
        ("synthesise", "candidate spaces, temp 0.85, 3 lensed passes"),
        ("critic", "adversarial pass, temp 0.10, different prompt"),
        ("rubric", "strategic relevance 0–5 against anchors"),
        ("actions", "next action per role"),
        ("describe", "long-form narrative + diagram structure")]
yy = 48.0
for name, why in rows:
    c.text(2.6, yy, name, fs=6.8, color=PURPLE, weight="bold")
    c.text(10.4, yy, why, fs=6.2, color=GREY_D)
    yy -= 3.6
c.ax.add_line(Line2D([2.6, 29.4], [27.6, 27.6], color=GREY, lw=0.9))
c.text(2.6, 24.8, "Never:  counting, publisher diversity, momentum, right to win,\nor any figure that appears in a brief.",
       fs=6.4, color=RED, ls_=1.7)

# ---- guardrail chain
c.text(34.0, 85.6, "THE GUARDRAIL CHAIN — every generated artefact passes all of it, in this order", fs=8.0, color=INK, weight="bold")
gates = [
    ("Schema parse", "JSON only. A malformed response is retried once,\nthen the candidate is dropped.", GREY_D, 72.5, 9.5),
    ("Closed vocabulary", "Every taxonomy value is validated against the\nenumeration. A recognised synonym is repaired\nONCE; anything else is dropped.", TEAL, 58.5, 12.0),
    ("Evidence binding", "Every claim must cite signal ids, validated to exist\nin the cluster that produced the candidate. Uncited\nclaims are STRIPPED, not rewritten.", GREEN, 44.5, 12.0),
    ("Numeric guard", "A regex over every generated sentence. A model\nsentence carrying a percentage or a euro figure kills\nthe section carrying it.", ORANGE_D, 30.5, 12.0),
    ("Named-entity check", "No customer, partner or competitor beyond the supplied\nlists — naming a plausible account is the failure most\nlikely to be repeated as though it were true.", BLUE, 16.5, 12.0),
    ("Entailment check", "A cheap second pass verifies each claim is entailed\nby the span it cites.", PURPLE, 5.0, 9.5),
]
for i, (name, body, col, y, h) in enumerate(gates):
    c.box(34.0, y, 40.0, h, "", None, fc="#FFFFFF", ec=col, lw=1.2, shadow=True)
    c.ax.add_patch(FancyBboxPatch((34.0, y), 5.4, h,
                                  boxstyle="round,pad=0,rounding_size=0.7", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((36.6, y), 2.8, h, fc=col, ec="none", zorder=4))
    c.text(36.7, y + h / 2, str(i + 1), fs=11.0, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(40.6, y + h - 2.8, name, fs=7.6, color=col, weight="bold")
    c.ax.text(40.6, y + h - 5.4, body, fontsize=6.3, color=INK, ha="left", va="top", zorder=6, linespacing=1.7)
    if i < len(gates) - 1:
        c.arrow((54.0, y), (54.0, y - 2.0), color=GREY_D, lw=1.2)

# ---- right-hand notes
c.box(77.0, 62.0, 22.0, 20.0, "", None, fc=RED_L, ec=RED, lw=1.1)
c.text(78.4, 79.4, "WHAT HAPPENS TO A FAILURE", fs=7.2, color=RED, weight="bold")
c.ax.text(78.4, 76.6, "Nothing is silently discarded. The\ncount and the reason go into the\nrefresh stats, and for descriptions\nthe stripped sections are listed in\nthe UI — a reader can see that\nsomething was removed, and why.",
          fontsize=6.3, color=INK, ha="left", va="top", zorder=8, linespacing=1.7)
c.box(77.0, 38.0, 22.0, 22.0, "", None, fc=GOLD_L, ec=GOLD, lw=1.1)
c.text(78.4, 57.4, "WHY STRIP RATHER THAN FIX", fs=7.2, color=GOLD, weight="bold")
c.ax.text(78.4, 54.4, "Asking a model to repair an uncited\nclaim teaches it to attach a citation\nat random. The cheapest correct\nanswer to \"this claim has no source\"\nis to delete the claim — the ones that\nremain are still true, and the topic is\nstill supported by what is left.",
          fontsize=6.3, color=INK, ha="left", va="top", zorder=8, linespacing=1.7)
c.box(77.0, 19.0, 22.0, 17.0, "", None, fc=BLUE_L, ec=BLUE, lw=1.1)
c.text(78.4, 33.4, "PROVENANCE", fs=7.2, color=BLUE, weight="bold")
c.ax.text(78.4, 30.4, "Every generated row records\npipeline_version, prompt_version and\nmodel_version (DR-10), so a regression\ncan be traced to the prompt that\ncaused it — and a brief that cannot\nbe traced is a brochure.",
          fontsize=6.3, color=INK, ha="left", va="top", zorder=8, linespacing=1.7)
c.box(77.0, 4.0, 22.0, 12.0, "ACCEPTED", "written to the database with its\nprompt and model version stamped",
      fc=GREEN_L, ec=GREEN, tc=GREEN, fs=9.0, subfs=6.3)
c.path([(74.0, 9.75), (76.6, 9.75)], color=GREEN, lw=1.6)
c.save(OUT + "ta-11-llm.png")
