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

if pgrep -x firefox >/dev/null 2>&1 || pgrep -x firefox-bin >/dev/null 2>&1; then
  for url in "${urls[@]}"; do
    firefox --new-tab "$url" >/dev/null 2>&1 &
  done
  exit 0
fi

firefox --new-window "${urls[0]}" >/dev/null 2>&1 &
sleep 2

for url in "${urls[@]:1}"; do
  firefox --new-tab "$url" >/dev/null 2>&1 &
done
