from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from quantfish.data.release_lock import ReleaseLockCancelled, ReleaseLockManager
from quantfish.data.releases import ReleaseBuildProgress, build_releases_from_config
from quantfish.data.scoring_datasets import scoring_required_dataset_ids
from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.submissions.track_config import track_scoring_config

HistoricalReleaseName = Literal["learning_1", "learning_2", "learning_3"]
HISTORICAL_RELEASE_NAMES: tuple[HistoricalReleaseName, ...] = (
    "learning_1",
    "learning_2",
    "learning_3",
)
_ACTIVE_JOB_STATUSES = {"queued", "running"}


class ReleaseBuildAlreadyRunning(RuntimeError):
    pass


class _ReleaseBuildCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class ReleaseTrackBuildProgress:
    release_name: str
    status: str = "queued"
    phase: str = "queued"
    progress_percent: float = 0
    completed_datasets: int = 0
    total_datasets: int = 0
    current_dataset: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_name": self.release_name,
            "status": self.status,
            "phase": self.phase,
            "progress_percent": self.progress_percent,
            "completed_datasets": self.completed_datasets,
            "total_datasets": self.total_datasets,
            "current_dataset": self.current_dataset,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class ReleaseBuildJob:
    job_id: str
    status: str
    release_names: tuple[str, ...]
    progress_percent: float
    tracks: tuple[ReleaseTrackBuildProgress, ...]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    current_release_name: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "release_names": list(self.release_names),
            "progress_percent": self.progress_percent,
            "tracks": [track.to_dict() for track in self.tracks],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_release_name": self.current_release_name,
            "error_message": self.error_message,
        }


ReleaseBuilder = Callable[..., object]


