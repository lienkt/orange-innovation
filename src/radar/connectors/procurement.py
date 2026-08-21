"""Procurement connectors (§4.3.3).

"This is, in our view, the single highest-leverage source that a conventional
trend-scanning approach would miss, and it deserves a connector in Sprint 1."

TED is not a proxy for demand — it IS demand, with a budget attached, in a
structured format. Contract AWARD notices additionally reveal who is winning,
which feeds the competitive side of right-to-win.

Every TED item is emitted with `signal_type_hint = "buying_signal"`: unlike a
news article, there is no ambiguity about what a tender notice is, so the
classifier in stage 3 is bypassed and the LLM never gets asked a question that
already has a deterministic answer (Table 23).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Iterator

from .base import CollectedItem, Connector, clean_text, parse_date, register, to_alpha2

log = logging.getLogger(__name__)


@register("ted")
class TedConnector(Connector):
    """TED (Tenders Electronic Daily) search API v3."""

    default_tier = 1
    ENDPOINT = "https://api.ted.europa.eu/v3/notices/search"

    FIELDS = [
        "publication-number",
        "notice-title",
        "publication-date",
        "buyer-country",
        "buyer-name",
        "classification-cpv",
        "total-value",
        "notice-type",
        # Award notices name who won. 1,691 of the first corpus's 3,788 TED
        # notices were awards (can-standard, can-modif, can-social) and every
        # one of them was parsed with the winner discarded, because these three
        # fields were never requested. §4.3.3: "contract AWARD notices reveal
        # who is winning, which feeds the competitive side of right-to-win" —
        # and competitive intensity was left marking a competitor "evidenced"
        # only when its name appeared in a news article, when a dated public
        # award record was available in a response already being downloaded.
        "winner-name",
        "organisation-name-tenderer",
        "winner-decision-date",
    ]

    #: Notice types that carry an award. Prefix match — TED has can-standard,
    #: can-modif, can-social, can-desg and adds more over time.
    AWARD_PREFIX = "can"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        """Collect tender notices, sliced by time window.

        TED's search API accepts NO sort parameter and returns results in
        publication-date ASCENDING order. A broad CPV query over 90 days matches
        tens of thousands of notices (72000000 alone returned 14,485), so a
        single capped request yields only the oldest day in the window — 182 of
        218 notices from one date, in the first live run.

        That is a sampling failure, not merely a volume limit: procurement is
        the highest-value signal category (§4.3.3), and momentum (§4.6) is the
        slope of signal volume over trailing periods. Feeding it a corpus
        clustered on one date makes every procurement-driven momentum figure
        meaningless.

        So the window is sliced and each slice queried separately. Every slice
        contributes its own notices, which gives even temporal coverage across
        the window and makes the resulting volume series honest. Token-based
        iteration (`iterationNextToken`) exists and works, but walking to the
        recent end of a 14,485-notice result set costs hundreds of requests for
        data a narrow slice returns directly.
        """
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        limit = int(self.params.get("limit_per_slice", self.params.get("limit_per_query", 20)))
        slice_days = max(1, int(self.params.get("window_slice_days", 14)))
        below_floor = 0

        for group in self.params.get("cpv_groups") or []:
            cpv_list = ", ".join(group["cpv"])
            # Walk backwards from the reference date so the most recent slice is
            # fetched first; if a run is cut short, what survives is the recent
            # end, which is the part a radar needs most.
            offset = 0
            while offset < since_days:
                slice_end = reference_date - dt.timedelta(days=offset)
                slice_start = max(
                    reference_date - dt.timedelta(days=since_days),
                    slice_end - dt.timedelta(days=slice_days - 1),
                )
                offset += slice_days

                # Absolute dates rather than today(-n): a replay must query the
                # window around the reference date, not around now (FR-35).
                # TED accepts dates only as YYYYMMDD; an ISO date with dashes is
                # rejected with HTTP 400.
                query = (
                    f"classification-cpv IN ({cpv_list}) "
                    f"AND publication-date >= {slice_start.strftime('%Y%m%d')} "
                    f"AND publication-date <= {slice_end.strftime('%Y%m%d')}"
                )
                resp = self.post(
                    endpoint,
                    json={"query": query, "limit": limit, "fields": self.FIELDS},
                    headers={"Content-Type": "application/json"},
                )
                if resp is None:
                    # Circuit breaker or a hard failure — stop hammering TED.
                    return
                try:
                    payload = resp.json()
                except ValueError:
                    log.warning("TED returned non-JSON for CPV group %s", group.get("label"))
                    continue

                notices = payload.get("notices", [])
                total = payload.get("totalNoticeCount")
                if total and total > limit:
                    # NFR-08 / §4.12: a silent cap reads as "we covered
                    # everything". Say what was dropped.
                    log.info("TED %s %s..%s: sampled %d of %d matching notices",
                             group.get("label"), slice_start, slice_end, len(notices), total)

                for notice in notices:
                    item = self._to_item(notice, group, reference_date, since_days)
                    if item is None:
                        continue
                    if self._below_value_floor(item):
                        below_floor += 1
                        continue
                    item.attributes["sampled_from_total"] = total
                    yield item

        if below_floor:
            log.info("TED: %d notices dropped below the %s EUR disclosed-value floor",
                     below_floor, self.params.get("min_value_eur"))

    def _below_value_floor(self, item: CollectedItem) -> bool:
        """Drop small disclosed contracts; never drop an undisclosed one.

        A €4,000 printer maintenance contract is a procurement record, not a
        market signal, and TED is already the noisiest high-volume source in the
        corpus — 52% of signals, 33% passing the relevance gate, 8% attaching to
        a topic. The floor is deliberately ASYMMETRIC: roughly a third of TED
        notices disclose no value at all, and treating "not disclosed" as "small"
        would silently delete the large framework agreements that disclose least
        often. Only a value we can actually read is allowed to disqualify a
        notice, and what that removed is logged.
        """
        floor = self.params.get("min_value_eur")
        if not floor:
            return False
        value = item.attributes.get("total_value_eur")
        return isinstance(value, (int, float)) and value < float(floor)

    def _to_item(self, notice: dict[str, Any], group: dict[str, Any],
                 reference_date: dt.date, since_days: int) -> CollectedItem | None:
        pub_number = notice.get("publication-number")
        if not pub_number:
            return None
        published = parse_date(notice.get("publication-date"))
        if not self.in_window(published, reference_date, since_days):
            return None

        title = _pick_language(notice.get("notice-title"))
        if not title:
            return None
        buyer = _pick_language(notice.get("buyer-name"))

        # FR-28, at no extra cost. TED returns `notice-title` as a dict keyed by
        # language and the English one is taken above; the rest were downloaded
        # and thrown away. Carrying one local-language title into the extract
        # gives the multilingual relevance gate something to match on when the
        # English rendering is generic boilerplate and the local one names the
        # actual subject.
        local_language, local_title = _pick_non_english(notice.get("notice-title"))

        countries = [to_alpha2(c) for c in _as_list(notice.get("buyer-country"))]
        # TED repeats CPV codes across lots; order-preserving dedup keeps the
        # main-object code first, which is the one the crosswalk should weight.
        cpv_codes = list(dict.fromkeys(str(c) for c in _as_list(notice.get("classification-cpv"))))

        notice_type = str(notice.get("notice-type") or "")
        value = notice.get("total-value")
        if isinstance(value, list):
            value = next((v for v in value if isinstance(v, (int, float))), None)

        attributes: dict[str, Any] = {
            "publication_number": pub_number,
            "cpv": cpv_codes,
            "cpv_group": group.get("label"),
            "use_case_hint": group.get("use_case"),
            "buyer_name": buyer,
            "buyer_country": countries,
            "notice_type": notice_type,
        }
        # A zero total-value is TED's "not disclosed", not a €0 contract.
        if isinstance(value, (int, float)) and value > 0:
            attributes["total_value_eur"] = value

        if notice_type.startswith(self.AWARD_PREFIX):
            winners = _names(notice.get("winner-name")) or _names(notice.get("organisation-name-tenderer"))
            if winners:
                attributes["winners"] = winners
                attributes["is_award"] = True
            decided = _as_list(notice.get("winner-decision-date"))
            award_date = next((d for d in (parse_date(x) for x in decided) if d), None)
            if award_date:
                attributes["award_decision_date"] = award_date.isoformat()

        if local_title and local_language:
            attributes["local_title"] = local_title
            attributes["local_title_language"] = local_language

        extract = f"{title}"
        if buyer:
            extract += f" — contracting authority: {buyer}"
        winners = attributes.get("winners") or []
        if winners:
            extract += f" — awarded to: {', '.join(winners[:4])}"
        if cpv_codes:
            extract += f" [CPV {', '.join(cpv_codes[:4])}]"
        if local_title and local_title.lower() != title.lower():
            extract += f" · {local_title}"

        return CollectedItem(
            source_id=self.source_id,
            url=f"https://ted.europa.eu/en/notice/-/detail/{pub_number}",
            title=clean_text(title),
            published_at=published,
            extract=self.clip(extract),
            publisher="ted.europa.eu",
            # The stored title and most of the extract are English, so that is
            # what the record says. The local title travels in `attributes`
            # rather than relabelling the whole signal (NFR-08 counts languages
            # from this field, and inflating it would make coverage a fiction).
            language="en",
            geographies=self.geographies_for([c for c in countries if c]),
            signal_type_hint="buying_signal",
            attributes=attributes,
            payload=notice,
        )


def _pick_language(value: Any, preferred: tuple[str, ...] = ("eng", "fra", "deu", "nld")) -> str:
    """TED returns multilingual dicts keyed by 3-letter language code."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return _pick_language(value[0]) if value else ""
    if isinstance(value, dict):
        for lang in preferred:
            if lang in value:
                return _pick_language(value[lang])
        for candidate in value.values():
            text = _pick_language(candidate)
            if text:
                return text
    return ""


