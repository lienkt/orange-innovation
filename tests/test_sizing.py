"""Market-sizing invariants (§4.3.4, Table 19).

The tests here are the ones that would be expensive to discover late, and each
maps to something §4.3.4 or §4.5.2 explicitly warns about: a denominator and an
adoption rate on different bases, a crosswalk error landing silently in a
figure, a contract value taken from the wrong kind of contract, and a proxy
being presented as an observation.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from radar.config import get_config
from radar.db import Database, js
from radar.sizing import (ALL_ACTIVITIES, BOTTOM_UP, ICT_SIZE_CLASS, MIN_WINDOW_DAYS,
                          PROCUREMENT, MarketSizer, format_eur, sizes_for_topic)

REF = dt.date(2026, 8, 17)


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


def seed_topic(db, topic_id="OS001", *, vertical="manufacturing",
               use_case="it_operations_automation", technology="machine_learning",
               geographies=("EU",), domains=("ox_smart_industries",)):
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
                 (id, version, vertical, use_case, technology, statement, domains, personas,
                  geographies, state, first_seen, last_refresh, pipeline_version)
               VALUES (?,1,?,?,?,?,?,'[]',?,'active','2026-01-01','2026-08-01','0.1.0')""",
            (topic_id, vertical, use_case, technology, "A specific opportunity statement",
             js(list(domains)), js(list(geographies))),
        )
    return db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?", (topic_id,))


def seed_reference(db, *, enterprises_per_slice=1000.0, adoption_pc=20.0,
                   nace_sbs="C10", nace_ict="C10-C12", geo="EU27_2020",
                   indicator="E_AI_TML", series="ict_ai", period="2024"):
    with db.cursor() as cur:
        for series_id in ("sbs", series):
            cur.execute(
                """INSERT OR REPLACE INTO reference_series
                     (id, dataset, publisher, label, url, licence, source_updated, fetched_at, rows)
                   VALUES (?,?,?,?,?,?,?,?,0)""",
                (series_id, f"{series_id}_dataset", "Eurostat", "label", "https://example.invalid",
                 "open", "2026-01-01", dt.date.today().isoformat()),
            )
        for size_class in ("10-19", "20-49", "50-249", "GE250"):
            cur.execute(
                """INSERT OR REPLACE INTO reference_observations
                     (series_id, indicator, nace, geo, size_class, period, value, unit)
                   VALUES ('sbs','ENT_NR',?,?,?,?,?,'ENT')""",
                (nace_sbs, geo, size_class, period, enterprises_per_slice),
            )
        cur.execute(
            """INSERT OR REPLACE INTO reference_observations
                 (series_id, indicator, nace, geo, size_class, period, value, unit)
               VALUES (?,?,?,?,?,?,?,'PC_ENT')""",
            (series, indicator, nace_ict, geo, ICT_SIZE_CLASS, period, adoption_pc),
        )


