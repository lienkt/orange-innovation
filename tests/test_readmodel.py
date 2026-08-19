"""Role-mode ranking, filtering and serving guarantees (FR-13, FR-21, FR-31, AC-04/05)."""

from __future__ import annotations

import pytest

from radar.config import get_config
from radar.readmodel import SORTS, ReadModel, _for_list, _matches, _sorted


@pytest.fixture(scope="module")
def cfg():
    return get_config()


def topic(topic_id: str, **overrides):
    base = {
        "id": topic_id,
        "triple": {"vertical": "manufacturing", "use_case": "predictive_maintenance",
                   "technology": "machine_learning"},
        "labels": {"vertical": "Manufacturing", "use_case": "Predictive maintenance",
                   "technology": "Machine learning"},
        "statement": "Predictive maintenance for rotating equipment in chemical plants.",
        "domains": ["ox_smart_industries"],
        "personas": ["coo_production"],
        "geographies": ["FR"],
        "state": "active",
        "horizon": "next",
        "why_hot": [],
        "next_actions": {},
        "attractiveness": {"score": 70.0, "components": {"novelty_momentum": 60.0}, "weight_set": "w"},
        "right_to_win": {"score": 50.0, "components": {}, "weight_set": "w"},
        "portfolio_distance": 0,
        "link_types": ["L0"],
        "links": [{"node_type": "reference", "link_type": "SUP"}],
        "evidence_gap_warning": False,
        "signal_count": 5,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# FR-31 — role-mode filtering is driven by portfolio distance
# ---------------------------------------------------------------------------

def test_sales_never_sees_white_space(cfg):
    """§4.5.3: a high-attractiveness L4 topic is "precisely the thing a
    salesperson should never be shown"."""
    read = ReadModel(cfg, db=None)
    white_space = topic("OS-WS", link_types=["L4"], portfolio_distance=4,
                        attractiveness={"score": 95.0, "components": {}, "weight_set": "w"})
    assert read.rank([white_space], "sales") == []
    # ...but it is exactly what the strategist is looking for.
    assert len(read.rank([white_space], "strategist")) == 1


def test_sales_requires_a_published_reference_in_the_vertical(cfg):
    """§4.5.3 makes the sales acceptance criterion computable."""
    read = ReadModel(cfg, db=None)
    no_reference = topic("OS-NR", links=[{"node_type": "offer", "link_type": "L0"}])
    assert read.rank([no_reference], "sales") == []
    with_reference = topic("OS-R", links=[
        {"node_type": "offer", "link_type": "L0"},
        {"node_type": "reference", "link_type": "SUP"},
    ])
    assert len(read.rank([with_reference], "sales")) == 1


def test_sales_excludes_evidence_gap_topics(cfg):
    """SC-13 / §2.7: a radar that ignores the reference asymmetry hands a
    salesperson a topic with no proof point behind it."""
    read = ReadModel(cfg, db=None)
    gapped = topic("OS-GAP", evidence_gap_warning=True,
                   link_types=["L0", "L2"], portfolio_distance=0)
    assert read.rank([gapped], "sales") == []
    # The strategist still sees it — the gap is information, not a disqualifier.
    assert len(read.rank([gapped], "strategist")) == 1


def test_a_directly_sellable_topic_is_not_on_the_strategist_agenda(cfg):
    """§4.5.3: sales sees L0-L1, presales L0-L2, strategy L1-L4.

    A topic an existing offer already addresses needs no study, so it does not
    belong in the "where do we invest next quarter" view.
    """
    read = ReadModel(cfg, db=None)
    sellable = topic("OS-L0", link_types=["L0"], portfolio_distance=0)
    assert read.rank([sellable], "strategist") == []
    assert len(read.rank([sellable], "sales")) == 1
    assert len(read.rank([sellable], "presales")) == 1


def test_supporting_links_alone_do_not_qualify_a_topic_for_sales(cfg):
    """A certification is not a delivery path — see graph.SUPPORTING."""
    read = ReadModel(cfg, db=None)
    only_supporting = topic("OS-SUP", link_types=["SUP"], portfolio_distance=4,
                            links=[{"node_type": "certification", "link_type": "SUP"},
                                   {"node_type": "reference", "link_type": "SUP"}])
    assert read.rank([only_supporting], "sales") == []


# ---------------------------------------------------------------------------
# FR-13 / §3.2 — each role has a DISTINCT ranking function
# ---------------------------------------------------------------------------

def test_roles_rank_the_same_topics_differently(cfg):
    """§3.2: "The same topic can be excellent for a strategist and useless for a
    salesperson. The system must express this as different default ranking
    functions per role mode, not as a single score with different filters."
    """
    read = ReadModel(cfg, db=None)
    links = [{"node_type": "offer", "link_type": "L0"}, {"node_type": "reference", "link_type": "SUP"}]
    early_and_big = topic(
        "OS-EARLY", link_types=["L0", "L2"], portfolio_distance=2, links=links,
        attractiveness={"score": 90.0, "components": {"novelty_momentum": 95.0}, "weight_set": "w"},
        right_to_win={"score": 20.0, "components": {"reference_density": 10.0}, "weight_set": "w"},
    )
    sellable_now = topic(
        "OS-SELL", link_types=["L0"], portfolio_distance=0, links=links,
        attractiveness={"score": 55.0, "components": {"novelty_momentum": 30.0}, "weight_set": "w"},
        right_to_win={"score": 85.0, "components": {"reference_density": 90.0,
                                                    "external_validation": 100.0}, "weight_set": "w"},
    )
    topics = [early_and_big, sellable_now]
    # Both carry an L1 link so both are visible to every role; only the ranking
    # function differs, which is the point of §3.2.
    for t in topics:
        t["link_types"] = sorted(set(t["link_types"]) | {"L1"})
    assert read.rank(list(topics), "strategist")[0]["id"] == "OS-EARLY"
    assert read.rank(list(topics), "sales")[0]["id"] == "OS-SELL"


def test_ranking_is_explained_not_just_produced(cfg):
    """NFR-01: if a user cannot explain why a topic is ranked where it is, the
    scoring is not good enough (§3.8)."""
    read = ReadModel(cfg, db=None)
    ranked = read.rank([topic("OS-1", link_types=["L2"], portfolio_distance=2)], "strategist")
    explanation = ranked[0]["rank_explanation"]
    assert explanation
    for term, detail in explanation.items():
        assert {"value", "weight", "contribution"} <= set(detail), term


def test_low_right_to_win_is_a_flag_for_the_strategist_not_a_penalty(cfg):
    """Table 33: for the strategist, "low right-to-win is not a penalty but a flag"."""
    read = ReadModel(cfg, db=None)
    weak = topic("OS-WEAK", link_types=["L3"], portfolio_distance=3,
                 right_to_win={"score": 10.0, "components": {}, "weight_set": "w"})
    ranked = read.rank([weak], "strategist")
    assert ranked[0].get("strategist_flag")
    assert cfg.role_mode("strategist")["ranking"]["right_to_win"] == 0.0


# ---------------------------------------------------------------------------
# AC-04 / FR-12 — multi-select filtering
# ---------------------------------------------------------------------------

def test_all_four_filter_dimensions_apply():
    t = topic("OS-1")
    assert _matches(t, {"vertical": ["manufacturing"]})
    assert not _matches(t, {"vertical": ["retail"]})
    assert _matches(t, {"domain": ["ox_smart_industries"]})
    assert not _matches(t, {"domain": ["cloud"]})
    assert _matches(t, {"persona": ["coo_production"]})
    assert not _matches(t, {"persona": ["ciso"]})
    assert _matches(t, {"geography": ["FR"]})
    assert not _matches(t, {"geography": ["JP"]})


def test_multi_select_is_a_union_within_a_dimension():
    t = topic("OS-1")
    assert _matches(t, {"vertical": ["retail", "manufacturing"]})


def test_dimensions_combine_as_an_intersection():
    t = topic("OS-1")
    assert _matches(t, {"vertical": ["manufacturing"], "domain": ["ox_smart_industries"]})
    assert not _matches(t, {"vertical": ["manufacturing"], "domain": ["cloud"]})


def test_a_topic_without_geography_is_global_not_excluded():
    t = topic("OS-1", geographies=[])
    assert _matches(t, {"geography": ["JP"]})


def test_free_text_search_covers_statement_and_claims():
    t = topic("OS-1", why_hot=[{"claim": "A regulator mandated continuous monitoring.", "signals": ["SIG-1"]}])
    assert _matches(t, {"q": "rotating equipment"})
    assert _matches(t, {"q": "regulator mandated"})
    assert not _matches(t, {"q": "quantum"})


# ---------------------------------------------------------------------------
# Sorting and the new filter dimensions (§4.3.3, §4.3.4)
# ---------------------------------------------------------------------------

def sized(topic_id: str, sam: float | None, level: str | None = "medium", **overrides):
    return topic(
        topic_id,
        market_size_summary=({"method": "bottom_up_adoption", "sam_base": sam,
                              "tam_base": (sam or 0) * 2, "confidence": "observed"}
                             if sam is not None else None),
        competition=({"level": level, "level_label": level.title()} if level else None),
        **overrides,
    )


def test_unsized_topics_sort_last_not_first():
    """§4.3.4 leaves a topic unsized on purpose when nothing attributable exists.

    An unsized topic is not a topic worth nothing, so it must never lead a
    "largest market" list by being read as zero — or as infinity.
    """
    ordered = _sorted([sized("OS001", None), sized("OS002", 5e9), sized("OS003", 1e6)], "market_size")
    assert [t["id"] for t in ordered] == ["OS002", "OS003", "OS001"]


def test_competition_sort_puts_the_open_field_first():
    """"Where would we not be fighting four incumbents" is the question this answers."""
    ordered = _sorted(
        [sized("OS001", 1e6, "high"), sized("OS002", 1e6, "none"), sized("OS003", 1e6, "medium")],
        "competition",
    )
    assert [t["id"] for t in ordered] == ["OS002", "OS003", "OS001"]


def test_sorting_never_widens_what_a_role_may_see(cfg):
    """FR-13 and §4.5.3: sort re-orders the eligible set, it does not replace it.

    A salesperson sorting by market size must still be unable to reach white
    space — the largest markets in the radar are exactly the ones with no proof
    point behind them, so this is the failure mode that matters.
    """
    read = ReadModel(cfg, db=None)
    topics = [
        sized("OS001", 9e9, "low", portfolio_distance=4, link_types=["L4"], links=[]),
        sized("OS002", 1e6, "low"),
    ]
    ranked = read.rank(topics, "sales")
    ordered = _sorted(ranked, "market_size")
    assert [t["id"] for t in ordered] == ["OS002"]


@pytest.mark.parametrize("sort", sorted(SORTS))
def test_every_advertised_sort_is_total_and_stable(sort):
    """A sort the API advertises must order every topic, including empty ones."""
    topics = [sized("OS001", None, None, attractiveness=None, right_to_win=None,
                    signal_count=0, last_refresh="2026-01-01"),
              sized("OS002", 2e6, "high", last_refresh="2026-08-01"),
              sized("OS003", 1e6, "low", last_refresh="2026-05-01")]
    ordered = _sorted(topics, sort)
    assert sorted(t["id"] for t in ordered) == ["OS001", "OS002", "OS003"]


def test_competition_and_brief_filters():
    """§4.3.3 / FR-18 made two new facts filterable."""
    crowded = sized("OS001", 1e6, "high", has_brief=True)
    open_field = sized("OS002", 1e6, "low", has_brief=False)
    assert _matches(open_field, {"competition": ["low", "none"]})
    assert not _matches(crowded, {"competition": ["low", "none"]})
    assert _matches(crowded, {"has_brief": True})
    assert not _matches(open_field, {"has_brief": True})


# ---------------------------------------------------------------------------
# The list projection (payload discipline)
# ---------------------------------------------------------------------------

def test_list_rows_drop_detail_only_fields_but_keep_what_they_render():
    """§4.9 puts the decomposition on the topic page; the list ships what it shows."""
    row = _for_list(topic(
        "OS001",
        why_hot=[{"claim": "c", "signals": ["SIG-1"]}],
        next_actions={"sales": "do the thing"},
        rank_explanation={"attractiveness": {"value": 1, "weight": 1, "contribution": 1}},
        provenance={"pipeline_version": "0.1.0"},
        competition={"level": "high", "level_label": "High", "meaning": "crowded",
                     "competitors": [{"id": "x"}], "inputs": {"bands": {}}},
        conviction={"assessed": 1, "score": 60.0,
                    "axes": {"customer_demand": {"score": 60.0, "voices": [{"author": "a"}]}}},
    ))
    for dropped in ("links", "why_hot", "rank_explanation", "provenance"):
        assert dropped not in row
    # AC-03 keeps this one: the CLI list prints the role's next action, and
    # "every topic in every role mode renders a non-empty action" is a
    # requirement rather than a nicety.
    assert row["next_actions"]["sales"] == "do the thing"
    # ... and everything a row or a marker actually draws survives.
    for kept in ("id", "statement", "labels", "triple", "domains", "horizon", "state",
                 "attractiveness", "right_to_win", "portfolio_distance", "signal_count",
                 "evidence_gap_warning", "competition"):
        assert kept in row
    # The level survives; the roster does not.
    assert row["competition"]["level"] == "high"
    assert "competitors" not in row["competition"]
    assert "voices" not in row["conviction"]["axes"]["customer_demand"]
