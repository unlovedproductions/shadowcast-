#!/usr/bin/env bash
set -Eeuo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <url> [<url> ...]"
  exit 1
fi

if ! command -v firefox >/dev/null 2>&1; then
  echo "firefox not found on PATH."
  exit 1
fi

urls=("$@")

# Already-running Firefox: open each URL as a new tab in the existing session.
if pgrep -x firefox >/dev/null 2>&1 || pgrep -x firefox-bin >/dev/null 2>&1; then
  for url in "${urls[@]}"; do
    firefox --new-tab "$url" >/dev/null 2>&1 &
  done
  exit 0
fi

# Cold start: one process with all URLs so Firefox shows at most one profile picker
# instead of one picker window per URL.
firefox --new-window "${urls[@]}" >/dev/null 2>&1 &
