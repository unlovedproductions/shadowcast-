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

apf_port="$(read_env_var "$APF_DIR/.env" PORT || true)"
apf_port="${apf_port:-3001}"

"$LAUNCHER_DIR/wait-open-urls.sh" 120 \
  "http://localhost:8000" \
  "http://localhost:${apf_port}" \
  "http://localhost:3100"
