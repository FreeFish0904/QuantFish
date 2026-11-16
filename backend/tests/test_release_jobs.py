from dataclasses import replace
from pathlib import Path
import threading
import time

import pytest

from quantfish.data.release_jobs import (
    DataReleaseBuildService,
    ReleaseBuildAlreadyRunning,
)
from quantfish.data.release_lock import ReleaseLockManager
from quantfish.data.releases import ReleaseBuildProgress
from quantfish.platform_config import ConfigRepository, PlatformConfig


def _config_repository(tmp_path: Path) -> ConfigRepository:
    raw_data_root = tmp_path / "raw"
    raw_data_root.mkdir()
    release_root = tmp_path / "releases"
    default = PlatformConfig.default()
    config = replace(
        default,
        data_releases=replace(
            default.data_releases,
            raw_data_root=raw_data_root.as_posix(),
            learning_output_root=(release_root / "learning").as_posix(),
            hidden_output_root=(release_root / "hidden_test").as_posix(),
            learning_1_output_root=(release_root / "learning_1").as_posix(),
            learning_2_output_root=(release_root / "learning_2").as_posix(),
            learning_3_output_root=(release_root / "learning_3").as_posix(),
        ),
    )
    repository = ConfigRepository(tmp_path / "platform.yaml")
    repository.save(config)
    return repository


def _wait_for_terminal_job(service: DataReleaseBuildService) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = service.status_payload()["job"]
        assert isinstance(job, dict)
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(0.01)
    raise AssertionError("release job did not finish")


def test_release_job_runs_selected_tracks_sequentially_and_reports_progress(
    tmp_path: Path,
) -> None:
    first_track_started = threading.Event()
    allow_first_track_to_finish = threading.Event()
    calls: list[str] = []

    def builder(  # type: ignore[no-untyped-def]
        config,
        *,
        release_names,
        progress_callback,
        required_dataset_ids,
    ):
        assert required_dataset_ids == (
            "stock.daily_returns",
            "factor_benchmark.adj_factor",
            "basic.company_info",
        )
        release_name = tuple(release_names)[0]
        calls.append(release_name)
        progress_callback(
            ReleaseBuildProgress(
                phase="building",
                percent=40,
                completed_datasets=2,
                total_datasets=5,
                current_dataset="market.daily",
            )
        )
        if release_name == "learning_1":
            first_track_started.set()
            assert allow_first_track_to_finish.wait(timeout=2)
        progress_callback(ReleaseBuildProgress(phase="publishing", percent=97))

    service = DataReleaseBuildService(_config_repository(tmp_path), builder=builder)
    queued = service.start(["learning_1", "learning_3", "learning_1"])

    assert queued["status"] == "queued"
    assert queued["release_names"] == ["learning_1", "learning_3"]
    assert first_track_started.wait(timeout=1)
    running = service.status_payload()["job"]
    assert running["status"] == "running"
    assert running["current_release_name"] == "learning_1"
    assert running["progress_percent"] == 20
    assert running["tracks"][0] == {
        "release_name": "learning_1",
        "status": "running",
        "phase": "building",
        "progress_percent": 40,
        "completed_datasets": 2,
        "total_datasets": 5,
        "current_dataset": "market.daily",
        "error_message": None,
    }
    with pytest.raises(ReleaseBuildAlreadyRunning):
        service.start(["learning_2"])

    allow_first_track_to_finish.set()
    completed = _wait_for_terminal_job(service)

    assert calls == ["learning_1", "learning_3"]
    assert completed["status"] == "completed"
    assert completed["progress_percent"] == 100
    assert [track["status"] for track in completed["tracks"]] == [
        "completed",
        "completed",
    ]
    assert completed["started_at"] is not None
    assert completed["finished_at"] is not None


