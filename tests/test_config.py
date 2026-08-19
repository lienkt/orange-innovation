"""Configuration and controlled-vocabulary invariants (§3.3, LK-02, DR-12)."""

from __future__ import annotations

import pytest

from radar.config import Crosswalk, get_config


@pytest.fixture(scope="module")
def cfg():
    return get_config()


def test_config_validates_on_load(cfg):
    """Config.__init__ raises if any cross-reference is dangling.

    §4.5.2: crosswalk errors propagate silently into every downstream number,
    so a dangling id must be a startup failure rather than a runtime surprise.
    """
    assert cfg.weight_set
    assert cfg.pipeline_version


def test_vocabulary_sizes_meet_sprint_0_targets(cfg):
    """§3.3 sets 40-60 use cases and 25-40 technologies as the tractable target."""
    assert len(cfg.verticals) == 15, "the briefing fixes fifteen verticals (Table 7)"
    assert len(cfg.domains) == 6, "the briefing fixes six business domains"
    assert len(cfg.personas) == 9, "the briefing fixes nine target personas"
    assert len(cfg.signal_types) == 6, "the signal taxonomy has exactly six types (FR-03)"
    assert 40 <= len(cfg.use_cases) <= 60
    assert 25 <= len(cfg.technologies) <= 40


def test_attractiveness_weights_are_the_briefing_figures(cfg):
    """SC-01 indicative weighting, to be calibrated but not silently drifted."""
    weights = cfg.attractiveness_weights
    assert weights["market_signal_strength"] == pytest.approx(0.30)
    assert weights["source_diversity"] == pytest.approx(0.20)
    assert weights["evidence_quality"] == pytest.approx(0.20)
    assert weights["novelty_momentum"] == pytest.approx(0.15)
    assert weights["strategic_relevance"] == pytest.approx(0.15)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_horizontal_cpv_codes_carry_no_vertical_signal(cfg):
    """CPV 72 (IT services) is bought by every vertical and must not be attributed.

    This is the single most likely source of a silently wrong reference-density
    or procurement number (§4.5.2).
    """
    assert cfg.cpv_to_vertical.resolve(["72000000"]) == {}
    assert cfg.cpv_to_vertical.resolve(["48000000"]) == {}
    assert cfg.cpv_to_vertical.resolve(["64200000"]) == {}
    # ...but they do carry a use-case signal, which is what makes a tender a
    # buying signal for a specific opportunity space.
    assert "identity_access_management" in cfg.cpv_to_use_case.resolve(["72212730"])


def test_crosswalk_longest_prefix_wins(cfg):
    """Classification schemes are hierarchical; 72212730 beats 72."""
    specific = cfg.cpv_to_use_case.resolve(["72212730"])
    assert specific == {"identity_access_management": pytest.approx(0.9)}


def test_crosswalk_confidence_is_carried_not_discarded(cfg):
    rows = cfg.cpv_to_vertical.lookup("33110000")
    assert rows, "expected a mapping for imaging equipment"
    assert all(0.0 < r.confidence <= 1.0 for r in rows)
    assert all(r.owner for r in rows), "DR-12 requires a named owner per row"


def test_story_labels_reconcile_onto_verticals(cfg):
    """LK-03: 12 published industry labels onto 15 radar verticals."""
    split = cfg.vertical_for_story_label("Resources and energy")
    assert set(split) == {"energy", "natural_resources"}
    assert sum(split.values()) == pytest.approx(1.0)
    assert cfg.vertical_for_story_label("Manufacturing") == {"manufacturing": 1.0}


def test_privileged_verticals_are_defense_and_health(cfg):
    """§2.2: both divisions were created in 2025 and carry positive weight."""
    privileged = cfg.strategy["privileged_verticals"]
    assert privileged.get("defense") == 1.0
    assert privileged.get("healthcare") == 1.0


def test_vocabulary_is_closed_and_resolvable(cfg):
    """§4.4.2: the model may only emit values from these lists."""
    assert cfg.technologies.resolve("Private 5G / LTE") == "private_5g"
    assert cfg.technologies.resolve("private cellular") == "private_5g"   # synonym
    assert cfg.technologies.resolve("quantum blockchain mesh") is None    # invented


def test_every_use_case_declares_a_known_domain(cfg):
    for use_case in cfg.use_cases:
        domains = use_case.get("domains") or []
        assert domains, f"{use_case.id} declares no domain — it cannot be routed to an offer owner"
        assert all(d in cfg.domains for d in domains)


def test_enabled_sources_have_a_terms_of_use_position(cfg):
    """NFR-07 / DR-08: ingestion respects source terms.

    `pending` is an acceptable value — it records a Sprint 0 action. A MISSING
    value is not, because it means nobody has looked.
    """
    for source in cfg.enabled_sources():
        assert source.get("terms_checked"), f"{source['id']} has no terms_checked position"