#: TED language codes worth carrying as the local title, in preference order.
_LOCAL_LANGUAGES = ("fra", "deu", "nld", "spa", "ita")

#: TED 3-letter codes -> the 2-letter codes used everywhere else in the radar.
_TED_LANGUAGE_ALPHA2 = {"fra": "fr", "deu": "de", "nld": "nl", "spa": "es", "ita": "it", "eng": "en"}


def _pick_non_english(value: Any) -> tuple[str, str]:
    """Return (alpha-2 language, title) for one local-language rendering."""
    if not isinstance(value, dict):
        return "", ""
    for code in _LOCAL_LANGUAGES:
        if code in value:
            text = _pick_language(value[code], preferred=(code,))
            if text:
                return _TED_LANGUAGE_ALPHA2[code], clean_text(text)
    return "", ""


def _names(value: Any) -> list[str]:
    """Flatten TED's multilingual name fields into a deduplicated name list.

    `winner-name` arrives as {"pol": ["A", "B", "B"]} — one entry per lot, so
    the same winner repeats. Order-preserving dedup keeps the first mention.
    """
    collected: list[str] = []
    if isinstance(value, dict):
        for code in ("eng",) + _LOCAL_LANGUAGES:
            if code in value:
                collected = _as_list(value[code])
                break
        else:
            for candidate in value.values():
                collected = _as_list(candidate)
                if collected:
                    break
    else:
        collected = _as_list(value)

    out: list[str] = []
    seen: set[str] = set()
    for name in collected:
        cleaned = clean_text(str(name))
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            out.append(cleaned)
    return out


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


