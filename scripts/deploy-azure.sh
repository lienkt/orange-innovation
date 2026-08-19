#!/usr/bin/env bash
# Deploy the radar to Azure App Service.
#
# One command, repeatable, no state kept anywhere but Azure. It builds the
# frontend, assembles a serving-only package and pushes it; provisioning is
# idempotent, so the same script creates the app the first time and updates it
# afterwards.
#
# What it deliberately does NOT deploy:
#   * the pipeline's heavy dependencies (torch, scikit-learn, sentence-transformers).
#     `radar.api` imports none of them — see requirements-azure.txt.
#   * the replay archive (`raw_items`). It exists so the pipeline can be re-run
#     as of a past date without re-fetching (DR-14, FR-35), which is a local
#     batch concern. Dropping it halves the package; every citation still
#     resolves, because signals keep their URL and extract.
#   * .env. Secrets are App Settings, set from the local .env at deploy time and
#     never written into the package.
#
# Discovery is not run in Azure. The pipeline writes to the same SQLite file
# locally and the deployed app serves what it produced; `make redeploy` after a
# refresh is the publish step.
set -euo pipefail

# The radar shares the RailPulse Free App Service plan. Two constraints forced
# that, and both are worth knowing before changing it:
#
#   * The subscription carries an "Allowed resource deployment regions" policy —
#     Italy North, France Central, Germany West Central, Poland Central, Spain
#     Central. All EU, which suits this product.
#   * A Free plan hosts several apps, so the radar joins the RailPulse one and
#     the two share its 60 CPU-minutes per day.
#
# And one trap worth the comment: /home is an SMB mount, where SQLite's WAL does
# not work. RADAR_SQLITE_JOURNAL_MODE=DELETE is set below for that reason; drop
# it and the app crash-loops until the plan's restart quota is spent, which then
# disables Kudu and hides the logs that would explain it.
#
# Moving to a dedicated plan means paying for it: B1 is about USD 13/month.
#   RG=rg-orange-radar PLAN=plan-orange-radar SKU=B1 REGION=francecentral ./scripts/deploy-azure.sh
RG="${RG:-rg-railpulse-cloud}"
APP="${APP:-web-orange-radar-1521f5}"
PLAN="${PLAN:-plan-railpulse-cdb4ce}"
REGION="${REGION:-francecentral}"
SKU="${SKU:-F1}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "==> building the frontend"
npm --prefix "$ROOT/frontend" run build

echo "==> assembling the deployment package in $STAGE"
mkdir -p "$STAGE/frontend" "$STAGE/data/briefs"
cp -R "$ROOT/src" "$ROOT/config" "$STAGE/"
cp -R "$ROOT/frontend/dist" "$STAGE/frontend/dist"
cp "$ROOT/main.py" "$ROOT/fallback_server.py" "$ROOT/.deployment" "$STAGE/"
cp "$ROOT/requirements-azure.txt" "$STAGE/requirements.txt"
cp "$ROOT"/data/briefs/*.pdf "$STAGE/data/briefs/"   # unsilenced: the rows ship regardless,
                                                    # so a missing PDF is a 404 in the UI
find "$STAGE" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

echo "==> trimming the serving database"
python3 - "$ROOT/data/radar.db" "$STAGE/data/radar.db" <<'PY'
import sqlite3, sys, pathlib
src, dst = sys.argv[1], sys.argv[2]
# VACUUM INTO, not a file copy: the source is in WAL, and copying the main file
# alone leaves anything still in the -wal behind — which can ship the brief PDFs
# without the rows that make them reachable.
source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
source.execute("VACUUM INTO ?", (dst,))
source.close()
con = sqlite3.connect(dst)
con.execute("PRAGMA foreign_keys = OFF")
con.execute("UPDATE signals SET raw_item_id = NULL")
con.execute("DELETE FROM raw_items")
con.commit(); con.execute("VACUUM")
# Ship it in the mode the server must use. /home is SMB, where WAL does not work,
# and the first write now happens before bootstrap could convert it.
con.execute("PRAGMA journal_mode = DELETE")
con.close()
print(f"    {pathlib.Path(src).stat().st_size/1048576:.1f} MB -> "
      f"{pathlib.Path(dst).stat().st_size/1048576:.1f} MB")
PY

echo "==> ensuring the Azure resources exist"
az group create -n "$RG" -l "$REGION" --tags project=orange-innovation-radar -o none
az appservice plan show -g "$RG" -n "$PLAN" -o none 2>/dev/null \
  || az appservice plan create -g "$RG" -n "$PLAN" --is-linux --sku "$SKU" --location "$REGION" -o none
az webapp show -g "$RG" -n "$APP" -o none 2>/dev/null \
  || az webapp create -g "$RG" -p "$PLAN" -n "$APP" --runtime "PYTHON:3.13" -o none

echo "==> pushing configuration (secrets from .env, never into the package)"
read_env() { grep "^$1=" "$ROOT/.env" 2>/dev/null | cut -d= -f2- || true; }
az webapp config appsettings set -g "$RG" -n "$APP" --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  ENABLE_ORYX_BUILD=true \
  RADAR_DB_PATH=/home/data/radar.db \
  RADAR_BRIEF_DIR=/home/data/briefs \
  RADAR_ARCHIVE_DIR=/home/data/archive \
  RADAR_SQLITE_JOURNAL_MODE=DELETE \
  RADAR_STARTUP_LOG=/home/LogFiles/radar-startup.log \
  RADAR_LLM_PROVIDER="$(read_env RADAR_LLM_PROVIDER)" \
  RADAR_LLM_MODEL_STRONG="$(read_env RADAR_LLM_MODEL_STRONG)" \
  RADAR_LLM_MODEL_CHEAP="$(read_env RADAR_LLM_MODEL_CHEAP)" \
  RADAR_CONTACT_EMAIL="$(read_env RADAR_CONTACT_EMAIL)" \
  DEEPSEEK_BASE_URL="$(read_env DEEPSEEK_BASE_URL)" \
  DEEPSEEK_API_KEY="$(read_env DEEPSEEK_API_KEY)" \
  WEBSITES_CONTAINER_START_TIME_LIMIT=600 \
  -o none

# Filesystem logging keeps the container log in /home/LogFiles, which survives a
# container that does not. Without it, a failed boot leaves nothing to read.
az webapp log config -g "$RG" -n "$APP" --docker-container-logging filesystem \
  --application-logging filesystem --level verbose -o none
az webapp update -g "$RG" -n "$APP" --https-only true -o none

echo "==> deploying"
(cd "$STAGE" && zip -qr "$STAGE/package.zip" . -x '*.DS_Store')
az webapp deploy -g "$RG" -n "$APP" --src-path "$STAGE/package.zip" --type zip -o none

# Oryx extracts the build to a fresh /tmp/<hash> and cds there, so the command
# must not name an absolute path or a console script. `python3 -m uvicorn`
# resolves through PYTHONPATH (which Oryx points at the extracted virtualenv)
# rather than PATH (which it does not extend), and `main:app` resolves through
# the working directory. Earlier commands failed both ways and exited 127.
az webapp config set -g "$RG" -n "$APP" --startup-file \
  "python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 60" -o none

HOST="$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"
echo "==> waiting for the app to answer"
for _ in $(seq 1 60); do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$HOST/healthz" || true)"
  [ "$code" = "200" ] && { echo "    live: https://$HOST"; exit 0; }
  sleep 10
done
echo "    still not answering — check: az webapp log tail -g $RG -n $APP" >&2
exit 1
