"""Second-tranche connectors: practitioner attention, national procurement,
early regulatory signals and EU-funded research (Appendix A).

These complete the source categories the first tranche left thin:

  hackernews     practitioner attention, "months ahead of analyst coverage"
                 (Table 17) — the only tier-3 community signal wired
  boamp          French below-threshold procurement, extending TED's coverage
                 downward (§4.3.3) and adding French-language buying signals
  have_your_say  EC consultations and calls for evidence — "the earliest formal
                 indicator of a coming rule" (Table 18), which is what lets a
                 topic be classified Later on policy grounds rather than guessed
  cordis         EU-funded research projects — "shows what Europe has decided to
                 fund, often with Orange or its partners as participants"
                 (Table 20)
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Any, Iterator

from .base import CollectedItem, Connector, clean_text, parse_date, publisher_from_url, register

log = logging.getLogger(__name__)


@register("hackernews")
class HackerNewsConnector(Connector):
    """Hacker News via the Algolia search API (Table 17).

    Tier 3 by construction: practitioner attention is an early adoption signal
    but is "noisy and heavily anglophone", so it is discounted in evidence
    quality and capped in diversity rather than trusted.
    """

    default_tier = 3
    ENDPOINT = "https://hn.algolia.com/api/v1/search_by_date"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        per_query = int(self.params.get("hits_per_page", 20))
        min_points = int(self.params.get("min_points", 2))
        start = reference_date - dt.timedelta(days=since_days)

        for query in self.params.get("queries") or []:
            resp = self.get(endpoint, params={
                "query": query,
                "tags": "story",
                "hitsPerPage": per_query,
                # Algolia numeric filters bound the window server-side, which
                # keeps the replay honest without post-filtering (FR-35).
                "numericFilters": (
                    f"created_at_i>{int(dt.datetime.combine(start, dt.time.min).timestamp())},"
                    f"created_at_i<{int(dt.datetime.combine(reference_date, dt.time.max).timestamp())}"
                ),
            })
            if resp is None:
                continue
            try:
                hits = resp.json().get("hits", [])
            except ValueError:
                log.warning("Hacker News returned non-JSON for %r", query)
                continue

            for hit in hits:
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                title = clean_text(hit.get("title") or "")
                published = parse_date(hit.get("created_at"))
                points = int(hit.get("points") or 0)
                # A story nobody upvoted is not attention, it is a submission.
                if not title or points < min_points:
                    continue
                if not self.in_window(published, reference_date, since_days):
                    continue
                yield CollectedItem(
                    source_id=self.source_id,
                    url=url,
                    title=title,
                    published_at=published,
                    extract=self.clip(title),
                    # Attribute the ORIGINATING publisher, not HN: §4.3.7 counts
                    # diversity across publishers, and treating every HN story as
                    # one publisher would collapse genuinely independent sources.
                    publisher=publisher_from_url(url) or "news.ycombinator.com",
                    language="en",
                    attributes={"query": query, "points": points,
                                "num_comments": hit.get("num_comments"),
                                "hn_id": hit.get("objectID")},
                    payload={"title": title, "url": url, "points": points},
                )


@register("boamp")
class BoampConnector(Connector):
    """BOAMP — French public procurement, via the Opendatasoft Explore API.

    §4.3.3: national equivalents "extend coverage below the EU threshold".
    TED only carries above-threshold notices, so a French mid-size tender for
    exactly the kind of work Orange Business sells is invisible without this.

    Also a French-language buying signal, which FR-28 asks for and which the
    first live run had none of.
    """

    default_tier = 1
    ENDPOINT = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        limit = min(100, int(self.params.get("limit_per_query", 40)))
        start = reference_date - dt.timedelta(days=since_days)

        for term in self.params.get("search_terms") or []:
            where = (
                f"dateparution>='{start.isoformat()}' "
                f"AND dateparution<='{reference_date.isoformat()}' "
                f"AND search(objet,'{term}')"
            )
            resp = self.get(endpoint, params={
                "limit": limit, "order_by": "dateparution DESC", "where": where,
            })
            if resp is None:
                continue
            try:
                payload = resp.json()
            except ValueError:
                log.warning("BOAMP returned non-JSON for %r", term)
                continue

            total = payload.get("total_count")
            records = payload.get("results", [])
            if total and total > limit:
                log.info("BOAMP %r: sampled %d of %d matching notices", term, len(records), total)

            for record in records:
                title = clean_text(str(record.get("objet") or ""))
                published = parse_date(record.get("dateparution"))
                if not title or not self.in_window(published, reference_date, since_days):
                    continue
                notice_id = record.get("idweb") or record.get("id") or ""
                descriptors = record.get("descripteur_libelle") or []
                if isinstance(descriptors, str):
                    descriptors = [descriptors]
                cpv = record.get("code_cpv")
                yield CollectedItem(
                    source_id=self.source_id,
                    url=f"https://www.boamp.fr/avis/detail/{notice_id}" if notice_id
                        else "https://www.boamp.fr/",
                    title=title,
                    published_at=published,
                    extract=self.clip(title),
                    publisher="boamp.fr",
                    language="fr",
                    geographies=["FR"],
                    signal_type_hint="buying_signal",
                    attributes={
                        "search_term": term,
                        "cpv": [str(cpv)] if cpv else [],
                        "descriptors": descriptors[:6],
                        "nature": record.get("nature"),
                        "departement": record.get("code_departement"),
                        "deadline": record.get("datelimitereponse"),
                        "sampled_from_total": total,
                    },
                    payload={"idweb": notice_id, "objet": title,
                             "dateparution": record.get("dateparution")},
                )


@register("have_your_say")
class HaveYourSayConnector(Connector):
    """EC "Have your say" — consultations, calls for evidence, planned initiatives.

    Table 18 calls this "the earliest formal indicator of a coming rule". It is
    what distinguishes a Later-horizon topic with a real policy trajectory from
    one that is merely being talked about (§4.8).
    """

    default_tier = 1
    ENDPOINT = "https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        size = int(self.params.get("size", 50))
        pages = int(self.params.get("pages", 2))

        for page in range(pages):
            resp = self.get(endpoint, params={"size": size, "page": page, "language": "EN"})
            if resp is None:
                return
            try:
                payload = resp.json()
            except ValueError:
                log.warning("Have your say returned non-JSON")
                return
            page_obj = payload.get("initiativeResultDtoPage") or {}
            items = page_obj.get("content") or []
            if not items:
                return

            for item in items:
                title = clean_text(item.get("shortTitle") or "")
                if not title:
                    # `initiativeTranslations` is a flat list of
                    # {field, language, value}, not a per-language object.
                    for tr in item.get("initiativeTranslations") or []:
                        if tr.get("field") == "SHORT_TITLE" and (tr.get("language") or "").upper() == "EN":
                            title = clean_text(tr.get("value") or "")
                            break
                if not title:
                    continue

                # The search payload carries no publication date of its own; the
                # dates live on the current status. `feedbackStartDate` is when
                # the consultation opened, which is the item's date as evidence.
                statuses = item.get("currentStatuses") or []
                current = next((s for s in statuses if s.get("isCurrent")), statuses[0] if statuses else {})
                published = parse_date(str(current.get("feedbackStartDate") or "")[:10].replace("/", "-"))
                if not self.in_window(published, reference_date, since_days):
                    continue

                # `feedbackEndDate` is a DATED OBLIGATION, and §4.8 derives the
                # Now horizon from exactly that: a dated deadline inside twelve
                # months. Carrying it through is the difference between "there is
                # a consultation" and "it closes on 28 September".
                deadline = parse_date(str(current.get("feedbackEndDate") or "")[:10].replace("/", "-"))

                reference = item.get("reference") or item.get("id")
                topics = [t.get("label") if isinstance(t, dict) else str(t)
                          for t in (item.get("topics") or [])]
                yield CollectedItem(
                    source_id=self.source_id,
                    url="https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/"
                        f"{reference}",
                    title=title,
                    published_at=published,
                    extract=self.clip(title),
                    publisher="ec.europa.eu",
                    language="en",
                    geographies=["EU"],
                    signal_type_hint="regulation",
                    attributes={
                        "reference": reference,
                        # Stage drives horizon derivation: a consultation is a
                        # Later signal, an adopted act is Now/Next (§4.8).
                        "instrument_stage": "consultation",
                        "initiative_status": item.get("initiativeStatus"),
                        "foreseen_act_type": item.get("foreseenActType"),
                        "feedback_status": current.get("receivingFeedbackStatus"),
                        "deadline": deadline.isoformat() if deadline else None,
                        "topics": [t for t in topics if t][:6],
                    },
                    payload={"reference": reference, "shortTitle": title},
                )


@register("cordis")
class CordisConnector(Connector):
    """CORDIS — EU-funded research projects, via the public search API.

    Table 20: "shows what Europe has decided to fund, often with Orange or its
    partners as participants". The bulk download referenced in the source
    catalogue is 139 MB; this search endpoint returns the same corpus filtered,
    which suits a per-refresh cadence far better.
    """

    default_tier = 1
    ENDPOINT = "https://cordis.europa.eu/api/search/results"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        num = int(self.params.get("num", 20))

        for query in self.params.get("queries") or []:
            # Without the contenttype filter the endpoint returns mostly
            # `result` records (journal articles), which carry no project dates
            # and duplicate what OpenAlex already covers. Projects are the point
            # here: they are what Europe has decided to FUND.
            resp = self.get(endpoint, params={
                "q": f"{query} AND contenttype=project", "format": "json", "p": 1, "num": num,
            })
            if resp is None:
                continue
            try:
                payload = resp.json()
            except ValueError:
                log.warning("CORDIS returned non-JSON for %r", query)
                continue
            if not payload.get("status"):
                log.warning("CORDIS rejected query %r", query)
                continue

            body = payload.get("payload") or {}
            hits = body.get("results") or []
            for hit in hits if isinstance(hits, list) else []:
                title = clean_text(str(hit.get("title") or ""))
                if not title:
                    continue
                published = _cordis_date(hit.get("startDate")) or _cordis_date(hit.get("lastUpdateDate"))
                if not self.in_window(published, reference_date, since_days):
                    continue
                project_id = hit.get("id") or hit.get("rcn")
                yield CollectedItem(
                    source_id=self.source_id,
                    url=f"https://cordis.europa.eu/project/id/{project_id}" if project_id
                        else f"https://cordis.europa.eu/search?q={query}",
                    title=title,
                    published_at=published,
                    extract=self.clip(str(hit.get("teaser") or title)),
                    publisher="cordis.europa.eu",
                    language="en",
                    geographies=["EU"],
                    signal_type_hint="technology_maturity",
                    attributes={
                        "query": query,
                        "rcn": hit.get("rcn"),
                        "acronym": hit.get("acronym"),
                        "programme": hit.get("programme"),
                        "reference": hit.get("reference"),
                        "end_date": (_cordis_date(hit.get("endDate")).isoformat()
                                     if _cordis_date(hit.get("endDate")) else None),
                        "total_matching": body.get("total"),
                    },
                    payload={"id": project_id, "title": title, "acronym": hit.get("acronym")},
                )


_CORDIS_MONTH_RE = re.compile(r"^\s*(\d{1,2})\s*\{\{month_(\d{1,2})\}\}\s*(\d{4})\s*$")


def _cordis_date(value: Any) -> dt.date | None:
    """Parse CORDIS's dates.

    The API leaks its own localisation template into the payload and returns
    dates as `1 {{month_11}} 2023` — the month placeholder is never substituted.
    `parse_date` cannot read that, so every CORDIS item was silently rejected as
    undated (DR-04) and the connector returned nothing at all.
    """
    if value is None:
        return None
    text = str(value)
    match = _CORDIS_MONTH_RE.match(text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    return parse_date(text)


@register("uk_contracts")
class UkContractsConnector(Connector):
    """UK Contracts Finder, via its OCDS search endpoint.

    §4.3.3 names Contracts Finder as one of the national equivalents that extend
    procurement coverage below the EU threshold. It also widens the radar's
    geography beyond the EU, which matters because §2.6 makes urgency
    jurisdiction-specific and Orange has teams in 65 countries.

    Releases carry a CPV classification, so UK tenders join the SAME crosswalk
    as TED without any additional mapping work.
    """

    default_tier = 1
    ENDPOINT = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        limit = int(self.params.get("limit_per_query", 50))
        start = reference_date - dt.timedelta(days=since_days)

        for keyword in self.params.get("keywords") or [""]:
            params: dict[str, Any] = {
                "stages": "tender",
                "limit": limit,
                "publishedFrom": start.isoformat(),
                "publishedTo": reference_date.isoformat(),
            }
            if keyword:
                params["keyword"] = keyword
            resp = self.get(endpoint, params=params)
            if resp is None:
                continue
            try:
                releases = resp.json().get("releases", [])
            except ValueError:
                log.warning("Contracts Finder returned non-JSON for %r", keyword)
                continue

            for release in releases:
                tender = release.get("tender") or {}
                title = clean_text(str(tender.get("title") or ""))
                published = parse_date(tender.get("datePublished") or release.get("date"))
                if not title or not self.in_window(published, reference_date, since_days):
                    continue

                classifications = [tender.get("classification") or {}]
                classifications += tender.get("additionalClassifications") or []
                cpv = [
                    str(c.get("id")) for c in classifications
                    if isinstance(c, dict) and c.get("scheme") == "CPV" and c.get("id")
                ]
                value = (tender.get("value") or {})
                buyer = (release.get("buyer") or {}).get("name")
                ocid = release.get("ocid") or ""

                yield CollectedItem(
                    source_id=self.source_id,
                    url=f"https://www.contractsfinder.service.gov.uk/notice/{ocid}" if ocid
                        else "https://www.contractsfinder.service.gov.uk/",
                    title=title,
                    published_at=published,
                    extract=self.clip(f"{title} — {clean_text(str(tender.get('description') or ''))}"),
                    publisher="contractsfinder.service.gov.uk",
                    language="en",
                    geographies=["GB"],
                    signal_type_hint="buying_signal",
                    attributes={
                        "keyword": keyword,
                        "cpv": list(dict.fromkeys(cpv)),
                        "buyer_name": buyer,
                        "ocid": ocid,
                        "status": tender.get("status"),
                        "procurement_category": tender.get("mainProcurementCategory"),
                        # Currency is recorded rather than converted: §4.4.4's
                        # no-invented-numbers rule applies to us too, and a made-up
                        # FX rate would be exactly that.
                        "value_amount": value.get("amount"),
                        "value_currency": value.get("currency"),
                    },
                    payload={"ocid": ocid, "title": title},
                )


@register("crossref")
class CrossrefConnector(Connector):
    """Crossref — scholarly metadata across publishers.

    Complements OpenAlex rather than duplicating it: Crossref indexes the
    publisher record directly, so it surfaces conference and industry-track work
    that the open-access-weighted corpora under-represent. Table 20 wants
    research volume and velocity as a leading indicator; two independent
    scholarly sources also improve publisher diversity (SC-03).
    """

    default_tier = 1
    ENDPOINT = "https://api.crossref.org/works"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        rows = int(self.params.get("rows", 20))
        window = int(self.params.get("since_days", since_days))
        start = reference_date - dt.timedelta(days=window)
        mailto = self.params.get("mailto") or ""

        for query in self.params.get("queries") or []:
            resp = self.get(endpoint, params={
                "query": query,
                "rows": rows,
                "filter": f"from-pub-date:{start.isoformat()},until-pub-date:{reference_date.isoformat()}",
                "select": "DOI,title,abstract,published,container-title,publisher,type",
                "mailto": mailto,
            })
            if resp is None:
                continue
            try:
                items = resp.json().get("message", {}).get("items", [])
            except ValueError:
                log.warning("Crossref returned non-JSON for %r", query)
                continue

            for item in items:
                titles = item.get("title") or []
                title = clean_text(titles[0] if titles else "")
                if not title:
                    continue
                parts = ((item.get("published") or {}).get("date-parts") or [[]])[0]
                published = None
                if parts:
                    padded = list(parts) + [1, 1]
                    try:
                        published = dt.date(int(padded[0]), int(padded[1]), int(padded[2]))
                    except (ValueError, TypeError):
                        published = None
                if not self.in_window(published, reference_date, window):
                    continue
                doi = item.get("DOI")
                container = (item.get("container-title") or [""])[0]
                yield CollectedItem(
                    source_id=self.source_id,
                    url=f"https://doi.org/{doi}" if doi else "https://www.crossref.org/",
                    title=title,
                    published_at=published,
                    extract=self.clip(clean_text(str(item.get("abstract") or title))),
                    # The journal or conference is the real publisher here, which
                    # keeps diversity honest rather than collapsing everything to
                    # "crossref.org".
                    publisher=clean_text(container) or item.get("publisher") or "crossref.org",
                    language="en",
                    signal_type_hint="technology_maturity",
                    attributes={"query": query, "doi": doi, "type": item.get("type"),
                                "container": clean_text(container)},
                    payload={"DOI": doi, "title": title},
                )
