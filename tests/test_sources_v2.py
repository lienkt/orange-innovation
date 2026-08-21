"""Second-tranche source work: the multilingual gate, the taxonomy query grid,
redirect unwrapping, TED award parsing, OCDS, and internal intake.

Each test here pins a specific failure the first live corpus exhibited, so the
names say what broke rather than what the code does.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.config import get_config
from radar.connectors.base import unwrap_redirect
from radar.connectors.news import _slices
from radar.connectors.procurement import _names, _ocds_cpv, _pick_non_english
from radar.pipeline.query_grid import build_cpv_groups, build_queries, expand_source_params, taxonomy_terms


# ---------------------------------------------------------------------------
# FR-28 — the English-only relevance gate deleted the French corpus
# ---------------------------------------------------------------------------

def test_lexicon_covers_every_declared_language():
    cfg = get_config()
    assert cfg.lexicon_languages, "no languages declared"
    for language in cfg.lexicon_languages:
        assert cfg.lexicon_terms([language]), f"no terms for {language!r}"


def test_lexicon_keys_are_real_vocabulary_ids():
    """A renamed use case would silently take its whole term set out of the gate."""
    cfg = get_config()
    known = set(cfg.use_cases.ids) | set(cfg.technologies.ids) | set(cfg.verticals.ids) | set(cfg.domains.ids)
    for vocab_id in cfg.lexicon["terms"]:
        assert vocab_id in known, f"lexicon key {vocab_id!r} is not a vocabulary id"


def test_french_text_now_passes_the_relevance_gate(tmp_path):
    """The exact failure: French signals averaged 0.06 relevance to English's 0.26."""
    from radar.db import Database
    from radar.pipeline.ingest import Ingestor

    cfg = get_config()
    ingestor = Ingestor(cfg, Database(tmp_path / "t.db"))
    french = "Déploiement d'un réseau 5G privé et supervision de la maintenance prédictive sur site industriel"
    score, hits = ingestor.keyword_relevance(french)
    assert score > 0.0, f"French text still scores zero — gated out before the model sees it ({hits})"


def test_dutch_and_german_procurement_language_is_matched():
    """TenderNed and CERT-Bund are pointless without these."""
    from radar.db import Database
    from radar.pipeline.ingest import Ingestor
    import tempfile, pathlib

    cfg = get_config()
    with tempfile.TemporaryDirectory() as tmp:
        ingestor = Ingestor(cfg, Database(pathlib.Path(tmp) / "t.db"))
        assert ingestor.keyword_relevance("Aanbesteding cyberbeveiliging en netwerk voor de gemeente")[0] > 0
        assert ingestor.keyword_relevance("Ausschreibung IT-Sicherheit und Campusnetz für die Fertigung")[0] > 0


# ---------------------------------------------------------------------------
# NFR-11 — the "taxonomy grid at runtime" that was 59 hand-written literals
# ---------------------------------------------------------------------------

def test_taxonomy_queries_are_generated_from_the_vocabulary():
    cfg = get_config()
    terms = taxonomy_terms(cfg, {"vocabularies": ["technologies"]})
    assert len(terms) > 20
    assert any("5g" in t.lower() for t in terms)


def test_generated_queries_use_the_connectors_own_syntax():
    cfg = get_config()
    queries = build_queries(cfg, {"vocabularies": ["technologies"], "template": 'all:"{term}"', "max_queries": 3})
    assert len(queries) == 3
    assert all(q.startswith('all:"') for q in queries)


def test_taxonomy_expansion_keeps_the_hand_written_queries():
    """A literal query encoding a boolean the vocabulary cannot express is not
    a duplicate, and deleting it would be a silent coverage regression."""
    cfg = get_config()
    source = {
        "id": "test",
        "params": {
            "queries": ['"NIS2" OR "DORA" AND compliance'],
            "queries_from_taxonomy": {"vocabularies": ["technologies"], "max_queries": 5},
        },
    }
    merged = expand_source_params(cfg, source)["params"]["queries"]
    assert merged[0] == '"NIS2" OR "DORA" AND compliance'
    assert len(merged) == 6


def test_expansion_does_not_mutate_the_shared_config_object():
    """Config is shared across the refresh and a replay expands it again."""
    cfg = get_config()
    source = {"id": "t", "params": {"queries_from_taxonomy": {"vocabularies": ["technologies"]}}}
    expand_source_params(cfg, source)
    assert "queries" not in source["params"]


def test_sources_without_a_taxonomy_spec_are_untouched():
    cfg = get_config()
    source = {"id": "t", "params": {"queries": ["one"]}}
    assert expand_source_params(cfg, source) is source


