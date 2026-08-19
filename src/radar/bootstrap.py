"""Prepare a serving instance's storage, without ever raising at import.

Three facts about Azure App Service shape this module, and each of them broke a
deployment before it was written down:

  * `/home` is the only path that survives a restart, and it is an SMB mount.
    SQLite's WAL needs shared memory that SMB does not provide, so a database
    opened in WAL mode there fails on first write.
  * A container that exits is restarted, and fifteen restarts exhaust a Free
    plan's quota — which then disables Kudu, hiding the logs that would explain
    the original failure. A crash loop destroys its own evidence.
  * Therefore nothing here may raise. A serving process that cannot open its
    database should start, say so, and keep answering: a readable 503 is worth
    more than an invisible restart loop.

The pipeline is unaffected: it runs locally against a local file, in WAL, with
none of this in the path.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import sqlite3
from pathlib import Path

#: Set when preparation failed, and reported by /healthz instead of crashing.
STARTUP_ERROR: str | None = None
STARTUP_NOTES: list[str] = []


def _note(message: str) -> None:
    stamped = f"{dt.datetime.now(dt.timezone.utc):%H:%M:%S} bootstrap: {message}"
    STARTUP_NOTES.append(stamped)
    print(stamped, flush=True)
    log_path = os.getenv("RADAR_STARTUP_LOG")
    if log_path:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(stamped + "\n")
        except OSError:
            pass  # the log is a courtesy; failing to write one must not matter


def prepare(db_path: Path, package_root: Path) -> None:
    """Seed the persistent database and make its journal mode usable.

    Seeds only when the target is missing: a deployment must not discard the
    feedback, assessments, descriptions and briefs that production accumulated.
    """
    global STARTUP_ERROR
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        briefs = os.getenv("RADAR_BRIEF_DIR")
        if briefs:
            Path(briefs).mkdir(parents=True, exist_ok=True)

        seed = package_root / "data" / "radar.db"
        if not db_path.exists() and seed.exists():
            _note(f"seeding {db_path} from {seed} ({seed.stat().st_size / 1048576:.0f} MB)")
            shutil.copy(seed, db_path)
            _note("seed complete")

        packaged_briefs = package_root / "data" / "briefs"
        if briefs and packaged_briefs.is_dir():
            copied = 0
            for pdf in packaged_briefs.glob("*.pdf"):
                target = Path(briefs) / pdf.name
                if not target.exists():
                    shutil.copy(pdf, target)
                    copied += 1
            if copied:
                _note(f"copied {copied} brief(s) into {briefs}")

        if db_path.exists():
            mode = os.getenv("RADAR_SQLITE_JOURNAL_MODE", "WAL").upper()
            connection = sqlite3.connect(db_path, timeout=30)
            try:
                before = connection.execute("PRAGMA journal_mode").fetchone()[0]
                after = connection.execute(f"PRAGMA journal_mode = {mode}").fetchone()[0]
                _note(f"journal mode {before} -> {after}")
            finally:
                connection.close()
        else:
            _note(f"no database at {db_path} — the API will report this rather than crash")
    except Exception as exc:  # noqa: BLE001 — see the module docstring
        STARTUP_ERROR = f"{type(exc).__name__}: {exc}"
        _note(f"FAILED: {STARTUP_ERROR}")
