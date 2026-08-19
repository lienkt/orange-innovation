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
    ]

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
                    if item is not None:
                        item.attributes["sampled_from_total"] = total
                        yield item

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

        countries = [to_alpha2(c) for c in _as_list(notice.get("buyer-country"))]
        # TED repeats CPV codes across lots; order-preserving dedup keeps the
        # main-object code first, which is the one the crosswalk should weight.
        cpv_codes = list(dict.fromkeys(str(c) for c in _as_list(notice.get("classification-cpv"))))

        value = notice.get("total-value")
        attributes: dict[str, Any] = {
            "publication_number": pub_number,
            "cpv": cpv_codes,
            "cpv_group": group.get("label"),
            "buyer_name": buyer,
            "buyer_country": countries,
            "notice_type": notice.get("notice-type"),
        }
        # A zero total-value is TED's "not disclosed", not a €0 contract.
        if isinstance(value, (int, float)) and value > 0:
            attributes["total_value_eur"] = value

        extract = f"{title}"
        if buyer:
            extract += f" — contracting authority: {buyer}"
        if cpv_codes:
            extract += f" [CPV {', '.join(cpv_codes[:4])}]"

        return CollectedItem(
            source_id=self.source_id,
            url=f"https://ted.europa.eu/en/notice/-/detail/{pub_number}",
            title=clean_text(title),
            published_at=published,
            extract=self.clip(extract),
            publisher="ted.europa.eu",
            language="en",
            geographies=[c for c in countries if c],
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


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
