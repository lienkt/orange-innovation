import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

# ------------------------------------------------------- 5. LIFECYCLE
c = Canvas(11.6, 5.8)
c.title("Figure 5 — Opportunity space lifecycle",
        "A recurring topic is updated, never recreated. State is recomputed on every refresh from the evidence attached to it, and every transition records its reason.")

cand = c.box(3.0, 62.0, 17.0, 12.0, "CANDIDATE", "synthesised, evidence\nnot yet sufficient",
             fc="#FFFFFF", ec=GREY_D, tc=GREY_D, fs=9.0, subfs=6.8, shadow=True)
watch = c.box(27.0, 62.0, 17.0, 12.0, "WATCHLIST", "real but thin\n≥ 1 qualifying signal",
              fc=GOLD_L, ec=GOLD, tc=GOLD, fs=9.0, subfs=6.8, shadow=True)
act = c.box(51.0, 62.0, 17.0, 12.0, "ACTIVE", "met every promotion\nthreshold", fc=GREEN_L, ec=GREEN,
            tc=GREEN, fs=9.6, subfs=6.8, shadow=True)
fade = c.box(75.0, 62.0, 17.0, 12.0, "FADING", "no new signal for\n1 period, or momentum < 50",
             fc=ORANGE_L, ec=ORANGE_D, tc=ORANGE_D, fs=9.0, subfs=6.8, shadow=True)
dorm = c.box(75.0, 36.0, 17.0, 12.0, "DORMANT", "silent for 3 periods\nkept, not deleted", fc=GREY_L,
             ec=GREY_D, tc=GREY_D, fs=9.0, subfs=6.8, shadow=True)
rej = c.box(3.0, 36.0, 17.0, 12.0, "REJECTED", "terminal — a curator\ndecision, never automatic",
            fc=RED_L, ec=RED, tc=RED, fs=9.0, subfs=6.8, shadow=True)

c.arrow(cand.right, watch.left, color=GREY_D, label="≥ 1 qualifying signal", fs=6.8, dy=1.6)
c.arrow(watch.right, act.left, color=GREEN, label="promotion gate", fs=6.8, dy=1.6)
c.arrow(act.right, fade.left, color=ORANGE_D, label="evidence stops", fs=6.8, dy=1.6)
c.path([(83.5, 62.0), (83.5, 48.0)], color=GREY_D, label="3 periods silent", fs=6.8,
       labelat=(83.5, 55.0), labeldx=-12.5, labeldy=0.0)
c.path([(75.0, 42.0), (60.0, 42.0), (60.0, 62.0)], color=GREEN, label="new qualifying signal → re-promoted",
       fs=6.8, labelat=(66.5, 42.0), labeldy=1.8)
c.path([(83.5, 74.0), (83.5, 81.0), (59.5, 81.0), (59.5, 74.0)], color=GREEN,
       label="momentum recovers above 50", fs=6.8, labelat=(71.5, 81.0), labeldy=1.8)
c.path([(35.5, 62.0), (35.5, 42.0), (20.0, 42.0)], color=RED, label="curator rejects", fs=6.8,
       labelat=(27.8, 42.0), labeldy=1.8)
c.path([(11.5, 62.0), (11.5, 48.0)], color=RED, head=True)

c.zone(3.0, 5.0, 43.0, 21.0, "PROMOTION GATE  —  all four must hold", fc=GREEN_L, ec=GREEN, ls="-", alpha=0.4)
c.text(4.6, 17.0, "≥ 4 attached signals        ≥ 3 distinct publishers", fs=7.4, color=INK)
c.text(4.6, 12.6, "evidence quality ≥ 45      at least one non-tier-4 source", fs=7.4, color=INK)
c.text(4.6, 8.0, "No topic reaches active status on vendor evidence alone.", fs=7.0, color=GREEN, style="italic")

c.zone(51.0, 5.0, 45.0, 21.0, "WHY THE FADED STATES ARE KEPT", fc=GREY_LL, ec=GREY, alpha=0.9)
c.text(52.6, 17.0, "A dormant topic still holds its evidence, its links and its score history.", fs=7.4, color=INK)
c.text(52.6, 12.6, "Deleting it would destroy the trajectory momentum is measured from —", fs=7.4, color=INK)
c.text(52.6, 8.2, "and a topic that goes quiet for two quarters and returns is itself a signal.", fs=7.4, color=INK)
c.save(OUT + "fdd-05-lifecycle.png")


# ------------------------------------------------------- 6. WORKFLOW
c = Canvas(11.6, 6.4)
c.title("Figure 6 — Collaboration: the stage gate and team conviction",
        "Model A gives accountability, Model C gives judgement. Conviction is a third quantity that moves the ordering of a list and nothing else.")

c.text(0.8, 88.0, "MODEL A — STAGE GATE", fs=8.6, color=INK, weight="bold")
c.text(0.8, 84.6, "Ownership follows the stage. Every transition records who moved it and why; age-in-stage is computed so a stalled card is flagged rather than left to be noticed.",
       fs=7.2, color=GREY_D)
