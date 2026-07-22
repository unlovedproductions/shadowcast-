#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"

"$LAUNCHER_DIR/preflight-mission-control.sh"

"$LAUNCHER_DIR/open-terminal.sh" \
  "Mission Control" \
  "$LAUNCHER_DIR/run-mission-control-terminal.sh"

"$LAUNCHER_DIR/wait-open-url.sh" \
  "http://localhost:3100" \
  90