def test_cpv_groups_are_narrower_than_the_hand_written_roots():
    """72000000 matched 785,215 notices; a 20-notice sample of that is noise."""
    cfg = get_config()
    groups = build_cpv_groups(cfg, {"min_code_digits": 5})
    assert groups
    assert all(g["label"] in cfg.use_cases for g in groups)
    assert all(len(code) >= 5 for g in groups for code in g["cpv"])


# ---------------------------------------------------------------------------
# SC-03 / NFR-02 — Bing booked 76 items to one publisher behind a redirect
# ---------------------------------------------------------------------------

def test_bing_redirect_resolves_to_the_real_article():
    url = ("http://www.bing.com/news/apiclick.aspx?ref=FexRss&aid=&tid=6a8&url="
           "https%3a%2f%2fiottechnews.com%2fnews%2fit-ot-convergence%2f&c=88&mkt=nl-be")
    assert unwrap_redirect(url) == "https://iottechnews.com/news/it-ot-convergence/"


def test_a_plain_url_is_returned_unchanged():
    assert unwrap_redirect("https://example.com/a?b=c") == "https://example.com/a?b=c"
    assert unwrap_redirect("") == ""


def test_a_redirect_param_that_is_not_a_url_is_ignored():
    """Never turn a tracking token into a stored URL."""
    assert unwrap_redirect("https://x.test/go?url=not-a-url") == "https://x.test/go?url=not-a-url"


# ---------------------------------------------------------------------------
# §4.6 momentum — GDELT's 14-day memory made every slope an artefact
# ---------------------------------------------------------------------------

def test_gdelt_window_is_sliced_across_the_whole_period():
    slices = list(_slices(dt.date(2026, 8, 20), 60, 14))
    assert len(slices) == 5
    assert slices[0][1] == dt.date(2026, 8, 20), "most recent slice must come first"
    assert min(s for s, _ in slices) == dt.date(2026, 6, 21)


def test_slices_never_reach_past_the_reference_date():
    """FR-35: a replay must not see the future."""
    reference = dt.date(2026, 1, 15)
    assert all(end <= reference for _, end in _slices(reference, 90, 30))


# ---------------------------------------------------------------------------
# §4.3.3 — 1,691 award notices were parsed with the winner discarded
# ---------------------------------------------------------------------------

def test_ted_winner_names_are_deduplicated_across_lots():
    """`winner-name` repeats one entry per lot, so the same firm appears twice."""
    assert _names({"pol": ["SHIM-POL", "SPECTRO-LAB", "SPECTRO-LAB"]}) == ["SHIM-POL", "SPECTRO-LAB"]


def test_ted_winner_falls_back_to_any_language():
    assert _names({"deu": ["Schlagberger Haustechnik GmbH"]}) == ["Schlagberger Haustechnik GmbH"]


def test_ted_winner_handles_scalars_and_absence():
    assert _names("Acme Ltd") == ["Acme Ltd"]
    assert _names(None) == []
    assert _names({}) == []


def test_ted_local_title_is_picked_for_the_gate():
    language, title = _pick_non_english({"eng": "Ventilation works", "fra": "Travaux de ventilation"})
    assert (language, title) == ("fr", "Travaux de ventilation")


def test_ted_local_title_is_absent_when_only_english_exists():
    assert _pick_non_english({"eng": "Only English"}) == ("", "")
    assert _pick_non_english("a plain string") == ("", "")


# ---------------------------------------------------------------------------
# OCDS — CPV lives in a different place per publisher
# ---------------------------------------------------------------------------

def test_ocds_cpv_is_read_from_item_level_additional_classifications():
    """Find a Tender leaves tender.classification null and puts CPV on items."""
    tender = {"classification": None, "items": [
        {"additionalClassifications": [
            {"scheme": "CPV", "id": "71000000", "description": "Architectural"},
            {"scheme": "CPV", "id": "71300000"},
        ]}]}
    assert _ocds_cpv(tender) == ["71000000", "71300000"]


def test_ocds_cpv_ignores_other_classification_schemes():
    tender = {"classification": {"scheme": "UNSPSC", "id": "43230000"}}
    assert _ocds_cpv(tender) == []


def test_ocds_cpv_deduplicates_across_levels():
    tender = {"classification": {"scheme": "CPV", "id": "72000000"},
              "lots": [{"classification": {"scheme": "CPV", "id": "72000000"}}]}
    assert _ocds_cpv(tender) == ["72000000"]


# ---------------------------------------------------------------------------
# TED value floor — asymmetric on purpose
# ---------------------------------------------------------------------------

def _ted(params):
    from radar.connectors.base import HttpSession
    from radar.connectors.procurement import TedConnector
    return TedConnector({"id": "ted", "params": params}, HttpSession("test"))


