#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/a2t.ro}"
WEB_ROOT="${WEB_ROOT:-/var/www/dev.proclick.ro/a2t.ro}"
ENV_FILE="${ENV_FILE:-$PROJECT_DIR/.env.server}"

cd "$PROJECT_DIR"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install google-ads >/dev/null

RUN_DATE="${REPORT_DATE:-$(date +%F)}"
PYTHONPATH=src .venv/bin/python -m a2t_budget_control.cli --from-google-ads --date "$RUN_DATE"

mkdir -p "$WEB_ROOT/data/output"
cp index.html dashboard.html "$WEB_ROOT/"
cp -R data/output/*.csv "$WEB_ROOT/data/output/"

echo "[$(date '+%F %T')] Refreshed dashboard data for date $RUN_DATE"
