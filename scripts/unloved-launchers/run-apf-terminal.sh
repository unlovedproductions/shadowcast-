#!/usr/bin/env bash

finish() {
  rc=$?
  echo
  echo "APF process exited with code: $rc"
  echo "Terminal left open for logs/debugging."
  exec bash
}
trap finish EXIT

set -Eeuo pipefail

cd /home/unloved/APF || {
  echo "Missing /home/unloved/APF"
  exit 1
}

echo "Starting APF from: $(pwd)"

if [ -s "$HOME/.nvm/nvm.sh" ]; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"
  nvm use 22 || nvm use 24 || true
fi

echo "Node: $(node -v 2>/dev/null || echo missing)"
echo "pnpm: $(pnpm -v 2>/dev/null || echo missing)"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm not found. Try:"
  echo "  corepack enable"
  echo "  corepack prepare pnpm@11.8.0 --activate"
  exit 1
fi

if [ ! -f .env ]; then
  echo "Missing /home/unloved/APF/.env"
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  if ! systemctl is-active --quiet mysql; then
    echo "MySQL is not active. Attempting to start it..."
    sudo systemctl start mysql || true
  fi
fi

set -a
source .env
set +a

export PORT="${PORT:-3001}"

echo "Opening APF on http://localhost:${PORT}"
pnpm dev
