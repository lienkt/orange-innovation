"""Competitor profiling from published vendor material (§4.3.3 extension).

The curated register in `config/business_graph/competitors.yaml` says what a
competitor sells. It is a Sprint 0 curation deliverable with a named owner, and
its weakness is obvious: it is a human's summary, written once, going stale from
the day it is written.

This module adds the other half — what the competitor *says* it sells, taken
from its own published pages, with the page that said it attached to every
claim. That is a different kind of evidence and it is treated as such:

  * A vendor's own website is TIER 4 ("interested party") everywhere it is
    scored, exactly like a vendor press release. Nothing here changes
    attractiveness, and SC-09's guarantee — vendor-only evidence scores low —
    is untouched.
  * A profile may do two things and no more. It may EXPLAIN a competitor that
    competition.py has already matched to a topic, and it may SEED generation
    through the competitor-move lens in synthesis. A candidate that lens
    produces still has to bind to independent, non-vendor evidence before it is
    accepted, exactly like every other candidate.

Three refusals are worth naming, because each is a place where it would have
been easy to do the convenient thing:

  robots.txt is obeyed, per URL, not per host.  A site that disallows a path
  is not crawled on that path even when the rest of the host is open.

  A 403 to a declared automated client is a refusal, and it is recorded as one.
  Six competitors answer 403 to our user agent. Spoofing a browser agent would
  work and is not done: the register carries `scrape.status: blocked` with the
  reason, the interface shows those competitors as an explicit profiling gap,
  and the analysis says how many of the competitors behind a topic are unread.
  This is the same discipline `config/sources.yaml` already applies to Ofcom.

  DR-08 applies unchanged.  A page is stored as its URL plus a bounded extract,
  never as a mirror.
"""

from __future__ import annotations

import concurrent.futures as futures
import datetime as dt
import hashlib
import logging
import re
import urllib.robotparser as robotparser
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from .config import Config
from .connectors.base import HttpSession, clean_text
from .db import Database, js, unjs

log = logging.getLogger(__name__)

#: Bumped when the shape of a stored profile changes, so a stale profile is
#: detectable without re-reading its pages.
PROFILE_SCHEMA = "cprofile-1"

#: Page kinds, inferred from the URL. Used to balance the corpus: forty
#: solution pages and no customer story says less than a mix of both.
KIND_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("customer_story", ("customer-stor", "case-stud", "success-stor", "client-stor", "/references/")),
    ("industry", ("industr", "/sector", "/verticals")),
    ("solution", ("solution", "what-we-do", "use-case", "capabilit", "offering")),
    ("product", ("product", "platform", "/service")),
)

_BLOCK_TAGS = re.compile(
    r"(?is)<(script|style|noscript|svg|head|nav|header|footer|aside|form|iframe)[^>]*>.*?</\1>")
_COMMENT = re.compile(r"(?is)<!--.*?-->")
_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
#: Locale segments recognised in a URL path: /fr, /de-de, /pt_br.
#:
#: An ALLOWLIST rather than "any two letters", and a deliberately incomplete
#: one. `ai`, `it`, `id`, `is` and `no` are all ISO language codes AND ordinary
#: path segments — /ai/platform, /it/services, /id/verification. Treating one of
#: those as a locale silently merges two genuinely different pages into one and
#: loses the content of both, which is a worse failure than keeping a duplicate
#: translation. So the ambiguous codes are simply not recognised.
_LOCALE_CODES = frozenset("""
    en fr de es pt nl da sv fi nb pl cs sk hu ro bg hr sl et lv lt el tr ru uk
    ja ko zh ar he th vi ms ca eu gl
""".split())
_LOCALE_REGION = re.compile(r"^([a-z]{2})[-_]([a-z]{2})$")
#: Both quote styles, and unquoted. Real pages use all three.
_LANG = re.compile(r"""(?is)<html[^>]*\blang\s*=\s*["']?([a-z]{2}(?:[-_][a-z]{2})?)""")


