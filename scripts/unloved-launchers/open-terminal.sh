#!/usr/bin/env bash
set -Eeuo pipefail

TITLE="${1:?Missing terminal title}"
SCRIPT_PATH="${2:?Missing script path}"

if command -v gnome-terminal >/dev/null 2>&1; then
  gnome-terminal --title="$TITLE" -- bash -lc "exec '$SCRIPT_PATH'" &
elif command -v x-terminal-emulator >/dev/null 2>&1; then
  x-terminal-emulator -T "$TITLE" -e bash -lc "exec '$SCRIPT_PATH'" &
elif command -v konsole >/dev/null 2>&1; then
  konsole --new-tab --workdir "$HOME" -p tabtitle="$TITLE" -e bash -lc "exec '$SCRIPT_PATH'" &
elif command -v xterm >/dev/null 2>&1; then
  xterm -T "$TITLE" -e bash -lc "exec '$SCRIPT_PATH'" &
else
  echo "No supported terminal emulator found."
  echo "Install gnome-terminal or xterm."
  exit 1
fi
