"""Reference data for market sizing (§4.3.4, Table 19).

Table 19 lists Eurostat's ICT-usage survey and Structural Business Statistics as
the two sources that make bottom-up sizing possible: "adoption rates for cloud,
AI, IoT, big data, e-commerce, security measures ... gives both a denominator
for sizing and an adoption gap that is itself an opportunity", and "enterprise
counts, turnover and value added by NACE sector and size class: the denominator
for any bottom-up TAM".

They are deliberately NOT ingested as signals. A signal is a dated event with a
publisher, and every attractiveness component treats it as one — volume,
publisher diversity, momentum, tier. An annual statistical series is none of
those things, and pushing 30,000 Eurostat cells through the signal store would
corrupt every one of those components while adding no discovery value. They are
reference series, on their own cadence, read only by `radar.sizing`.

What is stored per observation is the value and its coordinates, plus the
dataset's own `updated` stamp — enough for any figure to be re-derived and
attributed, and nothing more (DR-08).
"""

from __future__ import annotations

import datetime as dt
import itertools
import logging
from typing import Any, Iterator

import requests

from .config import Config
from .db import Database

log = logging.getLogger(__name__)

EUROSTAT_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"

#: Eurostat publishes the enterprise ICT survey for enterprises with ten or more
#: persons employed only. Recording the code explicitly is what lets the sizing
#: engine assert that its denominator and its adoption rate share a base.
ICT_SIZE_CLASS = "GE10"

#: How many trailing periods to pull. More than one because the sector-level
#: tables are patchy — the IoT breakdown by NACE stops at 2021 while the AI one
#: runs to 2025 — and the sizer picks the most recent year that actually has a
#: value for the cell it needs, then reports that year.
LAST_PERIODS = 3

#: Geographies per request. Eurostat answers a 30-geography query happily, but
#: chunking keeps any single failure small and the payloads reviewable.
GEO_CHUNK = 10


class EurostatError(RuntimeError):
    pass


