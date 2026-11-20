from __future__ import annotations

import hashlib
import json
import shutil
import uuid
import zipfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from quantfish.data.releases import build_releases_from_config
from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.student_exports.platforms import ENVIRONMENT_PLATFORMS
from quantfish.submissions.starter_strategy import starter_strategy_text

if TYPE_CHECKING:
    from quantfish.web_app.settings import WebSettings


BACKEND_ROOT = Path("backend")
SOURCE_PACKAGE_PATH = BACKEND_ROOT / "src" / "quantfish"
KIT_PACKAGE_PATH = Path("src") / "quantfish"
KIT_METADATA_FILES = ("pyproject.toml", "environment.yml")


@dataclass(frozen=True)
class StudentExportRefreshResult:
    learning_data_zip: Path
    environment_zips: dict[str, Path]
    refreshed: bool


class StudentExportService:
    def __init__(
        self,
        settings: WebSettings,
        config_repository: ConfigRepository,
        *,
        project_root: Path | str | None = None,
    ):
        self.settings = settings
        self.config_repository = config_repository
        self.project_root = Path(project_root) if project_root else Path.cwd()

    @property
    def student_exports_root(self) -> Path:
        return self.settings.exports_root / "student"

    @property
    def runtime_import_root(self) -> Path:
        return self.settings.exports_root / "offline_runtimes"

    def learning_data_zip_path(self) -> Path:
        return self.student_exports_root / "learning-data.zip"

    def environment_zip_path(self, platform: str) -> Path:
        return self.student_exports_root / f"environment-{platform}.zip"

    def refresh(self, config: PlatformConfig | None = None) -> StudentExportRefreshResult:
        config = config or self.config_repository.load()
        raw_data_root = Path(config.data_releases.raw_data_root)
        if not raw_data_root.exists() or not raw_data_root.is_dir():
            raise FileNotFoundError(f"raw data root not found: {raw_data_root}")
        self.settings.ensure_runtime_dirs()
        self.student_exports_root.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_refresh_roots()
        current = self._current_refresh_result(config)
        if current is not None:
            return current
        refresh_root = self.settings.exports_root / f".student-refresh-{uuid.uuid4().hex}"
        releases_root = refresh_root / "data_releases"
        refresh_root.mkdir(parents=True)
        try:
            tmp_config = replace(
                config,
                data_releases=replace(
                    config.data_releases,
                    learning_output_root=(releases_root / "learning").as_posix(),
                    hidden_output_root=(releases_root / "hidden_test").as_posix(),
                ),
            )
            build_releases_from_config(
                tmp_config,
                release_names=("learning", "hidden_test"),
            )
            self._publish_releases(
                {
                    releases_root / "learning": Path(config.data_releases.learning_output_root),
                    releases_root / "hidden_test": Path(config.data_releases.hidden_output_root),
                }
            )

            learning_zip = refresh_root / "learning-data.zip"
            self._write_learning_data_zip(
                Path(config.data_releases.learning_output_root),
                learning_zip,
            )
            _publish_file(learning_zip, self.learning_data_zip_path())

            environment_zips: dict[str, Path] = {}
            for platform in self._platform_ids():
                if self._runtime_status(platform)["status"] != "available":
                    continue
                env_zip = refresh_root / f"environment-{platform}.zip"
                self._write_environment_zip(config, platform, env_zip)
                target = self.environment_zip_path(platform)
                _publish_file(env_zip, target)
                environment_zips[platform] = target

            self._write_export_manifest(config)
            return StudentExportRefreshResult(
                learning_data_zip=self.learning_data_zip_path(),
                environment_zips=environment_zips,
                refreshed=True,
            )
        finally:
            if refresh_root.exists():
                shutil.rmtree(refresh_root)

    def environment_options(self) -> dict[str, Any]:
        return {
            "platforms": [self._environment_option(platform) for platform in ENVIRONMENT_PLATFORMS]
        }

    def dependency_signature(self) -> str:
        digest = hashlib.sha256()
        for relative in KIT_METADATA_FILES:
            path = self.project_root / BACKEND_ROOT / relative
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_file_sha256(path).encode("ascii") if path.exists() else b"missing")
            digest.update(b"\0")
        return digest.hexdigest()

    def export_signature(self, config: PlatformConfig | None = None) -> str:
        config = config or self.config_repository.load()
        digest = hashlib.sha256()
        digest.update(json.dumps(config.to_dict(), sort_keys=True).encode("utf-8"))
        digest.update(b"\0")
        for relative in KIT_METADATA_FILES:
            path = self.project_root / BACKEND_ROOT / relative
            digest.update(_file_sha256(path).encode("ascii") if path.exists() else b"missing")
            digest.update(b"\0")
        source_root = self.project_root / SOURCE_PACKAGE_PATH
        if source_root.exists():
            for path in sorted(source_root.rglob("*")):
                if _skip_packaged_path(path):
                    continue
                if path.is_file():
                    digest.update(path.relative_to(self.project_root).as_posix().encode("utf-8"))
                    digest.update(b"\0")
                    digest.update(_file_sha256(path).encode("ascii"))
                    digest.update(b"\0")
        docs_root = self.project_root / "docs" / "student"
        if docs_root.exists():
            for path in _student_doc_paths(docs_root):
                relative = Path("docs") / "student" / path.relative_to(docs_root)
                digest.update(relative.as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(_file_sha256(path).encode("ascii"))
                digest.update(b"\0")
        return digest.hexdigest()

    def _publish_releases(self, releases: dict[Path, Path]) -> None:
        backups: list[tuple[Path, Path]] = []
        published: list[Path] = []
        try:
            for source, target in releases.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                backup = target.with_name(f".{target.name}.backup-{uuid.uuid4().hex}")
                if target.exists():
                    target.rename(backup)
                    backups.append((target, backup))
                shutil.move(source.as_posix(), target.as_posix())
                published.append(target)
            for _target, backup in backups:
                if backup.exists():
                    shutil.rmtree(backup)
        except Exception:
            for target in published:
                if target.exists():
                    shutil.rmtree(target)
            for target, backup in backups:
                if backup.exists() and not target.exists():
                    backup.rename(target)
            raise

    def _cleanup_stale_refresh_roots(self) -> None:
        for path in self.settings.exports_root.glob(".student-refresh-*"):
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()

    def _write_learning_data_zip(self, learning_root: Path, output: Path) -> None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(learning_root.rglob("*")):
                if not path.is_file() or _skip_packaged_path(path):
                    continue
                relative = Path("data_releases") / "learning" / path.relative_to(learning_root)
                archive.write(path, relative.as_posix())
            self._write_student_docs(archive)

    def _write_student_docs(self, archive: zipfile.ZipFile) -> None:
        docs_root = self.project_root / "docs" / "student"
        if not docs_root.exists():
            return
        for path in _student_doc_paths(docs_root):
            relative = Path("docs") / "student" / path.relative_to(docs_root)
            archive.write(path, relative.as_posix())

    def _write_environment_zip(
        self,
        config: PlatformConfig,
        platform: str,
        output: Path,
    ) -> None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            self._write_kit_files(archive, config, platform)
            runtime_zip = self.runtime_import_root / f"{platform}.zip"
            archive.write(runtime_zip, f"offline-runtime/{platform}.zip")
            source_root = self.project_root / SOURCE_PACKAGE_PATH
            for path in sorted(source_root.rglob("*")):
                if not path.is_file() or _skip_packaged_path(path):
                    continue
                archive.write(
                    path,
                    (KIT_PACKAGE_PATH / path.relative_to(source_root)).as_posix(),
                )
            for filename in KIT_METADATA_FILES:
                path = self.project_root / BACKEND_ROOT / filename
                if path.exists():
                    archive.write(path, filename)

    def _write_kit_files(
        self,
        archive: zipfile.ZipFile,
        config: PlatformConfig,
        platform: str,
    ) -> None:
        archive.writestr("README.zh-CN.md", _readme_text(platform))
        archive.writestr("generate_signals.py", starter_strategy_text())
        archive.writestr("run_learning_backtest.py", _runner_script_text())
        archive.writestr("plot_results.py", _plot_script_text())
        archive.writestr("setup_mac.command", _mac_setup_text(platform))
        archive.writestr("setup_windows.ps1", _windows_setup_text(platform))
        archive.writestr(
            "config/platform.yaml",
            yaml.safe_dump(
                config.to_dict(),
                allow_unicode=True,
                sort_keys=False,
            ),
        )
        archive.writestr(
            "export_manifest.json",
            json.dumps(
                {
                    "platform": platform,
                    "dependency_signature": self.dependency_signature(),
                    "export_signature": self.export_signature(config),
                    "generated_at": _utc_now(),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

    def _write_export_manifest(self, config: PlatformConfig) -> None:
        path = self.student_exports_root / "manifest.json"
        path.write_text(
            json.dumps(
                {
                    "dependency_signature": self.dependency_signature(),
                    "export_signature": self.export_signature(config),
                    "generated_at": _utc_now(),
                    "learning_zip": self.learning_data_zip_path().name,
                    "platforms": self.environment_options()["platforms"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _current_refresh_result(
        self,
        config: PlatformConfig,
    ) -> StudentExportRefreshResult | None:
        manifest_path = self.student_exports_root / "manifest.json"
        manifest = _read_json(manifest_path)
        if not manifest:
            return None
        if manifest.get("dependency_signature") != self.dependency_signature():
            return None
        if manifest.get("export_signature") != self.export_signature(config):
            return None
        if _parse_manifest_time(manifest.get("generated_at")) is None:
            return None
        learning_zip = self.learning_data_zip_path()
        if not learning_zip.exists():
            return None
        environment_zips: dict[str, Path] = {}
        for platform in self._platform_ids():
            if self._runtime_status(platform)["status"] != "available":
                continue
            package_path = self.environment_zip_path(platform)
            if not package_path.exists():
                return None
            environment_zips[platform] = package_path
        if _refresh_inputs_newer_than_manifest(
            config,
            manifest_path,
            self.project_root,
            self.runtime_import_root,
        ):
            return None
        return StudentExportRefreshResult(
            learning_data_zip=learning_zip,
            environment_zips=environment_zips,
            refreshed=False,
        )

    def _runtime_status(self, platform: str) -> dict[str, Any]:
        runtime_zip = self.runtime_import_root / f"{platform}.zip"
        manifest_path = self.runtime_import_root / f"{platform}.json"
        if not runtime_zip.exists():
            return {"status": "missing", "runtime_zip": runtime_zip}
        manifest = _read_json(manifest_path)
        if manifest.get("dependency_signature") != self.dependency_signature():
            return {"status": "stale", "runtime_zip": runtime_zip}
        return {"status": "available", "runtime_zip": runtime_zip}

    def _environment_option(self, platform_info: dict[str, str]) -> dict[str, Any]:
        platform = platform_info["platform"]
        status = self._runtime_status(platform)["status"]
        package_path = self.environment_zip_path(platform)
        available = status == "available" and package_path.exists()
        return {
            "platform": platform,
            "label": platform_info["label"],
            "architecture": platform_info["architecture"],
            "status": "available" if available else status,
            "size_bytes": package_path.stat().st_size if available else None,
            "updated_at": (
                datetime.fromtimestamp(package_path.stat().st_mtime, UTC)
                .replace(microsecond=0)
                .isoformat()
                if available
                else None
            ),
            "download_url": (f"/api/downloads/environment/{platform}.zip" if available else None),
        }

    def _platform_ids(self) -> list[str]:
        return [item["platform"] for item in ENVIRONMENT_PLATFORMS]


def _publish_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex}")
    shutil.move(source.as_posix(), temp_target.as_posix())
    temp_target.replace(target)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_manifest_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _refresh_inputs_newer_than_manifest(
    config: PlatformConfig,
    manifest_path: Path,
    project_root: Path,
    runtime_import_root: Path,
) -> bool:
    try:
        manifest_mtime_ns = manifest_path.stat().st_mtime_ns
    except FileNotFoundError:
        return True
    raw_data_root = Path(config.data_releases.raw_data_root)
    for path in _refresh_input_paths(raw_data_root, project_root, runtime_import_root):
        try:
            if path.stat().st_mtime_ns > manifest_mtime_ns:
                return True
        except FileNotFoundError:
            return True
    return False


def _refresh_input_paths(
    raw_data_root: Path,
    project_root: Path,
    runtime_import_root: Path,
) -> list[Path]:
    paths: list[Path] = []
    if raw_data_root.exists():
        paths.extend(path for path in raw_data_root.rglob("*") if path.is_file())
    for relative in KIT_METADATA_FILES:
        path = project_root / BACKEND_ROOT / relative
        if path.exists():
            paths.append(path)
    source_root = project_root / SOURCE_PACKAGE_PATH
    if source_root.exists():
        paths.extend(
            path
            for path in source_root.rglob("*")
            if path.is_file() and not _skip_packaged_path(path)
        )
    docs_root = project_root / "docs" / "student"
    if docs_root.exists():
        paths.extend(_student_doc_paths(docs_root))
    if runtime_import_root.exists():
        paths.extend(path for path in runtime_import_root.glob("*.zip") if path.is_file())
        paths.extend(path for path in runtime_import_root.glob("*.json") if path.is_file())
    return paths


def _student_doc_paths(docs_root: Path) -> list[Path]:
    return [
        path
        for path in sorted(docs_root.rglob("*"))
        if path.is_file()
        and not _skip_packaged_path(path)
        and not _skip_student_doc_relative_path(path.relative_to(docs_root))
    ]


def _skip_student_doc_relative_path(path: Path) -> bool:
    return path.name == ".DS_Store" or any(part.startswith("_") for part in path.parts)


def _skip_packaged_path(path: Path) -> bool:
    return any(part in {"__pycache__", ".pytest_cache"} for part in path.parts) or path.suffix in {
        ".pyc",
        ".pyo",
    }


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _runner_script_text() -> str:
    return """from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from quantfish.backtest import run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report
from quantfish.platform_config import ConfigRepository


def main() -> int:
    parser = argparse.ArgumentParser(description="Run QuantFish learning-data backtest.")
    parser.add_argument("--strategy", default="generate_signals.py")
    parser.add_argument("--data-root", default="data_releases/learning")
    parser.add_argument("--output", default="output/local_run")
    args = parser.parse_args()

    config = ConfigRepository(ROOT / "config" / "platform.yaml").load()
    learning_start = config.data_releases.learning_start
    learning_end = config.data_releases.learning_end
    config = replace(
        config,
        backtest=replace(
            config.backtest,
            data_start=learning_start,
            scoring_start=learning_start,
            scoring_end=learning_end,
        ),
    )
    data_root = ROOT / args.data_root
    if not (data_root / "data_catalog.json").exists():
        print(
            "Missing learning data. Download learning-data.zip from the website, "
            "then unzip it so data_releases/learning/data_catalog.json exists.",
            file=sys.stderr,
        )
        return 2

    result = run_student_backtest(ROOT / args.strategy, data_root, config)
    write_backtest_report(result, ROOT / args.output)
    print(result.summary.to_string(index=False))
    print(f"Results written to {ROOT / args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _plot_script_text() -> str:
    return """from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _series(frame, x_key, y_key):
    return [row[x_key] for row in frame], [row[y_key] for row in frame]


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot QuantFish local backtest results.")
    parser.add_argument("--report", default="output/local_run")
    parser.add_argument("--output", default="output/local_run/equity_metrics.png")
    args = parser.parse_args()
    report = Path(args.report)
    summary = pd.read_csv(report / "summary.csv")
    graph = json.loads((report / "graph_data.json").read_text(encoding="utf-8"))
    print(summary.to_string(index=False))

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.flatten()
    for axis, key, y_key, title in [
        (axes[0], "equity", "equity", "Cumulative return"),
        (axes[1], "drawdown", "drawdown", "Drawdown"),
        (axes[2], "turnover", "turnover", "Turnover"),
        (axes[3], "alpha", "alpha", "Alpha"),
    ]:
        rows = graph.get(key, [])
        if rows:
            x, y = _series(rows, "date", y_key)
            axis.plot(x, y)
        axis.set_title(title)
        axis.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150)
    print(f"Chart written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _mac_setup_text(platform: str) -> str:
    return f"""#!/bin/zsh
set -e
cd "$(dirname "$0")"
mkdir -p runtime
unzip -o offline-runtime/{platform}.zip -d runtime
if [ -x runtime/bin/conda-unpack ]; then
  runtime/bin/conda-unpack
fi
echo "Offline runtime unpacked. Run: runtime/bin/python run_learning_backtest.py"
"""


def _windows_setup_text(platform: str) -> str:
    return f"""$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force runtime | Out-Null
Expand-Archive -Force offline-runtime/{platform}.zip runtime
if (Test-Path .\\runtime\\Scripts\\conda-unpack.exe) {{
    .\\runtime\\Scripts\\conda-unpack.exe
}} elseif (Test-Path .\\runtime\\Scripts\\conda-unpack-script.py) {{
    .\\runtime\\python.exe .\\runtime\\Scripts\\conda-unpack-script.py
}}
Write-Host "Offline runtime unpacked. Run: .\\runtime\\python.exe run_learning_backtest.py"
"""


def _readme_text(platform: str) -> str:
    return f"""# QuantFish 本地离线回测包

本包适用于 `{platform}`。学生下载本包和 `learning-data.zip` 后，不需要联网安装 Python 包。

## 你应该得到的文件结构

```text
quantfish-local-kit/
  README.zh-CN.md
  offline-runtime/
    {platform}.zip
  setup_mac.command
  setup_windows.ps1
  pyproject.toml
  environment.yml
  src/quantfish/
  config/platform.yaml
  data_releases/learning/
  generate_signals.py
  run_learning_backtest.py
  plot_results.py
  output/
```

## macOS

```bash
cd quantfish-local-kit
unzip ../learning-data.zip
chmod +x setup_mac.command
./setup_mac.command
runtime/bin/python run_learning_backtest.py --strategy generate_signals.py --output output/local_run
runtime/bin/python plot_results.py --report output/local_run
```

## Windows PowerShell

```powershell
cd quantfish-local-kit
Expand-Archive ..\\learning-data.zip -DestinationPath .
Set-ExecutionPolicy -Scope Process Bypass
.\\setup_windows.ps1
.\\runtime\\python.exe run_learning_backtest.py --strategy generate_signals.py --output output/local_run
.\\runtime\\python.exe plot_results.py --report output/local_run
```

## 写策略

只修改 `generate_signals.py`。函数必须叫 `generate_signals`。

最推荐的新手写法是返回 pandas Series：index 放股票代码，value 放 score。平台会自动整理股票代码，例如 `1.0` 会变成 `000001`，也会把 score 转成仓位并处理交易限制。

```python
import pandas as pd


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "dretwd"],
        numeric_columns=["dretwd"],
    )
    score = -today["dretwd"]
    return pd.Series(score.values, index=today["stkcd"])
```

这里 `numeric_columns=["dretwd"]` 让平台自动把 `dretwd` 列转成数字；如果某一行是异常文本或空值，平台会把它变成 `NaN`（表示无信号），不需要手动写 `pd.to_numeric`。

如果你更喜欢表格，也可以返回包含 `code` 和 `score` 两列的 pandas DataFrame。

回测结果会写入 `output/local_run`，其中 `summary.csv` 是指标表，`graph_data.json` 是画图数据，`equity_metrics.png` 是本地生成的累计收益图。
"""
