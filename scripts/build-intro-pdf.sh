#!/usr/bin/env bash
# Rebuild docs/intro/QuantFish-简介.pdf from the HTML sources in docs/intro/.
#
# KaTeX is only needed to pre-render the formulas, so it is installed into a
# throw-away directory instead of becoming a dependency of frontend/package.json.
# Requires node + npm, network access on the first run, and Google Chrome for
# the HTML-to-PDF print step (set CHROME_BIN to override the binary).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTRO_DIR="$PROJECT_ROOT/docs/intro"
WORK_DIR="${TMPDIR:-/tmp}/quantfish-intro-build"
CHROME="${CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
KATEX_VERSION="0.19.1"

if [ ! -d "$WORK_DIR/node_modules/katex/dist" ]; then
  echo "installing katex@$KATEX_VERSION into $WORK_DIR"
  mkdir -p "$WORK_DIR"
  (cd "$WORK_DIR" && npm init -y >/dev/null 2>&1 && npm install "katex@$KATEX_VERSION" --no-audit --no-fund)
fi

KATEX_DIST="$WORK_DIR/node_modules/katex/dist" \
  node "$INTRO_DIR/render-math.mjs" "$WORK_DIR/intro-full.html"

if [ ! -x "$CHROME" ]; then
  echo "Chrome not found at $CHROME; set CHROME_BIN and re-run." >&2
  exit 1
fi

"$CHROME" --headless --disable-gpu --hide-scrollbars --no-pdf-header-footer \
  --virtual-time-budget=15000 \
  --user-data-dir="$WORK_DIR/chrome-profile" \
  --print-to-pdf="$INTRO_DIR/QuantFish-简介.pdf" \
  "file://$WORK_DIR/intro-full.html" 2>&1 | grep -E "bytes written" || true

echo "SUCCESS: $INTRO_DIR/QuantFish-简介.pdf ($(wc -c < "$INTRO_DIR/QuantFish-简介.pdf" | tr -d ' ') bytes)"
