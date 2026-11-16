#!/usr/bin/env bash
# Re-point the published repository at a different GitHub owner/repo.
#
# Updates the README badges, clone URLs and Pages demo link, the CONTRIBUTING
# clone URL and the landing page "View the source" button. Useful when forking
# the project or publishing it under another account.
#
# Usage: scripts/set-repo-owner.sh <owner> [repo]
set -Eeuo pipefail

OWNER="${1:-}"
REPO="${2:-quantfish}"

if [ -z "$OWNER" ]; then
  echo "usage: scripts/set-repo-owner.sh <owner> [repo]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

python3 - "$OWNER" "$REPO" \
  README.md \
  CONTRIBUTING.md \
  frontend/src/features/landing/view.tsx <<'PY'
import re
import sys
from pathlib import Path

owner, repo, *files = sys.argv[1:]
pages_pattern = re.compile(r"(?P<owner>[A-Za-z0-9_.-]+)\.github\.io/(?P<repo>quantfish)")
github_pattern = re.compile(r"github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>quantfish)")

changed = []
for name in files:
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    updated = pages_pattern.sub(f"{owner}.github.io/{repo}", text)
    updated = github_pattern.sub(f"github.com/{owner}/{repo}", updated)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        changed.append(name)

for name in changed:
    print(f"updated {name}")
if not changed:
    print("nothing to change")
print(f"repository now points at github.com/{owner}/{repo}")
PY

printf '\nNext:\n'
printf '  git remote add origin https://github.com/%s/%s.git\n' "$OWNER" "$REPO"
printf '  git push -u origin main\n'
