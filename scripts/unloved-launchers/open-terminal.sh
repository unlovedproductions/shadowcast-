#!/usr/bin/env bash
set -Eeuo pipefail

TITLE="${1:?Missing terminal title}"
SCRIPT_PATH="${2:?Missing script path}"

LAUNCHER_DIR="$(dirname "$0")"
exec "$LAUNCHER_DIR/open-terminal-tabs.sh" "$TITLE" "$SCRIPT_PATH"
