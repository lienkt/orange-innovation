"""Technology-maturity connectors (§4.3.5, Table 20).

Research publication volume and velocity is "a leading indicator with a
multi-year lead over market coverage". These sources carry
`signal_type_hint = "technology_maturity"`.

§2.5 makes the stronger point: Orange's own research activity precedes market
signals by years and is machine-readable, so the radar can measure not only
"is the market talking about this" but "has Orange already been building this".
The `orange_affiliated` attribute set here is what makes that query possible;
the patent connector that completes the picture is catalogued but deferred
(config/sources.yaml).
"""

from __future__ import annotations

import datetime as dt
import logging
import xml.etree.ElementTree as ET
from typing import Iterator

from .base import CollectedItem, Connector, clean_text, parse_date, register, to_alpha2

log = logging.getLogger(__name__)

ORANGE_AFFILIATION_MARKERS = ("orange labs", "orange s.a", "orange sa", "france telecom", "orange innovation")


@register("openalex")
class OpenAlexConnector(Connector):
    """OpenAlex works search — open scholarly graph, CC0."""

    default_tier = 1
    ENDPOINT = "https://api.openalex.org/works"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        per_page = int(self.params.get("per_page", 25))
        window = int(self.params.get("since_days", since_days))
        start = reference_date - dt.timedelta(days=window)

        for query in self.params.get("queries") or []:
            resp = self.get(
                endpoint,
                params={
                    "search": query,
                    "per-page": per_page,
                    "filter": f"from_publication_date:{start.isoformat()},"
                              f"to_publication_date:{reference_date.isoformat()}",
                    # OpenAlex asks for a contact address in the polite pool.
                    "mailto": self.session.session.headers.get("User-Agent", "").split("<")[-1].rstrip(">"),
                },
            )
            if resp is None:
                continue
            try:
                results = resp.json().get("results", [])
            except ValueError:
                log.warning("OpenAlex returned non-JSON for query %r", query)
                continue

            for work in results:
                published = parse_date(work.get("publication_date"))
                title = clean_text(work.get("display_name") or "")
                if not title or not self.in_window(published, reference_date, window):
                    continue

                institutions = []
                countries = []
                for authorship in (work.get("authorships") or [])[:10]:
                    for inst in authorship.get("institutions") or []:
                        if inst.get("display_name"):
                            institutions.append(inst["display_name"])
                        if inst.get("country_code"):
                            countries.append(to_alpha2(inst["country_code"]))

                orange_affiliated = any(
                    marker in inst.lower() for inst in institutions for marker in ORANGE_AFFILIATION_MARKERS
                )
                abstract = _decode_inverted_abstract(work.get("abstract_inverted_index"))

                yield CollectedItem(
                    source_id=self.source_id,
                    url=work.get("doi") or work.get("id") or "",
                    title=title,
                    published_at=published,
                    extract=self.clip(abstract or title),
                    publisher="openalex.org",
                    language=(work.get("language") or "en")[:2],
                    geographies=sorted(set(countries)),
                    signal_type_hint="technology_maturity",
                    attributes={
                        "openalex_id": work.get("id"),
                        "cited_by_count": work.get("cited_by_count"),
                        "institutions": institutions[:8],
                        "orange_affiliated": orange_affiliated,
                        "query": query,
                    },
                    payload={k: work.get(k) for k in ("id", "doi", "display_name", "publication_date",
                                                      "cited_by_count", "type")},
                )


@register("arxiv")
class ArxivConnector(Connector):
    """arXiv Atom API — preprint velocity (Table 20)."""

    default_tier = 3
    ENDPOINT = "http://export.arxiv.org/api/query"
    NS = "{http://www.w3.org/2005/Atom}"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        max_results = int(self.params.get("max_results", 20))

        for query in self.params.get("queries") or []:
            resp = self.get(
                endpoint,
                params={
                    "search_query": query,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
            )
            if resp is None:
                continue
            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError as exc:
                log.warning("arXiv parse error for %r: %s", query, exc)
                continue

            for entry in root.iter(f"{self.NS}entry"):
                title = clean_text(_text(entry, f"{self.NS}title"))
                link = _text(entry, f"{self.NS}id")
                published = parse_date(_text(entry, f"{self.NS}published"))
                if not title or not link:
                    continue
                if not self.in_window(published, reference_date, since_days):
                    continue
                summary = clean_text(_text(entry, f"{self.NS}summary"))
                authors = [
                    clean_text(_text(a, f"{self.NS}name"))
                    for a in entry.findall(f"{self.NS}author")
                ]
                # DR-09: no personal data beyond the strictly necessary, and
                # named individuals in news items are not indexed as entities.
                # Author names are dropped; only the affiliation check survives.
                affiliation_blob = " ".join(authors).lower()
                yield CollectedItem(
                    source_id=self.source_id,
                    url=link,
                    title=title,
                    published_at=published,
                    extract=self.clip(summary or title),
                    publisher="arxiv.org",
                    language="en",
                    signal_type_hint="technology_maturity",
                    attributes={
                        "query": query,
                        "orange_affiliated": any(m in affiliation_blob for m in ORANGE_AFFILIATION_MARKERS),
                    },
                    payload={"title": title, "id": link},
                )


def _decode_inverted_abstract(index: dict | None) -> str:
    """OpenAlex ships abstracts as an inverted index for licensing reasons."""
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, spots in index.items():
        positions.extend((spot, word) for spot in spots)
    positions.sort()
    return " ".join(word for _, word in positions)


def _text(element: ET.Element, qualified: str) -> str:
    child = element.find(qualified)
    return (child.text or "") if child is not None else ""
