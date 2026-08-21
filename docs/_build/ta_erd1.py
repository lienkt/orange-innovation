import sys; sys.path.insert(0, ".")
from dg import *
from erd import Entity, rel, erd_key
OUT = "/Users/nstephane/Dev/AI_Data_Science_training/orange/docs/diagrams/"

c = Canvas(12.4, 8.2)
ax = c.ax
c.title("Figure 7 — Physical data model, part 1:  discovery, opportunity spaces and scores",
        "SQLite. PK = primary key · FK = foreign key · U = participates in a unique index. Column order follows src/radar/db.py, which carries data requirements DR-01…DR-15 directly.")

raw = Entity(ax, 1.0, 84.0, 20.0, "raw_items", [
    ("id", "pk"), ("source_id", ""), ("url", ""), ("fetched_at", ""),
    ("payload", ""), ("content_hash", "")],
    header_fc=GREY_D, row_h=2.0, fs=6.4,
    note="the replay archive — retained so a past date can be\nre-run without re-fetching (DR-14, FR-35)")

sig = Entity(ax, 26.0, 90.0, 23.0, "signals", [
    ("id", "pk"), ("source_id", ""), ("publisher", ""), ("title", ""), ("url", "idx"),
    ("published_at", ""), ("published_at_inferred", ""), ("ingested_at", ""),
    ("language", ""), ("geographies", ""), ("signal_type", ""),
    ("signal_type_confidence", ""), ("tier", ""), ("extract", ""), ("relevance", ""),
    ("relevance_reason", ""), ("cluster_id", "fk"), ("embedding", ""),
    ("raw_item_id", "fk"), ("attributes", ""), ("pipeline_version", ""),
    ("prompt_version", ""), ("model_version", "")],
    header_fc=TEAL, row_h=1.95, fs=6.3)

clu = Entity(ax, 1.0, 52.0, 20.0, "clusters", [
    ("id", "pk"), ("label", ""), ("keyphrases", ""), ("size", ""),
    ("created_at", ""), ("refresh_id", "")],
    header_fc=GREY_D, row_h=2.0, fs=6.4)

osp = Entity(ax, 54.0, 90.0, 22.0, "opportunity_spaces", [
    ("id", "pk"), ("version", ""), ("vertical", "idx"), ("use_case", "idx"),
    ("technology", "idx"), ("statement", ""), ("domains", ""), ("personas", ""),
    ("geographies", ""), ("state", ""), ("state_reason", ""), ("state_changed_at", ""),
    ("horizon", ""), ("horizon_basis", ""), ("horizon_anchor_date", ""),
    ("why_hot", ""), ("next_actions", ""), ("critic_score", ""), ("critic_notes", ""),
    ("first_seen", ""), ("last_refresh", ""), ("pipeline_version", ""),
    ("prompt_version", ""), ("model_version", ""), ("merged_into", "fk")],
    header_fc=ORANGE, row_h=1.95, fs=6.3)

osig = Entity(ax, 26.0, 36.0, 23.0, "opportunity_signals", [
    ("opportunity_id", "pkfk"), ("signal_id", "pkfk"), ("attached_at", ""), ("refresh_id", "")],
    header_fc=TEAL, row_h=2.0, fs=6.4,
    note="associative table — the row records WHICH refresh first attached\neach signal, so momentum is the honest trajectory of accretion")

sco = Entity(ax, 80.0, 90.0, 19.0, "scores", [
    ("id", "pk"), ("opportunity_id", "fk"), ("computed_at", ""), ("refresh_id", ""),
    ("kind", ""), ("score", ""), ("components", ""), ("inputs", ""),
    ("weight_set", ""), ("pipeline_version", ""), ("model_version", "")],
    header_fc=ORANGE_D, row_h=2.0, fs=6.4,
    note="DR-05 — every component is stored\nwith the inputs that produced it")

rfr = Entity(ax, 80.0, 55.0, 19.0, "refreshes", [
    ("id", "pk"), ("started_at", ""), ("finished_at", ""), ("reference_date", ""),
    ("is_replay", ""), ("pipeline_version", ""), ("weight_set", ""), ("stats", ""), ("notes", "")],
    header_fc=GREY_D, row_h=2.0, fs=6.4,
    note="reference_date drives the leakage control: every\nconnector rejects anything published after it")

# --- relationships
rel(ax, [(21.0, 76.0), (23.5, 76.0), (23.5, 54.0), (26.0, 54.0)], "one", "many",
    color=GREY_D, label="archives", labelat=(23.5, 66.0), labeldy=0.0, right_optional=True)
rel(ax, [(21.0, 46.0), (23.5, 46.0), (23.5, 50.0), (26.0, 50.0)], "one", "many",
    color=GREY_D, label="clusters", labelat=(23.9, 46.0), labeldy=1.6, right_optional=True)
rel(ax, [(37.5, sig.y), (37.5, 36.0)], "one", "many", color=TEAL,
    label="attaches through", labelat=(37.5, 39.0), labeldx=12.0, labeldy=0.0)
rel(ax, [(65.0, osp.y), (65.0, 30.5), (49.0, 30.5)], "one", "many", color=ORANGE,
    label="carries", labelat=(57.0, 30.5), labeldy=1.6)
rel(ax, [(76.0, 78.0), (80.0, 78.0)], "one", "many", color=ORANGE_D,
    label="is scored by", labelat=(78.0, 78.0), labeldy=1.7)
rel(ax, [(76.0, 52.0), (78.0, 52.0), (78.0, 45.0), (80.0, 45.0)], "many", "one",
    color=GREY_D, ls=(0, (3, 2)), label="last_refresh", labelat=(78.0, 48.5), labeldy=0.0)
rel(ax, [(58.0, osp.y), (58.0, 33.5), (52.0, 33.5), (52.0, 44.0), (54.0, 44.0)], "many", "one",
    color=ORANGE, label="merged_into → id   (a duplicate points at its survivor)",
    labelat=(66.0, 33.5), labeldy=1.6, left_optional=True)

erd_key(ax, 71.0, 21.0)
c.text(1.0, 17.4, "TWO IDENTITY RULES DO MOST OF THE WORK", fs=8.0, color=INK, weight="bold")
c.text(1.0, 12.6, "idx_signals_url — a partial UNIQUE index on signals(url) where url IS NOT NULL. Syndication collapses to one\n"
                  "item, so five outlets carrying the same wire story cannot inflate publisher diversity.", fs=6.7, color=GREY_D, ls_=1.6)
c.text(1.0, 5.6, "idx_os_triple — UNIQUE(vertical, use_case, technology) WHERE merged_into IS NULL. Canonical identity, so a\n"
                 "recurring topic is UPDATED rather than recreated: new signals attach, the score is recomputed, the previous score is\n"
                 "retained. This is what makes momentum measurable, and §4.4.5 calls it the requirement most often missed in a first build.",
       fs=6.7, color=GREY_D, ls_=1.6)
c.save(OUT + "ta-07-erd-core.png")
