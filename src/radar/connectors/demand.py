"""Demand-side leading indicators (§4.3.1, Table 17 extension).

Two sources that precede a tender rather than report it.

SEC EDGAR full-text search. Named enterprises describing their own deployments
in filings they are legally obliged to make accurate. The first corpus had only
309 `market_move` signals out of 7,275, and nearly all of them were vendor
announcements filtered through a news outlet — the party with the least
incentive to be conservative. A filing is the opposite: the buyer's own account,
dated, attributable, and the single most quotable piece of evidence a
salesperson can carry into a meeting (FR-18).

Adzuna job postings. An enterprise hiring an OT security engineer or a private-5G
RF planner has committed budget months before a tender exists. Postings are
dated, employer-named and geo-tagged — everything the signal schema wants —
which makes them a demand signal with roughly the lead time §4.3.3 credits
procurement with removing. Requires credentials, so it stays catalogued and
disabled until a key exists (the same treatment as the patent connector).
"""

from __future__ import annotations

import datetime as dt
import logging
import os
from typing import Any, Iterator

from .base import CollectedItem, Connector, clean_text, parse_date, register, to_alpha2

log = logging.getLogger(__name__)


@register("sec_edgar")
class SecEdgarConnector(Connector):
    """SEC EDGAR full-text search over recent filings.

    Free, no key, no registration — the SEC asks only for a descriptive
    User-Agent carrying a contact address, which `ingestion.user_agent` already
    provides, and for request rates below ten per second.

    Only the filing METADATA is stored: company, form type, date and the
    Archives URL. The filing body is never mirrored (DR-08), which for a public
    filing is a storage decision rather than a licence one, but the rule is the
    rule.
    """

    default_tier = 1
    ENDPOINT = "https://efts.sec.gov/LATEST/search-index"
    min_interval = 0.6

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        forms = self.params.get("forms") or "8-K,10-K,10-Q"
        window = int(self.params.get("since_days", since_days))
        start = reference_date - dt.timedelta(days=window)
        max_hits = int(self.params.get("max_hits_per_query", 20))

        for query in self.params.get("queries") or []:
            # EDGAR's full-text index wants the phrase quoted; an unquoted
            # multi-word query becomes an OR and returns the whole market.
            phrase = query if query.startswith('"') else f'"{query}"'
            resp = self.get(endpoint, params={
                "q": phrase,
                "forms": forms,
                "startdt": start.isoformat(),
                "enddt": reference_date.isoformat(),
            })
            if resp is None:
                continue
            try:
                hits = resp.json().get("hits", {}).get("hits", [])
            except ValueError:
                log.warning("EDGAR returned non-JSON for %r", query)
                continue

            for hit in hits[:max_hits]:
                item = self._to_item(hit, query, reference_date, window)
                if item is not None:
                    yield item

    def _to_item(self, hit: dict[str, Any], query: str, reference_date: dt.date,
                 window: int) -> CollectedItem | None:
        source = hit.get("_source") or {}
        published = parse_date(source.get("file_date"))
        if not self.in_window(published, reference_date, window):
            return None

        names = source.get("display_names") or []
        company = clean_text(str(names[0])) if names else ""
        if not company:
            return None
        # "EchoStar CORP  (ECHO)  (CIK 0001415404)" — the ticker and CIK are
        # useful as attributes but make a poor title.
        company_name = company.split("  (")[0].strip()

        form = str(source.get("form") or "")
        accession = str(source.get("adsh") or "")
        ciks = [str(c) for c in source.get("ciks") or []]
        document = str(hit.get("_id") or "").split(":", 1)
        filename = document[1] if len(document) > 1 else ""

        url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
        if ciks and accession and filename:
            url = (f"https://www.sec.gov/Archives/edgar/data/{int(ciks[0])}/"
                   f"{accession.replace('-', '')}/{filename}")

        title = f"{company_name} — {form} filing mentioning “{query}”"
        extract = (f"{company_name} filed a {form} with the SEC on {published.isoformat()} "
                   f"whose text contains “{query}”.")
        location = (source.get("biz_locations") or [""])[0]
        if location:
            extract += f" Business address: {location}."
        sics = source.get("sics") or []
        if sics:
            extract += f" SIC {sics[0]}."

        return CollectedItem(
            source_id=self.source_id,
            url=url,
            title=title,
            published_at=published,
            extract=self.clip(extract),
            # The filer is the publisher. Attributing to "sec.gov" would collapse
            # every filing onto one publisher and inflate nothing but noise in
            # the SC-03 diversity measure.
            publisher=company_name or "sec.gov",
            language="en",
            geographies=self.geographies_for([to_alpha2("USA")]),
            # A company telling its investors it is deploying something is a
            # market move, not a trend piece (FR-03).
            signal_type_hint="market_move",
            attributes={
                "query": query,
                "form": form,
                "accession": accession,
                "ciks": ciks,
                "sic": sics[:2],
                "business_location": location,
                "filer": company,
            },
            payload={"adsh": accession, "form": form, "display_names": names[:3]},
        )


