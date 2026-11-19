from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from quantfish.platform_config import ConfigRepository
from quantfish.student_exports.runtime_packages import (
    RuntimeBuildRequest,
    build_runtime_package,
    import_runtime_package,
)
from quantfish.student_exports.service import StudentExportService
from quantfish.web_app.settings import WebSettings


def _write_runtime_zip(path: Path, executable: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(executable, "")
        archive.writestr("pyvenv.cfg", "home = packed\n")


def test_import_runtime_package_validates_zip_and_writes_manifest(tmp_path: Path) -> None:
    source_zip = tmp_path / "source" / "macos-arm64.zip"
    _write_runtime_zip(source_zip, "bin/python")
    runtime_root = tmp_path / "runtime"

    result = import_runtime_package(
        platform="macos-arm64",
        zip_path=source_zip,
        runtime_root=runtime_root,
        project_root=Path.cwd(),
    )

    imported_zip = runtime_root / "exports" / "offline_runtimes" / "macos-arm64.zip"
    imported_manifest = runtime_root / "exports" / "offline_runtimes" / "macos-arm64.json"
    expected_signature = StudentExportService(
        WebSettings(runtime_root=runtime_root),
        ConfigRepository(Path("config/platform.yaml")),
        project_root=Path.cwd(),
    ).dependency_signature()

    assert result.zip_path == imported_zip
    assert result.manifest_path == imported_manifest
    assert imported_zip.read_bytes() == source_zip.read_bytes()
    assert json.loads(imported_manifest.read_text(encoding="utf-8")) == {
        "dependency_signature": expected_signature,
        "platform": "macos-arm64",
    }


def test_import_runtime_package_rejects_zip_without_expected_python(tmp_path: Path) -> None:
    source_zip = tmp_path / "windows-x86_64.zip"
    _write_runtime_zip(source_zip, "bin/python")

    with pytest.raises(ValueError, match=re.escape("python.exe")):
        import_runtime_package(
            platform="windows-x86_64",
            zip_path=source_zip,
            runtime_root=tmp_path / "runtime",
            project_root=Path.cwd(),
        )


def test_runtime_package_module_does_not_need_web_stack() -> None:
    code = """
import builtins
from pathlib import Path

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    blocked = ("fastapi", "pandas", "yaml")
    if any(name == package or name.startswith(f"{package}.") for package in blocked):
        raise ModuleNotFoundError(f"blocked {name}")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from quantfish.student_exports import runtime_packages

payload = runtime_packages._manifest_payload("macos-arm64", Path("."))
print(payload["platform"])
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "backend" / "src")

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "macos-arm64"


def test_export_monitor_module_does_not_need_fastapi_stack() -> None:
    code = """
import builtins

original_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "fastapi" or name.startswith("fastapi."):
        raise ModuleNotFoundError("blocked fastapi")
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from quantfish.student_exports import monitor

print(monitor.__name__)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "backend" / "src")

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "quantfish.student_exports.monitor"


def test_build_runtime_package_runs_conda_pack_and_writes_manifest(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, cwd: Path | None = None) -> None:
        commands.append(command)
        if command[:2] == ["conda-pack", "-p"]:
            output = Path(command[command.index("-o") + 1])
            _write_runtime_zip(output, "bin/python")

    request = RuntimeBuildRequest(
        platform="macos-arm64",
        project_root=Path.cwd(),
        output_dir=tmp_path / "dist",
        build_root=tmp_path / "build",
        conda_executable="conda",
        pip_index_url="https://pypi.tuna.tsinghua.edu.cn/simple",
    )

    result = build_runtime_package(request, run=fake_run)

    assert result.zip_path == tmp_path / "dist" / "macos-arm64.zip"
    assert result.manifest_path == tmp_path / "dist" / "macos-arm64.json"
    assert commands[0][:4] == ["conda", "create", "-y", "-p"]
    assert commands[1][:4] == ["conda", "run", "-p", (tmp_path / "build" / "macos-arm64").as_posix()]
    assert "https://pypi.tuna.tsinghua.edu.cn/simple" in commands[1]
    assert commands[2][:2] == ["conda-pack", "-p"]
    assert "--zip-symlinks" in commands[2]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["platform"] == "macos-arm64"
    assert manifest["dependency_signature"]


def test_github_workflow_builds_all_offline_runtime_platforms() -> None:
    workflow = Path(".github/workflows/offline-runtimes.yml")

    text = workflow.read_text(encoding="utf-8")

    assert "macos-arm64" in text
    assert "macos-x86_64" in text
    assert "windows-x86_64" in text
    assert "quantfish.student_exports.runtime_packages build" in text
    assert 'CONDA_EXE="$CONDA/Scripts/conda.exe"' in text
    assert '--conda "$CONDA_EXE"' in text
    assert "actions/upload-artifact" in text


def test_runtime_wrapper_scripts_use_quantfish_conda_env() -> None:
    shell_build = Path("scripts/build-offline-runtime.sh").read_text(encoding="utf-8")
    shell_import = Path("scripts/import-offline-runtime.sh").read_text(encoding="utf-8")
    powershell_build = Path("scripts/build-offline-runtime.ps1").read_text(encoding="utf-8")
    powershell_import = Path("scripts/import-offline-runtime.ps1").read_text(encoding="utf-8")

    assert "QUANTFISH_CONDA_ENV" in shell_build
    assert "QUANTFISH_CONDA_ENV" in shell_import
    assert "conda run -n \"$QUANTFISH_CONDA_ENV\" python" in shell_build
    assert "conda run -n \"$QUANTFISH_CONDA_ENV\" python" in shell_import
    assert "QUANTFISH_CONDA_ENV" in powershell_build
    assert "QUANTFISH_CONDA_ENV" in powershell_import
    assert '"conda", "run", "-n", $CondaEnv, "python"' in powershell_build
    assert '"conda", "run", "-n", $CondaEnv, "python"' in powershell_import
