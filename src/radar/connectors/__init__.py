"""Connector registry (pipeline stage 1).

Importing this package registers every connector implementation under the name
used in config/sources.yaml. A source whose `connector` has no implementation is
catalogued but skipped with a warning — config/sources.yaml is the requirements
record (Appendix A), not only the runtime wiring, so it deliberately lists
sources that are not yet built.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import REGISTRY, CollectedItem, Connector, HttpSession, clean_text, parse_date, publisher_from_url
from . import demand, extra, news, procurement, regulation, research, standards  # noqa: F401 — import registers connectors

log = logging.getLogger(__name__)

__all__ = [
    "REGISTRY",
    "CollectedItem",
    "Connector",
    "HttpSession",
    "build_connector",
    "clean_text",
    "parse_date",
    "publisher_from_url",
]


def build_connector(source: dict[str, Any], session: HttpSession, max_extract_chars: int = 1200) -> Connector | None:
    name = source.get("connector")
    cls = REGISTRY.get(name)
    if cls is None:
        log.warning("Source %r requests connector %r, which is not implemented — skipping.",
                    source.get("id"), name)
        return None
    return cls(source, session, max_extract_chars=max_extract_chars)
