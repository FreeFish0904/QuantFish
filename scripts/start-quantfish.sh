#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MODE="dev"
CONDA_ENV="QuantFish"
HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_PORT="5173"
RUNTIME_ROOT="runs/web_platform"
SKIP_INSTALL="0"

usage() {
  cat <<'USAGE'
Usage: scripts/start-quantfish.sh [options]

Easy startup for the QuantFish classroom platform.

Options:
  --mode setup|dev|prod|verify
      setup   Install backend/frontend dependencies, then exit.
      dev     Install if needed, start backend and Vite dev server. Default.
      prod    Install if needed, build frontend, serve app from FastAPI.
      verify  Run Python tests, frontend tests, and frontend build.
  --host HOST
      Bind address. Default: 127.0.0.1. Use 0.0.0.0 explicitly for LAN access.
  --backend-port PORT
      FastAPI port. Default: 8000
  --frontend-port PORT
      Vite dev server port. Default: 5173
  --runtime-root PATH
      Runtime directory for submissions/reports. Default: runs/web_platform
  --conda-env NAME
      Conda environment name. Default: QuantFish
  --skip-install
      Do not run pip/npm install before startup.
  -h, --help
      Show this help.

Examples:
  scripts/start-quantfish.sh
  scripts/start-quantfish.sh --mode setup
  scripts/start-quantfish.sh --mode prod --host 0.0.0.0 --backend-port 8000
  scripts/start-quantfish.sh --mode verify
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

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --backend-port)
      BACKEND_PORT="${2:-}"
      shift 2
      ;;
    --frontend-port)
      FRONTEND_PORT="${2:-}"
      shift 2
      ;;
    --runtime-root)
      RUNTIME_ROOT="${2:-}"
      shift 2
      ;;
    --conda-env)
      CONDA_ENV="${2:-}"
      shift 2
      ;;
    --skip-install)
      SKIP_INSTALL="1"
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

case "$MODE" in
  setup|dev|prod|verify)
    ;;
  *)
    die "Invalid --mode: ${MODE}. Expected setup, dev, prod, or verify."
    ;;
esac

cd "$PROJECT_ROOT"

install_backend() {
  log "Installing backend package into conda env '${CONDA_ENV}'"
  conda run -n "$CONDA_ENV" python -m pip install -e './backend[dev]' \
    -i https://pypi.tuna.tsinghua.edu.cn/simple
}

install_frontend() {
  log "Installing frontend packages"
  npm --prefix frontend install --legacy-peer-deps
}

ensure_dependencies() {
  need_command conda
  need_command npm
  need_command curl
  need_command python3
  if [ "$SKIP_INSTALL" = "1" ]; then
    log "Skipping dependency install"
    return
  fi
  install_backend
  install_frontend
}

ensure_admin_password() {
  if [ -n "${QUANTFISH_ADMIN_PASSWORD:-}" ]; then
    log "Using existing QUANTFISH_ADMIN_PASSWORD"
    ensure_session_secrets
    return
  fi
  QUANTFISH_ADMIN_PASSWORD="$(
    python3 -c 'import secrets; print(secrets.token_urlsafe(18))'
  )"
  GENERATED_ADMIN_PASSWORD="1"
  export GENERATED_ADMIN_PASSWORD
  export QUANTFISH_ADMIN_PASSWORD
  log "Generated an admin password"
  ensure_session_secrets
}

run_verify() {
  ensure_dependencies
  log "Running Python tests"
  conda run -n "$CONDA_ENV" python -m pytest
  log "Running frontend tests"
  npm --prefix frontend test -- --run
  log "Building frontend"
  npm --prefix frontend run build
}

