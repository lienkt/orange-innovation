import sys; sys.path.insert(0, ".")
from dg import *
from erd import Entity, rel
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"
STUB = [("id", "pk"), ("vertical / use_case / technology", "idx"), ("…  full definition in Figure 7", "")]

# ============================================ PART 2 — BUSINESS GRAPH & LINKS
c = Canvas(11.8, 6.4); ax = c.ax
c.title("Figure 8 — Physical data model, part 2:  the Orange Business Graph and link typing",
        "The join between an opportunity space and the portfolio. No language model writes to any of these tables — link assertion is a retrieval and rules problem.")

nod = Entity(ax, 1.0, 84.0, 22.0, "graph_nodes", [
    ("id", "pk"), ("node_type", ""), ("label", ""), ("attributes", ""),
    ("source", ""), ("as_of", "")], header_fc=BLUE, row_h=2.3, fs=6.5,
    note="node_type ∈ offer | reference | partner | certification\n| analyst_position | capability_pool | research_asset")

edg = Entity(ax, 1.0, 58.0, 22.0, "graph_edges", [
    ("id", "pk"), ("src", ""), ("dst", ""), ("edge_type", ""), ("strength", ""),
    ("as_of", ""), ("source", ""), ("attributes", "")], header_fc=BLUE, row_h=2.3, fs=6.5,
    note="edge_type ∈ ADDRESSES | DEMONSTRATES | PROVIDES\n| REQUIRED_BY | STAFFS | COVERS.  A partner's tier\nlives here, as an EDGE property, not a node property")

lpd = Entity(ax, 1.0, 24.0, 22.0, "link_pattern_decisions", [
    ("pattern", "pk"), ("decision", ""), ("curator", ""), ("reason", ""), ("decided_at", "")],
    header_fc=PURPLE, row_h=2.3, fs=6.5,
    note="pattern e.g. \"offer:live_objects|use_case:asset_tracking\"")

lnk = Entity(ax, 30.0, 80.0, 22.0, "opportunity_links", [
    ("id", "pk"), ("opportunity_id", "fk"), ("node_id", "fk"), ("link_type", ""),
    ("confidence", ""), ("evidence", ""), ("confirmed_by", ""), ("confirmed_at", ""),
    ("rejected", ""), ("rejection_reason", ""), ("created_at", ""), ("revalidated_at", "")],
    header_fc=BLUE, row_h=2.3, fs=6.5,
    note="UNIQUE(opportunity_id, node_id)\nlink_type ∈ L0 | L1 | L2 | L3 | L4 | SUP")

stub = Entity(ax, 62.0, 84.0, 22.0, "opportunity_spaces", STUB,
              header_fc=ORANGE, row_h=2.3, fs=6.5, body_fc="#FFFDF8")

rel(ax, [(23.0, 76.0), (26.5, 76.0), (26.5, 70.0), (30.0, 70.0)], "one", "many",
    color=BLUE, label="is linked from", labelat=(26.5, 76.0), labeldy=1.7, right_optional=True)
rel(ax, [(23.0, 72.0), (24.8, 72.0), (24.8, 50.0), (23.0, 50.0)], "one", "many", color=BLUE,
    label="src / dst", labelat=(24.8, 61.0), labeldy=0.0)
rel(ax, [(23.0, 19.0), (26.5, 19.0), (26.5, 56.0), (30.0, 56.0)], "one", "many",
    color=PURPLE, ls=(0, (3, 2)), label="adjudicates", labelat=(26.5, 38.0), labeldy=0.0,
    right_optional=True)
rel(ax, [(62.0, 78.0), (57.0, 78.0), (57.0, 74.0), (52.0, 74.0)], "one", "many",
    color=ORANGE, label="is linked by", labelat=(57.0, 78.0), labeldy=1.7, right_optional=True)

c.zone(62.0, 3.0, 37.0, 66.0, None, fc=GREY_LL, ec=GREY)
c.text(63.4, 66.0, "WHAT EACH LINK ROW HAS TO CARRY, AND WHY", fs=8.0, color=INK, weight="bold")
c.text(63.4, 61.2, "§4.5.4:  \"A link nobody can explain is worse than no link,\nbecause it will eventually appear in front of a customer.\"",
       fs=7.0, color=GREY_D, style="italic", ls_=1.6)
