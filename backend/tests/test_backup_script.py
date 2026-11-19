from __future__ import annotations

import hashlib
import subprocess
import tarfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "backup-quantfish-user-data.sh"


def _fixture_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    runtime = project / "runs" / "web_platform"
    files = {
        project / "config" / "platform.yaml": "course: test\n",
        runtime / "repositories" / "teams.json": "[]\n",
        runtime / "repositories" / "quantfish.db": "sqlite fixture\n",
        runtime / "submissions" / "submission-1" / "generate_signals.py": "pass\n",
        runtime / "reports" / "submission-1" / "summary.csv": "metric,value\n",
        runtime / "mini_games" / "state.json": "{}\n",
        runtime / "exports" / "student" / "learning-data.zip": "generated\n",
    }
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return project, runtime


def _run_backup(project: Path, destination: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(SCRIPT),
            "--confirm-stopped",
            "--project-root",
            str(project),
            "--destination",
            str(destination),
            *extra,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _archive_names(destination: Path) -> tuple[Path, set[str]]:
    archives = list(destination.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0], "r:gz") as archive:
        return archives[0], set(archive.getnames())


def test_core_backup_contains_user_data_and_excludes_exports(tmp_path: Path) -> None:
    project, _ = _fixture_project(tmp_path)
    destination = tmp_path / "backups"

    result = _run_backup(project, destination)

    assert result.returncode == 0, result.stderr
    archive, names = _archive_names(destination)
    assert "quantfish-backup/config/platform.yaml" in names
    assert "quantfish-backup/runtime/repositories/teams.json" in names
    assert "quantfish-backup/runtime/repositories/quantfish.db" in names
    assert "quantfish-backup/runtime/submissions/submission-1/generate_signals.py" in names
    assert "quantfish-backup/runtime/reports/submission-1/summary.csv" in names
    assert "quantfish-backup/runtime/mini_games/state.json" in names
    assert "quantfish-backup/BACKUP_MANIFEST.txt" in names
    assert not any("/exports/" in name for name in names)

    checksum_path = Path(f"{archive}.sha256")
    expected = checksum_path.read_text(encoding="utf-8").split()[0]
    assert expected == hashlib.sha256(archive.read_bytes()).hexdigest()


def test_full_backup_includes_exports(tmp_path: Path) -> None:
    project, _ = _fixture_project(tmp_path)
    destination = tmp_path / "backups"

    result = _run_backup(project, destination, "--full")

    assert result.returncode == 0, result.stderr
    _, names = _archive_names(destination)
    assert "quantfish-backup/runtime/exports/student/learning-data.zip" in names


def test_custom_runtime_root_is_supported(tmp_path: Path) -> None:
    project, runtime = _fixture_project(tmp_path)
    custom_runtime = tmp_path / "persistent" / "quantfish-runtime"
    custom_runtime.parent.mkdir(parents=True)
    runtime.rename(custom_runtime)
    destination = tmp_path / "backups"

    result = _run_backup(
        project,
        destination,
        "--runtime-root",
        str(custom_runtime),
    )

    assert result.returncode == 0, result.stderr
    _, names = _archive_names(destination)
    assert "quantfish-backup/runtime/repositories/teams.json" in names


def test_missing_required_core_path_fails_without_archive(tmp_path: Path) -> None:
    project, runtime = _fixture_project(tmp_path)
    (runtime / "reports").rename(runtime / "reports-missing")
    destination = tmp_path / "backups"

    result = _run_backup(project, destination)

    assert result.returncode != 0
    assert "required path" in result.stderr.lower()
    assert not list(destination.glob("*.tar.gz"))


def test_destination_inside_archived_data_is_rejected(tmp_path: Path) -> None:
    project, runtime = _fixture_project(tmp_path)
    destination = runtime / "reports" / "backups"

    result = _run_backup(project, destination)

    assert result.returncode != 0
    assert "must not be inside archived path" in result.stderr
    assert not list(destination.glob("*.tar.gz"))


def test_help_documents_consistency_secrets_and_restore() -> None:
    result = subprocess.run(
        [str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--confirm-stopped" in result.stdout
    assert "QUANTFISH_ADMIN_PASSWORD" in result.stdout
    assert "Restore" in result.stdout
