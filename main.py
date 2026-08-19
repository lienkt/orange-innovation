"""The entry point Oryx's generated startup script imports.

App Service does not run the deployed tree in place. Oryx builds it, compresses
the result into `output.tar.zst`, and on every container start extracts that
tarball to a fresh `/tmp/<hash>` directory which then becomes the working
directory. `/home/site/wwwroot` holds the tarball and nothing else, and the real
path changes with each deploy, so *no absolute path into wwwroot is valid at
runtime* — not for a startup script, not for PYTHONPATH, not for a module. Five
deployments exited 127 on that.

The only path that survives the indirection is one resolved relative to this
file. That is all this module does: put the sibling `src` on `sys.path` and hand
gunicorn/uvicorn the application. Everything else the app needs — seeding the
database onto /home, fixing its journal mode — lives in `radar.bootstrap` and
runs on import.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from radar.api import app  # noqa: E402 — the path fix above has to come first

__all__ = ["app"]
