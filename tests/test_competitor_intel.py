"""Competitor profiling invariants (§4.3.3 extension).

Every test here is a failure that would put something wrong in front of a
customer, and three of them are regressions against defects this feature
actually shipped with before they were caught:

  * a model handed an enumeration returning the FIRST N ITEMS of it verbatim —
    OVHcloud credited with private 5G, O-RAN, network slicing and satellite NTN
    on a corpus that mentions 5G zero times, every id valid, every one passing
    closed-vocabulary validation;
  * a "named offer" carrying a page citation that the page does not support —
    Accenture credited with an "LED Flashlight" product line;
  * a differentiation paragraph naming an Orange asset that is not linked to the
    topic, which is the one sentence on the pane a salesperson will repeat
    verbatim in a meeting.
"""

from __future__ import annotations

import datetime as dt

import pytest

from radar.competitor_analysis import CompetitorAnalyst
from radar.competitor_intel import (CompetitorCrawler, ProfileBuilder, classify_url,
                                    corpus_hash, extract, profile_coverage)
from radar.config import get_config
from radar.db import Database, js


@pytest.fixture(scope="module")
def cfg():
    return get_config()


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


class _Builder(ProfileBuilder):
    """ProfileBuilder without the model client, for the validation paths."""

    def __init__(self, cfg, db, payload=None):
        self.cfg = cfg
        self.db = db
        self.settings = cfg.settings["competitor_intel"]
        self.pipeline_version = cfg.settings["pipeline_version"]
        self.llm = _FakeLLM(payload or {})


class _FakeLLM:
    strong_model = "test-model"

    def __init__(self, payload):
        self.payload = payload

    def complete_json(self, system, user, **kwargs):
        return self.payload


def seed_pages(db, competitor_id="ovhcloud", text="sovereign cloud bare metal kubernetes"):
    pages = []
    for i in range(3):
        pid = f"page{i}"
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO competitor_pages
                     (id, competitor_id, url, kind, title, extract, content_hash,
                      fetched_at, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pid, competitor_id, f"https://example.com/{i}", "solution",
                 f"Page {i}", text, "hash", dt.datetime.now(dt.timezone.utc).isoformat(), "0.1.0"))
        pages.append({"id": pid, "url": f"https://example.com/{i}", "kind": "solution",
                      "title": f"Page {i}", "extract": text})
    return pages


# ---------------------------------------------------------------- extraction

def test_extract_strips_chrome_and_keeps_content():
    html = ("<html lang='en'><head><title>Acme | Solutions</title>"
            "<script>var x=1;</script></head><body><nav>Menu Close</nav>"
            "<main><h1>Private 5G for factories</h1></main>"
            "<footer>Cookies</footer></body></html>")
    text, title, lang = extract(html)
    assert title == "Acme | Solutions"
    assert lang == "en"
    assert "Private 5G for factories" in text
    # Chrome and script bodies must not reach the profile prompt: they are the
    # same on every page of a site and would dominate a short corpus.
    assert "var x" not in text
    assert "Menu Close" not in text
    assert "Cookies" not in text


@pytest.mark.parametrize("url,expected", [
    ("https://x.com/solutions/iot", "solution"),
    ("https://x.com/industries/manufacturing", "industry"),
    ("https://x.com/customer-stories/acme", "customer_story"),
    ("https://x.com/products/firewall", "product"),
    ("https://x.com/about", "other"),
])
def test_classify_url(url, expected):
    assert classify_url(url) == expected


def test_locale_variants_collapse_to_one_page():
    """/en/ai-solutions and /fr/ai-solutions are one page, not two.

    A sitemap lists every locale. Forty pages of which thirty are translations
    of ten is a corpus that says a tenth of what it cost to fetch.
    """
    key = CompetitorCrawler._canonical_key
    assert key("https://x.com/en/ai-solutions") == key("https://x.com/fr/ai-solutions")
    assert key("https://x.com/de-de/products") == key("https://x.com/en-gb/products")
    # A two-letter first segment that is NOT a locale must survive as a path.
    assert key("https://x.com/ai/platform") == "ai/platform"


