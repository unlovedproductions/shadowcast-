#!/usr/bin/env bash

finish() {
  rc=$?
  echo
  echo "Mission Control frontend exited with code: $rc"
  echo "Terminal left open for logs/debugging."
  exec bash
}
trap finish EXIT

set -Eeuo pipefail

cd /home/unloved/mission-control/frontend || {
  echo "Missing /home/unloved/mission-control/frontend"
  exit 1
}

echo "Starting Mission Control frontend from: $(pwd)"

if [ -s "$HOME/.nvm/nvm.sh" ]; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"
  nvm use 22 || true
fi

echo "Node: $(node -v 2>/dev/null || echo missing)"
echo "pnpm: $(pnpm -v 2>/dev/null || echo missing)"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found. Try:"
  echo "  corepack enable"
  echo "  corepack prepare pnpm@11.8.0 --activate"
  exit 1
fi

echo "Opening Mission Control frontend on http://localhost:3100"

pnpm run dev -- --host 0.0.0.0 --port 3100