def test_undisclosed_value_is_never_dropped_by_the_floor():
    """A third of TED discloses no value, and framework agreements least often —
    treating that as 'small' would delete the largest contracts in the corpus."""
    from radar.connectors.base import CollectedItem
    connector = _ted({"min_value_eur": 50000})
    item = CollectedItem(source_id="ted", url="u", title="t", published_at=None, extract="e")
    assert connector._below_value_floor(item) is False


def test_small_disclosed_contracts_are_dropped():
    from radar.connectors.base import CollectedItem
    connector = _ted({"min_value_eur": 50000})
    small = CollectedItem(source_id="ted", url="u", title="t", published_at=None, extract="e",
                          attributes={"total_value_eur": 4000})
    large = CollectedItem(source_id="ted", url="u", title="t", published_at=None, extract="e",
                          attributes={"total_value_eur": 900000})
    assert connector._below_value_floor(small) is True
    assert connector._below_value_floor(large) is False


def test_no_floor_configured_means_nothing_is_dropped():
    from radar.connectors.base import CollectedItem
    connector = _ted({})
    item = CollectedItem(source_id="ted", url="u", title="t", published_at=None, extract="e",
                         attributes={"total_value_eur": 1})
    assert connector._below_value_floor(item) is False


# ---------------------------------------------------------------------------
# §2.5 — internal_signals had a schema, no writer and zero rows
# ---------------------------------------------------------------------------

def test_internal_signal_is_inert_until_moderated(tmp_path):
    from radar.db import Database
    from radar import internal

    cfg = get_config()
    db = Database(tmp_path / "t.db")
    db.init_schema()
    internal_id = internal.record(db, author="tester", kind="rfp_theme",
                                  title="Segmentation appears in three RFPs", body="…")
    assert internal.promote(cfg, db)["promoted"] == 0, "unmoderated evidence must not score"
    assert [r["id"] for r in internal.pending(db)] == [internal_id]

    internal.moderate(db, internal_id)
    assert internal.promote(cfg, db)["promoted"] == 1
    assert internal.pending(db) == []


def test_promoted_internal_signal_carries_no_invented_url(tmp_path):
    """§4.4.4: inventing a URL to satisfy a schema is fabricated attribution."""
    from radar.db import Database
    from radar import internal

    cfg = get_config()
    db = Database(tmp_path / "t.db")
    db.init_schema()
    internal_id = internal.record(db, author="tester", kind="lost_deal", title="Lost on sovereignty",
                                  body="Incumbent won on data residency.", moderated=True)
    internal.promote(cfg, db)
    row = db.query("SELECT url, tier, signal_type FROM signals WHERE source_id='internal'")[0]
    assert row["url"] is None
    assert row["tier"] == 3, "a conversation is not an authoritative published record (§4.3.7)"
    assert row["signal_type"] == "market_move"
    assert db.query("SELECT signal_id FROM internal_signals WHERE id=?", (internal_id,))[0]["signal_id"]


def test_promotion_is_idempotent(tmp_path):
    from radar.db import Database
    from radar import internal

    cfg = get_config()
    db = Database(tmp_path / "t.db")
    db.init_schema()
    internal.record(db, author="t", kind="customer_conversation", title="A conversation",
                    body="body", moderated=True)
    internal.promote(cfg, db)
    assert internal.promote(cfg, db)["promoted"] == 0


def test_unknown_internal_kind_is_rejected(tmp_path):
    from radar.db import Database
    from radar import internal

    db = Database(tmp_path / "t.db")
    db.init_schema()
    with pytest.raises(ValueError, match="Unknown kind"):
        internal.record(db, author="t", kind="water_cooler", title="x", body="y")


# ---------------------------------------------------------------------------
# DR-04 — two feeds parsed as entirely undated and were silently rejected
# ---------------------------------------------------------------------------

def test_rfc822_two_digit_year_is_parsed():
    """CISA's advisory feed dates as 'Wed, 19 Aug 26'. Without this the whole
    feed is undated, and DR-04 rejects it — 30 advisories lost with no error."""
    from radar.connectors.base import parse_date
    assert parse_date("Wed, 19 Aug 26 12:00:00 +0000") == dt.date(2026, 8, 19)


def test_drupal_slash_date_is_parsed():
    """'Fri, 08/14/2026 - 16:01', emitted by several europa.eu site feeds."""
    from radar.connectors.base import parse_date
    assert parse_date("Fri, 08/14/2026 - 16:01") == dt.date(2026, 8, 14)


def test_a_four_digit_year_still_wins_over_the_two_digit_pattern():
    from radar.connectors.base import parse_date
    assert parse_date("Wed, 19 Aug 2026 12:00:00 +0000") == dt.date(2026, 8, 19)


