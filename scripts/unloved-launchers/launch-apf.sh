#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"
ORIGINAL="$LAUNCHER_DIR/launch-apf.sh.before-enrichment"

"$LAUNCHER_DIR/preflight-apf.sh"

# Start enrichment after APF has had time to start and open the webpage.
(
  sleep "${APF_ENRICHMENT_START_DELAY_SECONDS:-20}"

  cd /home/unloved/APF || exit 0
  mkdir -p exports

  if [ -f ".env" ] && grep -q '^REVIEW_ENRICHMENT_ENABLED=true' .env; then
    echo "[$(date -Is)] Starting review enrichment from Start APF launcher" >> exports/review-enrichment-startup.log
    bash scripts/start-review-enrichment-daemon.sh >> exports/review-enrichment-startup.log 2>&1 || true
  else
    echo "[$(date -Is)] Review enrichment disabled or .env missing" >> exports/review-enrichment-startup.log
  fi
) &

exec "$ORIGINAL" "$@"