class DataReleaseBuildService:
    def __init__(
        self,
        config_repository: ConfigRepository,
        *,
        builder: ReleaseBuilder = build_releases_from_config,
        release_lock_manager: ReleaseLockManager | None = None,
    ) -> None:
        self.config_repository = config_repository
        self._builder = builder
        self.release_lock_manager = release_lock_manager or ReleaseLockManager(
            config_repository.path.parent / ".data-release-locks"
        )
        self._lock = threading.RLock()
        self._job: ReleaseBuildJob | None = None
        self._thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

    def status_payload(self) -> dict[str, Any]:
        config = self.config_repository.load()
        releases = []
        for release_name in HISTORICAL_RELEASE_NAMES:
            window = config.data_releases.release_window(release_name)
            catalog_path = Path(window.output_root) / "data_catalog.json"
            releases.append(
                {
                    "release_name": release_name,
                    "start": window.start.isoformat(),
                    "end": window.end.isoformat(),
                    "output_root": window.output_root,
                    "status": "ready" if catalog_path.is_file() else "missing",
                    "last_built_at": _file_modified_at(catalog_path),
                }
            )
        with self._lock:
            job = self._job.to_dict() if self._job is not None else None
        return {
            "source_available": Path(config.data_releases.raw_data_root).is_dir(),
            "buildable_release_names": list(HISTORICAL_RELEASE_NAMES),
            "releases": releases,
            "job": job,
        }

    def start(self, release_names: list[str] | tuple[str, ...]) -> dict[str, Any]:
        selected = tuple(dict.fromkeys(release_names))
        if not selected:
            raise ValueError("select at least one historical data release")
        unknown = [name for name in selected if name not in HISTORICAL_RELEASE_NAMES]
        if unknown:
            raise ValueError(f"unsupported historical data release: {unknown[0]}")

        config = self.config_repository.load()
        config.validate()
        raw_data_root = Path(config.data_releases.raw_data_root)
        if not raw_data_root.is_dir():
            raise FileNotFoundError(f"raw data root not found: {raw_data_root}")

        created_at = _utc_now()
        job = ReleaseBuildJob(
            job_id=uuid.uuid4().hex,
            status="queued",
            release_names=selected,
            progress_percent=0,
            tracks=tuple(
                ReleaseTrackBuildProgress(release_name=name) for name in selected
            ),
            created_at=created_at,
        )
        with self._lock:
            if self._shutdown_event.is_set():
                raise RuntimeError("data release build service is stopping")
            if self._job is not None and self._job.status in _ACTIVE_JOB_STATUSES:
                raise ReleaseBuildAlreadyRunning(
                    f"data release build already running: {self._job.job_id}"
                )
            self._job = job
            thread = threading.Thread(
                target=self._run_job,
                args=(job.job_id, config),
                daemon=True,
                name=f"quantfish-release-{job.job_id[:8]}",
            )
            self._thread = thread
            thread.start()
        return job.to_dict()

    def stop(self) -> None:
        self._shutdown_event.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=5)

    def _run_job(self, job_id: str, config: PlatformConfig) -> None:
        self._update_job(
            job_id,
            status="running",
            started_at=_utc_now(),
        )
        try:
            for release_name in self._release_names(job_id):
                self._ensure_running()
                self._update_job(
                    job_id,
                    current_release_name=release_name,
                )
                self._update_track(
                    job_id,
                    release_name,
                    status="running",
                    phase="waiting_for_scoring",
                    progress_percent=0,
                    error_message=None,
                )

                def report(
                    progress: ReleaseBuildProgress,
                    release_name: str = release_name,
                ) -> None:
                    if progress.phase != "completed":
                        self._ensure_running()
                    self._update_track(
                        job_id,
                        release_name,
                        status="running",
                        phase=progress.phase,
                        progress_percent=progress.percent,
                        completed_datasets=progress.completed_datasets,
                        total_datasets=progress.total_datasets,
                        current_dataset=progress.current_dataset,
                    )

                with self.release_lock_manager.write(
                    release_name,
                    should_cancel=self._shutdown_event.is_set,
                ):
                    self._builder(
                        config,
                        release_names=(release_name,),
                        progress_callback=report,
                        required_dataset_ids=scoring_required_dataset_ids(
                            track_scoring_config(config, release_name)
                        ),
                    )
                self._update_track(
                    job_id,
                    release_name,
                    status="completed",
                    phase="completed",
                    progress_percent=100,
                    current_dataset=None,
                )
            self._update_job(
                job_id,
                status="completed",
                progress_percent=100,
                current_release_name=None,
                finished_at=_utc_now(),
            )
        except (_ReleaseBuildCancelled, ReleaseLockCancelled):
            self._mark_terminal_failure(
                job_id,
                status="cancelled",
                message="data release build stopped with the web service",
            )
        except Exception as exc:
            self._mark_terminal_failure(
                job_id,
                status="failed",
                message=str(exc) or exc.__class__.__name__,
            )
        finally:
            with self._lock:
                if self._thread is threading.current_thread():
                    self._thread = None

    def _ensure_running(self) -> None:
        if self._shutdown_event.is_set():
            raise _ReleaseBuildCancelled

    def _release_names(self, job_id: str) -> tuple[str, ...]:
        with self._lock:
            if self._job is None or self._job.job_id != job_id:
                return ()
            return self._job.release_names

    def _update_track(
        self,
        job_id: str,
        release_name: str,
        **changes: Any,
    ) -> None:
        with self._lock:
            if self._job is None or self._job.job_id != job_id:
                return
            tracks = tuple(
                replace(track, **changes)
                if track.release_name == release_name
                else track
                for track in self._job.tracks
            )
            overall = _overall_progress(tracks)
            self._job = replace(
                self._job,
                tracks=tracks,
                progress_percent=overall,
            )

    def _update_job(self, job_id: str, **changes: Any) -> None:
        with self._lock:
            if self._job is None or self._job.job_id != job_id:
                return
            self._job = replace(self._job, **changes)

    def _mark_terminal_failure(
        self,
        job_id: str,
        *,
        status: str,
        message: str,
    ) -> None:
        with self._lock:
            if self._job is None or self._job.job_id != job_id:
                return
            tracks = tuple(
                replace(
                    track,
                    status=status,
                    phase=status,
                    error_message=message,
                )
                if track.status == "running"
                else track
                for track in self._job.tracks
            )
            self._job = replace(
                self._job,
                status=status,
                tracks=tracks,
                progress_percent=_overall_progress(tracks),
                current_release_name=None,
                error_message=message,
                finished_at=_utc_now(),
            )


def _overall_progress(tracks: tuple[ReleaseTrackBuildProgress, ...]) -> float:
    if not tracks:
        return 0
    return round(
        sum(track.progress_percent for track in tracks) / len(tracks),
        1,
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _file_modified_at(path: Path) -> str | None:
    try:
        modified_at = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(modified_at, UTC).isoformat(timespec="seconds")
