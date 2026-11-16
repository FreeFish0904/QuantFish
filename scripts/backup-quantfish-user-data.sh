#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNTIME_ROOT=""
DESTINATION=""
MODE="core"
CONFIRM_STOPPED="0"
TEMP_ARCHIVE=""

usage() {
  cat <<'USAGE'
Usage: scripts/backup-quantfish-user-data.sh [options]

Create and verify a compressed QuantFish user-data backup.

Stop the QuantFish web server and every scoring worker before running this script.

Options:
  --confirm-stopped
      Confirm that QuantFish and its scoring workers are stopped. Required.
  --full
      Include the complete runtime root, including rebuildable exports.
  --runtime-root PATH
      Runtime directory. Default: <project>/runs/web_platform
  --destination PATH
      Backup output directory. Default: <project>/backups
  --project-root PATH
      QuantFish repository root. Normally detected from this script's location.
  -h, --help
      Show this help.

Examples:
  scripts/backup-quantfish-user-data.sh --confirm-stopped
  scripts/backup-quantfish-user-data.sh --confirm-stopped --full
  scripts/backup-quantfish-user-data.sh --confirm-stopped \
    --runtime-root /srv/quantfish/runtime --destination /mnt/backups

The archive does not contain deployment secrets supplied through environment
variables, including QUANTFISH_ADMIN_PASSWORD and QUANTFISH_ADMIN_SESSION_SECRET.
Store those separately in a password manager or deployment secret store.

Restore:
  1. Stop QuantFish and all scoring workers.
  2. Verify the archive with its adjacent .sha256 file.
  3. Extract it into a temporary directory.
  4. Move the current runtime and config/platform.yaml aside.
  5. Copy quantfish-backup/runtime to the configured runtime root and copy
     quantfish-backup/config/platform.yaml to the project config directory.
  6. Restart with the same runtime root and deployment secrets, then verify a
     team login, submission history, and one submission detail page.
USAGE
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [ -n "$TEMP_ARCHIVE" ] && [ -e "$TEMP_ARCHIVE" ]; then
    rm -f "$TEMP_ARCHIVE"
  fi
}
trap cleanup EXIT

while [ "$#" -gt 0 ]; do
  case "$1" in
    --confirm-stopped)
      CONFIRM_STOPPED="1"
      shift
      ;;
    --full)
      MODE="full"
      shift
      ;;
    --runtime-root)
      [ "$#" -ge 2 ] || die "--runtime-root requires a path"
      RUNTIME_ROOT="$2"
      shift 2
      ;;
    --destination)
      [ "$#" -ge 2 ] || die "--destination requires a path"
      DESTINATION="$2"
      shift 2
      ;;
    --project-root)
      [ "$#" -ge 2 ] || die "--project-root requires a path"
      PROJECT_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

command -v python3 >/dev/null 2>&1 || die "required command not found: python3"
[ "$CONFIRM_STOPPED" = "1" ] || die \
  "stop QuantFish and its scoring workers, then rerun with --confirm-stopped"

PROJECT_ROOT="$(cd "$PROJECT_ROOT" 2>/dev/null && pwd)" || die \
  "project root does not exist: $PROJECT_ROOT"
RUNTIME_ROOT="${RUNTIME_ROOT:-${PROJECT_ROOT}/runs/web_platform}"
DESTINATION="${DESTINATION:-${PROJECT_ROOT}/backups}"
CONFIG_PATH="${PROJECT_ROOT}/config/platform.yaml"

[ -f "$CONFIG_PATH" ] || die "required path is missing: $CONFIG_PATH"
[ -d "$RUNTIME_ROOT" ] || die "required path is missing: $RUNTIME_ROOT"

if [ "$MODE" = "core" ]; then
  for name in repositories submissions reports mini_games; do
    [ -d "${RUNTIME_ROOT}/${name}" ] || die \
      "required path is missing: ${RUNTIME_ROOT}/${name}"
  done
fi

mkdir -p "$DESTINATION"
DESTINATION="$(cd "$DESTINATION" && pwd)"
python3 - "$MODE" "$RUNTIME_ROOT" "$DESTINATION" <<'PY'
from pathlib import Path
import sys


