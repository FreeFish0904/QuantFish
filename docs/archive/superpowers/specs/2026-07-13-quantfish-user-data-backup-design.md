# QuantFish User-Data Backup Design

## Goal

Provide an operator-friendly shell script that creates a verified, restorable
backup of QuantFish user-owned data while the server is stopped.

The default backup should preserve authoritative user state without copying
large artifacts that QuantFish can rebuild. An explicit full mode should remain
available when an operator wants the entire runtime tree.

## Scope

The script will live at `scripts/backup-quantfish-user-data.sh` and run from any
working directory. It will accept the repository root as its default context,
with options for a different runtime root and backup destination.

The default core backup contains:

- `runs/web_platform/repositories/`: team accounts, password records, cohorts,
  submission metadata, SQLite state, and administrator settings history.
- `runs/web_platform/submissions/`: uploaded student strategy source files.
- `runs/web_platform/reports/`: backtest results, charts, diagnostics, series,
  and worker logs.
- `runs/web_platform/mini_games/`: participant-owned mini-game state.
- `config/platform.yaml`: administrator-managed course, execution, scoring, and
  dataset-window configuration.

Full mode contains the complete runtime root plus `config/platform.yaml`,
including generated student exports and offline runtime packages.

The script will not include source datasets such as `new_data/` or
`data_releases/`. These are platform data rather than user-owned state. It will
also not capture secrets supplied through environment variables, including the
admin password and session-signing secret; operators must store those in a
password manager or deployment secret store.

## Operator Interface

The script will provide:

- a default core-backup command;
- `--full` for the complete runtime root;
- `--runtime-root PATH` for non-default deployments;
- `--destination PATH` for the output directory;
- `--help` with examples and restore guidance.

Output names will contain the backup mode and a sortable UTC timestamp. The
successful result will be a compressed tar archive, a SHA-256 checksum file,
and concise restoration instructions.

## Backup Workflow

1. Resolve and validate repository, runtime, configuration, and destination
   paths before creating output.
2. Refuse to proceed when required core paths are absent.
3. Warn clearly that the QuantFish web process and scoring workers must be
   stopped. The script will require an explicit operator acknowledgement rather
   than attempting to kill processes itself.
4. Build the archive at a temporary path in the destination directory.
5. Add a generated manifest containing the backup mode, source paths, creation
   time, and archived file list.
6. Verify that the temporary archive is readable and contains every required
   top-level entry.
7. Atomically rename the verified archive to its final timestamped name.
8. Generate and verify its SHA-256 checksum.
9. Print the final paths and restoration steps.

The script will not delete or rotate earlier backups.

## Consistency And Failure Handling

Stopping QuantFish before backup is the consistency boundary. This prevents JSON,
SQLite, uploaded source, and report artifacts from changing independently while
the archive is being created. SQLite WAL and shared-memory sidecar files will be
included when present because the whole repositories directory is archived.

The script will use strict shell error handling. Any validation, archive, or
verification failure will remove only its own temporary files and exit without
publishing a successful-looking archive. Existing backups and runtime data will
never be modified.

## Restore Procedure

Restoration is intentionally manual and explicit:

1. Stop QuantFish and its scoring workers.
2. Verify the archive against its checksum.
3. Move the current runtime root and `config/platform.yaml` aside rather than
   deleting them.
4. Extract the backup from the repository root so recorded relative paths land
   in their original locations.
5. Start QuantFish with the same runtime-root argument and deployment secrets.
6. Confirm team login, submission history, and one submission detail page.

The script will print these instructions but will not automate destructive
restore operations.

## Verification

Automated tests will exercise the script against a temporary fixture tree and
verify:

- core mode includes all required user-data paths and excludes exports;
- full mode includes exports;
- custom runtime and destination paths work;
- missing required paths fail without leaving a final archive;
- archive and checksum verification succeed;
- help output documents secrets and restoration.

The final verification will also run a shell syntax check and the focused test
file in the `QuantFish` Conda environment.
