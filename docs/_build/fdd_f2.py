import sys; sys.path.insert(0, ".")
from dg import *
from erd import rel
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(11.8, 7.0)
ax = c.ax
c.title("Figure 10 — Conceptual data model",
        "The business objects and the relationships between them, independent of storage. The physical schema is in the Technical Architecture, Figure 7.")

def ent(x, y, w, h, name, lines, col, fill, nfs=8.0):
    c.box(x, y, w, h, "", None, fc=fill, ec=col, lw=1.3, shadow=True)
    ax.add_patch(FancyBboxPatch((x, y + h - 5.0), w, 5.0,
                                boxstyle="round,pad=0,rounding_size=0.8", fc=col, ec="none", zorder=4))
    ax.add_patch(Rectangle((x, y + h - 5.0), w, 1.2, fc=col, ec="none", zorder=4))
    c.text(x + w / 2, y + h - 2.5, name, fs=nfs, color="#FFFFFF", ha="center", weight="bold", z=6)
    ax.text(x + 1.3, y + h - 6.6, lines, fontsize=6.2, color=INK, ha="left", va="top",
            zorder=6, linespacing=1.75)

ent(1.5, 60.0, 19.5, 25.0, "SIGNAL",
    "id, publisher, title, url\npublished_at — never ingested_at\nsignal_type  (one of six)\ntier 1–4, language, geographies\nextract only, never a mirror", TEAL, TEAL_L)
ent(1.5, 41.0, 19.5, 12.0, "THEME CLUSTER",
    "label, keyphrases, size\nrecomputed each refresh", GREY_D, GREY_LL)
ent(1.5, 8.0, 19.5, 22.0, "BUSINESS ASSET",
    "offer · reference · partner\ncertification · analyst position\ncapability pool · research asset\nsource + as_of — auditable to\nthe same standard as a signal", BLUE, "#FFFFFF")
ent(28.0, 60.0, 23.0, 25.0, "OPPORTUNITY SPACE",
    "id — stable across refreshes\nvertical × use_case × technology\n     the canonical identity\nstatement, why_hot [cited claims]\nstate, horizon, version\nnext_actions per role", ORANGE, ORANGE_L, nfs=8.4)
ent(28.0, 36.0, 23.0, 19.0, "LINK",
    "link_type  L0–L4  or  SUP\nconfidence, evidence\nconfirmed_by (curator), rejected", BLUE, BLUE_L)
ent(28.0, 19.0, 23.0, 13.0, "ASSESSMENT",
    "role → its own axis only\nrating 0–5 + confidence, rationale", PURPLE, PURPLE_L)
ent(28.0, 3.0, 23.0, 13.0, "WORKFLOW STATE",
    "stage, owner_role, owner\nentered_stage_at + transitions", PURPLE, "#FFFFFF")
ent(58.5, 62.0, 19.0, 23.0, "SCORE",
    "kind: attractiveness |\n          right_to_win\nvalue, components\ninputs — every component\nstored with what produced it\nweight_set", ORANGE_D, "#FFFFFF")
ent(58.5, 36.0, 19.0, 19.0, "DESCRIPTION",
    "sections, each with the signal\nids it was written from\nstripped[] — what evidence\nbinding removed, and why", PURPLE, PURPLE_L)
ent(58.5, 8.0, 19.0, 22.0, "MARKET SIZE",
    "method: bottom-up |\n          procurement-observed\nTAM / SAM / SOM · low·base·high\nfactors, coverage, caveats\nconfidence: observed|partial|\n                    modelled", GREEN, GREEN_L)
ent(81.0, 62.0, 17.5, 23.0, "COMPETITION",
    "level NONE · LOW ·\n        MEDIUM · HIGH\nnamed competitors,\neach with its basis\nand its evidence", TEAL, "#FFFFFF")
ent(81.0, 36.0, 17.5, 19.0, "BRIEF",
    "PDF on disk\ntopic_version\nweight_set, sizing_version\nprompt + model version", PURPLE, "#FFFFFF")
ent(81.0, 8.0, 17.5, 22.0, "REFERENCE SERIES",
    "Eurostat observations by\nindicator, NACE, geography,\nsize class and period\n\nnot signals — denominators", GREEN, GREEN_L, nfs=7.6)

# ---- relationships
rel(ax, [(21.0, 72.0), (28.0, 72.0)], "many", "many", color=TEAL,
    label="evidences", labelat=(24.5, 72.0), labeldy=1.7)
rel(ax, [(11.25, 60.0), (11.25, 53.0)], "many", "one", color=GREY_D,
    label="grouped into", labelat=(11.25, 56.5), labeldx=11.0, labeldy=0.0)
rel(ax, [(21.0, 47.0), (22.6, 47.0), (22.6, 78.0), (28.0, 78.0)], "many", "one",
    color=GREY_D, ls=(0, (3, 2)), label="seeds", labelat=(22.6, 63.0), labeldy=0.0)
rel(ax, [(39.5, 60.0), (39.5, 55.0)], "one", "many", color=BLUE,
    label="joins the portfolio via", labelat=(39.5, 57.5), labeldy=0.0)
rel(ax, [(28.0, 45.0), (24.6, 45.0), (24.6, 19.0), (21.0, 19.0)], "many", "one",
    color=BLUE, label="points at", labelat=(24.6, 32.0), labeldy=0.0)
rel(ax, [(51.0, 74.0), (58.5, 74.0)], "one", "many", color=ORANGE_D,
    label="is scored by", labelat=(54.7, 74.0), labeldy=1.7)
rel(ax, [(44.0, 85.0), (44.0, 88.5), (89.75, 88.5), (89.75, 85.0)], "one", "one",
    color=TEAL, label="is contested by", labelat=(67.0, 88.5), labeldy=1.6)
rel(ax, [(51.0, 63.0), (52.4, 63.0), (52.4, 25.5), (51.0, 25.5)], "one", "many",
    color=PURPLE, label="is assessed by", labelat=(52.4, 44.0), labeldy=0.0)
rel(ax, [(51.0, 65.0), (53.8, 65.0), (53.8, 9.5), (51.0, 9.5)], "one", "one",
    color=PURPLE, label="sits in", labelat=(53.8, 17.0), labeldy=0.0)
rel(ax, [(51.0, 67.0), (55.2, 67.0), (55.2, 19.0), (58.5, 19.0)], "one", "many",
    color=GREEN, label="is sized by", labelat=(55.2, 33.0), labeldy=0.0)
rel(ax, [(51.0, 69.0), (56.6, 69.0), (56.6, 45.0), (58.5, 45.0)], "one", "one",
    color=PURPLE, label="is described by", labelat=(56.6, 57.0), labeldy=0.0)
rel(ax, [(77.5, 45.0), (81.0, 45.0)], "one", "one", color=PURPLE,
    label="renders into", labelat=(79.25, 45.0), labeldy=1.7)
rel(ax, [(77.5, 19.0), (81.0, 19.0)], "many", "many", color=GREEN,
    label="reads", labelat=(79.25, 19.0), labeldy=1.7)
rel(ax, [(89.75, 55.0), (89.75, 62.0)], "one", "one", color=GREY, ls=(0, (3, 2)),
    label="quotes, never restates", labelat=(89.75, 58.5), labeldx=0.0, labeldy=0.0)

c.rule(1.6, x0=0.5, x1=99.5)
c.save(OUT + "fdd-10-domain.png")
