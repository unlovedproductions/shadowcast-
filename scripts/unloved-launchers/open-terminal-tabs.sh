#!/usr/bin/env bash
set -Eeuo pipefail

UNLOVED_KITTY_SOCK="${UNLOVED_KITTY_SOCK:-/tmp/unloved-stack.sock}"
UNLOVED_STATE_DIR="${HOME}/.local/state"
UNLOVED_SOCK_FILE="${UNLOVED_STATE_DIR}/unloved-terminal.sock"
UNLOVED_SESSION_FILE="${UNLOVED_STATE_DIR}/unloved-kitty.session"

if ! command -v kitty >/dev/null 2>&1; then
  echo "kitty is required for Unloved launchers but was not found on PATH."
  echo "Install kitty: sudo apt install kitty"
  exit 1
fi

if [ "$#" -lt 2 ] || [ $(( "$#" % 2 )) -ne 0 ]; then
  echo "Usage: $0 <title> <script> [<title> <script> ...]"
  exit 1
fi

kitty_socket_uri() {
  printf 'unix:%s' "$UNLOVED_KITTY_SOCK"
}

kitty_socket_alive() {
  kitty @ --to "$(kitty_socket_uri)" ls >/dev/null 2>&1
}

kitty_tab_exists() {
  local title="$1"
  kitty @ --to "$(kitty_socket_uri)" ls 2>/dev/null | grep -Fq "title: ${title}"
}

kitty_focus_tab() {
  local title="$1"
  kitty @ --to "$(kitty_socket_uri)" focus-tab --match "title:${title}" >/dev/null 2>&1 || true
}

kitty_new_window() {
  local session_file="$UNLOVED_SESSION_FILE"

  mkdir -p "$UNLOVED_STATE_DIR"
  : >"$session_file"

  while [ "$#" -gt 0 ]; do
    local title="$1"
    local script_path="$2"
    shift 2

    if [ ! -x "$script_path" ]; then
      echo "Missing or non-executable script: $script_path"
      exit 1
    fi

    {
      printf 'new_tab %s\n' "$title"
      printf 'launch bash -lc "exec %q"\n' "$script_path"
    } >>"$session_file"
  done

  # Keep session_file on disk — kitty reads it asynchronously after spawn.
  rm -f "$UNLOVED_KITTY_SOCK"
  kitty --listen-on="$(kitty_socket_uri)" -o allow_remote_control=yes --session "$session_file" &
  printf '%s\n' "$(kitty_socket_uri)" >"$UNLOVED_SOCK_FILE"
}

pending=()
while [ "$#" -gt 0 ]; do
  title="$1"
  script_path="$2"
  shift 2

  if kitty_socket_alive && kitty_tab_exists "$title"; then
    echo "[launcher] Tab already open: ${title} (focusing)"
    kitty_focus_tab "$title"
    continue
  fi

  pending+=("$title" "$script_path")
done

if [ "${#pending[@]}" -eq 0 ]; then
  exit 0
fi

if kitty_socket_alive; then
  i=0
  while [ "$i" -lt "${#pending[@]}" ]; do
    title="${pending[$i]}"
    script_path="${pending[$((i + 1))]}"
    i=$((i + 2))
    kitty @ --to "$(kitty_socket_uri)" launch \
      --type=tab \
      --tab-title "$title" \
      bash -lc "exec $(printf %q "$script_path")" &
  done
  exit 0
fi

if [ -S "$UNLOVED_KITTY_SOCK" ] && ! kitty_socket_alive; then
  rm -f "$UNLOVED_KITTY_SOCK"
fi

kitty_new_window "${pending[@]}"