def test_english_variant_wins_the_tie():
    assert CompetitorCrawler._prefers_english("https://x.com/en/solutions") == 0
    assert CompetitorCrawler._prefers_english("https://x.com/fr/solutions") == 1


# ------------------------------------------------------------ corroboration

def test_vocabulary_tag_needs_the_pages_to_mention_it(cfg, db):
    """The list-echo regression.

    Asked for OVHcloud's technologies the model returned the first eight ids of
    the technology vocabulary in vocabulary order. Every id was real, so closed
    vocabulary passed all eight. The pages mention 5G zero times.
    """
    builder = _Builder(cfg, db)
    haystack = "sovereign cloud, bare metal servers, kubernetes, managed databases"
    stripped: list[dict[str, str]] = []
    kept = builder._closed(
        ["private_5g", "5g_ran_oran", "network_slicing", "sovereign_cloud"],
        cfg.technologies, stripped, "technologies", haystack)

    assert kept == ["sovereign_cloud"]
    assert len(stripped) == 3
    assert all("no page mentioned it" in s["reason"] for s in stripped)


def test_corroboration_ignores_short_tokens(cfg, db):
    """"Private 5G / LTE" splits to "lte", which appears inside ordinary words.

    Substring matching on a three-letter token corroborates almost anything,
    which would make the check above quietly useless — the same false-positive
    competition.py guards against with word-boundary alias matching.
    """
    builder = _Builder(cfg, db)
    stripped: list[dict[str, str]] = []
    kept = builder._closed(["private_5g"], cfg.technologies, stripped,
                           "technologies", "our alternative filters deliver value")
    assert kept == []


def test_corroboration_accepts_a_synonym(cfg, db):
    builder = _Builder(cfg, db)
    stripped: list[dict[str, str]] = []
    kept = builder._closed(["private_5g"], cfg.technologies, stripped,
                           "technologies", "we deploy private cellular networks on site")
    assert kept == ["private_5g"]


# ------------------------------------------------------- profile validation

def test_uncited_claims_are_stripped_not_rewritten(cfg, db):
    pages = seed_pages(db)
    builder = _Builder(cfg, db, payload={
        "positioning": "A European cloud provider emphasising sovereignty.",
        "claims": [
            {"claim": "Runs sovereign cloud regions in France", "pages": ["page0"]},
            {"claim": "Is the market leader across Europe", "pages": []},
            {"claim": "Operates a global satellite constellation", "pages": ["nonexistent"]},
        ],
        "verticals": [], "use_cases": [], "technologies": [], "named_offers": [],
    })
    profile = builder.generate({"id": "ovhcloud", "label": "OVHcloud", "website": "https://x"}, pages)

    assert len(profile["claims"]) == 1
    reasons = [s["reason"] for s in profile["stripped"]]
    assert reasons.count("no page supported it") == 2


def test_a_generated_number_kills_the_claim(cfg, db):
    pages = seed_pages(db)
    builder = _Builder(cfg, db, payload={
        "positioning": "A cloud provider.",
        "claims": [{"claim": "Holds 35% of the European market", "pages": ["page0"]}],
        "verticals": [], "use_cases": [], "technologies": [], "named_offers": [],
    })
    profile = builder.generate({"id": "ovhcloud", "label": "OVHcloud", "website": "https://x"}, pages)
    assert profile["claims"] == []
    assert any("quantity" in s["reason"] for s in profile["stripped"])


def test_a_number_in_the_positioning_drops_the_positioning(cfg, db):
    pages = seed_pages(db)
    builder = _Builder(cfg, db, payload={
        "positioning": "Serves over 1.6 million customers worldwide.",
        "claims": [{"claim": "Runs sovereign cloud regions", "pages": ["page0"]}],
        "verticals": [], "use_cases": [], "technologies": [], "named_offers": [],
    })
    profile = builder.generate({"id": "ovhcloud", "label": "OVHcloud", "website": "https://x"}, pages)
    assert profile["positioning"] == ""


