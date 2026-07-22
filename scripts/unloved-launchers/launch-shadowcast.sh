#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"

"$LAUNCHER_DIR/preflight-shadowcast.sh"

"$LAUNCHER_DIR/open-terminal.sh" \
  "ShadowCast" \
  "$LAUNCHER_DIR/run-shadowcast-terminal.sh"

"$LAUNCHER_DIR/wait-open-url.sh" \
  "http://localhost:8000" \
  90
