#!/usr/bin/env bash
set -Eeuo pipefail

LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"
backend_pid=""

cleanup() {
  if [ -n "$backend_pid" ] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

bash -lc "exec '$LAUNCHER_DIR/run-mission-backend-terminal.sh'" &
backend_pid=$!

sleep 3

exec bash -lc "exec '$LAUNCHER_DIR/run-mission-frontend-terminal.sh'"
