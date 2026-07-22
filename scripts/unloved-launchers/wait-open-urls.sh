#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <timeout_seconds> <url> [<url> ...]"
  exit 1
fi

TIMEOUT="$1"
shift
urls=("$@")

all_ready() {
  local url
  for url in "${urls[@]}"; do
    if ! curl -fsS "$url" >/dev/null 2>&1; then
      return 1
    fi
  done
  return 0
}

for _ in $(seq 1 "$TIMEOUT"); do
  if all_ready; then
    "$LAUNCHER_DIR/open-firefox-tabs.sh" "${urls[@]}"
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for: ${urls[*]}"
echo "Opening URLs anyway..."
"$LAUNCHER_DIR/open-firefox-tabs.sh" "${urls[@]}"
