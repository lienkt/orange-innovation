"""Connector framework (pipeline stage 1, Table 16).

Table 16 stage 1: "Scheduled connectors per source: RSS/Atom, REST APIs, SPARQL,
bulk downloads. Per-source rate limits, ETags, incremental cursors."

Two constraints shape this module:

  DR-08 / NFR-07 — source content is stored BY REFERENCE (URL plus short
  extract), never mirrored in full, and robots.txt, terms of use and licence
  terms are respected per source. `CollectedItem.extract` is truncated here so
  no connector can accidentally mirror a full article.

  FR-35 / DR-14 — the pipeline must be replayable as of a past reference date
  with all features restricted to data published before that date. Every
  connector therefore receives a `reference_date` and must not return items
  published after it. §4.7.3: the filter is on the PUBLICATION date, not the
  ingestion date — leakage through late-arriving documents is invisible unless
  the pipeline is designed to prevent it from the start.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterator
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

REGISTRY: dict[str, type["Connector"]] = {}


def register(name: str):
    def wrap(cls):
        REGISTRY[name] = cls
        cls.connector_name = name
        return cls

    return wrap


@dataclass
class CollectedItem:
    """One item as fetched, with the connector's best normalisation applied.

    The connector fills what it authoritatively knows (a TED notice knows its
    CPV codes and buyer country; an RSS item does not). Stage 2 handles what is
    uniform across sources: hashing, dedup, tiering, language detection.
    """

    source_id: str
    url: str
    title: str
    published_at: dt.date | None
    extract: str
    publisher: str = ""
    language: str = ""
    geographies: list[str] = field(default_factory=list)
    signal_type_hint: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    published_at_inferred: bool = False

    def content_hash(self) -> str:
        basis = f"{self.title.strip().lower()}|{self.extract.strip()[:400].lower()}"
        return hashlib.sha256(basis.encode()).hexdigest()

    def raw_id(self) -> str:
        return hashlib.sha256(f"{self.source_id}|{self.url}".encode()).hexdigest()[:32]


class Connector(ABC):
    connector_name: str = "base"
    #: Declared tier; publisher_overrides in source_tiers.yaml take precedence.
    default_tier: int = 3
    #: Minimum seconds between requests to this source's host. Overridable per
    #: source via `rate_limit_seconds`. Free APIs differ by an order of
    #: magnitude here — GDELT throttles far harder than TED — and getting it
    #: wrong means either 429s or a needlessly slow refresh.
    min_interval: float = 0.4

    def __init__(self, source: dict[str, Any], session: "HttpSession", max_extract_chars: int = 1200):
        self.source = source
        self.source_id = source["id"]
        self.params = source.get("params") or {}
        self.session = session
        self.max_extract_chars = max_extract_chars
        self.default_tier = int(source.get("default_tier", self.default_tier))
        self.min_interval = float(source.get("rate_limit_seconds", self.min_interval))

    def get(self, url: str, **kwargs) -> "requests.Response | None":
        return self.session.get(url, min_interval=self.min_interval, **kwargs)

    def post(self, url: str, **kwargs) -> "requests.Response | None":
        return self.session.post(url, min_interval=self.min_interval, **kwargs)

    @abstractmethod
    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        """Yield items published on or before `reference_date`."""

    # -- shared helpers ----------------------------------------------------

    def clip(self, text: str) -> str:
        """Truncate to the configured extract length (DR-08)."""
        text = clean_text(text)
        if len(text) <= self.max_extract_chars:
            return text
        return text[: self.max_extract_chars].rsplit(" ", 1)[0] + "…"

    def in_window(self, published: dt.date | None, reference_date: dt.date, since_days: int) -> bool:
        """Reject anything published after the reference date (FR-35 leakage control)."""
        if published is None:
            return False
        if published > reference_date:
            return False
        return published >= reference_date - dt.timedelta(days=since_days)


class HttpSession:
    """Shared HTTP session with per-host rate limiting and retry/backoff."""

    def __init__(self, user_agent: str, timeout: int = 45, max_retries: int = 3, backoff: int = 5,
                 min_interval: float = 0.4, failure_budget: int = 2):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.min_interval = min_interval
        self._last_call: dict[str, float] = {}
        # Sources are fetched concurrently (see Ingestor.collect), so the
        # throttle clock and the breaker counters are shared mutable state.
        self._lock = threading.Lock()
        # Circuit breaker. A source that is hard-down (GDELT applies a long
        # per-IP cooldown and answers 429 to everything) would otherwise burn
        # retries × backoff on every one of its configured queries — minutes of
        # wall clock for a source that will not answer. After `failure_budget`
        # exhausted requests to a host, the rest of that host's requests in this
        # refresh short-circuit. NFR-04 asks the refresh to complete inside its
        # cadence window; one dead source must not put that at risk.
        self.failure_budget = failure_budget
        self._failures: dict[str, int] = {}
        self.tripped: set[str] = set()

    def _throttle(self, url: str, min_interval: float | None = None) -> None:
        host = urlparse(url).netloc
        interval = self.min_interval if min_interval is None else min_interval
        with self._lock:
            last = self._last_call.get(host)
            now = time.monotonic()
            wait = 0.0 if last is None else interval - (now - last)
            # Reserve this host's next slot before releasing the lock, so two
            # threads hitting the same host cannot both decide to go now.
            self._last_call[host] = now + max(0.0, wait)
        if wait > 0:
            time.sleep(wait)

    def request(self, method: str, url: str, min_interval: float | None = None, **kwargs) -> requests.Response | None:
        host = urlparse(url).netloc
        if host in self.tripped:
            return None
        kwargs.setdefault("timeout", self.timeout)
        for attempt in range(self.max_retries):
            self._throttle(url, min_interval)
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                log.warning("%s %s failed (%d/%d): %s", method, url, attempt + 1, self.max_retries, exc)
                time.sleep(self.backoff * (attempt + 1))
                continue
            # 429/5xx are worth retrying. GDELT in particular rate-limits hard
            # and needs a much longer pause than a transient 503, so 429 gets
            # its own multiplier rather than the shared backoff.
            if resp.status_code in (429, 500, 502, 503, 504):
                multiplier = 2 if resp.status_code == 429 else 1
                wait = self.backoff * (attempt + 1) * multiplier
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = max(wait, int(retry_after))
                log.warning("%s %s -> %d, retrying in %ds", method, url, resp.status_code, wait)
                time.sleep(wait)
                continue
            if resp.status_code >= 400:
                log.warning("%s %s -> %d (giving up)", method, url, resp.status_code)
                self._record_failure(host)
                return None
            # A success clears the host's failure history: a transient blip
            # should not push a healthy source toward its budget over time.
            with self._lock:
                self._failures.pop(host, None)
            return resp
        log.error("%s %s exhausted %d retries", method, url, self.max_retries)
        self._record_failure(host)
        return None

    def _record_failure(self, host: str) -> None:
        with self._lock:
            self._failures[host] = self._failures.get(host, 0) + 1
            tripped_now = self._failures[host] >= self.failure_budget and host not in self.tripped
            if tripped_now:
                self.tripped.add(host)
        if tripped_now:
            log.error(
                "Circuit breaker OPEN for %s after %d failed requests — skipping its remaining "
                "requests this refresh. The source is recorded as failed in the refresh stats.",
                host, self._failures[host],
            )

    def get(self, url: str, **kwargs) -> requests.Response | None:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response | None:
        return self.request("POST", url, **kwargs)


# ---------------------------------------------------------------------------
# Text and date utilities
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ENTITY_RE = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")


def clean_text(text: str) -> str:
    """Strip markup and collapse whitespace (stage 2 boilerplate stripping)."""
    if not text:
        return ""
    import html

    text = _TAG_RE.sub(" ", text)
    if _ENTITY_RE.search(text):
        text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y%m%dT%H%M%SZ",
)


def parse_date(value: Any) -> dt.date | None:
    """Best-effort date parsing.

    DR-04: undated evidence is either dated by inference at ingestion or
    rejected. Returning None here means the item is rejected downstream — that
    is the intended behaviour, not a gap.
    """
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    # Trim common timezone suffixes such as TED's "2026-06-18+02:00".
    trimmed = re.sub(r"([+-]\d{2}:\d{2})$", "", text)
    for pattern in _DATE_PATTERNS:
        for candidate in (text, trimmed):
            try:
                return dt.datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return dt.date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return None
    match = re.search(r"^(\d{4})(\d{2})(\d{2})", text)
    if match:
        try:
            return dt.date(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return None
    return None


def publisher_from_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


# ISO-3166 alpha-3 to alpha-2, for the subset the EU sources emit. Geography is
# a first-class scoring dimension (§2.6), so it is normalised at ingestion
# rather than left in whatever form each source happens to use.
ALPHA3_TO_ALPHA2 = {
    "AUT": "AT", "BEL": "BE", "BGR": "BG", "HRV": "HR", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR",
    "HUN": "HU", "IRL": "IE", "ITA": "IT", "LVA": "LV", "LTU": "LT", "LUX": "LU",
    "MLT": "MT", "NLD": "NL", "POL": "PL", "PRT": "PT", "ROU": "RO", "SVK": "SK",
    "SVN": "SI", "ESP": "ES", "SWE": "SE", "NOR": "NO", "CHE": "CH", "GBR": "GB",
    "USA": "US", "CAN": "CA", "BRA": "BR", "ARG": "AR", "CHL": "CL", "COL": "CO",
    "MEX": "MX", "PER": "PE", "JPN": "JP", "CHN": "CN", "IND": "IN", "AUS": "AU",
}


def to_alpha2(code: str) -> str:
    code = (code or "").strip().upper()
    if len(code) == 2:
        return code
    return ALPHA3_TO_ALPHA2.get(code, code[:2] if code else "")
