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

from .base import CollectedItem, Connector, clean_text, parse_date, publisher_from_url, register, to_alpha2

log = logging.getLogger(__name__)


@register("gdelt")
class GdeltConnector(Connector):
    """GDELT DOC 2.0 article search.

    Note on replay (FR-35): GDELT's `timespan` is relative to *now*, so a
    historical replay must use the explicit startdatetime/enddatetime form.
    Both paths are implemented; the reference date decides which is used.
    """

    default_tier = 2
    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        queries = self.params.get("queries") or []
        max_records = int(self.params.get("max_records", 50))
        today = dt.date.today()
        is_replay = reference_date < today

        for query in queries:
            params: dict[str, Any] = {
                "query": query,
                "mode": "artlist",
                "format": "json",
                "maxrecords": max_records,
                "sort": "datedesc",
            }
            if is_replay:
                start = reference_date - dt.timedelta(days=since_days)
                params["startdatetime"] = start.strftime("%Y%m%d000000")
                params["enddatetime"] = reference_date.strftime("%Y%m%d235959")
            else:
                params["timespan"] = self.params.get("timespan", f"{since_days}d")

            resp = self.get(self.ENDPOINT, params=params)
            if resp is None:
                continue
            try:
                articles = resp.json().get("articles", [])
            except ValueError:
                log.warning("GDELT returned non-JSON for query %r", query)
                continue

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
        for item in root.iter("item"):
            title = clean_text(_text(item, "title"))
            link = _text(item, "link")
            published = parse_date(_text(item, "pubDate"))
            if not title or not link:
                continue
            if not self.in_window(published, reference_date, since_days):
                continue
            source_el = item.find("source")
            publisher = clean_text(source_el.text or "") if source_el is not None else publisher_from_url(link)
            description = clean_text(_text(item, "description"))
            yield CollectedItem(
                source_id=self.source_id,
                url=link,
                title=title,
                published_at=published,
                extract=self.clip(description or title),
                publisher=publisher or publisher_from_url(link),
                language=self.params.get("hl", "en")[:2],
                attributes=extra,
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
                language="en",
                attributes={"feed": feed_url},
                payload={"title": title, "link": link, "summary": summary},
            )


def _text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "") if child is not None else ""


def _text_ns(element: ET.Element, qualified: str) -> str:
    child = element.find(qualified)
    return (child.text or "") if child is not None else ""
