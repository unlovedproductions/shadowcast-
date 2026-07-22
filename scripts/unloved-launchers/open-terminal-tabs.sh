#!/usr/bin/env bash
set -Eeuo pipefail

if ! command -v kitty >/dev/null 2>&1; then
  echo "kitty is required for tabbed stack launch but was not found on PATH."
  echo "Install kitty or use individual app launchers instead."
  exit 1
fi

if [ "$#" -lt 2 ] || [ $(( "$#" % 2 )) -ne 0 ]; then
  echo "Usage: $0 <title> <script> [<title> <script> ...]"
  exit 1
fi

session_file="$(mktemp /tmp/unloved-kitty-session.XXXXXX)"
cleanup() {
  rm -f "$session_file"
}
trap cleanup EXIT

while [ "$#" -gt 0 ]; do
  title="$1"
  script_path="$2"
  shift 2

  if [ ! -x "$script_path" ]; then
    echo "Missing or non-executable script: $script_path"
    exit 1
  fi

  {
    printf 'new_tab %s\n' "$title"
    printf 'launch bash -lc "exec %q"\n' "$script_path"
  } >> "$session_file"
done

kitty --session "$session_file" &
