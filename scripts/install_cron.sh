#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/a2t.ro}"
LOG_FILE="${LOG_FILE:-/var/log/a2t-refresh.log}"

CRON_LINE="5 * * * * PROJECT_DIR=$PROJECT_DIR $PROJECT_DIR/scripts/refresh_a2t.sh >> $LOG_FILE 2>&1"

( crontab -l 2>/dev/null | grep -v 'scripts/refresh_a2t.sh' ; echo "$CRON_LINE" ) | crontab -

echo "Installed hourly cron job:"
echo "$CRON_LINE"
