import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 6.0)
c.title("Figure 4 — Portfolio distance and the role modes",
        "The link type from an opportunity space to the portfolio is an ordinal distance. Role modes are not interface presets — they fall out of it.")

rungs = [
    ("L0", "Direct", "An existing commercial offer addresses this opportunity as it stands", "Sales", "Sell it", 0, "#1B5E3F"),
    ("L1", "Bundle", "Two or more existing offers combined address it", "Presales", "Package it", 1, "#2E7D5B"),
    ("L2", "Partner-dependent", "Requires a capability held by an existing partner at a usable tier", "Presales / alliances", "Assemble it", 2, "#2F6FB0"),
    ("L3", "Adjacent", "Requires building or acquiring one capability; nearby assets already exist", "Strategy", "Study it", 3, "#8A6D1F"),
    ("L4", "White space", "No plausible path from the current portfolio", "Strategy", "Watch it, or reject it", 4, "#A82820"),
]
H, GAP = 9.0, 10.2
TOPY = 78.0
ys = {}
y = TOPY
for code, label, meaning, owner, action, dist, col in rungs:
    ys[code] = y
    c.box(11.8, y, 6.2, H, code, None, fc=col, ec=col, tc="#FFFFFF", fs=11.5)
    c.box(18.4, y, 13.6, H, label, None, fc="#FFFFFF", ec=col, tc=col, fs=8.2)
    c.box(32.4, y, 33.6, H, "", None, fc=GREY_LL, ec=GREY_L, lw=0.8)
    c.text(33.6, y + H / 2, meaning, fs=7.3, color=INK)
    c.box(66.4, y, 12.6, H, owner, None, fc="#FFFFFF", ec=GREY, fs=7.2, bold=False)
    c.box(79.4, y, 10.6, H, action, None, fc="#FFFFFF", ec=col, tc=col, fs=7.4)
    c.chip(90.6, y + H / 2 - 2.1, 8.2, 4.2, f"distance {dist}", fc=col, tc="#FFFFFF", fs=6.8)
    y -= GAP

y -= 2.0
c.box(11.8, y, 6.2, H, "SUP", None, fc=PURPLE, ec=PURPLE, tc="#FFFFFF", fs=10.5)
c.box(18.4, y, 13.6, H, "Supporting\nevidence", None, fc="#FFFFFF", ec=PURPLE, tc=PURPLE, fs=8.0)
c.box(32.4, y, 33.6, H, "", None, fc=PURPLE_L, ec=PURPLE_L, lw=0.8)
c.text(33.6, y + H / 2, "Proof, certification, analyst recognition or capability pool. Strengthens\nthe case without itself delivering the opportunity.",
       fs=7.3, color=INK, ls_=1.5)
c.box(66.4, y, 12.6, H, "All roles", None, fc="#FFFFFF", ec=GREY, fs=7.2, bold=False)
c.box(79.4, y, 10.6, H, "Cite it", None, fc="#FFFFFF", ec=PURPLE, tc=PURPLE, fs=7.4)
c.chip(90.6, y + H / 2 - 2.1, 8.2, 4.2, "excluded", fc=PURPLE, tc="#FFFFFF", fs=6.8)
c.text(94.7, y - 1.6, "does not shorten the distance", fs=6.1, color=PURPLE, ha="center")

# --- role windows as nested vertical brackets
def bracket(x, ytop, ybot, color, label, sub):
    c.ax.add_patch(FancyBboxPatch((x, ybot), 2.6, ytop - ybot,
                                  boxstyle="round,pad=0,rounding_size=1.0",
                                  fc=color, ec="none", zorder=6, alpha=0.9))
    c.ax.text(x + 1.3, (ytop + ybot) / 2, label, rotation=90, ha="center", va="center",
              fontsize=7.4, color="#FFFFFF", weight="bold", zorder=7)
    c.ax.text(x - 1.5, (ytop + ybot) / 2, sub, rotation=90, ha="center", va="center",
              fontsize=6.3, color=color, weight="bold", zorder=7)

bracket(8.4, ys["L0"] + H, ys["L1"], "#1B5E3F", "SALES", "L0–L1")
bracket(5.0, ys["L0"] + H, ys["L2"], BLUE, "PRESALES", "L0–L2")
bracket(1.6, ys["L1"] + H, ys["L4"], GOLD, "STRATEGY", "L1–L4")
c.text(0.6, 19.6, "Sales additionally requires a published reference in the vertical and no evidence gap —\n"
                            "§4.5.3's computable definition of \"enough internal content to credibly back it up\".",
       fs=6.9, color=GREY_D, ls_=1.55)

c.rule(13.0)
c.text(0.6, 9.0, "Portfolio distance = min(distance) over the delivery links, or 4 when none exists. Supporting evidence is linked, displayed and scored, but excluded from the distance", fs=7.0, color=GREY_D)
c.text(0.6, 5.4, "and from the role filter: typing a certification L0 would make every topic in a regulated vertical read as a direct sell purely because Orange holds ISO 27001.", fs=7.0, color=GREY_D)
c.save(OUT + "fdd-04-portfolio.png")