def test_release_job_preserves_completed_track_and_marks_failed_track(
    tmp_path: Path,
) -> None:
    def builder(  # type: ignore[no-untyped-def]
        config,
        *,
        release_names,
        progress_callback,
        required_dataset_ids,
    ):
        release_name = tuple(release_names)[0]
        progress_callback(ReleaseBuildProgress(phase="building", percent=25))
        if release_name == "learning_2":
            raise OSError("disk full")

    service = DataReleaseBuildService(_config_repository(tmp_path), builder=builder)
    service.start(["learning_1", "learning_2", "learning_3"])

    failed = _wait_for_terminal_job(service)

    assert failed["status"] == "failed"
    assert failed["error_message"] == "disk full"
    assert [track["status"] for track in failed["tracks"]] == [
        "completed",
        "failed",
        "queued",
    ]
    assert failed["tracks"][1]["error_message"] == "disk full"


def test_release_job_status_reports_source_and_catalog_readiness(tmp_path: Path) -> None:
    repository = _config_repository(tmp_path)
    config = repository.load()
    learning_2_catalog = (
        Path(config.data_releases.release_window("learning_2").output_root)
        / "data_catalog.json"
    )
    learning_2_catalog.parent.mkdir(parents=True)
    learning_2_catalog.write_text("{}", encoding="utf-8")
    service = DataReleaseBuildService(repository, builder=lambda *_args, **_kwargs: None)

    status = service.status_payload()

    assert status["source_available"] is True
    assert status["buildable_release_names"] == [
        "learning_1",
        "learning_2",
        "learning_3",
    ]
    assert [release["status"] for release in status["releases"]] == [
        "missing",
        "ready",
        "missing",
    ]
    assert status["releases"][1]["last_built_at"] is not None
    assert status["job"] is None


def test_release_job_rejects_missing_source_and_unsupported_tracks(tmp_path: Path) -> None:
    repository = _config_repository(tmp_path)
    raw_data_root = Path(repository.load().data_releases.raw_data_root)
    raw_data_root.rmdir()
    service = DataReleaseBuildService(repository)

    with pytest.raises(ValueError, match="select at least one"):
        service.start([])
    with pytest.raises(ValueError, match="unsupported historical"):
        service.start(["learning"])
    with pytest.raises(FileNotFoundError, match="raw data root not found"):
        service.start(["learning_1"])


def test_release_job_waits_for_active_scoring_lock_on_the_same_track(
    tmp_path: Path,
) -> None:
    lock_manager = ReleaseLockManager(tmp_path / "locks", poll_interval_seconds=0.01)
    builder_started = threading.Event()

    def builder(  # type: ignore[no-untyped-def]
        config,
        *,
        release_names,
        progress_callback,
        required_dataset_ids,
    ):
        builder_started.set()
        progress_callback(ReleaseBuildProgress(phase="completed", percent=100))

    service = DataReleaseBuildService(
        _config_repository(tmp_path),
        builder=builder,
        release_lock_manager=lock_manager,
    )

    with lock_manager.read("learning_1"):
        service.start(["learning_1"])
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            job = service.status_payload()["job"]
            if job["tracks"][0]["phase"] == "waiting_for_scoring":
                break
            time.sleep(0.01)
        assert job["tracks"][0]["phase"] == "waiting_for_scoring"
        assert not builder_started.wait(timeout=0.1)

    assert builder_started.wait(timeout=1)
    assert _wait_for_terminal_job(service)["status"] == "completed"


def test_release_job_reports_published_track_completed_during_shutdown(
    tmp_path: Path,
) -> None:
    published = threading.Event()
    allow_completed_callback = threading.Event()

    def builder(  # type: ignore[no-untyped-def]
        config,
        *,
        release_names,
        progress_callback,
        required_dataset_ids,
    ):
        progress_callback(ReleaseBuildProgress(phase="publishing", percent=97))
        published.set()
        assert allow_completed_callback.wait(timeout=2)
        progress_callback(ReleaseBuildProgress(phase="completed", percent=100))

    service = DataReleaseBuildService(_config_repository(tmp_path), builder=builder)
    service.start(["learning_1"])
    assert published.wait(timeout=1)

    stop_thread = threading.Thread(target=service.stop)
    stop_thread.start()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and not service._shutdown_event.is_set():
        time.sleep(0.01)
    assert service._shutdown_event.is_set()
    allow_completed_callback.set()
    stop_thread.join(timeout=2)

    job = service.status_payload()["job"]
    assert job["status"] == "completed"
    assert job["tracks"][0]["status"] == "completed"
