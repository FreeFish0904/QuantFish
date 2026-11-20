from __future__ import annotations

import json
import os
import subprocess
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

import quantfish.student_exports.service as student_export_service_module
from quantfish.platform_config import (
    ConfigRepository,
    DataReleasesConfig,
    PlatformConfig,
)
from quantfish.student_exports.monitor import main as export_monitor_main
from quantfish.student_exports.service import StudentExportService, _runner_script_text
from quantfish.submissions.storage import SubmissionStorage
from quantfish.web_app.settings import WebSettings


def _write_source_data(root: Path) -> None:
    stock_dir = root / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {"TradingDate": "2022-06-01", "Symbol": "000001", "Ret": 0.01},
            {"TradingDate": "2023-06-01", "Symbol": "000001", "Ret": 0.02},
        ]
    ).to_csv(stock_dir / "daily_returns.csv", index=False)

    market_dir = root / "distribute" / "market"
    market_dir.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "indexcd": "000300",
                "idxtrd01": "2023-06-01",
                "idxtrd05": 4000.0,
                "idxtrd08": 1.0,
            }
        ]
    ).to_csv(market_dir / "index_daily.csv", index=False)


def _config(tmp_path: Path) -> PlatformConfig:
    return PlatformConfig.default().__class__(
        course=PlatformConfig.default().course,
        data_releases=DataReleasesConfig(
            raw_data_root=(tmp_path / "new_data").as_posix(),
            learning_output_root=(tmp_path / "releases" / "learning").as_posix(),
            hidden_output_root=(tmp_path / "releases" / "hidden_test").as_posix(),
            learning_start=PlatformConfig.default().data_releases.learning_start,
            learning_end=PlatformConfig.default().data_releases.learning_end,
            hidden_start=PlatformConfig.default().data_releases.hidden_start,
            hidden_end=PlatformConfig.default().data_releases.hidden_end,
        ),
        backtest=PlatformConfig.default().backtest,
        scoring=PlatformConfig.default().scoring,
        execution=PlatformConfig.default().execution,
    )


def _settings(tmp_path: Path, config_path: Path) -> WebSettings:
    return WebSettings(
        runtime_root=tmp_path / "runtime",
        config_path=config_path,
        admin_password="quantfish-admin",
        admin_session_secret="test-session-secret",
    )


def _write_runtime_zip(settings: WebSettings, platform: str, signature: str) -> None:
    runtime_root = settings.exports_root / "offline_runtimes"
    runtime_root.mkdir(parents=True)
    zip_path = runtime_root / f"{platform}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("runtime-marker.txt", platform)
    (runtime_root / f"{platform}.json").write_text(
        json.dumps({"dependency_signature": signature}),
        encoding="utf-8",
    )


def _is_internal_student_doc(zip_name: str) -> bool:
    path = Path(zip_name)
    if len(path.parts) < 3 or path.parts[:2] != ("docs", "student"):
        return False
    return path.name == ".DS_Store" or any(part.startswith("_") for part in path.parts[2:])


def test_student_docs_tree_only_contains_student_facing_files() -> None:
    internal_files = [
        path.relative_to("docs/student").as_posix()
        for path in sorted(Path("docs/student").rglob("*"))
        if path.is_file()
        and (
            path.name == ".DS_Store"
            or any(part.startswith("_") for part in path.relative_to("docs/student").parts)
        )
    ]

    assert internal_files == []


