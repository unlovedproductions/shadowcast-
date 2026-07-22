#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <url> [timeout_seconds]"
  exit 1
fi

URL="$1"
TIMEOUT="${2:-60}"

exec "$LAUNCHER_DIR/wait-open-urls.sh" "$TIMEOUT" "$URL"
