"""News and attention connectors (§4.3.1, Table 17).

GDELT is "the strongest single source for market signal strength, source
diversity and momentum, because it is already deduplicated across outlets and
carries geography and tone". RSS covers targeted per-query monitoring once
candidates exist.
"""

from __future__ import annotations

import datetime as dt
import logging
import xml.etree.ElementTree as ET
from typing import Any, Iterator
from urllib.parse import urljoin

from .base import (CollectedItem, Connector, clean_text, parse_date, publisher_from_url, register,
                   to_alpha2, unwrap_redirect)

log = logging.getLogger(__name__)


@register("gdelt")
class GdeltConnector(Connector):
    """GDELT DOC 2.0 article search.

    Note on replay (FR-35): GDELT's `timespan` is relative to *now*, so a
    historical replay must use the explicit startdatetime/enddatetime form.

    THE WINDOW IS SLICED, and not only for replay. `timespan` returns one
    result set capped at `maxrecords`, sorted by date — so a single request
    against a 60-day window returns whatever fits, clustered at one end of it.
    The first corpus showed the damage: counting back in 14-day periods GDELT
    returned 272 / 9 / 0 / 0. Momentum (§4.6) is the slope of signal volume over
    six trailing periods, so a source with a 14-day memory does not measure a
    trend — it measures the length of its own result set, and the slope it
    produces is an artefact.

    Slicing costs one request per slice per query, which against a source that
    already needs 6s pacing is the expensive part of a refresh. It is
    nonetheless the only way the trailing series is real; `window_slice_days`
    and `max_queries` are how the budget is controlled.
    """

    default_tier = 2
    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        queries = self.params.get("queries") or []
        max_records = int(self.params.get("max_records", 50))
        slice_days = max(1, int(self.params.get("window_slice_days", since_days)))

        for query in queries:
            for slice_start, slice_end in _slices(reference_date, since_days, slice_days):
                params: dict[str, Any] = {
                    "query": query,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": max_records,
                    "sort": "datedesc",
                    # Absolute dates in every case: `timespan` is relative to
                    # now, which silently breaks both replay (FR-35) and the
                    # trailing series above.
                    "startdatetime": slice_start.strftime("%Y%m%d000000"),
                    "enddatetime": slice_end.strftime("%Y%m%d235959"),
                }

                resp = self.get(self.ENDPOINT, params=params)
                if resp is None:
                    # Circuit breaker tripped or the host is refusing — the
                    # remaining slices would all fail the same way.
                    return
                try:
                    articles = resp.json().get("articles", [])
                except ValueError:
                    log.warning("GDELT returned non-JSON for query %r", query)
                    continue

                yield from self._to_items(articles, query, reference_date, since_days)

    def _to_items(self, articles: list[dict[str, Any]], query: str,
                  reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        for art in articles:
            url = art.get("url") or ""
            published = parse_date(art.get("seendate"))
            if not self.in_window(published, reference_date, since_days):
                continue
            title = clean_text(art.get("title") or "")
            if not title or not url:
                continue
            country = art.get("sourcecountry") or ""
            yield CollectedItem(
                source_id=self.source_id,
                url=url,
                title=title,
                published_at=published,
                # GDELT's artlist gives no body text, and fetching each
                # article would breach DR-08's store-by-reference rule for
                # sources whose terms we have not cleared. The title is the
                # extract; the URL is the reference.
                extract=self.clip(title),
                publisher=art.get("domain") or publisher_from_url(url),
                language=(art.get("language") or "").lower()[:2],
                geographies=[to_alpha2(country)] if country else [],
                attributes={"gdelt_query": query, "sourcecountry": country},
                payload=art,
            )


def _slices(reference_date: dt.date, since_days: int, slice_days: int):
    """Walk a window backwards in fixed slices, most recent first.

    Most recent first so that a run cut short by the circuit breaker keeps the
    part a radar actually needs.
    """
    offset = 0
    while offset < since_days:
        end = reference_date - dt.timedelta(days=offset)
        start = max(reference_date - dt.timedelta(days=since_days),
                    end - dt.timedelta(days=slice_days - 1))
        yield start, end
        offset += slice_days


@register("rss_search")
class RssSearchConnector(Connector):
    """Query-driven news RSS (Google News / Bing News), Table 17."""

    default_tier = 2

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", "https://news.google.com/rss/search")
        # `extra_params` keeps this connector generic across query-driven feeds:
        # Google News wants hl/gl/ceid, Bing wants format=RSS. A second news
        # engine is worth having because SC-03 measures diversity across
        # PUBLISHERS, and two engines surface materially different outlets.
        extra = self.params.get("extra_params")
        for query in self.params.get("queries") or []:
            if extra is not None:
                params = {self.params.get("query_param", "q"): query, **extra}
            else:
                params = {
                    "q": query,
                    "hl": self.params.get("hl", "en-GB"),
                    "gl": self.params.get("gl", "GB"),
                    "ceid": self.params.get("ceid", "GB:en"),
                }
            resp = self.get(endpoint, params=params)
            if resp is None:
                continue
            yield from self._parse_rss(resp.content, reference_date, since_days, {"query": query})

    def _parse_rss(self, content: bytes, reference_date: dt.date, since_days: int,
                   extra: dict[str, Any]) -> Iterator[CollectedItem]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            log.warning("RSS parse error for %s: %s", self.source_id, exc)
            return
        # Bing wraps every link in a bing.com redirect. Left alone it books all
        # 76 of its items to one publisher for a source added specifically
        # because SC-03 measures diversity across publishers, and it stores a
        # redirect where NFR-02 wants a citable URL. The destination is already
        # in the query string, so unwrapping costs no extra request.
        unwrap = bool(self.params.get("unwrap_redirects", False))
        base = extra.get("feed") or ""
        for item in root.iter("item"):
            title = clean_text(_text(item, "title"))
            link = _text(item, "link")
            published = parse_date(_text(item, "pubDate"))
            # A feed that puts an anchor inside <title> has usually mangled
            # <link> too — ACER emits the whole title element percent-encoded
            # into its own URL path. NFR-02 requires a URL a reviewer can open,
            # so prefer the href the publisher actually rendered.
            anchor = _anchor_href(item, base)
            if anchor and not _looks_like_a_real_url(link):
                link = anchor
            if not title or not link:
                continue
            if not self.in_window(published, reference_date, since_days):
                continue
            redirect_from = ""
            if unwrap:
                resolved = unwrap_redirect(link)
                if resolved != link:
                    redirect_from, link = link, resolved
            source_el = item.find("source")
            publisher = clean_text(source_el.text or "") if source_el is not None else publisher_from_url(link)
            # `<source>` is the aggregator's own label when it names the outlet,
            # but Bing omits it — so fall back to the (now unwrapped) host
            # rather than to the aggregator.
            if unwrap and not (source_el is not None and (source_el.text or "").strip()):
                publisher = publisher_from_url(link)
            description = clean_text(_text(item, "description"))
            attributes = dict(extra)
            if redirect_from:
                attributes["redirect_from"] = redirect_from
            yield CollectedItem(
                source_id=self.source_id,
                url=link,
                title=title,
                published_at=published,
                extract=self.clip(description or title),
                publisher=publisher or publisher_from_url(link),
                language=self.params.get("hl", "en")[:2],
                # §2.6: a query-driven feed declares its own market, so the
                # geography of what it returns is knowable without asking.
                geographies=self.geographies_for(),
                attributes=attributes,
                payload={"title": title, "link": link, "description": description},
            )


@register("rss_feed")
class RssFeedConnector(RssSearchConnector):
    """Plain RSS/Atom feed list — regulators, agencies, standards bodies."""

    default_tier = 1

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        for feed_url in self.params.get("feeds") or []:
            resp = self.get(feed_url)
            if resp is None:
                continue
            yield from self._parse_rss(resp.content, reference_date, since_days, {"feed": feed_url})
            yield from self._parse_atom(resp.content, reference_date, since_days, feed_url)

    def _parse_atom(self, content: bytes, reference_date: dt.date, since_days: int,
                    feed_url: str) -> Iterator[CollectedItem]:
        ns = "{http://www.w3.org/2005/Atom}"
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            return
        for entry in root.iter(f"{ns}entry"):
            title_el = entry.find(f"{ns}title")
            link_el = entry.find(f"{ns}link")
            title = clean_text(title_el.text or "") if title_el is not None else ""
            link = link_el.get("href", "") if link_el is not None else ""
            published = parse_date(
                _text_ns(entry, f"{ns}published") or _text_ns(entry, f"{ns}updated")
            )
            if not title or not link or not self.in_window(published, reference_date, since_days):
                continue
            summary = clean_text(_text_ns(entry, f"{ns}summary") or _text_ns(entry, f"{ns}content"))
            yield CollectedItem(
                source_id=self.source_id,
                url=link,
                title=title,
                published_at=published,
                extract=self.clip(summary or title),
                publisher=publisher_from_url(link) or publisher_from_url(feed_url),
                language=self.params.get("language", "en")[:2],
                geographies=self.geographies_for(),
                attributes={"feed": feed_url},
                payload={"title": title, "link": link, "summary": summary},
            )


def _text(element: ET.Element, tag: str) -> str:
    """Element text, including any nested markup the publisher left inline.

    Some feeds put an anchor inside <title>, which leaves `.text` empty and the
    real title one level down. `itertext` picks it up; `clean_text` at the call
    site strips whatever tags survive.
    """
    child = element.find(tag)
    if child is None:
        return ""
    if child.text and child.text.strip():
        return child.text
    return "".join(child.itertext())


def _anchor_href(item: ET.Element, base: str) -> str:
    """The href of the first anchor inside <title>, resolved against the feed."""
    title = item.find("title")
    if title is None:
        return ""
    for anchor in title.iter("a"):
        href = (anchor.get("href") or "").strip()
        if href:
            return urljoin(base, href) if base else href
    return ""


def _looks_like_a_real_url(url: str) -> bool:
    """Reject the mangled URLs produced by feeds that encode markup into a path."""
    if not url.startswith(("http://", "https://")):
        return False
    # "%3Ca%20href%3D" is a percent-encoded "<a href=" — a title that ended up
    # in the path rather than a document that lives there.
    return "%3c" not in url.lower() and "<" not in url


def _text_ns(element: ET.Element, qualified: str) -> str:
    child = element.find(qualified)
    return (child.text or "") if child is not None else ""
