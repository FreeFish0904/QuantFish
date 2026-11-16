from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Sequence
import zipfile

from quantfish.student_exports.platforms import ENVIRONMENT_PLATFORMS


DEFAULT_PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
DEFAULT_CONDA_CHANNELS = (
    "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main",
    "https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/r",
)

EXPECTED_EXECUTABLES = {
    "macos-arm64": "bin/python",
    "macos-x86_64": "bin/python",
    "windows-x86_64": "python.exe",
}

CommandRunner = Callable[[list[str]], None]


@dataclass(frozen=True)
class RuntimePackageResult:
    zip_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class RuntimeBuildRequest:
    platform: str
    project_root: Path
    output_dir: Path = Path("dist/offline-runtimes")
    build_root: Path = Path(".runtime-build/offline-runtimes")
    conda_executable: str = "conda"
    conda_pack_executable: str = "conda-pack"
    pip_index_url: str = DEFAULT_PIP_INDEX_URL
    conda_channels: tuple[str, ...] = DEFAULT_CONDA_CHANNELS
    python_version: str = "3.12"


def build_runtime_package(
    request: RuntimeBuildRequest,
    *,
    run: Callable[[list[str]], None] | None = None,
) -> RuntimePackageResult:
    _validate_platform(request.platform)
    runner = run or _run_command
    project_root = request.project_root.resolve()
    output_dir = request.output_dir.resolve()
    build_prefix = request.build_root.resolve() / request.platform
    zip_path = output_dir / f"{request.platform}.zip"
    manifest_path = output_dir / f"{request.platform}.json"

    if build_prefix.exists():
        shutil.rmtree(build_prefix)
    output_dir.mkdir(parents=True, exist_ok=True)
    build_prefix.parent.mkdir(parents=True, exist_ok=True)

    create_command = [
        request.conda_executable,
        "create",
        "-y",
        "-p",
        build_prefix.as_posix(),
        f"python={request.python_version}",
        "pip",
    ]
    if request.conda_channels:
        create_command.append("--override-channels")
        for channel in request.conda_channels:
            create_command.extend(["-c", channel])
    runner(create_command)

    install_command = [
        request.conda_executable,
        "run",
        "-p",
        build_prefix.as_posix(),
        "python",
        "-m",
        "pip",
        "install",
    ]
    if request.pip_index_url:
        install_command.extend(["-i", request.pip_index_url])
    install_command.append(_backend_root(project_root).as_posix())
    runner(install_command)

    if zip_path.exists():
        zip_path.unlink()
    runner(
        [
            request.conda_pack_executable,
            "-p",
            build_prefix.as_posix(),
            "-o",
            zip_path.as_posix(),
            "--force",
            "--zip-symlinks",
        ]
    )
    _validate_runtime_zip(request.platform, zip_path)
    _write_runtime_manifest(request.platform, manifest_path, project_root)
    return RuntimePackageResult(zip_path=zip_path, manifest_path=manifest_path)


