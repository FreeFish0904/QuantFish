#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="${1:-macos-arm64}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cd "$TMP_DIR"
unzip -q "$PROJECT_ROOT/runs/web_platform/exports/student/learning-data.zip"
unzip -q "$PROJECT_ROOT/runs/web_platform/exports/student/environment-$PLATFORM.zip"
chmod +x setup_mac.command
./setup_mac.command
"runtime/bin/python" run_learning_backtest.py --strategy generate_signals.py --output output/local_run

echo "SUCCESS: student kit runs on $PLATFORM"
