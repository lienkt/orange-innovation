#!/usr/bin/env bash
# App Service startup (mirrors the railpulse deployment's `bash startup.sh`).
#
# The database and the generated briefs live under /home, which is the only
# persistent, shared-across-restarts path on Linux App Service. Everything else
# in the container is replaced on each deploy, so a brief generated at 14:00
# would vanish at the next push if it were written beside the code.
set -uo pipefail

APP_DIR="/home/site/wwwroot"
DATA_DIR="/home/data"
LOG_DIR="/home/LogFiles"
mkdir -p "$DATA_DIR/briefs" "$LOG_DIR"

# Everything below is echoed to /home/LogFiles as well as stdout. When a boot
# fails, App Service takes the container away and the platform log with it,
# while /home survives — the first attempt at this deployment died in a restart
# loop that left nothing readable, because the plan was quota-blocked by the
# loop itself.
exec > >(tee -a "$LOG_DIR/radar-startup.log") 2>&1
echo "=== startup $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "python: $(python3 -V 2>&1) · pwd: $(pwd) · PORT=${PORT:-unset}"

# Seed the read-only corpus on first boot, then leave it alone: the deployed
# database accumulates feedback, assessments, descriptions and briefs, and a
# deploy must not throw those away.
if [ ! -f "$DATA_DIR/radar.db" ] && [ -f "$APP_DIR/data/radar.db" ]; then
  echo "startup: seeding $DATA_DIR/radar.db from the deployment package"
  cp "$APP_DIR/data/radar.db" "$DATA_DIR/radar.db"
fi
if [ -d "$APP_DIR/data/briefs" ]; then
  cp -n "$APP_DIR/data/briefs/"*.pdf "$DATA_DIR/briefs/" 2>/dev/null || true
fi

# /home is an SMB (Azure Files) mount, and SQLite's WAL needs shared memory the
# protocol cannot provide: opening a WAL database there fails, and because the
# API calls init_schema() at import, that failure takes the worker with it and
# the platform restarts it until the plan's restart quota is spent. The classic
# rollback journal works on SMB, so the seeded copy is converted once and the
# app is told to keep using it (see RADAR_SQLITE_JOURNAL_MODE in db.py).
export RADAR_SQLITE_JOURNAL_MODE="${RADAR_SQLITE_JOURNAL_MODE:-DELETE}"
python3 - "$DATA_DIR/radar.db" <<'PYEOF'
import sqlite3, sys
path = sys.argv[1]
con = sqlite3.connect(path, timeout=30)
before = con.execute("PRAGMA journal_mode").fetchone()[0]
after = con.execute("PRAGMA journal_mode = DELETE").fetchone()[0]
con.close()
print(f"startup: journal mode {before} -> {after}")
PYEOF

export PYTHONPATH="$APP_DIR/src:${PYTHONPATH:-}"

# Oryx installs the dependencies into a virtualenv and the platform's DEFAULT
# startup activates it. A custom startup command does not get that for free, so
# `gunicorn` is simply not on PATH and the script dies before it prints anything
# useful — which is what the first two attempts did. Local testing missed it
# because a venv was already active there.
for CANDIDATE in "$APP_DIR/antenv" /tmp/*/antenv; do
  if [ -f "$CANDIDATE/bin/activate" ]; then
    echo "startup: activating virtualenv $CANDIDATE"
    # shellcheck disable=SC1091
    . "$CANDIDATE/bin/activate"
    break
  fi
done
echo "startup: python=$(command -v python3) gunicorn=$(command -v gunicorn || echo MISSING)"

# One worker: the Free tier has a single core and ~1 GB of memory, and SQLite
# with WAL is happiest with one writer. Threads carry the concurrency, which is
# right for a read-mostly API that spends its time waiting on the model.
# NOT `exec`, and no `set -e`: if this returns, the script has to survive it.
# A container that exits gets restarted by the platform, and fifteen restarts
# exhaust the plan's quota — which then disables the very log endpoints needed to
# find out why. Failing loudly on a port beats failing invisibly.
echo "startup: launching gunicorn"
gunicorn radar.api:app \
  --bind "0.0.0.0:${PORT:-8000}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 1 \
  --threads 4 \
  --timeout 180 \
  --access-logfile '-' \
  --error-logfile '-'
STATUS=$?

echo "startup: gunicorn exited with status $STATUS — serving diagnostics instead"
export APP_DIR RADAR_STARTUP_LOG="$LOG_DIR/radar-startup.log"
exec python3 "$APP_DIR/fallback_server.py"
