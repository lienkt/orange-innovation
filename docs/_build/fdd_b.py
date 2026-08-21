import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

# --------------------------------------------------- 3. FOUR QUANTITIES
c = Canvas(11.6, 6.2)
c.title("Figure 3 — Four quantities, never combined",
        "Each answers a different question, from a different kind of evidence, with a different owner. Averaging any two would hide both.")

qs = [
    ("ATTRACTIVENESS", "Is the world moving?", ORANGE_D, ORANGE_L,
     "External evidence only", ["Market signal strength   30%", "Source diversity   20%",
      "Evidence quality   20%", "Novelty & momentum   15%", "Strategic relevance   15%"],
     "0–100 · published"),
    ("RIGHT TO WIN", "Can we play, can we win?", BLUE, BLUE_L,
     "Orange Business Graph", ["Offer match   25%", "Reference density   20%",
      "Partner coverage   15%", "Compliance fit   12%", "Capability depth   12%",
      "External validation   8%", "Technology ownership   8%"],
     "0–100 · published"),
    ("COMPETITIVE INTENSITY", "How crowded is the field?", TEAL, TEAL_L,
     "Competitor register + corpus", ["Named competitors, each with its basis",
      "evidenced — this space's sources name them", "structural — the register says they sell here",
      "Weighted count → NONE / LOW / MEDIUM / HIGH"],
     "band + named list"),
    ("CONVICTION", "Do our own people believe it?", PURPLE, PURPLE_L,
     "Role assessments", ["Strategist → strategic fit", "Sales → customer demand",
      "Presales → deliverability", "0–5 with written anchors, confidence-weighted"],
     "ranking only"),
]
x = 1.2
for name, q, col, fill, basis, rows, foot in qs:
    c.zone(x, 12.0, 23.6, 70.0, None, fc=fill, ec=col, ls="-", lw=1.3, alpha=0.45)
    c.ax.add_patch(FancyBboxPatch((x, 74.0), 23.6, 8.0,
                                  boxstyle="round,pad=0,rounding_size=0.9", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, 74.0), 23.6, 1.6, fc=col, ec="none", zorder=4))
    c.text(x + 11.8, 79.4, name, fs=8.4, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(x + 11.8, 76.2, q, fs=7.2, color="#FFFFFFDD", ha="center", style="italic", z=6)
    c.text(x + 11.8, 70.6, basis.upper(), fs=6.6, color=col, ha="center", weight="bold")
    yy = 65.0
    for r in rows:
        c.box(x + 1.2, yy - 5.2, 21.2, 5.2, r, None, fc="#FFFFFF", ec="#00000018",
              fs=6.7, bold=False, radius=0.5, lw=0.8)
        yy -= 6.2
    c.chip(x + 2.6, 14.0, 18.4, 4.2, foot, fc=col, tc="#FFFFFF", fs=6.6)
    x += 24.6

for xx in (25.8, 50.4, 75.0):
    c.ax.add_line(Line2D([xx - 0.5, xx - 0.5], [12.6, 82.0], color=RED, lw=1.4, ls=(0, (4, 3)), zorder=8))
    c.ax.text(xx - 0.5, 84.8, "✕", fontsize=9.5, color=RED, ha="center", va="center",
              weight="bold", zorder=9,
              bbox=dict(boxstyle="circle,pad=0.22", fc="#FFFFFF", ec=RED, lw=1.2))
c.text(50.0, 88.6, "no arithmetic crosses these lines", fs=7.6, color=RED, ha="center", weight="bold")
c.rule(9.0)
c.text(1.2, 6.0, "SC-12: the two published scores travel as separate fields end to end and occupy two different visual channels — marker size and marker colour.\n"
                 "SC-14: internal judgement adjusts the ordering of a list; it never replaces external discovery, and it never enters a published number.",
       fs=7.0, color=GREY_D, ls_=1.6)
c.save(OUT + "fdd-03-quantities.png")


# --------------------------------------------------- 4. PORTFOLIO DISTANCE
c = Canvas(11.6, 6.6)
c.title("Figure 4 — Portfolio distance and the role modes",
        "The link type from an opportunity space to the portfolio is an ordinal distance. Role modes are not interface presets — they fall out of it.")

rungs = [
    ("L0", "Direct", "An existing commercial offer addresses this opportunity as it stands", "Sales", "Sell it", 0, "#1B5E3F"),
    ("L1", "Bundle", "Two or more existing offers combined address it", "Presales", "Package it", 1, "#2E7D5B"),
    ("L2", "Partner-dependent", "Requires a capability held by an existing partner at a usable tier", "Presales / alliances", "Assemble it", 2, "#2F6FB0"),
    ("L3", "Adjacent", "Requires building or acquiring one capability; nearby assets exist", "Strategy", "Study it", 3, "#8A6D1F"),
    ("L4", "White space", "No plausible path from the current portfolio", "Strategy", "Watch it, or reject it", 4, "#A82820"),
]
y = 72.0
for code, label, meaning, owner, action, dist, col in rungs:
    c.box(1.2, y, 7.0, 8.4, code, None, fc=col, ec=col, tc="#FFFFFF", fs=12.0)
    c.box(8.6, y, 15.0, 8.4, label, None, fc="#FFFFFF", ec=col, tc=col, fs=8.6)
    c.box(24.0, y, 38.0, 8.4, "", None, fc=GREY_LL, ec=GREY_L, lw=0.8)
    c.text(25.4, y + 4.2, meaning, fs=7.4, color=INK)
    c.box(62.4, y, 14.0, 8.4, owner, None, fc="#FFFFFF", ec=GREY, fs=7.4, bold=False)
    c.box(76.8, y, 12.0, 8.4, action, None, fc="#FFFFFF", ec=col, tc=col, fs=7.6)
    c.chip(89.6, y + 2.2, 9.0, 4.0, f"distance {dist}", fc=col, tc="#FFFFFF", fs=6.8)
    y -= 9.6

y -= 1.4
c.box(1.2, y, 7.0, 8.4, "SUP", None, fc=PURPLE, ec=PURPLE, tc="#FFFFFF", fs=11.0)
c.box(8.6, y, 15.0, 8.4, "Supporting\nevidence", None, fc="#FFFFFF", ec=PURPLE, tc=PURPLE, fs=8.0)
c.box(24.0, y, 38.0, 8.4, "", None, fc=PURPLE_L, ec=PURPLE_L, lw=0.8)
c.text(25.4, y + 5.6, "Proof, certification, analyst recognition or capability pool. Strengthens the case", fs=7.2, color=INK)
c.text(25.4, y + 2.8, "without itself delivering the opportunity.", fs=7.2, color=INK)
c.box(62.4, y, 14.0, 8.4, "All roles", None, fc="#FFFFFF", ec=GREY, fs=7.4, bold=False)
c.box(76.8, y, 12.0, 8.4, "Cite it", None, fc="#FFFFFF", ec=PURPLE, tc=PURPLE, fs=7.6)
c.chip(89.6, y + 2.2, 9.0, 4.0, "excluded", fc=PURPLE, tc="#FFFFFF", fs=6.8)
c.text(89.6 + 4.5, y - 2.0, "does not shorten the distance", fs=6.2, color=PURPLE, ha="center")

# role windows
c.ax.add_patch(FancyBboxPatch((0.4, 71.2), 99.0, 19.6, boxstyle="round,pad=0,rounding_size=0.6",
                              fc="none", ec="#1B5E3F", lw=1.6, ls=(0, (5, 3)), zorder=9))
c.text(0.0, 0, "")
c.text(50.0, 92.2, "SALES sees L0–L1  ·  and only where a published reference exists in the vertical", fs=7.4,
       color="#1B5E3F", ha="center", weight="bold")
c.ax.add_patch(FancyBboxPatch((0.0, 61.0), 99.8, 30.4, boxstyle="round,pad=0,rounding_size=0.6",
                              fc="none", ec=BLUE, lw=1.4, ls=(0, (2, 2)), zorder=9))
c.text(50.0, 59.2, "PRESALES sees L0–L2", fs=7.4, color=BLUE, ha="center", weight="bold")
c.ax.add_patch(FancyBboxPatch((-0.4, 32.6), 100.6, 49.0, boxstyle="round,pad=0,rounding_size=0.6",
                              fc="none", ec=GOLD, lw=1.4, ls=(0, (1, 2)), zorder=9))
c.text(50.0, 30.8, "STRATEGY sees L1–L4  —  including the white space nobody else may see", fs=7.4,
       color=GOLD, ha="center", weight="bold")
c.rule(9.6)
c.text(1.2, 6.4, "Portfolio distance is the shortest delivery path from the space to the portfolio: min(distance) over the delivery links, or 4 when none exists.\n"
                 "Typing a certification L0 would make every topic in a regulated vertical read as a direct sell, so supporting evidence is scored but excluded.",
       fs=7.0, color=GREY_D, ls_=1.6)
c.save(OUT + "fdd-04-portfolio.png")