items = [
    ("evidence", "the join that justified this link, stored as JSON —\nwhich offer field matched which taxonomy value"),
    ("confidence", "how strong the match is, so a weak link can be shown\nas weak rather than shown as a link"),
    ("confirmed_by / confirmed_at", "LK-06: the FIRST occurrence of each pattern needs a named\nhuman. Later occurrences inherit the decision from\nlink_pattern_decisions, which is why that table exists"),
    ("rejected / rejection_reason", "a rejection is kept, not deleted — both confirmations and\nrejections are training data for the learned model that\nreplaces this rule set later"),
    ("revalidated_at", "LK-07: when an asset is withdrawn from the catalogue, every\ntopic that leaned on it has to be told"),
]
yy = 53.0
for name, body in items:
    c.text(63.4, yy, name, fs=7.0, color=BLUE, weight="bold")
    c.text(63.4, yy - 4.4, body, fs=6.4, color=INK, ls_=1.6)
    yy -= 10.2
c.save(OUT + "ta-08-erd-graph.png")


# ============================================ PART 3 — SIZING, COMPETITION, OUTPUTS
c = Canvas(12.2, 6.6); ax = c.ax
c.title("Figure 9 — Physical data model, part 3:  market sizing, competition and generated outputs",
        "Reference data is deliberately NOT in the signals table. No figure in market_sizes was produced by a language model.")

rs = Entity(ax, 1.0, 84.0, 21.0, "reference_series", [
    ("id", "pk"), ("dataset", ""), ("publisher", ""), ("label", ""), ("url", ""),
    ("licence", ""), ("source_updated", ""), ("fetched_at", ""), ("rows", ""), ("notes", "")],
    header_fc=GREEN, row_h=2.25, fs=6.5)

ro = Entity(ax, 1.0, 52.0, 21.0, "reference_observations", [
    ("series_id", "pkfk"), ("indicator", "pk"), ("nace", "pk"), ("geo", "pk"),
    ("size_class", "pk"), ("period", "pk"), ("value", ""), ("unit", "")],
    header_fc=GREEN, row_h=2.25, fs=6.5,
    note="56,385 rows. An annual statistical series has no publisher\ndiversity, no momentum and no relevance — pushing it through\nthe signal store would corrupt every component that counts\nattached signals while adding nothing to discovery")

ms = Entity(ax, 27.0, 84.0, 22.0, "market_sizes", [
    ("id", "pk"), ("opportunity_id", "fk"), ("computed_at", ""), ("method", ""),
    ("currency", ""), ("tam_low · tam_base · tam_high", ""),
    ("sam_low · sam_base · sam_high", ""), ("som_low · som_base · som_high", ""),
    ("confidence", ""), ("factors", ""), ("coverage", ""), ("caveats", ""),
    ("sizing_version", ""), ("pipeline_version", "")],
    header_fc=GREEN, row_h=2.25, fs=6.5,
    note="factors holds every input with its source and date, so\nany figure can be re-derived. sizing_version travels with\nthe row for the same reason weight_set does: sizes\ncomputed under different assumptions are not comparable")

stub = Entity(ax, 55.0, 84.0, 21.0, "opportunity_spaces", STUB,
              header_fc=ORANGE, row_h=2.3, fs=6.5, body_fc="#FFFDF8")

tc = Entity(ax, 55.0, 66.0, 21.0, "topic_competition", [
    ("opportunity_id", "pkfk"), ("computed_at", ""), ("level", ""), ("score", ""),
    ("competitors", ""), ("inputs", ""), ("register_version", ""), ("pipeline_version", "")],
    header_fc=TEAL, row_h=2.25, fs=6.5,
    note="competitors stores the NAMED list with the evidence\nfor each entry, so the level can be re-derived")