mode, runtime_text, destination_text = sys.argv[1:]
runtime = Path(runtime_text).resolve()
destination = Path(destination_text).resolve()
protected = [runtime] if mode == "full" else [
    runtime / name for name in ("repositories", "submissions", "reports", "mini_games")
]
for source in protected:
    if destination == source or source in destination.parents:
        raise SystemExit(
            f"error: backup destination must not be inside archived path: {source}"
        )
PY
TIMESTAMP="$(date -u '+%Y%m%dT%H%M%SZ')"
FINAL_ARCHIVE="${DESTINATION}/quantfish-user-data-${MODE}-${TIMESTAMP}-$$.tar.gz"
TEMP_ARCHIVE="${FINAL_ARCHIVE}.partial"
CHECKSUM_PATH="${FINAL_ARCHIVE}.sha256"

printf 'Creating %s backup from %s\n' "$MODE" "$RUNTIME_ROOT"

python3 - "$MODE" "$RUNTIME_ROOT" "$CONFIG_PATH" "$TEMP_ARCHIVE" <<'PY'
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import sys
import tarfile


mode, runtime_text, config_text, archive_text = sys.argv[1:]
runtime = Path(runtime_text).resolve()
config = Path(config_text).resolve()
archive_path = Path(archive_text)
core_directories = ("repositories", "submissions", "reports", "mini_games")


def add_tree(archive: tarfile.TarFile, source: Path, target: str) -> None:
    archive.add(source, arcname=target, recursive=True)


with tarfile.open(archive_path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
    archive.add(config, arcname="quantfish-backup/config/platform.yaml")
    if mode == "full":
        add_tree(archive, runtime, "quantfish-backup/runtime")
        included = ("complete runtime root",)
    else:
        for directory in core_directories:
            add_tree(
                archive,
                runtime / directory,
                f"quantfish-backup/runtime/{directory}",
            )
        included = core_directories

    manifest_lines = [
        "QuantFish user-data backup",
        f"created_utc={datetime.now(timezone.utc).isoformat()}",
        f"mode={mode}",
        f"source_runtime_root={runtime}",
        f"source_config={config}",
        f"included={','.join(included)}",
        "archive_root=quantfish-backup",
        "",
        "Archived paths:",
    ]
    manifest_lines.extend(member.name for member in archive.getmembers())
    payload = "\n".join(manifest_lines).encode("utf-8")
    info = tarfile.TarInfo("quantfish-backup/BACKUP_MANIFEST.txt")
    info.size = len(payload)
    info.mtime = int(datetime.now(timezone.utc).timestamp())
    info.mode = 0o600
    archive.addfile(info, BytesIO(payload))
PY

python3 - "$MODE" "$TEMP_ARCHIVE" <<'PY'
from pathlib import Path
import sys
import tarfile


mode, archive_text = sys.argv[1:]
required = {
    "quantfish-backup/config/platform.yaml",
    "quantfish-backup/BACKUP_MANIFEST.txt",
}
if mode == "core":
    required.update(
        f"quantfish-backup/runtime/{name}"
        for name in ("repositories", "submissions", "reports", "mini_games")
    )
else:
    required.add("quantfish-backup/runtime")

with tarfile.open(Path(archive_text), "r:gz") as archive:
    names = set(archive.getnames())
missing = sorted(required - names)
if missing:
    raise SystemExit(f"archive verification failed; missing: {', '.join(missing)}")
PY

mv "$TEMP_ARCHIVE" "$FINAL_ARCHIVE"
TEMP_ARCHIVE=""

python3 - "$FINAL_ARCHIVE" "$CHECKSUM_PATH" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys


archive = Path(sys.argv[1])
checksum_path = Path(sys.argv[2])
digest = sha256()
with archive.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
value = digest.hexdigest()
checksum_path.write_text(f"{value}  {archive.name}\n", encoding="utf-8")

verification_digest = sha256()
with archive.open("rb") as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        verification_digest.update(chunk)
verification = verification_digest.hexdigest()
if verification != value:
    checksum_path.unlink(missing_ok=True)
    archive.unlink(missing_ok=True)
    raise SystemExit("checksum verification failed")
PY

printf '\nBackup complete and verified.\n'
printf 'Archive:  %s\n' "$FINAL_ARCHIVE"
printf 'Checksum: %s\n' "$CHECKSUM_PATH"
printf '\nRestore instructions: run %s --help and read the Restore section.\n' "$0"