def test_named_offer_must_appear_in_the_pages(cfg, db):
    """The "Accenture LED Flashlight" regression.

    A page citation proves a page was read. It does not prove the page said
    this, and a product name is exactly the kind of detail a model will supply
    with a plausible citation attached.
    """
    pages = seed_pages(db, text="We offer Bare Metal Pod and Public Cloud services.")
    builder = _Builder(cfg, db, payload={
        "positioning": "A cloud provider.",
        "claims": [{"claim": "Offers bare metal servers", "pages": ["page0"]}],
        "verticals": [], "use_cases": [], "technologies": [],
        "named_offers": [
            {"name": "Bare Metal Pod", "pages": ["page0"]},
            {"name": "LED Flashlight", "pages": ["page0"]},
        ],
    })
    profile = builder.generate({"id": "ovhcloud", "label": "OVHcloud", "website": "https://x"}, pages)
    assert [o["name"] for o in profile["named_offers"]] == ["Bare Metal Pod"]
    assert any("no page names it" in s["reason"] for s in profile["stripped"])


def test_corpus_hash_moves_when_the_pages_move():
    a = [{"url": "https://x/1", "extract": "alpha"}]
    b = [{"url": "https://x/1", "extract": "beta"}]
    assert corpus_hash(a) != corpus_hash(b)
    assert corpus_hash(a) == corpus_hash(list(a))


# ------------------------------------------------------------- the analysis