@register("ocds_releases")
class OcdsReleasesConnector(Connector):
    """Any OCDS release-package endpoint, cursor-paginated.

    Written generic because OCDS is the point of OCDS: UK Find a Tender is the
    first user, but a second national portal publishing the same standard costs
    a config block rather than a connector.

    WHY FIND A TENDER MATTERS. Contracts Finder — already wired — carries only
    BELOW-threshold UK notices. Find a Tender is the post-Brexit replacement for
    TED above the threshold, so the entire above-threshold UK market was
    invisible to the radar: 63 Contracts Finder signals stood in for a whole
    jurisdiction. §2.6 makes urgency jurisdiction-specific, so a missing
    jurisdiction is a missing answer, not a smaller sample.

    Releases carry CPV under `tender.items[].additionalClassifications`, so they
    join the SAME crosswalk as TED with no new mapping (LK-02).

    The API takes no keyword parameter, so relevance is decided here against the
    configured CPV prefixes rather than by the server. That is honest but blunt,
    and what it drops is logged.
    """

    default_tier = 1
    ENDPOINT = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        limit = int(self.params.get("limit_per_page", 100))
        max_pages = int(self.params.get("max_pages", 8))
        prefixes = tuple(str(c) for c in self.params.get("cpv_prefixes") or ())
        start = reference_date - dt.timedelta(days=since_days)

        url: str | None = endpoint
        params: dict[str, Any] | None = {
            "limit": limit,
            "updatedFrom": start.strftime("%Y-%m-%dT00:00:00"),
            "updatedTo": reference_date.strftime("%Y-%m-%dT23:59:59"),
        }
        if self.params.get("stages"):
            params["stages"] = self.params["stages"]

        seen_off_topic = 0
        for _ in range(max_pages):
            resp = self.get(url, params=params)
            if resp is None:
                break
            try:
                payload = resp.json()
            except ValueError:
                log.warning("%s returned non-JSON", self.source_id)
                break

            releases = payload.get("releases") or []
            if not releases:
                break
            for release in releases:
                item = self._to_item(release, reference_date, since_days, prefixes)
                if item is None:
                    seen_off_topic += 1
                    continue
                yield item

            # The cursor is a full URL and already carries its own query string.
            url = (payload.get("links") or {}).get("next")
            params = None
            if not url:
                break

        if seen_off_topic:
            log.info("%s: %d releases skipped (outside the configured CPV prefixes or undated)",
                     self.source_id, seen_off_topic)

    def _to_item(self, release: dict[str, Any], reference_date: dt.date, since_days: int,
                 prefixes: tuple[str, ...]) -> CollectedItem | None:
        tender = release.get("tender") or {}
        title = clean_text(str(tender.get("title") or ""))
        published = parse_date(release.get("date"))
        if not title or not self.in_window(published, reference_date, since_days):
            return None

        cpv = _ocds_cpv(tender)
        if prefixes and not any(code.startswith(prefixes) for code in cpv):
            return None

        buyer = next(
            (p.get("name") for p in (release.get("parties") or []) if "buyer" in (p.get("roles") or [])),
            None,
        )
        # An award release names the supplier — the same right-to-win evidence
        # TED's `winner-name` gives, in OCDS vocabulary.
        winners: list[str] = []
        for award in release.get("awards") or []:
            for supplier in award.get("suppliers") or []:
                name = clean_text(str(supplier.get("name") or ""))
                if name and name not in winners:
                    winners.append(name)

        value = tender.get("value") or {}
        ocid = release.get("ocid") or ""
        extract = title
        description = clean_text(str(tender.get("description") or ""))
        if description and description.lower() not in title.lower():
            extract += f" — {description}"
        if buyer:
            extract += f" — contracting authority: {buyer}"
        if winners:
            extract += f" — awarded to: {', '.join(winners[:4])}"
        if cpv:
            extract += f" [CPV {', '.join(cpv[:4])}]"

        attributes: dict[str, Any] = {
            "ocid": ocid,
            "cpv": cpv,
            "buyer_name": buyer,
            "tags": release.get("tag") or [],
            "status": tender.get("status"),
        }
        if winners:
            attributes["winners"] = winners
            attributes["is_award"] = True
        # Currency is recorded, never converted: §4.4.4's no-invented-numbers
        # rule applies to us, and a made-up FX rate would be exactly that.
        if isinstance(value.get("amount"), (int, float)):
            attributes["value_amount"] = value["amount"]
            attributes["value_currency"] = value.get("currency")

        detail = self.params.get("notice_url_template", "")
        return CollectedItem(
            source_id=self.source_id,
            url=detail.format(ocid=ocid) if detail and ocid else (release.get("url") or self.ENDPOINT),
            title=title,
            published_at=published,
            extract=self.clip(extract),
            publisher=self.params.get("publisher") or "find-tender.service.gov.uk",
            language=self.params.get("language", "en"),
            geographies=self.geographies_for(),
            signal_type_hint="buying_signal",
            attributes=attributes,
            payload={"ocid": ocid, "title": title, "tag": release.get("tag")},
        )