def _chunks(items: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def decode_jsonstat(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Decode a JSON-stat 2.0 response into flat observations.

    Eurostat returns a sparse value map keyed by the row-major index into the
    dimension grid, so the coordinates have to be reconstructed rather than read.
    Doing it here — once, tested — keeps every caller out of index arithmetic.
    """
    dim_ids: list[str] = payload.get("id") or []
    sizes: list[int] = payload.get("size") or []
    if not dim_ids or len(dim_ids) != len(sizes):
        raise EurostatError("JSON-stat response has no usable dimension header")

    # position -> code, per dimension
    positions: list[dict[int, str]] = []
    for dim_id in dim_ids:
        index = payload["dimension"][dim_id]["category"]["index"]
        if isinstance(index, list):  # single-category dimensions may come as a list
            index = {code: i for i, code in enumerate(index)}
        positions.append({int(pos): code for code, pos in index.items()})

    # Strides for row-major order: the last dimension varies fastest.
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    for flat, value in (payload.get("value") or {}).items():
        if value is None:
            continue
        remainder = int(flat)
        coords: dict[str, str] = {}
        for dim_id, stride, lookup in zip(dim_ids, strides, positions):
            coords[dim_id] = lookup[remainder // stride]
            remainder %= stride
        coords["_value"] = float(value)
        yield coords


class ReferenceDataFetcher:
    """Fetches the sizing denominators and adoption rates into the DB."""

    def __init__(self, cfg: Config, db: Database, session: requests.Session | None = None):
        self.cfg = cfg
        self.db = db
        self.sizing = cfg.sizing
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": cfg.user_agent})
        self.timeout = int(cfg.settings["ingestion"]["request_timeout_seconds"])

    # -- HTTP --------------------------------------------------------------

    def _fetch(self, dataset: str, params: list[tuple[str, str]]) -> dict[str, Any]:
        query = [("format", "JSON"), ("lang", "EN"), ("lastTimePeriod", str(LAST_PERIODS))] + params
        response = self.session.get(EUROSTAT_BASE + dataset, params=query, timeout=self.timeout)
        if response.status_code != 200:
            raise EurostatError(f"{dataset} -> HTTP {response.status_code}: {response.text[:200]}")
        return response.json()

    # -- codes needed, derived from the crosswalk --------------------------

    def _sbs_codes(self) -> list[str]:
        return sorted({row.sbs_nace for rows in self.cfg.vertical_to_nace.values() for row in rows})

    def _ict_codes(self) -> list[str]:
        return sorted({row.ict_nace for rows in self.cfg.vertical_to_nace.values() for row in rows})

    # -- run ---------------------------------------------------------------

    def run(self, series_ids: list[str] | None = None, force: bool = False,
            max_age_days: int = 60) -> dict[str, Any]:
        """Fetch every configured reference series.

        `max_age_days` exists because these are annual statistics: refetching
        them on the discovery cadence costs requests and changes nothing. A
        refresh skips a series that was fetched recently unless asked not to.
        """
        self.db.init_schema()
        geographies = list(self.sizing["scope"]["fetch_geographies"])
        stats: dict[str, Any] = {"series": {}, "skipped": [], "errors": {}}

        for series_id, spec in self.sizing["reference_datasets"].items():
            if series_ids and series_id not in series_ids:
                continue
            if not force and self._is_fresh(series_id, max_age_days):
                stats["skipped"].append(series_id)
                continue
            try:
                if series_id == "sbs":
                    stats["series"][series_id] = self._fetch_sbs(spec, geographies)
                else:
                    stats["series"][series_id] = self._fetch_adoption(series_id, spec, geographies)
            except Exception as exc:  # noqa: BLE001 — one dead series must not fail a refresh
                log.error("Reference series %s failed: %s", series_id, exc)
                stats["errors"][series_id] = str(exc)[:300]
        return stats

    def _is_fresh(self, series_id: str, max_age_days: int) -> bool:
        row = self.db.query_one("SELECT fetched_at FROM reference_series WHERE id = ?", (series_id,))
        if not row or not row["fetched_at"]:
            return False
        try:
            fetched = dt.datetime.fromisoformat(row["fetched_at"]).date()
        except ValueError:
            return False
        return (dt.date.today() - fetched).days < max_age_days

    # -- the two shapes ----------------------------------------------------

    def _fetch_sbs(self, spec: dict[str, Any], geographies: list[str]) -> dict[str, Any]:
        """Enterprise counts and turnover by NACE division, size class and country."""
        nace = self._sbs_codes()
        size_classes = list(self.sizing["scope"]["size_classes"])
        indicators = list(spec["indicators"].values())
        observations: list[tuple] = []
        source_updated = None

        for geo_chunk in _chunks(geographies, GEO_CHUNK):
            params = (
                [("geo", g) for g in geo_chunk]
                + [("nace_r2", n) for n in nace]
                + [("size_emp", s) for s in size_classes]
                + [("indic_sbs", i) for i in indicators]
            )
            payload = self._fetch(spec["dataset"], params)
            source_updated = source_updated or payload.get("updated")
            for row in decode_jsonstat(payload):
                observations.append((
                    "sbs", row["indic_sbs"], row["nace_r2"], row["geo"],
                    row["size_emp"], row["time"], row["_value"],
                    "ENT" if row["indic_sbs"] == spec["indicators"]["enterprises"] else "MEUR",
                ))
        return self._store("sbs", spec, source_updated, observations)

    def _fetch_adoption(self, series_id: str, spec: dict[str, Any],
                        geographies: list[str]) -> dict[str, Any]:
        """Adoption rates, as a percentage of enterprises with 10+ employees."""
        nace = self._ict_codes()
        indicators = list(self.sizing["adoption_indicators"].get(series_id, []))
        if not indicators:
            return {"rows": 0, "note": "no indicators configured"}
        observations: list[tuple] = []
        source_updated = None

        for geo_chunk, indic_chunk in itertools.product(_chunks(geographies, GEO_CHUNK),
                                                        _chunks(indicators, 8)):
            params = (
                [("geo", g) for g in geo_chunk]
                + [("nace_r2", n) for n in nace]
                + [("indic_is", i) for i in indic_chunk]
                + [("unit", spec["unit"])]
            )
            payload = self._fetch(spec["dataset"], params)
            source_updated = source_updated or payload.get("updated")
            for row in decode_jsonstat(payload):
                observations.append((
                    series_id, row["indic_is"], row["nace_r2"], row["geo"],
                    row.get("size_emp", ICT_SIZE_CLASS), row["time"], row["_value"], spec["unit"],
                ))
        return self._store(series_id, spec, source_updated, observations)

    # -- persistence -------------------------------------------------------

    def _store(self, series_id: str, spec: dict[str, Any], source_updated: str | None,
               observations: list[tuple]) -> dict[str, Any]:
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        with self.db.cursor() as cur:
            cur.execute(
                """INSERT INTO reference_series
                       (id, dataset, publisher, label, url, licence, source_updated, fetched_at, rows)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       dataset=excluded.dataset, publisher=excluded.publisher, label=excluded.label,
                       url=excluded.url, licence=excluded.licence,
                       source_updated=excluded.source_updated, fetched_at=excluded.fetched_at,
                       rows=excluded.rows""",
                (series_id, spec["dataset"], spec["publisher"], spec["label"], spec["url"],
                 spec["licence"], source_updated, now, len(observations)),
            )
            cur.executemany(
                """INSERT INTO reference_observations
                       (series_id, indicator, nace, geo, size_class, period, value, unit)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(series_id, indicator, nace, geo, size_class, period)
                   DO UPDATE SET value=excluded.value, unit=excluded.unit""",
                observations,
            )
        log.info("Reference series %s: %d observations (dataset %s, updated %s)",
                 series_id, len(observations), spec["dataset"], source_updated)
        return {
            "dataset": spec["dataset"],
            "rows": len(observations),
            "source_updated": source_updated,
            "fetched_at": now,
        }


def reference_status(db: Database) -> dict[str, Any]:
    """What the sizing engine currently has to work with (NFR-08)."""
    series = [dict(r) for r in db.query("SELECT * FROM reference_series ORDER BY id")]
    for row in series:
        periods = db.query(
            "SELECT period, COUNT(*) n FROM reference_observations WHERE series_id = ? "
            "GROUP BY period ORDER BY period DESC", (row["id"],)
        )
        row["periods"] = {p["period"]: p["n"] for p in periods}
        geos = db.query_one(
            "SELECT COUNT(DISTINCT geo) n FROM reference_observations WHERE series_id = ?", (row["id"],)
        )
        row["geographies"] = geos["n"] if geos else 0
    return {"series": series, "count": len(series)}