def import_runtime_package(
    *,
    platform: str,
    zip_path: Path,
    runtime_root: Path,
    project_root: Path,
    manifest_path: Path | None = None,
) -> RuntimePackageResult:
    _validate_platform(platform)
    zip_path = zip_path.resolve()
    runtime_root = runtime_root.resolve()
    project_root = project_root.resolve()
    _validate_runtime_zip(platform, zip_path)

    target_root = runtime_root / "exports" / "offline_runtimes"
    target_root.mkdir(parents=True, exist_ok=True)
    target_zip = target_root / f"{platform}.zip"
    target_manifest = target_root / f"{platform}.json"
    _publish_file(zip_path, target_zip)

    manifest = _manifest_payload(platform, project_root)
    if manifest_path is not None:
        supplied = _read_manifest(manifest_path)
        supplied_signature = supplied.get("dependency_signature")
        if supplied_signature and supplied_signature != manifest["dependency_signature"]:
            raise ValueError(
                "runtime manifest dependency_signature does not match this project"
            )
        if supplied.get("platform") not in (None, platform):
            raise ValueError("runtime manifest platform does not match requested platform")
        manifest.update({key: value for key, value in supplied.items() if key != "platform"})
        manifest["platform"] = platform
    target_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return RuntimePackageResult(zip_path=target_zip, manifest_path=target_manifest)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build and import QuantFish offline Python runtime packages."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--platform", required=True, choices=_platform_ids())
    build_parser.add_argument("--project-root", default=".")
    build_parser.add_argument("--output-dir", default="dist/offline-runtimes")
    build_parser.add_argument("--build-root", default=".runtime-build/offline-runtimes")
    build_parser.add_argument("--conda", default="conda")
    build_parser.add_argument("--conda-pack", default="conda-pack")
    build_parser.add_argument("--pip-index-url", default=DEFAULT_PIP_INDEX_URL)
    build_parser.add_argument("--python-version", default="3.12")

    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--platform", required=True, choices=_platform_ids())
    import_parser.add_argument("--zip", required=True, dest="zip_path")
    import_parser.add_argument("--manifest")
    import_parser.add_argument("--runtime-root", default="runs/web_platform")
    import_parser.add_argument("--project-root", default=".")

    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_runtime_package(
            RuntimeBuildRequest(
                platform=args.platform,
                project_root=Path(args.project_root),
                output_dir=Path(args.output_dir),
                build_root=Path(args.build_root),
                conda_executable=args.conda,
                conda_pack_executable=args.conda_pack,
                pip_index_url=args.pip_index_url,
                python_version=args.python_version,
            )
        )
    elif args.command == "import":
        result = import_runtime_package(
            platform=args.platform,
            zip_path=Path(args.zip_path),
            manifest_path=Path(args.manifest) if args.manifest else None,
            runtime_root=Path(args.runtime_root),
            project_root=Path(args.project_root),
        )
    else:
        return 2
    print(
        json.dumps(
            {
                "manifest_path": result.manifest_path.as_posix(),
                "zip_path": result.zip_path.as_posix(),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _validate_platform(platform: str) -> None:
    if platform not in EXPECTED_EXECUTABLES:
        raise ValueError(f"unsupported runtime platform: {platform}")


def _platform_ids() -> list[str]:
    return [item["platform"] for item in ENVIRONMENT_PLATFORMS]


def _validate_runtime_zip(platform: str, zip_path: Path) -> None:
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)
    expected = EXPECTED_EXECUTABLES[platform]
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    if expected not in names:
        raise ValueError(
            f"{zip_path} does not look like a {platform} runtime package; "
            f"expected {expected} at the zip root"
        )


def _write_runtime_manifest(platform: str, manifest_path: Path, project_root: Path) -> None:
    manifest_path.write_text(
        json.dumps(
            _manifest_payload(platform, project_root),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _manifest_payload(platform: str, project_root: Path) -> dict[str, str]:
    return {
        "dependency_signature": _dependency_signature(project_root),
        "platform": platform,
    }


def _backend_root(project_root: Path) -> Path:
    """Return the directory that holds pyproject.toml for this project layout."""

    candidate = project_root / "backend"
    if (candidate / "pyproject.toml").is_file():
        return candidate
    return project_root


def _dependency_signature(project_root: Path) -> str:
    digest = hashlib.sha256()
    backend_root = _backend_root(project_root)
    for relative in ("pyproject.toml", "environment.yml"):
        path = backend_root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_sha256(path).encode("ascii") if path.exists() else b"missing")
        digest.update(b"\0")
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("runtime manifest must be a JSON object")
    return {str(key): str(value) for key, value in data.items()}


def _publish_file(source: Path, target: Path) -> None:
    temp_target = target.with_name(f".{target.name}.tmp")
    shutil.copyfile(source, temp_target)
    temp_target.replace(target)


def _run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


if __name__ == "__main__":
    raise SystemExit(main())