def _seed_topic_with_competitor(db, cfg):
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        cur.execute(
            """INSERT INTO opportunity_spaces
                 (id, version, vertical, use_case, technology, statement, domains, personas,
                  geographies, state, first_seen, last_refresh, pipeline_version)
               VALUES (?,1,?,?,?,?,'[]','[]','[]','active',?,?,'0.1.0')""",
            ("OS001", "manufacturing", "predictive_maintenance", "sovereign_cloud",
             "A statement long enough to pass validation for the test fixture.", now, now))
        cur.execute(
            """INSERT INTO topic_competition
                 (opportunity_id, computed_at, level, score, competitors, inputs,
                  register_version, pipeline_version)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("OS001", now, "medium", 3.5,
             js([{"id": "ovhcloud", "label": "OVHcloud", "basis": "structural", "mentions": []}]),
             js({}), cfg.competitors_raw["version"], "0.1.0"))
        cur.execute(
            """INSERT INTO competitor_profiles
                 (competitor_id, generated_at, status, positioning, claims, verticals,
                  technologies, use_cases, named_offers, register_version, pipeline_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("ovhcloud", now, "profiled", "A European sovereign cloud provider.",
             js([{"claim": "Runs sovereign cloud regions in France", "pages": ["page0"]}]),
             js(["manufacturing"]), js(["sovereign_cloud"]), js([]), js([]),
             cfg.competitors_raw["version"], "0.1.0"))


def test_join_is_arithmetic_and_needs_no_model(cfg, db):
    _seed_topic_with_competitor(db, cfg)
    analyst = CompetitorAnalyst(cfg, db, llm=object())      # never called
    entries = analyst.join("OS001")

    assert len(entries) == 1
    entry = entries[0]
    assert entry["id"] == "ovhcloud"
    assert entry["profile_status"] == "profiled"
    assert entry["profile_overlap"]["technology"] is True
    assert entry["profile_overlap"]["vertical"] is True
    assert entry["relevant_claims"]


def test_unprofiled_competitor_is_marked_not_omitted(cfg, db):
    """A competitor whose site refused us must still appear, saying so.

    Dropping them would make a partial field read as a complete one, which is
    the failure the coverage line exists to prevent.
    """
    _seed_topic_with_competitor(db, cfg)
    with db.cursor() as cur:
        cur.execute("UPDATE competitor_profiles SET status='blocked', "
                    "status_reason='403 to automated clients' WHERE competitor_id='ovhcloud'")
    entries = CompetitorAnalyst(cfg, db, llm=object()).join("OS001")
    assert len(entries) == 1
    assert entries[0]["profile_status"] == "blocked"
    assert entries[0]["relevant_claims"] == []


def test_differentiation_naming_an_unlinked_orange_asset_is_stripped(cfg, db):
    """The guard that matters most on this pane.

    The differentiation paragraph is the one sentence a salesperson repeats
    verbatim. It may only name Orange assets LINKED to this topic — an invented
    advantage is not caught in review, it is caught in the meeting.
    """
    _seed_topic_with_competitor(db, cfg)
    analyst = CompetitorAnalyst(cfg, db, llm=_FakeLLM({
        "competitors": [{
            "id": "ovhcloud",
            "activity": {"text": "They sell sovereign cloud regions in France.", "pages": ["page0"]},
            "differentiation": "Orange leads with Flexible Engine Premium, which OVHcloud cannot "
                               "match on regulated workloads, and pairs it with on-site delivery.",
            "orange_assets": ["Flexible Engine Premium"],
            "concession": "Their unit economics on bare metal are better.",
        }],
        "field": "Two sovereign providers and one hyperscaler.",
    }))
    topic = dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id='OS001'"))
    result = analyst.write(topic, analyst.join("OS001"))

    written = result["narrative"]["per_competitor"]["ovhcloud"]
    assert written["differentiation"] == ""
    assert any("unsupplied Orange assets" in s["reason"] for s in result["stripped"])
    # The activity half is independently valid and must survive.
    assert written["activity"]["text"]


def test_activity_must_cite_one_of_that_competitors_own_pages(cfg, db):
    _seed_topic_with_competitor(db, cfg)
    analyst = CompetitorAnalyst(cfg, db, llm=_FakeLLM({
        "competitors": [{
            "id": "ovhcloud",
            "activity": {"text": "They are the dominant player in this space.", "pages": []},
            "differentiation": "", "orange_assets": [], "concession": "",
        }],
        "field": "",
    }))
    topic = dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id='OS001'"))
    result = analyst.write(topic, analyst.join("OS001"))
    assert result["narrative"]["per_competitor"]["ovhcloud"]["activity"]["text"] == ""
    assert any("cited no page" in s["reason"] for s in result["stripped"])


def test_a_competitor_not_on_the_topic_cannot_be_added(cfg, db):
    _seed_topic_with_competitor(db, cfg)
    analyst = CompetitorAnalyst(cfg, db, llm=_FakeLLM({
        "competitors": [{"id": "aws_cloud", "activity": {"text": "x", "pages": []},
                         "differentiation": "", "orange_assets": [], "concession": ""}],
        "field": "",
    }))
    topic = dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id='OS001'"))
    result = analyst.write(topic, analyst.join("OS001"))
    assert "aws_cloud" not in result["narrative"]["per_competitor"]
    assert any("not a competitor on this topic" in s["reason"] for s in result["stripped"])


def test_rerunning_the_join_keeps_an_existing_comparison(cfg, db):
    """The join is cheap and runs often; the writing is neither."""
    _seed_topic_with_competitor(db, cfg)
    analyst = CompetitorAnalyst(cfg, db, llm=_FakeLLM({
        "competitors": [{
            "id": "ovhcloud",
            "activity": {"text": "They sell sovereign cloud.", "pages": ["page0"]},
            "differentiation": "", "orange_assets": [], "concession": "",
        }],
        "field": "A field of two.",
    }))
    topic = dict(db.query_one("SELECT * FROM opportunity_spaces WHERE id='OS001'"))
    analyst.write(topic, analyst.join("OS001"))
    analyst.run(topic_ids=["OS001"], use_llm=False)          # join only

    from radar.competitor_analysis import analysis_for_topic
    stored = analysis_for_topic(db, "OS001")
    assert stored["has_narrative"] is True
    assert stored["narrative"]["field"] == "A field of two."


# --------------------------------------------------------------- coverage

def test_coverage_reconciles_against_the_register(cfg, db):
    """Every competitor is accounted for, so a gap cannot hide as an absence."""
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with db.cursor() as cur:
        for cid, status in (("ovhcloud", "profiled"), ("cisco_comp", "blocked")):
            cur.execute(
                """INSERT INTO competitor_profiles
                     (competitor_id, generated_at, status, register_version, pipeline_version)
                   VALUES (?,?,?,?,?)""",
                (cid, now, status, cfg.competitors_raw["version"], "0.1.0"))
    coverage = profile_coverage(db, cfg)
    total = coverage["register_total"]
    accounted = (coverage["profiled"] + coverage["blocked"] + coverage["unreachable"]
                 + coverage["no_pages"] + coverage["unread"])
    assert accounted == total
