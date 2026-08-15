#!/usr/bin/env bash

finish() {
  rc=$?
  echo
  echo "Mission Control backend exited with code: $rc"
  echo "Terminal left open for logs/debugging."
  exec bash
}
trap finish EXIT

set -Eeuo pipefail

cd /home/unloved/mission-control/backend || {
  echo "Missing /home/unloved/mission-control/backend"
  exit 1
}

echo "Starting Mission Control backend from: $(pwd)"

if [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "Missing Mission Control backend venv."
  echo "Create it first with Python 3.12 or 3.11:"
  echo "  cd /home/unloved/mission-control/backend"
  echo "  python3.12 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

if [ ! -f .env ]; then
  echo "Missing /home/unloved/mission-control/backend/.env"
  exit 1
fi

set -a
source .env
set +a

echo "Python: $(python --version)"
echo "Opening Mission Control backend on http://localhost:8100"

python -m uvicorn main:app --host 0.0.0.0 --port 8100 --reload