def seed_tender(db, signal_id, value_eur, *, cpv=("72514000",), days_ago=20, country="FR"):
    published = (REF - dt.timedelta(days=days_ago)).isoformat()
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO signals
                 (id, source_id, publisher, title, url, published_at, ingested_at, tier, extract,
                  attributes, pipeline_version)
               VALUES (?, 'ted', 'ted.europa.eu', ?, ?, ?, ?, 1, 'x', ?, '0.1.0')""",
            (signal_id, f"Tender {signal_id}", f"https://ted.europa.eu/{signal_id}", published,
             published,
             js({"total_value_eur": value_eur, "cpv": list(cpv), "buyer_country": [country]})),
        )


# ---------------------------------------------------------------------------
# The denominator and the adoption rate must share a base
# ---------------------------------------------------------------------------

def test_denominator_and_adoption_share_the_same_size_base(cfg, db):
    """The ICT survey publishes for 10+ employees only.

    Multiplying that rate by an all-sizes enterprise count — roughly 90% micro
    enterprises — would inflate every estimate by about an order of magnitude.
    The engine must count only the configured size classes.
    """
    topic = seed_topic(db)
    seed_reference(db, enterprises_per_slice=1000.0)
    sizer = MarketSizer(cfg, db)
    estimate = next(e for e in sizer.size_topic(dict(topic)) if e.method == BOTTOM_UP)

    enterprises = next(f for f in estimate.factors if f.name == "enterprises")
    # Four size classes seeded at 1000 each; nothing outside them may be counted.
    assert enterprises.value == pytest.approx(4000.0)
    assert enterprises.detail["size_classes"] == cfg.sizing["scope"]["size_classes"]


def test_crosswalk_confidence_is_applied_not_dropped(cfg, db):
    """§4.5.2: a shared NACE code must not be counted whole in two verticals.

    Retail's G45 row carries confidence 0.6 because motor trade is shared with
    automotive. The weight has to reach the arithmetic, not just the CSV.
    """
    topic = seed_topic(db, vertical="retail", use_case="it_operations_automation",
                       technology="computer_vision")
    seed_reference(db, enterprises_per_slice=1000.0, nace_sbs="G45", nace_ict="G45",
                   series="ict_ai", indicator="E_AI_TIR")
    estimate = next(e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == BOTTOM_UP)
    enterprises = next(f for f in estimate.factors if f.name == "enterprises")
    # 4 size classes x 1000 x 0.6 confidence.
    assert enterprises.value == pytest.approx(2400.0)


def test_size_weighting_reduces_the_effective_buyer_base(cfg, db):
    """A twelve-person firm does not buy a ministry-scale contract.

    The observed contract value comes from public tenders, so engagement value
    is scaled per size class. Without that, TAM is out by roughly an order of
    magnitude — the effective base must be far below the headcount.
    """
    topic = seed_topic(db)
    seed_reference(db, enterprises_per_slice=1000.0)
    estimate = next(e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == BOTTOM_UP)
    mix = next(f for f in estimate.factors if f.name == "size_mix")
    enterprises = next(f for f in estimate.factors if f.name == "enterprises")
    assert mix.value < enterprises.value / 2
    assert mix.basis == "assumption"


# ---------------------------------------------------------------------------
# Proxies must be declared, and must widen the range rather than move it
# ---------------------------------------------------------------------------

def test_proxy_adoption_is_flagged_and_widens_the_range(cfg, db):
    """private_5g has no Eurostat series; it borrows IoT use and must say so."""
    topic = seed_topic(db, technology="private_5g", use_case="predictive_maintenance")
    seed_reference(db, adoption_pc=20.0, series="ict_iot", indicator="E_IOT1")
    estimate = next(e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == BOTTOM_UP)

    adoption = next(f for f in estimate.factors if f.name == "adoption_rate")
    assert adoption.basis == "proxy"
    assert estimate.confidence in ("partial", "modelled")
    # The base is unmoved; only the uncertainty grows.
    assert adoption.value == pytest.approx(20.0)
    proxy_band = cfg.sizing["uncertainty"]["adoption_proxy"]
    assert adoption.low == pytest.approx(20.0 * (1 - proxy_band))
    assert any("proxy" in caveat.lower() for caveat in estimate.caveats)


def test_missing_sector_rate_falls_back_to_all_activities_as_a_proxy(cfg, db):
    """The ICT survey excludes finance, health, public administration and mining.

    Falling back to the all-activities aggregate is acceptable; doing it
    silently is not.
    """
    topic = seed_topic(db, vertical="financial_services", use_case="fraud_detection",
                       technology="machine_learning", domains=("cybersecurity",))
    seed_reference(db, nace_sbs="K64", nace_ict=ALL_ACTIVITIES, adoption_pc=15.0)
    estimate = next(e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == BOTTOM_UP)
    adoption = next(f for f in estimate.factors if f.name == "adoption_rate")
    assert adoption.basis == "proxy"
    assert adoption.detail["cells"][0]["nace"] == ALL_ACTIVITIES


def test_confidence_grade_is_the_worst_factor_not_an_average(cfg, db):
    """An estimate is exactly as good as its weakest input."""
    topic = seed_topic(db)
    seed_reference(db)                     # observed enterprises, observed adoption
    # No tender notices at all, so contract value falls back to a configured band.
    estimate = next(e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == BOTTOM_UP)
    contract = next(f for f in estimate.factors if f.name == "contract_value")
    assert contract.basis == "assumption"
    assert estimate.confidence == "modelled"


# ---------------------------------------------------------------------------
# Contract value: the right contracts, not merely the matching ones
# ---------------------------------------------------------------------------

def test_only_ict_main_object_tenders_price_an_engagement(cfg, db):
    """A turbine retrofit carrying an IT lot must not price a software project.

    Eligibility is tested on the notice's MAIN OBJECT. Both notices below match
    the same use case through the crosswalk; only the one whose first CPV is an
    IT code may contribute its value.
    """
    seed_topic(db)
    for index in range(8):
        seed_tender(db, f"SIG-IT{index}", 400_000.0, cpv=("72514000", "45259000"))
    for index in range(8):
        # Main object 45 (construction) with an IT lot attached, at 500x the value.
        seed_tender(db, f"SIG-CIV{index}", 200_000_000.0, cpv=("45259000", "72514000"))

    sizer = MarketSizer(cfg, db)
    index = sizer._build_procurement_index()
    values = {entry["value"] for entries in index["use_case"].values() for entry in entries}
    assert values == {400_000.0}


def test_observed_procurement_is_not_annualised_from_a_one_day_window(cfg, db):
    """Three notices on one day, multiplied by 365, is an artefact not a market."""
    topic = seed_topic(db)
    for index in range(6):
        seed_tender(db, f"SIG-T{index}", 1_000_000.0, days_ago=3)  # all the same day
    estimate = next(
        e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == PROCUREMENT
    )
    observed = next(f for f in estimate.factors if f.name == "observed_procurement")
    assert observed.detail["window_days"] >= MIN_WINDOW_DAYS
    # The stored factor is rounded for display, so compare like with like.
    assert observed.detail["annualisation_factor"] <= round(365 / MIN_WINDOW_DAYS, 2)


def test_serviceable_never_exceeds_total(cfg, db):
    """SAM is TAM restricted; a restriction that grows the number is a bug."""
    topic = seed_topic(db, geographies=("EU", "FR"))
    seed_reference(db)
    for index in range(10):
        seed_tender(db, f"SIG-T{index}", 500_000.0 * (index + 1), days_ago=index * 6)
    for estimate in MarketSizer(cfg, db).size_topic(dict(topic)):
        assert estimate.sam["base"] <= estimate.tam["base"] + 1e-6
        assert estimate.som["base"] <= estimate.sam["base"] + 1e-6


# ---------------------------------------------------------------------------
# Coverage, storage and reproducibility
# ---------------------------------------------------------------------------

def test_geographies_outside_the_reference_data_are_reported_not_dropped(cfg, db):
    """NFR-08: coverage is measured, not assumed."""
    topic = seed_topic(db, geographies=("EU", "US", "CN"))
    seed_reference(db)
    estimate = next(e for e in MarketSizer(cfg, db).size_topic(dict(topic)) if e.method == BOTTOM_UP)
    assert set(estimate.coverage["outside_reference_data"]) == {"US", "CN"}
    assert any("outside the European reference data" in c for c in estimate.caveats)


def test_public_sector_has_no_bottom_up_estimate_and_says_so(cfg, db):
    """SBS is the business economy; NACE O84 has no enterprise count at all.

    §4.3.4 prefers a missing number to a manufactured one, so the public-sector
    vertical is sized from observed procurement only.
    """
    topic = seed_topic(db, vertical="public_sector", use_case="citizen_service_automation",
                       technology="sovereign_cloud", domains=("cloud",))
    seed_reference(db)
    for index in range(8):
        seed_tender(db, f"SIG-P{index}", 900_000.0, cpv=("72512000",), days_ago=index * 10)
    methods = {e.method for e in MarketSizer(cfg, db).size_topic(dict(topic))}
    assert BOTTOM_UP not in methods
    assert PROCUREMENT in methods


def test_stored_size_records_the_assumptions_that_made_it(cfg, db):
    """SC-10's rule applied to sizes: two versions are not comparable."""
    topic = seed_topic(db)
    seed_reference(db)
    MarketSizer(cfg, db).run(topic_ids=[topic["id"]])
    stored = sizes_for_topic(db, topic["id"])
    assert stored
    assert all(entry["sizing_version"] == cfg.sizing_version for entry in stored)
    assert all(entry["factors"] for entry in stored)