print_urls() {
  printf '\nQuantFish URLs:\n'
  if [ "$MODE" = "dev" ]; then
    printf '  Frontend: http://localhost:%s/\n' "$FRONTEND_PORT"
    printf '  Backend:  http://localhost:%s/api/health\n' "$BACKEND_PORT"
    printf '  LAN:      http://<this-computer-lan-ip>:%s/\n' "$FRONTEND_PORT"
  else
    printf '  App:      http://localhost:%s/\n' "$BACKEND_PORT"
    printf '  Health:   http://localhost:%s/api/health\n' "$BACKEND_PORT"
    printf '  LAN:      http://<this-computer-lan-ip>:%s/\n' "$BACKEND_PORT"
  fi
  if [ -n "${GENERATED_ADMIN_PASSWORD:-}" ]; then
    printf '  Admin password: %s\n' "$QUANTFISH_ADMIN_PASSWORD"
  elif [ -n "${QUANTFISH_ADMIN_PASSWORD:-}" ]; then
    printf '  Admin password: set from QUANTFISH_ADMIN_PASSWORD\n'
  fi
  printf '\nPress Ctrl+C to stop.\n'
}

ensure_session_secrets() {
  if [ -z "${QUANTFISH_ADMIN_SESSION_SECRET:-}" ]; then
    QUANTFISH_ADMIN_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export QUANTFISH_ADMIN_SESSION_SECRET
  fi
  if [ -z "${QUANTFISH_PARTICIPANT_SESSION_SECRET:-}" ]; then
    QUANTFISH_PARTICIPANT_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export QUANTFISH_PARTICIPANT_SESSION_SECRET
  fi
}

start_backend() {
  log "Starting backend on ${HOST}:${BACKEND_PORT}"
  conda run -n "$CONDA_ENV" quantfish-web \
    --host "$HOST" \
    --port "$BACKEND_PORT" \
    --runtime-root "$RUNTIME_ROOT" &
  BACKEND_PID="$!"
}

start_frontend_dev() {
  log "Starting frontend dev server on ${HOST}:${FRONTEND_PORT}"
  npm --prefix frontend run dev -- \
    --host "$HOST" \
    --port "$FRONTEND_PORT" &
  FRONTEND_PID="$!"
}

cleanup() {
  if [ -n "${FRONTEND_PID:-}" ]; then
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "${BACKEND_PID:-}" ]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

install_cleanup_trap() {
  trap cleanup EXIT INT TERM
}

server_died() {
  if [ -n "${BACKEND_PID:-}" ] && ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    wait "$BACKEND_PID"
    exit $?
  fi
  if [ -n "${FRONTEND_PID:-}" ] && ! kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    wait "$FRONTEND_PID"
    exit $?
  fi
}

wait_for_http() {
  local label="$1"
  local url="$2"
  local attempts="${3:-60}"
  local attempt
  log "Waiting for ${label} readiness at ${url}"
  for attempt in $(seq 1 "$attempts"); do
    server_died
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "Timed out waiting for ${label}: ${url}"
}

wait_for_servers() {
  if [ "${BACKEND_READY:-0}" != "1" ]; then
    wait_for_http "backend" "http://127.0.0.1:${BACKEND_PORT}/api/health"
  fi
  if [ "$MODE" = "dev" ]; then
    wait_for_http "frontend" "http://127.0.0.1:${FRONTEND_PORT}/"
  fi
  print_urls
  while true; do
    server_died
    sleep 1
  done
}

case "$MODE" in
  setup)
    ensure_dependencies
    log "Setup complete"
    ;;
  verify)
    run_verify
    log "Verification complete"
    ;;
  dev)
    ensure_dependencies
    ensure_admin_password
    install_cleanup_trap
    start_backend
    wait_for_http "backend" "http://127.0.0.1:${BACKEND_PORT}/api/health"
    BACKEND_READY="1"
    start_frontend_dev
    wait_for_servers
    ;;
  prod)
    ensure_dependencies
    log "Building frontend for FastAPI static serving"
    npm --prefix frontend run build
    ensure_admin_password
    install_cleanup_trap
    start_backend
    wait_for_servers
    ;;
esac
