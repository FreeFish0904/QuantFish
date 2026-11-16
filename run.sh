#!/usr/bin/env bash
set -Eeuo pipefail

if [ -z "${QUANTFISH_ADMIN_PASSWORD:-}" ]; then
  QUANTFISH_ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
  export QUANTFISH_ADMIN_PASSWORD
  printf 'Generated QuantFish admin password: %s\n' "$QUANTFISH_ADMIN_PASSWORD"
fi
if [ -z "${QUANTFISH_ADMIN_SESSION_SECRET:-}" ]; then
  QUANTFISH_ADMIN_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export QUANTFISH_ADMIN_SESSION_SECRET
fi
if [ -z "${QUANTFISH_PARTICIPANT_SESSION_SECRET:-}" ]; then
  QUANTFISH_PARTICIPANT_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  export QUANTFISH_PARTICIPANT_SESSION_SECRET
fi

exec quantfish-web \
  --host "${QUANTFISH_HOST:-127.0.0.1}" \
  --port "${QUANTFISH_PORT:-7860}" \
  --runtime-root "${QUANTFISH_RUNTIME_ROOT:-runs/web_platform}"
