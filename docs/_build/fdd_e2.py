import sys, textwrap; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 6.2)
c.title("Figure 9 — Screens and the three role journeys",
        "Eight views over one read model. The role changes what may be seen and how it is ordered; it never changes what a number means.")

c.text(1.0, 87.0, "VIEWS", fs=8.2, color=INK, weight="bold")
screens = [
    ("Radar", "polar — sector = domain,\nradius = time horizon", 1.0, ORANGE_D),
    ("List", "ranked rows, server-computed\nfacet counts", 13.4, GREY_D),
    ("Detail", "four quantities first, then\nthe evidence behind each", 25.8, GREY_D),
    ("Brief", "the PDF rendered inline,\nwith a staleness warning", 38.2, GREY_D),
    ("Workflow", "stage board, assessments,\nstalled cards", 50.6, PURPLE),
    ("Analytics", "grid, funnel, divergence,\nevidence over time", 63.0, TEAL),
    ("White space", "high attractiveness,\nno portfolio path", 75.4, RED),
    ("Coverage", "language, geography\nand tier coverage", 87.8, BLUE),
]
for name, sub, x, col in screens:
    c.box(x, 69.0, 11.2, 14.0, name, sub, fc="#FFFFFF", ec=col, tc=col, fs=8.0, subfs=6.1, shadow=True)
c.text(1.0, 65.0, "Deep links carry the whole view:  ?topic=OS012&role=presales&tab=brief&theme=dark&explain=OS021  — a prepared view can be sent to a colleague.",
       fs=6.9, color=GREY_D)

lanes = [
    ("STRATEGIST", "Where do we invest\nnext quarter?", GOLD, 44.0,
     ["Radar — scan by domain and horizon", "White space — what nobody can deliver yet",
      "Detail — market size, and the evidence under it", "Analytics — the divergence review queue",
      "Workflow — shortlist it, with a written reason"]),
    ("SALES", "What do I open this\naccount with?", BLUE, 26.0,
     ["List — filtered to my vertical and persona", "Detail — the proof points and the reference",
      "Brief — generate it, take it into the meeting", "Feedback — useful / not useful, with the reason",
      "Workflow — rate customer demand 0–5"]),
    ("PRESALES", "How do I differentiate\nthis bid?", TEAL, 8.0,
     ["List — ordered by differentiation", "Detail — offers, partners, certifications",
      "Competition — who else is in the deal, and how we know", "Brief — the solution diagram and the objections",
      "Workflow — rate deliverability 0–5"]),
]
for name, q, col, y, steps in lanes:
    c.box(1.0, y, 15.0, 15.0, "", None, fc=col, ec=col)
    c.text(8.5, y + 10.0, name, fs=8.6, color="#FFFFFF", ha="center", weight="bold")
    c.text(8.5, y + 4.8, q, fs=6.5, color="#FFFFFFDD", ha="center", ls_=1.5)
    x = 17.6
    for i, s in enumerate(steps):
        c.box(x, y, 15.4, 15.0, "", None, fc=GREY_LL, ec=col, lw=1.0, radius=0.6)
        c.ax.add_patch(Circle((x + 2.0, y + 11.8), 1.35, fc=col, ec="none", zorder=5))
        c.text(x + 2.0, y + 11.8, str(i + 1), fs=6.4, color="#FFFFFF", ha="center", weight="bold", z=6)
        c.ax.text(x + 0.9, y + 8.4, "\n".join(textwrap.wrap(s, 27)), fontsize=6.5, color=INK,
                  ha="left", va="top", zorder=6, linespacing=1.55)
        if i < len(steps) - 1:
            c.arrow((x + 15.4, y + 7.5), (x + 16.4, y + 7.5), color=col, lw=1.3)
        x += 16.4
c.text(1.0, 4.0, "AC-05 caps a view at 24 topics, so an order control — market size, attractiveness, right to win, least contested, evidence, recency — re-orders WITHIN what the role may see, and says so.",
       fs=6.9, color=GREY_D)
c.save(OUT + "fdd-09-journeys.png")
