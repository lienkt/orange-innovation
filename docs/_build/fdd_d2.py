import sys; sys.path.insert(0, ".")
from dg import *
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 6.6)
c.title("Figure 8 — Market size: computed, never quoted",
        "Two independent methods published side by side. A figure with no method is not an argument; two figures from different data that agree in order of magnitude are.")

# ---- method panels
c.zone(1.0, 44.0, 48.0, 42.0, None, fc=GREEN_L, ec=GREEN, ls="-", alpha=0.32)
c.text(25.0, 82.4, "METHOD 1 — BOTTOM-UP ADOPTION", fs=8.6, color=GREEN, ha="center", weight="bold")
f1 = [("Enterprise count", "Eurostat SBS  sbs_sc_ovw\nNACE × size class × country", 2.6),
      ("×   Adoption rate", "Eurostat enterprise ICT survey\ncloud · AI · IoT · security", 18.4),
      ("×   Engagement value", "median matching TED tender,\nscaled per size class", 34.2)]
for t, s, x in f1:
    c.box(x, 60.0, 14.6, 16.0, t, s, fc="#FFFFFF", ec=GREEN, tc=GREEN, fs=7.5, subfs=6.4)
c.box(2.6, 47.0, 45.8, 10.4, "", None, fc="#FFFFFF", ec=GREEN, lw=1.1)
c.text(25.5, 53.8, "The denominator and the adoption rate must share a size base.", fs=7.2, color=GREEN, ha="center", weight="bold")
c.text(25.5, 50.0, "Eurostat publishes ICT adoption for firms of 10+ employees only. Against an all-sizes\nenterprise count — roughly 90% micro-firms — every estimate would be out by an order of magnitude.",
       fs=6.6, color=INK, ha="center", ls_=1.5)

c.zone(51.0, 44.0, 48.0, 42.0, None, fc=BLUE_L, ec=BLUE, ls="-", alpha=0.32)
c.text(75.0, 82.4, "METHOD 2 — OBSERVED PROCUREMENT", fs=8.6, color=BLUE, ha="center", weight="bold")
f2 = [("TED notices", "whose CPV crosswalks to\nthis opportunity space", 52.6),
      ("Eligibility test", "on the notice's MAIN OBJECT,\nnot any of its lots", 68.4),
      ("÷   Contract duration", "4 years assumed, printed,\nand open to challenge", 84.2)]
for t, s, x in f2:
    c.box(x, 60.0, 14.6, 16.0, t, s, fc="#FFFFFF", ec=BLUE, tc=BLUE, fs=7.5, subfs=6.4)
c.box(52.6, 47.0, 45.8, 10.4, "", None, fc="#FFFFFF", ec=BLUE, lw=1.1)
c.text(75.5, 53.8, "The contract value must come from the right kind of contract.", fs=7.2, color=BLUE, ha="center", weight="bold")
c.text(75.5, 50.0, "A €188m hydroelectric turbine retrofit, correctly crosswalked to industrial asset management,\nwas setting the price of a zero-trust deployment until eligibility was tested on the main object.",
       fs=6.6, color=INK, ha="center", ls_=1.5)

c.path([(25.0, 44.0), (25.0, 40.2)], color=GREEN, lw=1.4)
c.path([(75.0, 44.0), (75.0, 41.0), (25.0, 41.0)], color=BLUE, lw=1.4, head=False)
c.text(50.0, 42.4, "published side by side, never averaged", fs=6.8, color=GREY_D, ha="center")

# ---- TAM / SAM / SOM
c.zone(1.0, 12.0, 60.0, 27.5, None, fc="#FFFFFF", ec=GREY, alpha=1.0)
c.text(2.4, 36.9, "WHAT EACH FIGURE MEANS", fs=7.6, color=GREY_D, weight="bold")
tri = [("TAM", "every adopter in scope", 29.4, ORANGE_D),
       ("SAM", "computed, not discounted — the same estimate restricted to the size\nclasses and geographies Orange actually serves", 22.0, ORANGE),
       ("SOM", "the one genuinely modelled number — a share assumption anchored on\nright to win and portfolio distance, and labelled as such everywhere", 14.6, GOLD)]
for name, desc, y, col in tri:
    c.box(2.4, y, 10.0, 6.0, name, None, fc=col, ec=col, tc="#FFFFFF", fs=9.4)
    c.text(14.4, y + 3.0, desc, fs=6.9, color=INK, ls_=1.5)
c.path([(7.4, 29.4), (7.4, 28.2)], color=GREY_D, head=True)
c.path([(7.4, 22.0), (7.4, 20.8)], color=GREY_D, head=True)

# ---- confidence grade
c.zone(63.0, 12.0, 36.0, 27.5, None, fc=GREY_LL, ec=GREY)
c.text(64.4, 36.9, "CONFIDENCE GRADE", fs=7.6, color=GREY_D, weight="bold")
for lbl, sub, y, col in [("observed", "every factor from a dated, attributable series", 30.0, GREEN),
                         ("partial", "one or more factors from a declared proxy", 25.4, GOLD),
                         ("modelled", "no attributable base — no figure is published", 20.8, RED)]:
    c.chip(64.4, y, 11.0, 4.0, lbl, fc=col, tc="#FFFFFF", fs=7.0)
    c.text(76.6, y + 2.0, sub, fs=6.4, color=GREY_D)
c.text(64.4, 16.2, "The grade is the WORST basis among the factors, never an\naverage: an estimate is exactly as good as its weakest input.",
       fs=6.7, color=INK, ls_=1.5)

c.rule(9.4)
c.text(1.0, 6.2, "Proxies widen the range; they never move the base. Where one series stands in for another the substitution is declared, the uncertainty band widens from ±15% to ±40%, and the confidence", fs=6.9, color=GREY_D)
c.text(1.0, 3.2, "grade drops. Public administration has no Eurostat enterprise count at all, so those spaces are sized from observed procurement only rather than given a number the data cannot support.", fs=6.9, color=GREY_D)
c.save(OUT + "fdd-08-sizing.png")
