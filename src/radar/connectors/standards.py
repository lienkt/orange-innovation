"""Standards and developer-adoption connectors (§4.3.5, Table 20).

Table 20 calls standards bodies "the most reliable way to date when a network
technology becomes deployable", and config/sources.yaml catalogued 3GPP, ETSI,
O-RAN, IETF and GSMA as one `rss_feed` source with an empty feed list. That was
never going to work: none of those bodies publishes RSS. Probed on 2026-08-20,
3GPP and ETSI both return HTML to a feed request and ENISA's documented feed
paths still 404.

IETF is the one that does have a machine-readable route, and a good one — the
Datatracker exposes a full open REST API over every draft and RFC, with dates.
That is exactly the horizon evidence §4.8 wants: a draft moving to RFC is a
dated, attributable milestone in a technology's readiness, not a press release
about one.

GitHub covers the other half of maturity. arXiv and OpenAlex measure what is
being RESEARCHED; repository activity measures what is being BUILT, which is a
different and later point on the same curve.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any, Iterator

from .base import CollectedItem, Connector, clean_text, parse_date, register

log = logging.getLogger(__name__)


@register("ietf_datatracker")
class IetfDatatrackerConnector(Connector):
    """IETF Datatracker documents — drafts and RFCs, with their dates.

    The `time` field cannot be ordered on server-side (the API rejects
    `order_by=-time`), so the window filter is applied through `time__gt` and
    the results are date-filtered here. That is one request per subject term
    rather than a crawl.
    """

    default_tier = 1
    ENDPOINT = "https://datatracker.ietf.org/api/v1/doc/document/"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        window = int(self.params.get("since_days", since_days))
        limit = int(self.params.get("limit_per_query", 25))
        doc_types = self.params.get("doc_types") or ["draft"]
        start = reference_date - dt.timedelta(days=window)

        for term in self.params.get("queries") or []:
            for doc_type in doc_types:
                resp = self.get(endpoint, params={
                    "format": "json",
                    "limit": limit,
                    "type": doc_type,
                    "title__icontains": term,
                    "time__gt": start.isoformat(),
                })
                if resp is None:
                    continue
                try:
                    objects = resp.json().get("objects", [])
                except ValueError:
                    log.warning("IETF Datatracker returned non-JSON for %r", term)
                    continue

                for doc in objects:
                    item = self._to_item(doc, term, reference_date, window)
                    if item is not None:
                        yield item

    def _to_item(self, doc: dict[str, Any], term: str, reference_date: dt.date,
                 window: int) -> CollectedItem | None:
        title = clean_text(str(doc.get("title") or ""))
        name = str(doc.get("name") or "")
        published = parse_date(doc.get("time"))
        if not title or not name or not self.in_window(published, reference_date, window):
            return None

        rfc_number = doc.get("rfc_number")
        abstract = clean_text(str(doc.get("abstract") or ""))
        std_level = doc.get("std_level") or doc.get("intended_std_level") or ""

        extract = abstract or title
        if rfc_number:
            # A published RFC is a materially stronger maturity claim than a
            # draft, and §4.8 reads it as a horizon anchor rather than as noise.
            extract = f"Published as RFC {rfc_number}. {extract}"

        return CollectedItem(
            source_id=self.source_id,
            url=f"https://datatracker.ietf.org/doc/{name}/",
            title=title,
            published_at=published,
            extract=self.clip(extract),
            publisher="ietf.org",
            language="en",
            geographies=self.geographies_for(),
            signal_type_hint="technology_maturity",
            attributes={
                "query": term,
                "document": name,
                "revision": doc.get("rev"),
                "rfc_number": rfc_number,
                "std_level": std_level,
                "stream": doc.get("stream"),
                "is_rfc": bool(rfc_number),
            },
            payload={"name": name, "title": title, "rfc_number": rfc_number},
        )


@register("github_repos")
class GitHubReposConnector(Connector):
    """GitHub repository search — what is being built, not researched.

    Requires `GITHUB_TOKEN` in the environment. Unauthenticated search is
    rate-limited to the point of uselessness (probed 2026-08-20: HTTP 403 on the
    first request from a clean IP), so rather than pretend it works this source
    stays disabled until a token exists — the same treatment sources.yaml
    already gives the patent connector.

    Repositories are emitted at tier 3. A repository is real and dated, but its
    description is written by whoever wants the stars.
    """

    default_tier = 3
    ENDPOINT = "https://api.github.com/search/repositories"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            log.warning("github_repos is enabled but GITHUB_TOKEN is unset — "
                        "unauthenticated search is rate-limited to zero; skipping")
            return

        endpoint = self.params.get("endpoint", self.ENDPOINT)
        per_page = int(self.params.get("per_page", 20))
        min_stars = int(self.params.get("min_stars", 5))
        window = int(self.params.get("since_days", since_days))
        start = reference_date - dt.timedelta(days=window)

        for term in self.params.get("queries") or []:
            query = f'{term} pushed:>{start.isoformat()} stars:>={min_stars}'
            resp = self.get(endpoint, params={"q": query, "sort": "updated", "per_page": per_page},
                            headers={"Authorization": f"Bearer {token}",
                                     "Accept": "application/vnd.github+json"})
            if resp is None:
                continue
            try:
                repos = resp.json().get("items", [])
            except ValueError:
                log.warning("GitHub returned non-JSON for %r", term)
                continue

            for repo in repos:
                # `pushed_at` is the activity date; `created_at` would date the
                # repository rather than the evidence of current work.
                published = parse_date(repo.get("pushed_at"))
                name = clean_text(str(repo.get("full_name") or ""))
                if not name or not self.in_window(published, reference_date, window):
                    continue
                description = clean_text(str(repo.get("description") or ""))
                owner = (repo.get("owner") or {}).get("login") or "github.com"

                yield CollectedItem(
                    source_id=self.source_id,
                    url=repo.get("html_url") or f"https://github.com/{name}",
                    title=f"{name} — {description}" if description else name,
                    published_at=published,
                    extract=self.clip(description or name),
                    publisher=str(owner),
                    language="en",
                    geographies=self.geographies_for(),
                    signal_type_hint="technology_maturity",
                    attributes={
                        "query": term,
                        "repository": name,
                        "stars": repo.get("stargazers_count"),
                        "forks": repo.get("forks_count"),
                        "primary_language": repo.get("language"),
                        "pushed_at": repo.get("pushed_at"),
                    },
                    payload={"full_name": name, "stargazers_count": repo.get("stargazers_count")},
                )