def test_refresh_rebuilds_both_releases_and_student_archives(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    _write_runtime_zip(settings, "macos-arm64", service.dependency_signature())

    result = service.refresh(config)

    learning_returns = pd.read_csv(
        Path(config.data_releases.learning_output_root)
        / "distribute"
        / "stock"
        / "daily_returns.csv"
    )
    hidden_returns = pd.read_csv(
        Path(config.data_releases.hidden_output_root) / "distribute" / "stock" / "daily_returns.csv"
    )
    assert learning_returns["TradingDate"].tolist() == ["2022-06-01"]
    assert hidden_returns["TradingDate"].tolist() == ["2023-06-01"]

    assert result.learning_data_zip.exists()
    with zipfile.ZipFile(result.learning_data_zip) as archive:
        names = archive.namelist()
    assert "data_releases/learning/data_catalog.json" in names
    assert "docs/student/README.md" in names
    assert "docs/student/examples/hello_strategy.py" in names
    assert not any(_is_internal_student_doc(name) for name in names)
    assert not any("hidden_test" in name for name in names)

    env_zip = result.environment_zips["macos-arm64"]
    with zipfile.ZipFile(env_zip) as archive:
        names = archive.namelist()
        bundled_strategy = archive.read("generate_signals.py").decode("utf-8")
        mac_setup = archive.read("setup_mac.command").decode("utf-8")
        windows_setup = archive.read("setup_windows.ps1").decode("utf-8")
        readme = archive.read("README.zh-CN.md").decode("utf-8")
    assert "README.zh-CN.md" in names
    assert "generate_signals.py" in names
    assert "run_learning_backtest.py" in names
    assert "plot_results.py" in names
    assert bundled_strategy == SubmissionStorage(settings.runtime_root).starter_strategy_text()
    assert "价格成交额动量 starter strategy" in bundled_strategy
    assert "当天收益越高、成交越活跃" in bundled_strategy
    assert "学生主要负责构造 score" in bundled_strategy
    assert "numeric_columns" in bundled_strategy
    assert "dnvaltrd" in bundled_strategy
    assert "平台会自动整理股票代码" in readme
    assert "setup_mac.command" in names
    assert "setup_windows.ps1" in names
    assert "config/platform.yaml" in names
    assert "offline-runtime/macos-arm64.zip" in names
    assert "src/quantfish/__init__.py" in names
    assert not any("data_releases/hidden_test" in name for name in names)
    assert "pip install" not in mac_setup
    assert "conda install" not in mac_setup
    assert "pip install" not in windows_setup
    assert "conda install" not in windows_setup
    assert "conda-unpack" in mac_setup
    assert "conda-unpack" in windows_setup
    assert "data_releases/learning/" in readme

    options = service.environment_options()
    mac = next(item for item in options["platforms"] if item["platform"] == "macos-arm64")
    win = next(item for item in options["platforms"] if item["platform"] == "windows-x86_64")
    assert mac["status"] == "available"
    assert mac["download_url"] == "/api/downloads/environment/macos-arm64.zip"
    assert win["status"] == "missing"


def test_refresh_does_not_rebuild_explicit_historical_release_roots(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    historical_roots = [tmp_path / "live_releases" / f"learning_{index}" for index in range(1, 4)]
    for root in historical_roots:
        root.mkdir(parents=True)
        (root / "sentinel.txt").write_text("keep", encoding="utf-8")
    config = replace(
        config,
        data_releases=replace(
            config.data_releases,
            learning_1_output_root=historical_roots[0].as_posix(),
            learning_2_output_root=historical_roots[1].as_posix(),
            learning_3_output_root=historical_roots[2].as_posix(),
        ),
    )
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    service = StudentExportService(
        _settings(tmp_path, config_path),
        ConfigRepository(config_path),
    )

    service.refresh(config)

    for root in historical_roots:
        assert (root / "sentinel.txt").read_text(encoding="utf-8") == "keep"
        assert not (root / "data_catalog.json").exists()


def test_refresh_removes_stale_student_refresh_temp_dirs(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    stale_refresh = settings.exports_root / ".student-refresh-stale"
    stale_refresh.mkdir(parents=True)
    (stale_refresh / "partial.txt").write_text("aborted refresh", encoding="utf-8")

    service.refresh(config)

    assert not stale_refresh.exists()


def test_refresh_skips_rebuild_when_export_manifest_is_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    _write_runtime_zip(settings, "macos-arm64", service.dependency_signature())
    build_calls = 0
    original_build = student_export_service_module.build_releases_from_config

    def recording_build_releases(
        config: PlatformConfig,
        release_names: tuple[str, ...] | None = None,
    ) -> object:
        nonlocal build_calls
        build_calls += 1
        assert release_names == ("learning", "hidden_test")
        return original_build(config, release_names=release_names)

    monkeypatch.setattr(
        student_export_service_module,
        "build_releases_from_config",
        recording_build_releases,
    )

    first = service.refresh(config)
    second = service.refresh(config)

    assert first.refreshed is True
    assert second.refreshed is False
    assert build_calls == 1
    assert second.learning_data_zip == service.learning_data_zip_path()
    assert second.environment_zips["macos-arm64"] == service.environment_zip_path("macos-arm64")


def test_refresh_rebuilds_when_source_data_is_newer_than_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    raw_data_root = Path(config.data_releases.raw_data_root)
    _write_source_data(raw_data_root)
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    _write_runtime_zip(settings, "macos-arm64", service.dependency_signature())
    build_calls = 0
    original_build = student_export_service_module.build_releases_from_config

    def recording_build_releases(
        config: PlatformConfig,
        release_names: tuple[str, ...] | None = None,
    ) -> object:
        nonlocal build_calls
        build_calls += 1
        assert release_names == ("learning", "hidden_test")
        return original_build(config, release_names=release_names)

    monkeypatch.setattr(
        student_export_service_module,
        "build_releases_from_config",
        recording_build_releases,
    )

    first = service.refresh(config)
    manifest_path = settings.exports_root / "student" / "manifest.json"
    source_path = raw_data_root / "distribute" / "stock" / "daily_returns.csv"
    future_mtime_ns = manifest_path.stat().st_mtime_ns + 2_000_000_000
    os.utime(source_path, ns=(future_mtime_ns, future_mtime_ns))

    second = service.refresh(config)

    assert first.refreshed is True
    assert second.refreshed is True
    assert build_calls == 2


def test_runner_script_reports_missing_learning_data_before_backtest(tmp_path: Path) -> None:
    kit_root = tmp_path / "quantfish-local-kit"
    kit_root.mkdir()
    (kit_root / "config").mkdir()
    ConfigRepository(kit_root / "config" / "platform.yaml").save(PlatformConfig.default())
    (kit_root / "run_learning_backtest.py").write_text(
        _runner_script_text(),
        encoding="utf-8",
    )
    (kit_root / "generate_signals.py").write_text(
        "import pandas as pd\n\n"
        "def generate_signals(data, date):\n"
        "    return pd.Series(dtype=float)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("backend/src").resolve()) + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(
        [sys.executable, "run_learning_backtest.py"],
        cwd=kit_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 2
    assert "Missing learning data" in output
    assert "learning-data.zip" in output
    assert "Traceback" not in output


def test_runtime_dependency_signature_marks_environment_stale(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    _write_runtime_zip(settings, "macos-arm64", "old-dependencies")

    service.refresh(config)

    options = service.environment_options()
    mac = next(item for item in options["platforms"] if item["platform"] == "macos-arm64")
    assert mac["status"] == "stale"
    assert mac["download_url"] is None


def test_refresh_preserves_previous_releases_when_rebuild_fails(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    _write_runtime_zip(settings, "macos-arm64", service.dependency_signature())
    service.refresh(config)
    original_learning = (
        Path(config.data_releases.learning_output_root) / "data_catalog.json"
    ).read_text(encoding="utf-8")

    bad_config = PlatformConfig(
        course=config.course,
        data_releases=DataReleasesConfig(
            raw_data_root=(tmp_path / "missing-source").as_posix(),
            learning_output_root=config.data_releases.learning_output_root,
            hidden_output_root=config.data_releases.hidden_output_root,
            learning_start=config.data_releases.learning_start,
            learning_end=config.data_releases.learning_end,
            hidden_start=config.data_releases.hidden_start,
            hidden_end=config.data_releases.hidden_end,
        ),
        backtest=config.backtest,
        scoring=config.scoring,
        execution=config.execution,
    )

    with pytest.raises(FileNotFoundError):
        service.refresh(bad_config)

    assert (Path(config.data_releases.learning_output_root) / "data_catalog.json").read_text(
        encoding="utf-8"
    ) == original_learning


def test_export_monitor_status_and_refresh_commands(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _config(tmp_path)
    _write_source_data(Path(config.data_releases.raw_data_root))
    config_path = tmp_path / "config" / "platform.yaml"
    ConfigRepository(config_path).save(config)
    settings = _settings(tmp_path, config_path)
    service = StudentExportService(settings, ConfigRepository(config_path))
    _write_runtime_zip(settings, "macos-arm64", service.dependency_signature())

    status_code = export_monitor_main(
        [
            "status",
            "--config",
            config_path.as_posix(),
            "--runtime-root",
            settings.runtime_root.as_posix(),
            "--project-root",
            Path.cwd().as_posix(),
        ]
    )
    status_output = json.loads(capsys.readouterr().out)

    assert status_code == 0
    assert "export_signature" in status_output
    assert status_output["platforms"][0]["platform"] == "macos-arm64"

    refresh_code = export_monitor_main(
        [
            "refresh",
            "--config",
            config_path.as_posix(),
            "--runtime-root",
            settings.runtime_root.as_posix(),
            "--project-root",
            Path.cwd().as_posix(),
        ]
    )
    refresh_output = json.loads(capsys.readouterr().out)

    assert refresh_code == 0
    assert refresh_output["refreshed"] is True
    assert (settings.exports_root / "student" / "learning-data.zip").exists()