def _is_locale(segment: str) -> bool:
    """Is this path segment a language or language-region tag?

    `xx-YY` is unambiguous and always accepted. A bare two-letter segment is
    accepted only from the allowlist, because the ambiguous codes collide with
    real product paths.
    """
    low = segment.lower()
    region = _LOCALE_REGION.match(low)
    if region:
        return region.group(1) in _LOCALE_CODES or region.group(2) in _LOCALE_CODES
    return low in _LOCALE_CODES


def page_id(competitor_id: str, url: str) -> str:
    return hashlib.sha256(f"{competitor_id}|{url}".encode()).hexdigest()[:32]


def extract(html: str) -> tuple[str, str | None, str | None]:
    """Return (text, title, lang) from a page.

    Deliberately crude. A readability port would extract a cleaner article body,
    but these are marketing pages rather than articles: the useful content is
    the headings and the product names, and those survive tag-stripping intact
    once the chrome is gone.
    """
    title_match = _TITLE.search(html)
    title = clean_text(title_match.group(1))[:300] if title_match else None
    lang_match = _LANG.search(html)
    lang = lang_match.group(1).lower()[:5] if lang_match else None
    body = _COMMENT.sub(" ", html)
    body = _BLOCK_TAGS.sub(" ", body)
    return clean_text(body), title, lang


def classify_url(url: str) -> str:
    low = url.lower()
    for kind, needles in KIND_PATTERNS:
        if any(n in low for n in needles):
            return kind
    return "other"


class RobotsCache:
    """robots.txt per host, fetched once, failing CLOSED on an unreadable file.

    A host whose robots.txt cannot be read is not assumed permissive. That is
    the conservative reading and it costs us a handful of competitors; the
    alternative is crawling somebody who may have said no in a file we failed
    to parse.
    """

    def __init__(self, session: HttpSession, user_agent: str):
        self.session = session
        self.user_agent = user_agent
        self._parsers: dict[str, robotparser.RobotFileParser | None] = {}
        self.sitemaps: dict[str, list[str]] = {}

    def _parser(self, host_root: str) -> robotparser.RobotFileParser | None:
        if host_root in self._parsers:
            return self._parsers[host_root]
        parser: robotparser.RobotFileParser | None = None
        resp = self.session.get(f"{host_root}/robots.txt", min_interval=0.5)
        if resp is not None and resp.status_code < 400 and resp.text:
            parser = robotparser.RobotFileParser()
            try:
                parser.parse(resp.text.splitlines())
                self.sitemaps[host_root] = [
                    line.split(":", 1)[1].strip()
                    for line in resp.text.splitlines()
                    if line.lower().startswith("sitemap:")
                ]
            except Exception as exc:                       # pragma: no cover - defensive
                log.warning("robots.txt for %s did not parse: %s", host_root, exc)
                parser = None
        self._parsers[host_root] = parser
        return parser

    def allows(self, url: str) -> bool:
        parts = urlparse(url)
        root = f"{parts.scheme}://{parts.netloc}"
        parser = self._parser(root)
        if parser is None:
            # No readable robots.txt. Allow the entry point only — enough to
            # record that the host exists, not enough to crawl it.
            return parts.path in ("", "/")
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:                                   # pragma: no cover
            return False