def _ocds_cpv(tender: dict[str, Any]) -> list[str]:
    """CPV codes from wherever this publisher put them.

    OCDS allows classification at tender, lot and item level, and Find a Tender
    uses `items[].additionalClassifications` while others use
    `tender.classification`. Reading all three keeps the connector portable.
    """
    codes: list[str] = []

    def take(entry: Any) -> None:
        if isinstance(entry, dict) and entry.get("scheme") == "CPV" and entry.get("id"):
            code = str(entry["id"])
            if code not in codes:
                codes.append(code)

    take(tender.get("classification"))
    for entry in tender.get("additionalClassifications") or []:
        take(entry)
    for container in list(tender.get("items") or []) + list(tender.get("lots") or []):
        if not isinstance(container, dict):
            continue
        take(container.get("classification"))
        for entry in container.get("additionalClassifications") or []:
            take(entry)
    return codes


@register("tenderned")
class TenderNedConnector(Connector):
    """TenderNed — Dutch national procurement, via the open publications API.

    §4.3.3 asks for national equivalents that extend procurement coverage below
    the EU threshold; BOAMP proved the pattern for France and this is the Dutch
    one. It also repairs a geography skew the first corpus created by accident:
    Poland was the single largest represented country at 802 signals purely
    because TED's CPV roots happened to match Polish notices, not because Poland
    is the most interesting market.

    The API accepts no working keyword filter — `trefwoord` and `zoekwoorden`
    both return the unfiltered 145,067-record set — so subject filtering happens
    here, against the Dutch half of config/taxonomy/lexicon.yaml. Without that
    lexicon this connector would be pointless: every title is in Dutch and the
    English relevance gate would drop the lot, which is exactly what happened to
    BOAMP (289 collected, 23 relevant).
    """

    default_tier = 1
    ENDPOINT = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"

    def collect(self, reference_date: dt.date, since_days: int) -> Iterator[CollectedItem]:
        endpoint = self.params.get("endpoint", self.ENDPOINT)
        size = int(self.params.get("page_size", 100))
        max_pages = int(self.params.get("max_pages", 10))
        terms = [str(t).lower() for t in self.params.get("subject_terms") or ()]

        off_topic = 0
        for page in range(max_pages):
            resp = self.get(endpoint, params={"page": page, "size": size})
            if resp is None:
                break
            try:
                payload = resp.json()
            except ValueError:
                log.warning("TenderNed returned non-JSON on page %d", page)
                break

            records = payload.get("content") or []
            if not records:
                break
            stop = False
            for record in records:
                published = parse_date(record.get("publicatieDatum"))
                if published is None:
                    continue
                # Records come newest first, so once the window is passed there
                # is nothing older worth paging for.
                if published < reference_date - dt.timedelta(days=since_days):
                    stop = True
                    break
                if not self.in_window(published, reference_date, since_days):
                    continue

                title = clean_text(str(record.get("aanbestedingNaam") or ""))
                description = clean_text(str(record.get("opdrachtBeschrijving") or ""))
                if not title:
                    continue
                haystack = f"{title} {description}".lower()
                if terms and not any(term in haystack for term in terms):
                    off_topic += 1
                    continue

                buyer = clean_text(str(record.get("opdrachtgeverNaam") or ""))
                publication_id = str(record.get("publicatieId") or "")
                extract = title
                if description:
                    extract += f" — {description}"
                if buyer:
                    extract += f" — aanbestedende dienst: {buyer}"

                # `link` is an object, not a string: {"href": ..., "title": "self"}.
                link = record.get("link")
                if isinstance(link, dict):
                    link = link.get("href")

                yield CollectedItem(
                    source_id=self.source_id,
                    url=str(link) if link else
                        f"https://www.tenderned.nl/aankondigingen/overzicht/{publication_id}",
                    title=title,
                    published_at=published,
                    extract=self.clip(extract),
                    publisher="tenderned.nl",
                    language="nl",
                    geographies=self.geographies_for(),
                    signal_type_hint="buying_signal",
                    attributes={
                        "publication_id": publication_id,
                        "buyer_name": buyer,
                        "publication_type": (record.get("typePublicatie") or {}).get("omschrijving"),
                        "contract_type": (record.get("typeOpdracht") or {}).get("omschrijving"),
                        "above_eu_threshold": record.get("europees"),
                        "closing_date": record.get("sluitingsDatum"),
                    },
                    payload={"publicatieId": publication_id, "aanbestedingNaam": title},
                )
            if stop:
                break

        if off_topic:
            log.info("TenderNed: %d notices skipped as off-subject against the Dutch lexicon", off_topic)