td = Entity(ax, 55.0, 36.0, 21.0, "topic_descriptions", [
    ("opportunity_id", "pkfk"), ("generated_at", ""), ("topic_version", ""),
    ("sections", ""), ("stripped", ""), ("prompt_version", ""), ("model_version", ""),
    ("pipeline_version", "")], header_fc=PURPLE, row_h=2.25, fs=6.5,
    note="topic_version makes staleness detectable: a topic\nthat has moved on is flagged, not left to mislead")

tb = Entity(ax, 81.0, 66.0, 18.0, "topic_briefs", [
    ("opportunity_id", "pkfk"), ("generated_at", ""), ("topic_version", ""), ("path", ""),
    ("filename", ""), ("bytes", ""), ("content_hash", ""), ("description_at", ""),
    ("market_size_at", ""), ("weight_set", ""), ("sizing_version", ""),
    ("prompt_version", ""), ("model_version", ""), ("pipeline_version", "")],
    header_fc=PURPLE, row_h=2.25, fs=6.5,
    note="DR-08 keeps the PDF blob out of the row —\nthe file lives on disk and the row points at it")

rel(ax, [(11.5, rs.y), (11.5, 52.0)], "one", "many", color=GREEN,
    label="observations", labelat=(11.5, 55.5), labeldx=10.0, labeldy=0.0)
rel(ax, [(22.0, 44.0), (24.5, 44.0), (24.5, 62.0), (27.0, 62.0)], "many", "many",
    color=GREEN, ls=(0, (3, 2)), label="read by the sizing engine", labelat=(24.5, 53.0), labeldy=0.0)
rel(ax, [(55.0, 78.0), (52.0, 78.0), (52.0, 74.0), (49.0, 74.0)], "one", "many",
    color=GREEN, label="is sized by", labelat=(52.0, 78.0), labeldy=1.7, right_optional=True)
rel(ax, [(65.5, stub.y), (65.5, 66.0)], "one", "one", color=TEAL, label="", labelat=None)
rel(ax, [(65.5, tc.y), (65.5, 36.0)], "one", "one", color=PURPLE, label="", labelat=None)
rel(ax, [(76.0, 62.0), (78.5, 62.0), (78.5, 60.0), (81.0, 60.0)], "one", "one",
    color=PURPLE, label="", labelat=None)
rel(ax, [(76.0, 26.0), (78.5, 26.0), (78.5, 38.0), (81.0, 38.0)], "one", "one",
    color=PURPLE, ls=(0, (3, 2)), label="renders", labelat=(78.5, 32.0), labeldy=0.0)
rel(ax, [(38.0, ms.y), (38.0, 6.0), (90.0, 6.0), (90.0, tb.y)], "one", "one",
    color=GREEN, ls=(0, (3, 2)), label="market_size_at — the brief records which sizing run it printed",
    labelat=(64.0, 6.0), labeldy=1.8)
c.save(OUT + "ta-09-erd-outputs.png")


# ============================================ PART 4 — COLLABORATION & FEEDBACK
c = Canvas(11.8, 5.8); ax = c.ax
c.title("Figure 10 — Physical data model, part 4:  collaboration, conviction and feedback",
        "What the organisation contributes, recorded so that it adjusts the ordering of a list without ever entering a published score.")

wfs = Entity(ax, 1.0, 84.0, 21.0, "workflow_state", [
    ("opportunity_id", "pkfk"), ("stage", ""), ("owner_role", ""), ("owner", ""),
    ("entered_stage_at", ""), ("updated_at", ""), ("note", "")],
    header_fc=PURPLE, row_h=2.3, fs=6.5,
    note="one row per topic — the current position")

wft = Entity(ax, 1.0, 56.0, 21.0, "workflow_transitions", [
    ("id", "pk"), ("opportunity_id", "fk"), ("from_stage", ""), ("to_stage", ""),
    ("actor", ""), ("actor_role", ""), ("reason", ""), ("created_at", "")],
    header_fc=PURPLE, row_h=2.3, fs=6.5,
    note="every move is timestamped, so age-in-stage is\nqueryable and a stalled card is flagged rather\nthan left for someone to notice")

stub = Entity(ax, 28.0, 84.0, 21.0, "opportunity_spaces", STUB,
              header_fc=ORANGE, row_h=2.3, fs=6.5, body_fc="#FFFDF8")

