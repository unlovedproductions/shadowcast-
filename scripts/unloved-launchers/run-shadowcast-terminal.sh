#!/usr/bin/env bash

finish() {
  rc=$?
  echo
  echo "ShadowCast process exited with code: $rc"
  echo "Terminal left open for logs/debugging."
  exec bash
}
trap finish EXIT

set -Eeuo pipefail

cd /home/unloved/shadowcast-/backend || {
  echo "Missing /home/unloved/shadowcast-/backend"
  exit 1
}

echo "Starting ShadowCast from: $(pwd)"

if [ -f /home/unloved/shadowcast-/.venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source /home/unloved/shadowcast-/.venv/bin/activate
elif [ -f /home/unloved/shadowcast-/venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source /home/unloved/shadowcast-/venv/bin/activate
else
  echo "Missing ShadowCast venv at /home/unloved/shadowcast-/.venv or /home/unloved/shadowcast-/venv"
  echo "Create it first with:"
  echo "  cd /home/unloved/shadowcast-"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r backend/requirements.txt"
  exit 1
fi

if [ ! -f .env ]; then
  echo "Missing /home/unloved/shadowcast-/backend/.env"
  exit 1
fi

set -a
source .env
set +a

echo "Python: $(python --version)"
echo "Opening ShadowCast on http://127.0.0.1:8000 (localhost-only trust)"

# Match docs/RUNBOOK localhost trust model. For LAN bind use HOST=0.0.0.0 in
# backend/.env with INTERNAL_SERVICE_SECRET set, then: python backend/app.py
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
