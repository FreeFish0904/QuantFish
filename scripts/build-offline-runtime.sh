#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${1:-macos-arm64}"
OUTPUT_DIR="${QUANTFISH_RUNTIME_OUTPUT_DIR:-$PROJECT_ROOT/dist/offline-runtimes}"
BUILD_ROOT="${QUANTFISH_RUNTIME_BUILD_ROOT:-$PROJECT_ROOT/.runtime-build/offline-runtimes}"
PIP_INDEX_URL="${QUANTFISH_PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
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

"${PYTHON_CMD[@]}" -m quantfish.student_exports.runtime_packages build \
  --platform "$PLATFORM" \
  --project-root "$PROJECT_ROOT" \
  --output-dir "$OUTPUT_DIR" \
  --build-root "$BUILD_ROOT" \
  --pip-index-url "$PIP_INDEX_URL"