def test_sizing_is_reproducible(cfg, db):
    """Identical inputs and configuration produce an identical estimate (SC-11)."""
    topic = seed_topic(db)
    seed_reference(db)
    sizer = MarketSizer(cfg, db)
    first = sizer.size_topic(dict(topic))
    second = MarketSizer(cfg, db).size_topic(dict(topic))
    assert [e.as_row() for e in first] == [e.as_row() for e in second]


def test_run_stores_nothing_it_cannot_compute(cfg, db):
    """An empty reference store yields no estimate rather than a zero."""
    topic = seed_topic(db)
    stats = MarketSizer(cfg, db).run(topic_ids=[topic["id"]])
    assert stats["no_estimate"] == [topic["id"]]
    assert sizes_for_topic(db, topic["id"]) == []


@pytest.mark.parametrize("value,expected", [
    (None, "—"), (950, "€950"), (12_600, "€13k"), (4_200_000, "€4.2m"), (7_300_000_000, "€7.3bn"),
])
def test_currency_formatting_is_shared(value, expected):
    """One formatter, so the API, the CLI and the PDF never disagree."""
    assert format_eur(value) == expected


# ---------------------------------------------------------------------------
# The bulk read path must agree with the per-topic one
# ---------------------------------------------------------------------------

def test_batched_assembly_matches_per_topic_assembly(cfg, db):
    """A view assembles topics in bulk; a topic page assembles one at a time.

    Those are two code paths producing the same object, which is exactly how two
    surfaces start disagreeing about the same topic. The bulk path exists because
    the per-topic one cost 1,670 queries and 1.6 seconds per view — worth having,
    and only worth having while it stays identical.
    """
    import json

    from radar.competition import CompetitionAnalyser
    from radar.readmodel import ReadModel

    topic = seed_topic(db)
    seed_reference(db)
    for index in range(8):
        seed_tender(db, f"SIG-T{index}", 400_000.0, days_ago=index * 9)
    MarketSizer(cfg, db).run(topic_ids=[topic["id"]])
    CompetitionAnalyser(cfg, db).run(topic_ids=[topic["id"]])

    read = ReadModel(cfg, db)
    batched = {t["id"]: t for t in read.topics(states=("active",))}[topic["id"]]
    direct = read._assemble(dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id = ?",
                                              (topic["id"],))))
    assert json.dumps(batched, sort_keys=True, default=str) == \
           json.dumps(direct, sort_keys=True, default=str)