class CompetitorCrawler:
    """Sitemap-guided, robots-aware crawl of one competitor's own pages."""

    def __init__(self, cfg: Config, db: Database):
        self.cfg = cfg
        self.db = db
        self.settings = cfg.settings["competitor_intel"]
        ing = cfg.settings["ingestion"]
        self.user_agent = ing["user_agent"]
        self.session = HttpSession(
            user_agent=self.user_agent,
            timeout=int(ing["request_timeout_seconds"]),
            max_retries=2,
            backoff=int(ing["retry_backoff_seconds"]),
            min_interval=float(self.settings["min_interval_seconds"]),
            # A competitor site that answers twice is not worth a third attempt:
            # unlike a signal source, nothing downstream depends on completeness.
            failure_budget=2,
        )
        self.robots = RobotsCache(self.session, self.user_agent)
        self.max_pages = int(self.settings["max_pages_per_competitor"])
        self.max_sitemaps = int(self.settings["max_sitemaps_per_competitor"])
        self.max_chars = int(self.settings["max_page_chars"])
        self.include = tuple(self.settings["include_patterns"])
        self.exclude = tuple(self.settings["exclude_patterns"])
        self.pipeline_version = cfg.settings["pipeline_version"]

    # ------------------------------------------------------------------ run
    def run(self, only: Iterable[str] | None = None) -> dict[str, Any]:
        wanted = set(only) if only else None
        register = [
            entry for entry in self.cfg.competitors_raw["competitors"]
            if wanted is None or entry["id"] in wanted
        ]
        stats: dict[str, Any] = {
            "competitors": len(register), "crawled": 0, "pages": 0,
            "skipped_blocked": 0, "skipped_unreachable": 0, "errors": {},
        }
        crawlable = []
        for entry in register:
            status = (entry.get("scrape") or {}).get("status", "ok")
            if status != "ok":
                stats["skipped_blocked" if status == "blocked" else "skipped_unreachable"] += 1
                self._record_status(entry, status, (entry.get("scrape") or {}).get("reason"))
                continue
            crawlable.append(entry)

        workers = int(self.settings["max_parallel_competitors"])
        with futures.ThreadPoolExecutor(max_workers=workers) as pool:
            jobs = {pool.submit(self._crawl_one, e): e for e in crawlable}
            for job in futures.as_completed(jobs):
                entry = jobs[job]
                try:
                    pages = job.result()
                except Exception as exc:                     # pragma: no cover - defensive
                    log.exception("Crawl failed for %s", entry["id"])
                    stats["errors"][entry["id"]] = f"{type(exc).__name__}: {exc}"
                    continue
                stats["crawled"] += 1
                stats["pages"] += pages
        if self.session.tripped:
            stats["circuit_breaker_tripped"] = sorted(self.session.tripped)
        log.info("Competitor crawl: %s", stats)
        return stats

    # -------------------------------------------------------------- one site
    def _crawl_one(self, entry: dict[str, Any]) -> int:
        cid = entry["id"]
        home = entry["website"]
        # A publisher that disallows its own entry point has said no. That is a
        # refusal to record, not an obstacle to route around, and it reads
        # differently downstream from a site we simply found nothing on.
        if not self.robots.allows(home):
            log.info("%s: robots.txt disallows %s — not crawled", cid, home)
            self._record_status(entry, "blocked", "robots.txt disallows the entry point")
            return 0
        urls = self._select_urls(home)
        if not urls:
            log.warning("%s: no crawlable URL survived robots.txt and filtering", cid)
            self._record_status(entry, "no_pages", "no URL survived robots.txt and filtering")
            return 0

        stored = 0
        failures = 0
        thin = 0
        for url in urls:
            is_home = url.rstrip("/") == home.rstrip("/")
            resp = self.session.get(url)
            if resp is None:
                failures += 1
                continue
            text, title, lang = extract(resp.text)
            if len(text) < 200:
                # A page that renders its content in JavaScript gives us a nav
                # bar and a cookie banner. Storing that would put noise into the
                # profile prompt and cost a model call to reject it.
                thin += 1
                continue
            self._store_page(cid, url, text, title, lang, resp.status_code,
                             kind="home" if is_home else None)
            stored += 1

        if stored == 0:
            # A crawl that fetched nothing must say why. Without this the
            # competitor is indistinguishable from one never attempted, and the
            # coverage line in the interface would quietly count it as unread
            # when in fact their server refused us.
            if failures:
                reason = (f"{failures} of {len(urls)} requests failed or were rate-limited"
                          + (" (host circuit breaker tripped)"
                             if urlparse(home).netloc in self.session.tripped else ""))
                self._record_status(entry, "unreachable", reason)
            else:
                self._record_status(entry, "no_pages",
                                    f"{thin} page(s) fetched, none carried readable text — "
                                    f"the site renders its content client-side")
        log.info("%s: stored %d pages (%d failed, %d too thin)", cid, stored, failures, thin)
        return stored

    def _select_urls(self, home: str) -> list[str]:
        """Sitemap first, homepage links as the fallback.

        Selection is the whole difficulty. A global integrator's sitemap runs to
        tens of thousands of URLs and the naive read — take the first N — gets a
        documentation tree in alphabetical order. So URLs are partitioned as
        they arrive into the ones whose path says what the company sells and
        everything else, and the second group is only ever used to top up.
        """
        parts = urlparse(home)
        root = f"{parts.scheme}://{parts.netloc}"
        wanted, shallow = self._sitemap_urls(root)

        if not wanted and not shallow:
            links = self._homepage_links(home, root)
            wanted = [u for u in links if self._wanted(u)]
            shallow = [u for u in links if not self._wanted(u) and self._shallow(u)]

        # At most a quarter of the budget goes to pages that did not announce
        # themselves — enough to catch a site whose URLs carry no vocabulary,
        # not enough for one to fill the profile with documentation.
        filler_budget = max(2, self.max_pages // 4)
        ordered = [home] + self._rank(wanted, home) + self._rank(shallow, home)[:filler_budget]

        seen_urls: set[str] = set()
        seen_paths: set[str] = set()
        out: list[str] = []
        for url in ordered:
            clean = url.split("#")[0].split("?")[0].rstrip("/") or url
            key = self._canonical_key(clean)
            if clean in seen_urls or (key and key in seen_paths):
                continue
            if not self.robots.allows(clean):
                continue
            seen_urls.add(clean)
            if key:
                seen_paths.add(key)
            out.append(clean)
        return out[: self.max_pages]

    def _sitemap_urls(self, root: str) -> tuple[list[str], list[str]]:
        """Read sitemap.xml, following one level of index.

        Returns (wanted, shallow): URLs whose path names a solution, industry,
        product or customer story, and top-level pages that name nothing but are
        shallow enough to be a section landing page.
        """
        self.robots.allows(root + "/")          # populates the Sitemap: directives
        queue = list(self.robots.sitemaps.get(root, []))
        queue += [f"{root}/sitemap.xml", f"{root}/sitemap_index.xml"]
        seen: set[str] = set()
        wanted: list[str] = []
        shallow: list[str] = []
        read = 0
        # Enough to choose from without holding a whole newsroom in memory.
        cap = self.max_pages * 20
        while queue and read < self.max_sitemaps and len(wanted) < cap:
            sm = queue.pop(0)
            if sm in seen:
                continue
            seen.add(sm)
            resp = self.session.get(sm, min_interval=1.0)
            if resp is None or resp.status_code >= 400 or "<" not in resp.text[:400]:
                continue
            read += 1
            try:
                tree = ElementTree.fromstring(resp.content)
            except ElementTree.ParseError:
                continue
            tag = tree.tag.rsplit("}", 1)[-1]
            locs = [el.text.strip() for el in tree.iter()
                    if el.tag.rsplit("}", 1)[-1] == "loc" and el.text]
            if tag == "sitemapindex":
                # Prefer child sitemaps whose own name suggests the part of the
                # site we want; a newsroom sitemap is 40,000 URLs of noise.
                ranked = sorted(locs, key=lambda u: (0 if self._wanted(u) else 1, len(u)))
                queue = ranked[: self.max_sitemaps] + queue
            else:
                for loc in locs:
                    if self._excluded(loc):
                        continue
                    if self._wanted(loc):
                        wanted.append(loc)
                    elif self._shallow(loc):
                        shallow.append(loc)
        return wanted, shallow

    def _homepage_links(self, home: str, root: str) -> list[str]:
        resp = self.session.get(home)
        if resp is None:
            return []
        hrefs = re.findall(r'(?i)href="([^"#?]+)"', resp.text)
        out = []
        for href in hrefs:
            url = urljoin(home, href)
            if urlparse(url).netloc != urlparse(root).netloc:
                continue
            out.append(url)
        return out

    def _excluded(self, url: str) -> bool:
        low = url.lower()
        return any(bad in low for bad in self.exclude)

    def _wanted(self, url: str) -> bool:
        low = url.lower()
        return not self._excluded(low) and any(good in low for good in self.include)

    @staticmethod
    def _canonical_key(url: str) -> str:
        """Path identity with the locale segment removed.

        Every large vendor publishes the same page under a dozen locales, and a
        sitemap lists all of them. Forty pages of which thirty are translations
        of ten is a corpus that says a tenth of what it cost to fetch.
        """
        parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
        if parts and _is_locale(parts[0]):
            parts = parts[1:]
        return "/".join(parts)

    @staticmethod
    def _prefers_english(url: str) -> int:
        """Sort key: an English variant wins the tie against its translations."""
        parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
        if parts and _is_locale(parts[0]):
            return 0 if parts[0].lower().startswith("en") else 1
        return 0

    @staticmethod
    def _shallow(url: str) -> bool:
        """A top-level section landing page, by path depth.

        Scaleway sells `/en/ai/` and `/en/bare-metal/`; Mistral sells
        `/products`. Neither carries the word "solution" anywhere. Depth is the
        only signal those have in common, and it is a weak one — which is why
        these only ever top up a corpus that the vocabulary match has already
        filled.
        """
        path = urlparse(url).path.strip("/")
        return 0 < len([p for p in path.split("/") if p]) <= 2

    def _rank(self, urls: list[str], home: str) -> list[str]:
        """The pages that say what they sell first, then a story mix."""
        def key(url: str) -> tuple[int, int, int, int]:
            kind = classify_url(url)
            rank = {"solution": 1, "industry": 2, "customer_story": 3, "product": 4}.get(kind, 6)
            low = url.lower()
            # Shallow paths beat deep ones: /solutions/iot says more than
            # /solutions/iot/2019/emea/partner-programme/terms.
            return (rank, self._prefers_english(url), low.count("/"), len(low))
        return sorted(urls, key=key)

    # ------------------------------------------------------------- storage
    def _store_page(self, cid: str, url: str, text: str, title: str | None,
                    lang: str | None, status: int, kind: str | None = None) -> None:
        extract_text = text[: self.max_chars]
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO competitor_pages
                       (id, competitor_id, url, kind, title, extract, lang,
                        content_hash, fetched_at, http_status, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(competitor_id, url) DO UPDATE SET
                       title = excluded.title,
                       extract = excluded.extract,
                       lang = excluded.lang,
                       content_hash = excluded.content_hash,
                       fetched_at = excluded.fetched_at,
                       http_status = excluded.http_status""",
                (page_id(cid, url), cid, url, kind or classify_url(url), title, extract_text, lang,
                 hashlib.sha256(extract_text.encode()).hexdigest()[:32],
                 dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 status, self.pipeline_version),
            )

    def _record_status(self, entry: dict[str, Any], status: str, reason: str | None) -> None:
        """A competitor we could not read still gets a row, saying so.

        An absent profile and a refused profile look identical downstream unless
        the refusal is written down, and the interface has to be able to tell a
        reader which of the competitors behind a topic were never read.
        """
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO competitor_profiles
                       (competitor_id, generated_at, status, status_reason,
                        register_version, pipeline_version)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(competitor_id) DO UPDATE SET
                       status = excluded.status,
                       status_reason = excluded.status_reason,
                       generated_at = excluded.generated_at""",
                (entry["id"], dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 status, reason, self.cfg.competitors_raw["version"], self.pipeline_version),
            )


# ---------------------------------------------------------------------------
# Read helpers used by the profiler, the analyst and the read model
# ---------------------------------------------------------------------------

def pages_for(db: Database, competitor_id: str, limit: int = 40) -> list[dict[str, Any]]:
    rows = db.query(
        """SELECT id, url, kind, title, extract, lang FROM competitor_pages
           WHERE competitor_id = ? ORDER BY
             CASE kind WHEN 'solution' THEN 1 WHEN 'industry' THEN 2
                       WHEN 'customer_story' THEN 3 WHEN 'product' THEN 4
                       WHEN 'home' THEN 0 ELSE 5 END, length(extract) DESC
           LIMIT ?""",
        (competitor_id, limit),
    )
    return [dict(r) for r in rows]


def profile_for(db: Database, competitor_id: str) -> dict[str, Any] | None:
    row = db.query_one("SELECT * FROM competitor_profiles WHERE competitor_id = ?", (competitor_id,))
    return profile_from_row(row)


def profile_from_row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for field in ("claims", "verticals", "technologies", "use_cases", "named_offers", "stripped"):
        data[field] = unjs(data.get(field), [])
    return data


def corpus_hash(pages: list[dict[str, Any]]) -> str:
    """Identity of a page set, so a profile knows when its evidence moved."""
    joined = "|".join(sorted(f"{p['url']}:{p.get('extract','')[:64]}" for p in pages))
    return hashlib.sha256(joined.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Profile generation
# ---------------------------------------------------------------------------

class ProfileBuilder:
    """One structured profile per competitor, from that competitor's own pages.

    The guardrails are the ones synthesis uses, applied to a different input.
    Evidence binding means a claim carries the page id that made it; closed
    vocabulary means a taxonomy value the profile asserts is one the radar
    already knows; the numeric guard means a figure printed on a marketing page
    does not become a figure the radar repeats.
    """

    def __init__(self, cfg: Config, db: Database, llm: Any | None = None):
        self.cfg = cfg
        self.db = db
        self.settings = cfg.settings["competitor_intel"]
        self.pipeline_version = cfg.settings["pipeline_version"]
        if llm is None:
            from .llm import LLMClient
            llm = LLMClient(max_retries=cfg.settings["llm"]["max_retries"])
        self.llm = llm

    def run(self, only: Iterable[str] | None = None, force: bool = False) -> dict[str, Any]:
        from .pipeline import prompts

        wanted = set(only) if only else None
        register = {e["id"]: e for e in self.cfg.competitors_raw["competitors"]}
        todo: list[dict[str, Any]] = []
        stats = {"considered": 0, "profiled": 0, "skipped_current": 0,
                 "skipped_no_pages": 0, "claims_stripped": 0, "errors": {}}

        for cid, entry in register.items():
            if wanted is not None and cid not in wanted:
                continue
            stats["considered"] += 1
            pages = pages_for(self.db, cid, int(self.settings["max_pages_per_competitor"]))
            if not pages:
                stats["skipped_no_pages"] += 1
                continue
            if not force and self._is_current(cid, pages):
                stats["skipped_current"] += 1
                continue
            todo.append({"entry": entry, "pages": pages})

        cap = int(self.settings["max_profiles_per_run"])
        if len(todo) > cap:
            log.info("Profile cap: %d of %d competitors this run; the rest are logged, not dropped",
                     cap, len(todo))
            stats["deferred"] = [j["entry"]["id"] for j in todo[cap:]]
            todo = todo[:cap]

        system = prompts.competitor_profile_system_prompt(self.cfg)
        workers = int(self.settings["max_parallel_profiles"])

        def work(job: dict[str, Any]) -> None:
            entry, pages = job["entry"], job["pages"]
            try:
                result = self.generate(entry, pages, system)
            except Exception as exc:                          # pragma: no cover - defensive
                log.exception("Profile failed for %s", entry["id"])
                stats["errors"][entry["id"]] = f"{type(exc).__name__}: {exc}"
                return
            stats["profiled"] += 1
            stats["claims_stripped"] += len(result["stripped"])

        with futures.ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(work, todo))
        log.info("Competitor profiles: %s", stats)
        return stats

    # ------------------------------------------------------------------
    def generate(self, entry: dict[str, Any], pages: list[dict[str, Any]],
                 system: str | None = None) -> dict[str, Any]:
        from .pipeline import prompts
        from .pipeline.synthesis import _NUMERIC_CLAIM_RE

        system = system or prompts.competitor_profile_system_prompt(self.cfg)
        user = prompts.format_competitor_for_profile(entry, pages)
        # A forty-page corpus produces a long structured answer, and the default
        # completion budget truncates it mid-string — which surfaces as invalid
        # JSON and loses the whole profile rather than the tail of it. Microsoft
        # and Mistral both failed this way on the first full run.
        payload = self.llm.complete_json(
            system, user, max_tokens=6000,
            temperature=self.cfg.settings["llm"]["temperature_classify"])
        if not isinstance(payload, dict):
            payload = {}

        page_ids = {p["id"] for p in pages}
        # Everything the profile is allowed to be corroborated against, once.
        haystack = " ".join(
            f"{p.get('title') or ''} {p.get('extract') or ''}" for p in pages).lower()
        stripped: list[dict[str, str]] = []

        claims = []
        for raw in payload.get("claims") or []:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("claim", "")).strip()
            if len(text) < 12:
                continue
            if _NUMERIC_CLAIM_RE.search(text):
                stripped.append({"claim": text[:120], "reason": "contained a quantity"})
                continue
            cited = [p for p in raw.get("pages") or [] if p in page_ids]
            if not cited:
                stripped.append({"claim": text[:120], "reason": "no page supported it"})
                continue
            claims.append({"claim": text, "pages": cited})

        positioning = str(payload.get("positioning", "")).strip()
        if _NUMERIC_CLAIM_RE.search(positioning):
            stripped.append({"claim": "positioning", "reason": "contained a quantity"})
            positioning = ""

        offers = []
        for raw in payload.get("named_offers") or []:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip()
            if not (2 <= len(name) <= 80):
                continue
            cited = [p for p in raw.get("pages") or [] if p in page_ids]
            if not cited:
                stripped.append({"claim": f"offer {name}", "reason": "no page supported it"})
                continue
            # The same corroboration rule as the taxonomy tags. Asked for
            # Accenture's named offers the model returned "Accenture LED
            # Flashlight" and "Accenture PED Safety Bag" — page ids attached and
            # all. A citation proves a page was read, not that the page said this.
            if name.lower() not in haystack:
                stripped.append({"claim": f"offer {name}",
                                 "reason": "cited a page but no page names it"})
                continue
            offers.append({"name": name, "pages": cited})

        profile = {
            "competitor_id": entry["id"],
            "status": "profiled" if claims else "no_pages",
            "positioning": positioning,
            "claims": claims,
            "verticals": self._closed(payload.get("verticals"), self.cfg.verticals,
                                      stripped, "verticals", haystack),
            "use_cases": self._closed(payload.get("use_cases"), self.cfg.use_cases,
                                      stripped, "use_cases", haystack),
            "technologies": self._closed(payload.get("technologies"), self.cfg.technologies,
                                         stripped, "technologies", haystack),
            "named_offers": offers,
            "stripped": stripped,
            "pages_used": len(pages),
            "corpus_hash": corpus_hash(pages),
        }
        self._store(profile)
        return profile

    def _closed(self, values: Any, vocab: Any, stripped: list[dict[str, str]], field: str,
                haystack: str = "") -> list[str]:
        """Defence 2 — closed vocabulary — plus corroboration in the pages.

        Closed-vocabulary validation alone is not enough here, and the failure it
        misses is not hypothetical. Asked for OVHcloud's technologies, the model
        returned the first eight ids of the technology vocabulary in vocabulary
        order — private 5G, O-RAN, network slicing, SD-WAN, SASE, satellite NTN,
        LPWAN, Wi-Fi 6E. Every one is a real id, so every one passed. OVHcloud's
        pages mention 5G exactly zero times.

        A list-echo is the characteristic failure of handing a model an
        enumeration and asking it to pick from it, and the enumeration is exactly
        what makes it survive validation. So a tag now needs a SECOND,
        INDEPENDENT reason — the term has to actually appear in the pages the
        profile was built from. This is the rule `enrichment` already applies to
        signal attachment ("similarity alone is not evidence"), applied to the
        same problem in a different place.
        """
        if not isinstance(values, list):
            return []
        kept: list[str] = []
        for value in values:
            token = str(value).strip()
            resolved = vocab.resolve(token) if hasattr(vocab, "resolve") else None
            if not resolved:
                if token:
                    stripped.append({"claim": f"{field}:{token}", "reason": "outside the vocabulary"})
                continue
            if resolved in kept:
                continue
            if haystack and not self._corroborated(vocab, resolved, haystack):
                stripped.append({
                    "claim": f"{field}:{resolved}",
                    "reason": "no page mentioned it — a valid id the model supplied unsupported",
                })
                continue
            kept.append(resolved)
        return kept

    @staticmethod
    def _corroborated(vocab: Any, vocab_id: str, haystack: str) -> bool:
        """Does the crawled corpus actually mention this vocabulary item?

        Matched on the label, the synonyms and the id with separators relaxed.
        Deliberately generous — the cost of a false negative is a thinner
        profile, the cost of a false positive is a competitor credited with a
        capability they never claimed, in front of a customer.
        """
        try:
            item = vocab.get(vocab_id)
        except Exception:                                   # pragma: no cover - defensive
            return True
        terms = {vocab_id.replace("_", " "), vocab_id.replace("_", "-")}
        label = getattr(item, "label", "") or ""
        # "Private 5G / LTE" is two acceptable names, not one long one.
        terms.update(part.strip().lower() for part in re.split(r"[/,]", label))
        terms.update(str(s).strip().lower() for s in getattr(item, "synonyms", ()))
        # Word boundaries, and nothing shorter than four characters.
        #
        # Substring matching is what makes a corroboration check quietly useless:
        # "Private 5G / LTE" splits to "lte", and "lte" appears inside enough
        # ordinary words to corroborate almost anything. competition.py already
        # learned this with its alias matcher — "an ambiguous short name (SES,
        # Colt, NICE) produces false positives that would put an invented
        # competitor in front of a customer" — and the same rule applies to a
        # capability the profile is about to credit them with.
        for term in terms:
            if len(term) < 4:
                continue
            if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", haystack):
                return True
        return False

    def _is_current(self, competitor_id: str, pages: list[dict[str, Any]]) -> bool:
        row = self.db.query_one(
            "SELECT corpus_hash, status, prompt_version FROM competitor_profiles WHERE competitor_id = ?",
            (competitor_id,))
        if row is None or row["status"] != "profiled":
            return False
        from .pipeline import prompts
        return (row["corpus_hash"] == corpus_hash(pages)
                and row["prompt_version"] == prompts.PROMPT_VERSION_COMPETITOR_PROFILE)

    def _store(self, profile: dict[str, Any]) -> None:
        from .pipeline import prompts
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO competitor_profiles
                       (competitor_id, generated_at, status, status_reason, positioning, claims,
                        verticals, technologies, use_cases, named_offers, stripped, pages_used,
                        corpus_hash, register_version, prompt_version, model_version, pipeline_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(competitor_id) DO UPDATE SET
                       generated_at = excluded.generated_at,
                       status = excluded.status,
                       status_reason = excluded.status_reason,
                       positioning = excluded.positioning,
                       claims = excluded.claims,
                       verticals = excluded.verticals,
                       technologies = excluded.technologies,
                       use_cases = excluded.use_cases,
                       named_offers = excluded.named_offers,
                       stripped = excluded.stripped,
                       pages_used = excluded.pages_used,
                       corpus_hash = excluded.corpus_hash,
                       register_version = excluded.register_version,
                       prompt_version = excluded.prompt_version,
                       model_version = excluded.model_version""",
                (profile["competitor_id"],
                 dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 profile["status"], None, profile["positioning"], js(profile["claims"]),
                 js(profile["verticals"]), js(profile["technologies"]), js(profile["use_cases"]),
                 js(profile["named_offers"]), js(profile["stripped"]), profile["pages_used"],
                 profile["corpus_hash"], self.cfg.competitors_raw["version"],
                 prompts.PROMPT_VERSION_COMPETITOR_PROFILE,
                 getattr(self.llm, "strong_model", None), self.pipeline_version),
            )


def profile_coverage(db: Database, cfg: Config) -> dict[str, Any]:
    """How much of the register has actually been read.

    Surfaced in the interface rather than kept in a log: a competitive view
    built from 40 of 65 profiles is a different object from one built from all
    65, and the reader is the one who has to decide whether that matters.
    """
    rows = db.query("SELECT status, COUNT(*) n FROM competitor_profiles GROUP BY status")
    by_status = {r["status"]: r["n"] for r in rows}
    total = len(cfg.competitors_raw["competitors"])
    profiled = by_status.get("profiled", 0)
    return {
        "register_total": total,
        "profiled": profiled,
        "blocked": by_status.get("blocked", 0),
        "unreachable": by_status.get("unreachable", 0),
        "no_pages": by_status.get("no_pages", 0),
        "unread": total - sum(by_status.values()),
        "register_version": cfg.competitors_raw["version"],
    }
