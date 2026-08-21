import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.6, 6.4)
c.title("Figure 6 — Collaboration: the stage gate and team conviction",
        "Model A gives accountability, Model C gives judgement. Conviction is a third quantity that moves the ordering of a list and nothing else.")

c.text(0.8, 88.0, "MODEL A — STAGE GATE", fs=8.6, color=INK, weight="bold")
c.text(0.8, 84.4, "Ownership follows the stage. Every transition records who moved it and why; age-in-stage is computed so a stalled card is flagged rather than left to be noticed.",
       fs=7.2, color=GREY_D)
stages = [
    ("SHORTLISTED", "Strategist", "Worth someone's time", 2.0, GOLD),
    ("DEMAND-TESTED", "Sales", "Customers are asking", 26.0, BLUE),
    ("PACKAGED", "Presales", "There is something to sell", 50.0, TEAL),
    ("LIVE", "Presales", "In front of customers", 74.0, GREEN),
]
for name, owner, note, x, col in stages:
    c.box(x, 60.0, 21.0, 17.0, "", None, fc="#FFFFFF", ec=col, lw=1.3, shadow=True)
    c.ax.add_patch(FancyBboxPatch((x, 70.4), 21.0, 6.6,
                                  boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    c.ax.add_patch(Rectangle((x, 70.4), 21.0, 1.4, fc=col, ec="none", zorder=4))
    c.text(x + 10.5, 73.6, name, fs=8.6, color="#FFFFFF", ha="center", weight="bold", z=6)
    c.text(x + 10.5, 67.0, f"owner:  {owner}", fs=7.4, color=col, ha="center", weight="bold", z=6)
    c.text(x + 10.5, 63.2, note, fs=6.9, color=GREY_D, ha="center", z=6)
    if x < 74.0:
        c.arrow((x + 21.0, 68.5), (x + 24.0, 68.5), color=GREY_D, lw=1.7)
c.chip(80.0, 53.0, 15.0, 4.6, "parked / rejected", fc=GREY, tc="#FFFFFF", fs=6.8)
c.path([(87.5, 60.0), (87.5, 57.8)], color=GREY, head=True)
c.chip(2.0, 53.0, 27.0, 4.6, "stalled ≥ 30 days in stage  →  flagged", fc=RED, tc="#FFFFFF", fs=6.8)
c.path([(12.5, 60.0), (12.5, 57.8)], color=RED, head=True)

c.rule(48.0)
c.text(0.8, 43.8, "MODEL C — DISTRIBUTED ASSESSMENT", fs=8.6, color=INK, weight="bold")
c.text(0.8, 40.2, "Each role rates only its own axis, 0–5 against written anchors, with a separate confidence. A changed mind supersedes rather than duplicates — the earlier opinion is kept.",
       fs=7.2, color=GREY_D)
axes = [
    ("Strategist", "STRATEGIC FIT", "Owns where investment goes", 2.0, GOLD),
    ("Sales", "CUSTOMER DEMAND", "Authoritative on whether\ncustomers are asking", 26.0, BLUE),
    ("Presales", "DELIVERABILITY", "Knows what it would\nactually take to build", 50.0, TEAL),
]
for role, axis, why, x, col in axes:
    c.box(x, 21.0, 21.0, 15.0, "", None, fc="#FFFFFF", ec=col, lw=1.3)
    c.text(x + 10.5, 32.6, role, fs=8.4, color=col, ha="center", weight="bold")
    c.text(x + 10.5, 28.8, axis, fs=7.6, color=INK, ha="center", weight="bold")
    c.text(x + 10.5, 24.6, why, fs=6.8, color=GREY_D, ha="center", ls_=1.5)
    c.path([(x + 10.5, 21.0), (x + 10.5, 17.0)], color=PURPLE, lw=1.2, head=False)
c.path([(12.5, 17.0), (71.5, 17.0)], color=PURPLE, lw=1.2, head=False)
c.path([(71.5, 17.0), (71.5, 28.5), (73.6, 28.5)], color=PURPLE, lw=1.4, head=True)
c.box(74.0, 21.0, 25.4, 15.0, "CONVICTION", "confidence-weighted aggregate\nof the live assessments",
      fc=PURPLE_L, ec=PURPLE, tc=PURPLE, fs=9.2, subfs=6.9, shadow=True)

c.box(2.0, 1.5, 44.0, 12.0, "", None, fc=GREEN_L, ec=GREEN, lw=1.1)
c.text(3.4, 9.8, "Conviction enters the per-role RANKING function only.", fs=7.6, color=GREEN, weight="bold")
c.text(3.4, 5.8, "Weight 0.25. An unrated topic sits neutral, not last — treating \"nobody has\nlooked yet\" as \"everybody hates it\" is a popularity bias, not a judgement.",
       fs=7.0, color=INK, ls_=1.5)
c.box(50.0, 1.5, 49.4, 12.0, "", None, fc=RED_L, ec=RED, lw=1.1)
c.text(51.4, 9.8, "Divergence is the product, not the noise.", fs=7.6, color=RED, weight="bold")
c.text(51.4, 5.8, "Where conviction and the evidence-derived score disagree by more than 30 points, the topic\nenters a review queue with a written reading of the gap. It is flagged, never averaged away.",
       fs=7.0, color=INK, ls_=1.5)
c.save(OUT + "fdd-06-workflow.png")
