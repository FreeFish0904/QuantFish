#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: scripts/import-offline-runtime.sh <platform> <runtime-zip> [runtime-manifest]" >&2
  exit 2
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="$1"
RUNTIME_ZIP="$2"
MANIFEST="${3:-}"
RUNTIME_ROOT="${QUANTFISH_RUNTIME_ROOT:-$PROJECT_ROOT/runs/web_platform}"
QUANTFISH_CONDA_ENV="${QUANTFISH_CONDA_ENV:-QuantFish}"

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if [ -n "${QUANTFISH_PYTHON:-}" ]; then
  PYTHON_CMD=("$QUANTFISH_PYTHON")
elif [ "${CONDA_DEFAULT_ENV:-}" = "$QUANTFISH_CONDA_ENV" ]; then
  PYTHON_CMD=(python)
elif command -v conda >/dev/null 2>&1; then
  PYTHON_CMD=(conda run -n "$QUANTFISH_CONDA_ENV" python)
else
  PYTHON_CMD=(python)
fi

IMPORT_ARGS=(
  --platform "$PLATFORM"
  --zip "$RUNTIME_ZIP"
  --runtime-root "$RUNTIME_ROOT"
  --project-root "$PROJECT_ROOT"
)
if [ -n "$MANIFEST" ]; then
  IMPORT_ARGS+=(--manifest "$MANIFEST")
fi

"${PYTHON_CMD[@]}" -m quantfish.student_exports.runtime_packages import "${IMPORT_ARGS[@]}"
"${PYTHON_CMD[@]}" -m quantfish.student_exports.monitor refresh \
  --config "$PROJECT_ROOT/config/platform.yaml" \
  --runtime-root "$RUNTIME_ROOT" \
  --project-root "$PROJECT_ROOT"
