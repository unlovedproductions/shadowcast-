#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"

# shellcheck source=lib-unloved-preflight.sh
source "$LAUNCHER_DIR/lib-unloved-preflight.sh"

"$LAUNCHER_DIR/preflight-unloved-stack.sh"

"$LAUNCHER_DIR/open-terminal-tabs.sh" \
  "ShadowCast" "$LAUNCHER_DIR/run-shadowcast-terminal.sh" \
  "APF" "$LAUNCHER_DIR/run-apf-terminal.sh" \
  "Mission Control" "$LAUNCHER_DIR/run-mission-control-terminal.sh"

# Start enrichment after APF has had time to come up (same behavior as Start APF).
(
  sleep "${APF_ENRICHMENT_START_DELAY_SECONDS:-20}"

  cd /home/unloved/APF || exit 0
  mkdir -p exports

  if [ -f ".env" ] && grep -q '^REVIEW_ENRICHMENT_ENABLED=true' .env; then
    echo "[$(date -Is)] Starting review enrichment from Start Unloved Stack launcher" >> exports/review-enrichment-startup.log
    bash scripts/start-review-enrichment-daemon.sh >> exports/review-enrichment-startup.log 2>&1 || true
  else
    echo "[$(date -Is)] Review enrichment disabled or .env missing" >> exports/review-enrichment-startup.log
  fi
) &

apf_port="$(read_env_var "$APF_DIR/.env" PORT || true)"
apf_port="${apf_port:-3001}"

"$LAUNCHER_DIR/wait-open-urls.sh" 120 \
  "http://localhost:8000" \
  "http://localhost:${apf_port}" \
  "http://localhost:3100"