@register("adzuna_jobs")
class AdzunaJobsConnector(Connector):
    """Adzuna job-posting search — hiring as a leading demand signal.

    Credentials come from the environment (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`),
    never from config: .env is gitignored and sources.yaml is not.

    Tier 3 deliberately. A posting is real, dated and attributable, but it is
    also a recruiter's copy, prone to buzzword inflation — the same reason
    Hacker News sits at tier 3 (Table 17). It earns its place on lead time, not
    on authority, and evidence quality should keep treating it that way.
    """

    default_tier = 3
    ENDPOINT = "https://api.adzuna.com/v1/api/jobs"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        app_id = os.getenv("ADZUNA_APP_ID", "")
        app_key = os.getenv("ADZUNA_APP_KEY", "")
        if not (app_id and app_key):
            log.warning("adzuna_jobs is enabled but ADZUNA_APP_ID / ADZUNA_APP_KEY are unset — "
                        "the source contributes nothing this refresh")
            return

        base = self.params.get("endpoint", self.ENDPOINT)
        per_page = int(self.params.get("results_per_page", 20))
        window = int(self.params.get("since_days", since_days))

        for country in self.params.get("countries") or ["gb"]:
            for query in self.params.get("queries") or []:
                resp = self.get(f"{base}/{country}/search/1", params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "what_phrase": query,
                    "results_per_page": per_page,
                    "max_days_old": window,
                    "content-type": "application/json",
                })
                if resp is None:
                    continue
                try:
                    results = resp.json().get("results", [])
                except ValueError:
                    log.warning("Adzuna returned non-JSON for %r/%s", query, country)
                    continue

                for job in results:
                    published = parse_date(job.get("created"))
                    title = clean_text(str(job.get("title") or ""))
                    if not title or not self.in_window(published, reference_date, window):
                        continue
                    employer = clean_text(str((job.get("company") or {}).get("display_name") or ""))
                    where = clean_text(str((job.get("location") or {}).get("display_name") or ""))
                    description = clean_text(str(job.get("description") or ""))

                    yield CollectedItem(
                        source_id=self.source_id,
                        url=job.get("redirect_url") or "https://www.adzuna.com/",
                        title=f"{title} — {employer}" if employer else title,
                        published_at=published,
                        extract=self.clip(f"{title}. {employer}. {where}. {description}"),
                        # The hiring employer, not the job board: a posting is
                        # evidence about that company (SC-03).
                        publisher=employer or "adzuna.com",
                        language=self.params.get("language", "en"),
                        geographies=self.geographies_for([to_alpha2(country)]),
                        # DR-09: no personal data. Adzuna exposes no named
                        # individuals in this payload and none is stored.
                        signal_type_hint="buying_signal",
                        attributes={
                            "query": query,
                            "country": country.upper(),
                            "employer": employer,
                            "location": where,
                            "category": (job.get("category") or {}).get("label"),
                        },
                        payload={"id": job.get("id"), "title": title, "company": employer},
                    )