def test_a_view_costs_a_fixed_number_of_queries(cfg, db):
    """The prefetch must not regress into a per-topic query by accident.

    This is the guard on the 36x speedup: the count is allowed to grow when a
    new fact joins the read model, but it must not grow WITH THE NUMBER OF
    TOPICS, which is what makes a list view feel broken at 150 topics.
    """
    from radar.db import Database
    from radar.readmodel import ReadModel

    # Distinct triples, because canonical identity is the triple (§4.4.5) and
    # the unique index enforces it.
    technologies = ["machine_learning", "generative_ai", "agentic_ai", "computer_vision",
                    "iot_platform", "private_5g", "sd_wan", "sase", "edge_computing",
                    "digital_twin", "siem_soar", "zero_trust_architecture"]
    for index, technology in enumerate(technologies):
        seed_topic(db, f"OS{index:03d}", use_case="it_operations_automation", technology=technology)
    seed_reference(db)

    read = ReadModel(cfg, db)
    counted = []
    original = Database.query
    try:
        Database.query = lambda self, sql, params=(): (counted.append(sql), original(self, sql, params))[1]
        read.topics(states=("active",))
    finally:
        Database.query = original
    assert len(counted) <= 20, f"a 12-topic view issued {len(counted)} queries: {counted[-3:]}"
