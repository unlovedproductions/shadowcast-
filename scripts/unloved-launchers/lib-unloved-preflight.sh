#!/usr/bin/env bash
# Shared preflight helpers for Unloved Productions local stack launchers.

APF_DIR="/home/unloved/APF"
SHADOWCAST_DIR="/home/unloved/shadowcast-"
MC_DIR="/home/unloved/mission-control"
LAUNCHER_DIR="/home/unloved/.local/bin/unloved-launchers"

read_env_var() {
  local file="$1" key="$2"
  if [ ! -f "$file" ]; then
    return 1
  fi
  grep -E "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

ensure_mysql() {
  if command -v docker >/dev/null 2>&1; then
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'apf-mysql'; then
      echo "[preflight] Starting Docker MySQL (apf-mysql)..."
      docker start apf-mysql >/dev/null 2>&1 || {
        echo "ERROR: failed to start apf-mysql container"
        return 1
      }
      return 0
    fi
  fi

  if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files mysql.service 2>/dev/null | grep -q mysql; then
      if ! systemctl is-active --quiet mysql; then
        echo "[preflight] Starting system MySQL..."
        sudo systemctl start mysql 2>/dev/null || systemctl start mysql 2>/dev/null || {
          echo "WARN: could not start system MySQL via systemctl"
        }
      fi
    fi
  fi
}

ensure_ollama() {
  if ! command -v ollama >/dev/null 2>&1; then
    return 0
  fi
  if pgrep -x ollama >/dev/null 2>&1; then
    return 0
  fi
  echo "[preflight] Starting Ollama..."
  ollama serve >/dev/null 2>&1 &
  sleep 2
}

require_env_file() {
  local file="$1" label="$2"
  if [ ! -f "$file" ]; then
    echo "ERROR: Missing $label env file: $file"
    echo "       Copy from .env.example and set INTERNAL_SERVICE_SECRET."
    return 1
  fi
}

verify_internal_secrets_match() {
  local apf_env="$APF_DIR/.env"
  local sc_env="$SHADOWCAST_DIR/backend/.env"
  local mc_env="$MC_DIR/backend/.env"

  require_env_file "$apf_env" "APF" || return 1
  require_env_file "$sc_env" "ShadowCast" || return 1
  require_env_file "$mc_env" "Mission Control" || return 1

  local apf_secret sc_secret mc_secret
  apf_secret="$(read_env_var "$apf_env" INTERNAL_SERVICE_SECRET || true)"
  sc_secret="$(read_env_var "$sc_env" INTERNAL_SERVICE_SECRET || true)"
  mc_secret="$(read_env_var "$mc_env" INTERNAL_SERVICE_SECRET || true)"

  if [ -z "$apf_secret" ] || [ -z "$sc_secret" ] || [ -z "$mc_secret" ]; then
    echo "ERROR: INTERNAL_SERVICE_SECRET must be set in all three .env files."
    echo "       APF:            $apf_env"
    echo "       ShadowCast:     $sc_env"
    echo "       Mission Control: $mc_env"
    return 1
  fi

  if [ "$apf_secret" != "$sc_secret" ] || [ "$apf_secret" != "$mc_secret" ]; then
    echo "ERROR: INTERNAL_SERVICE_SECRET mismatch across repos."
    echo "       Set the same value in APF, shadowcast-/backend, and mission-control/backend .env"
    return 1
  fi

  echo "[preflight] INTERNAL_SERVICE_SECRET aligned across APF, ShadowCast, Mission Control"
}

verify_apf_deps() {
  if [ ! -d "$APF_DIR/node_modules" ]; then
    echo "ERROR: APF dependencies missing. Run: cd $APF_DIR && pnpm install"
    return 1
  fi
}

verify_shadowcast_deps() {
  if [ ! -f "$SHADOWCAST_DIR/venv/bin/activate" ]; then
    echo "ERROR: ShadowCast venv missing at $SHADOWCAST_DIR/venv"
    echo "       cd $SHADOWCAST_DIR && python3 -m venv venv && source venv/bin/activate && pip install -r backend/requirements.txt"
    return 1
  fi
}

verify_mission_control_deps() {
  if [ ! -f "$MC_DIR/backend/venv/bin/activate" ]; then
    echo "ERROR: Mission Control backend venv missing."
    echo "       cd $MC_DIR/backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    return 1
  fi
  if [ ! -d "$MC_DIR/frontend/node_modules" ]; then
    echo "ERROR: Mission Control frontend deps missing. Run: cd $MC_DIR/frontend && pnpm install"
    return 1
  fi
}

preflight_stack() {
  ensure_mysql || return 1
  ensure_ollama
  verify_internal_secrets_match || return 1
  verify_apf_deps || return 1
  verify_shadowcast_deps || return 1
  verify_mission_control_deps || return 1
  echo "[preflight] Stack preflight OK"
}

preflight_apf() {
  ensure_mysql || return 1
  require_env_file "$APF_DIR/.env" "APF" || return 1
  verify_apf_deps || return 1
  echo "[preflight] APF preflight OK"
}

preflight_shadowcast() {
  require_env_file "$SHADOWCAST_DIR/backend/.env" "ShadowCast" || return 1
  verify_shadowcast_deps || return 1
  echo "[preflight] ShadowCast preflight OK"
}

preflight_mission_control() {
  require_env_file "$MC_DIR/backend/.env" "Mission Control" || return 1
  verify_mission_control_deps || return 1
  echo "[preflight] Mission Control preflight OK"
}