stages = [
    ("SHORTLISTED", "Strategist", "Worth someone's time", 2.0, GOLD),
    ("DEMAND-TESTED", "Sales", "Customers are asking", 26.0, BLUE),
    ("PACKAGED", "Presales", "There is something to sell", 50.0, TEAL),
    ("LIVE", "Presales", "In front of customers", 74.0, GREEN),
]
for name, owner, note, x, col in stages:
    c.box(x, 62.0, 21.0, 16.0, name, None, fc=col, ec=col, tc="#FFFFFF", fs=8.8, shadow=True)
    c.ax.add_patch(Rectangle((x + 0.4, 62.4), 20.2, 8.4, fc="#FFFFFF", ec="none", zorder=4))
    c.text(x + 10.5, 68.4, f"owner: {owner}", fs=7.2, color=col, ha="center", weight="bold", z=5)
    c.text(x + 10.5, 65.0, note, fs=6.8, color=GREY_D, ha="center", z=5)
    if x < 74.0:
        c.arrow((x + 21.0, 74.0), (x + 24.0, 74.0), color=GREY_D, lw=1.6)
c.box(95.4, 62.0, 4.0, 16.0, "", None, fc="none", ec="none")
c.chip(84.0, 55.0, 15.0, 4.6, "parked / rejected", fc=GREY, tc="#FFFFFF", fs=6.8)
c.path([(84.5, 62.0), (84.5, 59.8)], color=GREY, head=True)
c.chip(2.0, 55.0, 26.0, 4.6, "stalled ≥ 30 days in stage → flagged", fc=RED, tc="#FFFFFF", fs=6.8)

c.rule(50.0)
c.text(0.8, 45.6, "MODEL C — DISTRIBUTED ASSESSMENT", fs=8.6, color=INK, weight="bold")
c.text(0.8, 42.2, "Each role rates only its own axis, 0–5 against written anchors, with a separate confidence. A changed mind supersedes rather than duplicates — the earlier opinion is kept.",
       fs=7.2, color=GREY_D)
axes = [
    ("Strategist", "STRATEGIC FIT", "Owns where investment goes", 2.0, GOLD),
    ("Sales", "CUSTOMER DEMAND", "Authoritative on whether customers are asking", 26.0, BLUE),
    ("Presales", "DELIVERABILITY", "Knows what it would actually take to build", 50.0, TEAL),
]
for role, axis, why, x, col in axes:
    c.box(x, 22.0, 21.0, 15.0, "", None, fc="#FFFFFF", ec=col, lw=1.3)
    c.text(x + 10.5, 33.4, role, fs=8.4, color=col, ha="center", weight="bold")
    c.text(x + 10.5, 29.6, axis, fs=7.6, color=INK, ha="center", weight="bold")
    c.text(x + 10.5, 25.4, why, fs=6.7, color=GREY_D, ha="center")
c.path([(23.0, 29.5), (25.0, 29.5)], color=GREY, head=False)
c.path([(47.0, 29.5), (49.0, 29.5)], color=GREY, head=False)
c.path([(12.5, 22.0), (12.5, 18.0), (60.0, 18.0), (60.0, 15.0)], color=PURPLE, lw=1.3, head=False)
c.path([(36.5, 22.0), (36.5, 18.0)], color=PURPLE, lw=1.3, head=False)
c.path([(60.5, 22.0), (60.5, 18.0)], color=PURPLE, lw=1.3, head=False)
c.box(74.0, 22.0, 25.4, 15.0, "CONVICTION", "confidence-weighted aggregate\nof the live assessments",
      fc=PURPLE_L, ec=PURPLE, tc=PURPLE, fs=9.0, subfs=6.9, shadow=True)
c.path([(71.0, 29.5), (73.6, 29.5)], color=PURPLE, lw=1.6)
c.path([(60.0, 18.0), (71.0, 18.0), (71.0, 29.5)], color=PURPLE, lw=1.3, head=False)

c.box(2.0, 3.0, 44.0, 12.0, "", None, fc=GREEN_L, ec=GREEN, lw=1.1)
c.text(3.4, 11.2, "Conviction enters the per-role RANKING function only.", fs=7.6, color=GREEN, weight="bold")
c.text(3.4, 7.4, "Weight 0.25. An unrated topic sits neutral, not last — treating \"nobody\nhas looked yet\" as \"everybody hates it\" is a popularity bias, not a judgement.",
       fs=7.0, color=INK, ls_=1.5)
c.box(50.0, 3.0, 49.4, 12.0, "", None, fc=RED_L, ec=RED, lw=1.1)
c.text(51.4, 11.2, "Divergence is the product, not the noise.", fs=7.6, color=RED, weight="bold")
c.text(51.4, 7.4, "Where conviction and the evidence-derived score disagree by more than 30 points, the topic enters\na review queue with a written reading of the gap. It is flagged, never averaged away.",
       fs=7.0, color=INK, ls_=1.5)
c.save(OUT + "fdd-06-workflow.png")