# ---------------------------------------------------------------------------
# NFR-02 — a feed that puts markup in <title> also mangles <link>
# ---------------------------------------------------------------------------

def test_title_with_inline_markup_is_still_read():
    import xml.etree.ElementTree as ET
    from radar.connectors.news import _text
    item = ET.fromstring('<item><title><a href="/news/x">Real title</a></title></item>')
    assert _text(item, "title").strip() == "Real title"


def test_mangled_link_is_replaced_by_the_title_anchor():
    import xml.etree.ElementTree as ET
    from radar.connectors.news import _anchor_href, _looks_like_a_real_url
    item = ET.fromstring('<item><title><a href="/news/remit">REMIT Quarterly</a></title></item>')
    assert _anchor_href(item, "https://www.acer.europa.eu/rss.xml") == "https://www.acer.europa.eu/news/remit"
    assert _looks_like_a_real_url("https://www.acer.europa.eu/%3Ca%20href%3D%22/news/x%22") is False
    assert _looks_like_a_real_url("https://www.acer.europa.eu/news/x") is True


def test_a_healthy_link_is_never_replaced():
    import xml.etree.ElementTree as ET
    from radar.connectors.news import _anchor_href, _looks_like_a_real_url
    item = ET.fromstring('<item><title><a href="/wrong">T</a></title><link>https://good.test/a</link></item>')
    assert _looks_like_a_real_url("https://good.test/a") is True
    assert _anchor_href(item, "https://good.test/feed") == "https://good.test/wrong"


# ---------------------------------------------------------------------------
# NFR-04 — a malformed item aborted the whole stage after every source had run
# ---------------------------------------------------------------------------

def test_tenderned_link_object_is_reduced_to_its_href():
    """TenderNed returns {"href": ..., "title": "self"} where a URL belongs."""
    from radar.connectors.base import HttpSession
    from radar.connectors.procurement import TenderNedConnector

    connector = TenderNedConnector({"id": "tenderned", "params": {"max_pages": 1}}, HttpSession("test"))
    record = {
        "publicatieId": "436864",
        "publicatieDatum": "2026-08-20",
        "aanbestedingNaam": "Netwerk en telefonie voor de gemeente",
        "opdrachtBeschrijving": "Levering en beheer",
        "link": {"href": "https://www.tenderned.nl/aankondigingen/overzicht/436864", "title": "self"},
    }
    connector.get = lambda *a, **k: type("R", (), {  # noqa: ARG005
        "json": staticmethod(lambda: {"content": [record]})})()
    items = list(connector.collect(dt.date(2026, 8, 20), 30))
    assert len(items) == 1
    assert items[0].url == "https://www.tenderned.nl/aankondigingen/overzicht/436864"
    assert isinstance(items[0].url, str)


def test_an_unstorable_item_is_skipped_not_raised(tmp_path):
    """One bad connector must not discard every other source's work."""
    from radar.connectors.base import CollectedItem
    from radar.db import Database
    from radar.pipeline.ingest import IngestStats, Ingestor

    cfg = get_config()
    db = Database(tmp_path / "t.db")
    db.init_schema()
    ingestor = Ingestor(cfg, db)

    good = CollectedItem(source_id="s", url="https://ok.test/a", title="Fine",
                         published_at=dt.date(2026, 8, 20), extract="body", publisher="ok.test")
    bad = CollectedItem(source_id="s", url={"href": "https://x.test"}, title="Broken",
                        published_at=dt.date(2026, 8, 20), extract="body", publisher="x.test")

    stats = IngestStats()
    ingestor._store([bad, good], {"id": "s"}, "REF-1", stats)

    assert stats.malformed == 1
    assert stats.new_signals == 1, "the healthy item must still be stored"
    assert db.query("SELECT COUNT(*) AS n FROM signals")[0]["n"] == 1


def test_short_cpv_hints_are_padded_not_dropped():
    """A 5-digit hint returned HTTP 400 from TED and cost its group the refresh.
    CPV is 8 digits and a short code is a prefix, so padding keeps the group."""
    from radar.pipeline.query_grid import _normalise_cpv
    assert _normalise_cpv("71314") == "71314000"
    assert _normalise_cpv("09300000") == "09300000"
    assert _normalise_cpv("") == ""
    assert _normalise_cpv("not-a-code") == ""


def test_every_generated_cpv_code_is_eight_digits():
    cfg = get_config()
    for group in build_cpv_groups(cfg, {"min_code_digits": 8}):
        for code in group["cpv"]:
            assert len(code) == 8 and code.isdigit(), f"{group['label']}: bad CPV {code!r}"
