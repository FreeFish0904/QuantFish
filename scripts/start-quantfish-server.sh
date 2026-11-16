#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

HOST="127.0.0.1"
BACKEND_PORT="7860"
RUNTIME_ROOT="runs/web_platform"
SKIP_INSTALL="0"
SKIP_BUILD="0"

usage() {
  cat <<'USAGE'
Usage: scripts/start-quantfish-server.sh [options]

Ubuntu server startup for the QuantFish classroom platform.
This script expects a project-local Python virtual environment at ./.venv.

Options:
  --host HOST
      Bind address. Default: 127.0.0.1. Use 0.0.0.0 explicitly for LAN access.
  --backend-port PORT
      FastAPI port. Default: 7860
  --runtime-root PATH
      Runtime directory for submissions/reports. Default: runs/web_platform
  --skip-install
      Do not run pip/npm install before startup.
  --skip-build
      Do not rebuild the frontend before startup.
  -h, --help
      Show this help.

Examples:
  scripts/start-quantfish-server.sh
  scripts/start-quantfish-server.sh --host 0.0.0.0 --backend-port 7860
  scripts/start-quantfish-server.sh --skip-install --skip-build
USAGE
}

log() {
  printf '\n\033[1;36m==>\033[0m %s\n' "$*"
}

die() {
  printf '\033[1;31merror:\033[0m %s\n' "$*" >&2
  exit 1
}

need_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

generate_secret() {
  python -c 'import secrets; print(secrets.token_urlsafe(32))'
}

ensure_credentials() {
  if [ -z "${QUANTFISH_ADMIN_PASSWORD:-}" ]; then
    QUANTFISH_ADMIN_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(18))')"
    GENERATED_ADMIN_PASSWORD="1"
    export GENERATED_ADMIN_PASSWORD
    export QUANTFISH_ADMIN_PASSWORD
  fi
  if [ -z "${QUANTFISH_ADMIN_SESSION_SECRET:-}" ]; then
    QUANTFISH_ADMIN_SESSION_SECRET="$(generate_secret)"
    export QUANTFISH_ADMIN_SESSION_SECRET
  fi
  if [ -z "${QUANTFISH_PARTICIPANT_SESSION_SECRET:-}" ]; then
    QUANTFISH_PARTICIPANT_SESSION_SECRET="$(generate_secret)"
    export QUANTFISH_PARTICIPANT_SESSION_SECRET
  fi
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="${2:-}"
      shift 2
      ;;
    --runtime-root)
      RUNTIME_ROOT="${2:-}"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL="1"
      shift
      ;;
    --skip-build)
      SKIP_BUILD="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

cd "$PROJECT_ROOT"

[ -f "./.venv/bin/activate" ] || die "Missing ./.venv/bin/activate. Create the server virtualenv first."
source "./.venv/bin/activate"

need_command python
need_command npm
ensure_credentials

if [ "$SKIP_INSTALL" != "1" ]; then
  log "Installing backend package into ./.venv"
  python -m pip install -e ./backend
  log "Installing frontend packages"
  npm --prefix frontend install --legacy-peer-deps
fi

if [ "$SKIP_BUILD" != "1" ]; then
  log "Building frontend for FastAPI static serving"
  npm --prefix frontend run build
fi

log "Starting QuantFish on ${HOST}:${BACKEND_PORT}"
printf 'Runtime root: %s\n' "$RUNTIME_ROOT"
if [ -n "${GENERATED_ADMIN_PASSWORD:-}" ]; then
  printf 'Generated admin password: %s\n' "$QUANTFISH_ADMIN_PASSWORD"
else
  printf 'Admin password: set from QUANTFISH_ADMIN_PASSWORD\n'
fi

exec quantfish-web \
  --host "$HOST" \
  --port "$BACKEND_PORT" \
  --runtime-root "$RUNTIME_ROOT"