asm = Entity(ax, 28.0, 68.0, 21.0, "assessments", [
    ("id", "pk"), ("opportunity_id", "fk"), ("role", ""), ("axis", ""), ("rating", ""),
    ("confidence", ""), ("rationale", ""), ("author", ""), ("created_at", ""),
    ("weight_set", ""), ("superseded", "")], header_fc=PURPLE, row_h=2.3, fs=6.5,
    note="role → axis is fixed: strategist → strategic_fit,\nsales → customer_demand, presales → deliverability")

fdb = Entity(ax, 54.0, 84.0, 22.0, "feedback", [
    ("id", "pk"), ("created_at", ""), ("role", ""), ("kind", ""),
    ("opportunity_id", "fk"), ("other_opportunity_id", "fk"), ("verdict", ""),
    ("reason", ""), ("exposure_context", "")], header_fc=GOLD, row_h=2.3, fs=6.5,
    note="kind ∈ rating | comparison | override | engagement")

isg = Entity(ax, 79.0, 84.0, 20.0, "internal_signals", [
    ("id", "pk"), ("created_at", ""), ("author", ""), ("kind", ""), ("title", ""),
    ("body", ""), ("vertical", ""), ("geographies", ""), ("account_hint", ""),
    ("moderated", ""), ("signal_id", "fk")], header_fc=TEAL, row_h=2.3, fs=6.5,
    note="kind ∈ customer_conversation | rfp_theme | lost_deal")

rel(ax, [(28.0, 80.0), (25.0, 80.0), (25.0, 78.0), (22.0, 78.0)], "one", "one",
    color=PURPLE, label="sits in", labelat=(25.0, 80.0), labeldy=1.7)
rel(ax, [(11.5, wfs.y), (11.5, 56.0)], "one", "many", color=PURPLE,
    label="history", labelat=(11.5, 59.4), labeldx=7.0, labeldy=0.0)
rel(ax, [(38.5, stub.y), (38.5, 68.0)], "one", "many", color=PURPLE,
    label="is assessed by", labelat=(38.5, 71.5), labeldx=12.0, labeldy=0.0)
rel(ax, [(49.0, 82.0), (51.5, 82.0), (51.5, 76.0), (54.0, 76.0)], "one", "many",
    color=GOLD, label="draws", labelat=(51.5, 82.0), labeldy=1.7, right_optional=True)
c.text(89.0, 50.0, "signal_id → signals.id  (Figure 7):  a moderated internal item\nbecomes a first-class signal and is scored like any other.",
       fs=6.4, color=TEAL, ha="center", ls_=1.6)

c.zone(1.0, 2.0, 47.0, 24.0, None, fc=GREEN_L, ec=GREEN)
c.text(2.4, 23.0, "THE LINE THIS DATA IS NOT ALLOWED TO CROSS", fs=8.0, color=GREEN, weight="bold")
ax.text(2.4, 20.0, "Assessments aggregate into CONVICTION, which enters the per-role ranking\n"
        "function at weight 0.25 and nothing else. SC-12 forbids collapsing the two published\n"
        "scores; SC-14 says internal data adjusts but does not replace external discovery.\n"
        "Every published number therefore stays reproducible from evidence alone, and an\n"
        "unrated topic sits neutral rather than last.", fontsize=6.7, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)

c.zone(52.0, 2.0, 47.0, 24.0, None, fc=GOLD_L, ec=GOLD)
c.text(53.4, 23.0, "WHY feedback STORES THE EXPOSURE CONTEXT", fs=8.0, color=GOLD, weight="bold")
ax.text(53.4, 20.0, "§4.7.6: engagement has to be weighted by the inverse of the probability that the topic\n"
        "was SHOWN. A topic ranked first gets clicked because it was ranked first. So the row\n"
        "records the rank, the view, the active filters and whether it came from the randomised\n"
        "exploration slot — without which the feedback loop would simply train the radar to\n"
        "agree with itself.", fontsize=6.7, color=INK, ha="left", va="top", linespacing=1.7, zorder=8)
c.save(OUT + "ta-10-erd-collab.png")
