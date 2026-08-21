import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(12.0, 7.4)
c.title("Figure 1 — System context",
        "Who uses the Innovation Radar, what it consumes, and what it produces. Everything crossing a boundary is dated and attributable.")

# --- left: external sources
c.zone(1.0, 6.0, 21.0, 83.0, None, fc=BLUE_L, ec=BLUE, alpha=0.32)
c.text(11.5, 86.2, "EXTERNAL EVIDENCE", fs=8.4, color=BLUE, ha="center", weight="bold")
c.text(11.5, 82.8, "public · licence position recorded", fs=6.8, color=BLUE, ha="center")
srcs = [
    ("Procurement", "TED · BOAMP\nbudget being committed", 68.4),
    ("Regulation", "EUR-Lex · Have your say\nNIST · CERT-FR", 57.2),
    ("Research & technology", "OpenAlex · arXiv · CORDIS\nwhat Europe chose to fund", 46.0),
    ("News & practice", "Google News EN/FR\nGDELT · Hacker News", 34.8),
    ("Official statistics", "Eurostat SBS + ICT surveys\ndenominators, not signals", 23.6),
]
for t, s, y in srcs:
    c.box(2.4, y, 18.2, 9.4, t, s, fc="#FFFFFF", ec=BLUE, tc=BLUE, fs=8.0, subfs=6.7, shadow=True)
c.text(11.5, 17.2, "19 of 25 catalogued sources wired.\nEvery item carries a tier, a publisher\nand a publication date.",
       fs=6.7, color=BLUE, ha="center", ls_=1.5)

# --- centre: the product
c.zone(25.0, 6.0, 33.0, 83.0, None, fc=ORANGE_L, ec=ORANGE, ls="-", alpha=0.55, lw=1.4)
c.text(41.5, 86.2, "ORANGE BUSINESS INNOVATION RADAR", fs=9.8, color=ORANGE_D, ha="center", weight="bold")
c.text(41.5, 82.6, "Opportunity space  =  Vertical × Use case × Technology", fs=7.4, color=GREY_D, ha="center")
caps = [
    ("Discover", "Collect, classify and cluster dated evidence", 68.4, GREEN),
    ("Synthesise", "Generate candidate spaces, each bound to\nthe evidence that justified it", 57.2, GREEN),
    ("Qualify", "Attractiveness · right to win · market size ·\ncompetitive intensity", 46.0, ORANGE_D),
    ("Join", "Link each space to Orange offers, references,\npartners and certifications", 34.8, ORANGE_D),
    ("Act", "Role-ranked radar, workflow board,\ndescription, PDF sales brief", 23.6, PURPLE),
]
for t, s, y, col in caps:
    c.box(26.6, y, 29.8, 9.4, t, s, fc="#FFFFFF", ec=col, tc=col, fs=8.6, subfs=6.7, shadow=True)
c.text(41.5, 16.4, "Every number decomposes into named components.\nEvery claim cites a dated, attributable source.",
       fs=7.2, color=ORANGE_D, ha="center", weight="bold", ls_=1.5)

# --- right: users
c.zone(61.0, 6.0, 22.5, 83.0, None, fc=PURPLE_L, ec=PURPLE, alpha=0.32)
c.text(72.2, 86.2, "USERS", fs=8.4, color=PURPLE, ha="center", weight="bold")
c.text(72.2, 82.8, "three role modes, plus the curator", fs=6.8, color=PURPLE, ha="center")
users = [
    ("Strategist / Innovator", "Decide where to invest study and\nprototyping effort next quarter", 68.4),
    ("Sales", "Open or re-open a conversation\nwith a named account", 55.6),
    ("Presales / Proposal", "Differentiate a bid and assemble\nthe supporting material", 42.8),
    ("Curator", "Adjudicates link patterns; owns the\nsizing and competitor assumptions", 30.0),
]
for t, s, y in users:
    c.actor(66.0, y + 6.4, "", scale=0.8, color=PURPLE)
    c.text(70.0, y + 7.6, t, fs=8.0, color=INK, weight="bold")
    c.text(70.0, y + 3.6, s, fs=6.7, color=GREY_D, ls_=1.5)
c.text(72.2, 20.0, "The role decides what may be seen:\nsales L0–L1, presales L0–L2, strategy L1–L4.",
       fs=6.7, color=PURPLE, ha="center", ls_=1.5)

# --- far right: outputs
c.zone(86.0, 14.0, 13.0, 66.0, None, fc=GREY_LL, ec=GREY, alpha=0.9)
c.text(92.5, 77.0, "OUTPUTS", fs=7.8, color=GREY_D, ha="center", weight="bold")
outs = [("Radar view", 65.0), ("Topic detail\n+ evidence", 54.4), ("Sales brief\n(PDF)", 43.8),
        ("White space\nregister", 33.2), ("Read API\n(JSON)", 22.6)]
for t, y in outs:
    c.box(87.4, y, 10.2, 8.4, t, None, fc="#FFFFFF", ec=GREY_D, fs=7.0, bold=False)

# --- flows
c.path([(20.7, 47.0), (23.6, 47.0)], color=BLUE, lw=2.0, label="dated evidence", fs=7.0,
       labelat=(22.2, 47.0), labeldy=2.4)
c.path([(56.5, 47.0), (59.6, 47.0)], color=PURPLE, lw=2.0, label="ranked spaces", fs=7.0,
       labelat=(58.0, 47.0), labeldy=2.4)
c.path([(83.6, 58.0), (84.8, 58.0), (84.8, 47.0), (85.9, 47.0)], color=GREY_D, lw=1.3)
c.text(84.3, 61.0, "reads", fs=6.7, color=GREY_D, ha="center")
c.path([(66.0, 29.4), (66.0, 13.0), (41.5, 13.0), (41.5, 21.4)], color=PURPLE, lw=1.2,
       ls=(0, (5, 3)))
c.text(56.0, 10.6, "curator decisions, role assessments and stage moves feed back into ranking — never into a published score",
       fs=6.7, color=PURPLE, ha="center")
c.save(OUT + "fdd-01-context.png")
