import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 5.8)
c.title("Figure 7 — From evidence to accepted opportunity space",
        "Generation is deliberately over-produced and then filtered. Each gate has a named reason to exist, and what it removed is reported rather than quietly dropped.")

c.text(1.0, 86.0, "THE FUNNEL, MEASURED ON A LIVE RUN", fs=8.2, color=INK, weight="bold")
rows = [
    ("254", "raw candidates", "27 clusters × 3 lensed passes at temperature 0.85", GREY_D, 100.0),
    ("248", "after closed vocabulary", "6 dropped — a taxonomy value outside the enumeration", TEAL, 97.6),
    ("241", "after evidence binding", "7 dropped — cited signal ids absent from the originating cluster", TEAL, 94.9),
    ("122", "after the adversarial critic", "119 dropped — the score is the MINIMUM across five tests", RED, 48.0),
    ("122", "after the entailment check", "15 claims stripped, not rewritten — the candidate survives, the claim does not", GOLD, 48.0),
    ("60", "accepted", "62 merged as duplicates on the canonical triple", GREEN, 23.6),
]
y = 71.0
for n, label, why, col, pct in rows:
    w = 5.0 + 15.0 * pct / 100.0
    c.box(1.0, y, w, 8.6, "", None, fc=col, ec=col, radius=0.6)
    c.text(1.0 + w / 2, y + 4.3, n, fs=10.5, color="#FFFFFF", ha="center", weight="bold")
    c.text(22.4, y + 5.9, label, fs=8.2, color=INK, weight="bold")
    c.text(22.4, y + 2.5, why, fs=6.8, color=GREY_D)
    y -= 10.6

c.text(1.0, 5.6, "24% yield — close to the briefing's \"generate forty candidates and keep eight\". The 62 merges are the price of over-producing on purpose,\n"
                 "and are exactly what the canonical-triple identity rule exists to absorb: two passes that reach the same triple are the same topic.",
       fs=6.9, color=GREY_D, ls_=1.6)

# --- right: the four defences
c.ax.add_line(Line2D([61.0, 61.0], [8.0, 88.0], color=GREY_L, lw=1.0))
c.text(63.0, 86.0, "THE FOUR DEFENCES, IN ORDER OF EFFECTIVENESS", fs=8.2, color=INK, weight="bold")
defs = [
    ("1", "Evidence binding", "Every claim cites signal ids, validated to exist in the cluster\nthat produced the candidate. Uncited claims are STRIPPED,\nnot rewritten — a model asked to fix a claim invents a source.", GREEN),
    ("2", "Closed-vocabulary output", "Taxonomy values are validated against the enumerations.\nA recognised synonym is repaired once; anything else is dropped.", TEAL),
    ("3", "No model-generated numbers", "Enforced in every system prompt and backstopped by a regex\nover generated claims. Figures come from the sizing engine.", BLUE),
    ("4", "Entailment check", "A cheap second pass verifies each \"why hot\" claim is actually\nentailed by the span it cites.", PURPLE),
]
yy = 74.0
for num, name, body, col in defs:
    c.box(63.0, yy - 15.0, 36.0, 15.0, "", None, fc="#FFFFFF", ec=col, lw=1.2)
    c.ax.add_patch(FancyBboxPatch((63.0, yy - 15.0), 4.6, 15.0,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((65.4, yy - 15.0), 2.2, 15.0, fc=col, ec="none", zorder=4))
    c.text(65.3, yy - 7.5, num, fs=12.0, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(69.0, yy - 3.4, name, fs=8.0, color=col, weight="bold")
    c.text(69.0, yy - 9.6, body, fs=6.6, color=INK, ls_=1.55)
    yy -= 17.0
c.text(63.0, 5.6, "Plus an adversarial critic pass under a different system prompt, which rejected\n119 of 254 candidates with a specific written reason for each.",
       fs=6.9, color=GREY_D, ls_=1.6)
c.save(OUT + "fdd-07-funnel.png")
