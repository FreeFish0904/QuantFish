#!/usr/bin/env bash
# QuantFish Docker demo entrypoint: prepare data, seed a demo cohort, serve.
set -Eeuo pipefail

export QUANTFISH_CONFIG="${QUANTFISH_CONFIG:-config/platform.demo.yaml}"
export QUANTFISH_HOST="${QUANTFISH_HOST:-0.0.0.0}"
export QUANTFISH_PORT="${QUANTFISH_PORT:-8010}"
export QUANTFISH_RUNTIME_ROOT="${QUANTFISH_RUNTIME_ROOT:-runs/web_platform}"

generate_secret() {
  python -c 'import secrets; print(secrets.token_urlsafe(32))'
}

if [ -z "${QUANTFISH_ADMIN_PASSWORD:-}" ]; then
  export QUANTFISH_ADMIN_PASSWORD="$(generate_secret)"
  printf '[quantfish] generated admin password: %s\n' "$QUANTFISH_ADMIN_PASSWORD"
fi
if [ -z "${QUANTFISH_ADMIN_SESSION_SECRET:-}" ]; then
  export QUANTFISH_ADMIN_SESSION_SECRET="$(generate_secret)"
fi
if [ -z "${QUANTFISH_PARTICIPANT_SESSION_SECRET:-}" ]; then
  export QUANTFISH_PARTICIPANT_SESSION_SECRET="$(generate_secret)"
fi

if [ ! -f data/sample/releases/hidden_test/data_catalog.json ]; then
  printf '[quantfish] generating synthetic dataset and releases...\n'
  python scripts/gen_sample_dataset.py --config "$QUANTFISH_CONFIG"
fi

python deploy/seed_demo.py || printf '[quantfish] demo seeding skipped\n'

printf '[quantfish] serving on http://%s:%s (config: %s)\n' \
  "$QUANTFISH_HOST" "$QUANTFISH_PORT" "$QUANTFISH_CONFIG"

exec quantfish-web \
  --host "$QUANTFISH_HOST" \
  --port "$QUANTFISH_PORT" \
  --config "$QUANTFISH_CONFIG" \
  --runtime-root "$QUANTFISH_RUNTIME_ROOT"
