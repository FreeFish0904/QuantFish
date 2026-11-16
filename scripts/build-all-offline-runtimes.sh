#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

for platform in macos-arm64 macos-x86_64; do
  echo "=== Building $platform ==="
  "$PROJECT_ROOT/scripts/build-offline-runtime.sh" "$platform"
done

echo "=== All local (Mac) platforms built ==="
echo "Windows-x86_64 must be built on a Windows machine or CI runner."
