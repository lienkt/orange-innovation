"""A last-resort HTTP server that explains why the radar did not start.

The platform restarts a container that exits, and on a Free plan fifteen
restarts exhaust the plan's `WP stop requests` quota. Once that happens the site
returns 403 — and so does Kudu, so the logs that would explain the original
failure become unreadable until the quota resets an hour later. A crash loop
therefore destroys its own evidence.

This breaks that cycle. If gunicorn cannot start, `startup.sh` runs this
instead: the container keeps answering on $PORT, so the platform never restarts
it, and the startup log is served over plain HTTPS where it can be read without
Kudu. A deployment that fails visibly is worth far more than one that fails
invisibly and takes the diagnostics with it.
"""

from __future__ import annotations

import html
import os
import platform
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

LOG = Path(os.getenv("RADAR_STARTUP_LOG", "/home/LogFiles/radar-startup.log"))
APP_DIR = Path(os.getenv("APP_DIR", "/home/site/wwwroot"))


def _run(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        return (result.stdout or result.stderr).strip()
    except Exception as exc:  # noqa: BLE001 — diagnostics must never raise
        return f"({' '.join(command)} failed: {exc})"


def diagnostics() -> str:
    def listing(path: Path) -> str:
        try:
            return ", ".join(sorted(p.name for p in path.iterdir())[:40]) or "(empty)"
        except Exception as exc:  # noqa: BLE001
            return f"(unreadable: {exc})"

    sections = {
        "startup log": LOG.read_text(errors="replace")[-8000:] if LOG.is_file() else "(no log written)",
        "python": f"{sys.executable}\n{platform.python_version()} on {platform.platform()}",
        "PATH": os.getenv("PATH", ""),
        "which gunicorn": _run(["bash", "-lc", "command -v gunicorn || echo NOT FOUND"]),
        "which python3": _run(["bash", "-lc", "command -v python3"]),
        "wwwroot": listing(APP_DIR),
        "virtualenvs found": _run(["bash", "-lc",
                                   "ls -d /home/site/wwwroot/antenv /tmp/*/antenv 2>/dev/null || echo none"]),
        "site-packages sample": _run(["bash", "-lc",
                                      "python3 -c 'import sys; print(chr(10).join(sys.path))'"]),
        "import radar.api": _run(["bash", "-lc",
                                  f"cd {APP_DIR} && PYTHONPATH={APP_DIR}/src python3 -c "
                                  f"'import radar.api; print(\"ok\")' 2>&1 | tail -20"]),
        "data dir": listing(Path("/home/data")),
        "env (RADAR_*)": "\n".join(f"{k}={v}" for k, v in sorted(os.environ.items())
                                   if k.startswith("RADAR_")),
    }
    return "\n\n".join(f"===== {name} =====\n{value}" for name, value in sections.items())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — http.server's interface
        body = diagnostics()
        if self.path.startswith("/healthz"):
            payload = b'{"ok": false, "reason": "the application did not start"}'
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
        else:
            payload = (
                "<!doctype html><meta charset=utf-8>"
                "<title>Innovation Radar — startup failed</title>"
                "<style>body{font:13px ui-monospace,monospace;margin:24px;max-width:1100px}"
                "h1{font:600 18px system-ui}pre{white-space:pre-wrap;background:#f6f6f6;"
                "padding:12px;border-radius:6px}</style>"
                "<h1>The radar did not start</h1>"
                "<p>The container is deliberately still running: exiting would make the platform "
                "restart it, and fifteen restarts exhaust the Free plan's quota, which also "
                "disables the log endpoints. Diagnostics below.</p>"
                f"<pre>{html.escape(body)}</pre>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:  # noqa: D102 — quieten the default logging
        pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"fallback: serving diagnostics on :{port}", flush=True)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
