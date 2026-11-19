from __future__ import annotations

import inspect
import threading
from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from quantfish.data.release_lock import ReleaseLockManager
from quantfish.platform_config import ConfigRepository
from quantfish.submissions.artifacts import ReportArtifactReader
from quantfish.submissions.models import (
    SubmissionDataTrack,
    SubmissionMetrics,
    SubmissionStatus,
    _utc_now,
)
from quantfish.submissions.repositories import SubmissionRepository


@dataclass
class _ActiveJob:
    submission_id: str
    cancel_event: threading.Event
    thread: threading.Thread | None = None
    handle: Any | None = None


class SubmissionScoringDispatcher:
    def __init__(
        self,
        submission_repository: SubmissionRepository,
        runner: Any,
        config_repository: ConfigRepository,
        release_lock_manager: ReleaseLockManager | None = None,
    ):
        self.submission_repository = submission_repository
        self.runner = runner
        self.config_repository = config_repository
        self.release_lock_manager = release_lock_manager
        self._lock = threading.RLock()
        self._active: dict[str, _ActiveJob] = {}
        self._stopped = False
        self._started = False

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stopped = False
            requeue_running = getattr(self.submission_repository, "requeue_running", None)
            if callable(requeue_running):
                requeue_running()
            else:
                for submission in self.submission_repository.list_all():
                    if submission.status == SubmissionStatus.RUNNING:
                        self.submission_repository.save(
                            replace(
                                submission,
                                status=SubmissionStatus.QUEUED,
                                error_message=None,
                                scored_at=None,
                            )
                        )
        self.pump()

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            active = list(self._active.values())
        for job in active:
            job.cancel_event.set()
            _terminate_handle(job.handle)
        for job in active:
            if job.thread is not None and job.thread is not threading.current_thread():
                job.thread.join(timeout=5)

    def pump(self) -> None:
        with self._lock:
            if self._stopped:
                return
            limit = self._concurrency_limit()
            slots = max(0, limit - len(self._active))
            if slots <= 0:
                return
            list_queued = getattr(self.submission_repository, "list_queued", None)
            if callable(list_queued):
                queued = list_queued(
                    limit=slots,
                    exclude_submission_ids=set(self._active),
                )
            else:
                queued = [
                    submission
                    for submission in self.submission_repository.list_all()
                    if submission.status == SubmissionStatus.QUEUED
                    and submission.submission_id not in self._active
                ]
                queued.sort(
                    key=lambda submission: (
                        submission.submission_number or 0,
                        submission.submitted_at,
                    )
                )
                queued = queued[:slots]
            for submission in queued:
                self._start_job_locked(submission.submission_id)

    def cancel_submission(self, submission_id: str) -> bool:
        with self._lock:
            job = self._active.get(submission_id)
            if job is None:
                return False
            job.cancel_event.set()
            handle = job.handle
        _terminate_handle(handle)
        return True

    def _start_job_locked(self, submission_id: str) -> None:
        cancel_event = threading.Event()
        job = _ActiveJob(submission_id=submission_id, cancel_event=cancel_event)
        thread = threading.Thread(
            target=self._run_job,
            args=(job,),
            daemon=True,
            name=f"quantfish-score-{submission_id}",
        )
        job.thread = thread
        self._active[submission_id] = job
        thread.start()

    def _run_job(self, job: _ActiveJob) -> None:
        try:
            self._score_job(job)
        finally:
            with self._lock:
                self._active.pop(job.submission_id, None)
                should_pump = not self._stopped
            if should_pump:
                self.pump()

    def _score_job(self, job: _ActiveJob) -> None:
        submission = self.submission_repository.get(job.submission_id)
        if submission is None or submission.status != SubmissionStatus.QUEUED:
            return
        strategy_path = Path(submission.strategy_path)
        report_dir = Path(submission.report_dir)
        try:
            with self._release_read_lock(job, submission.data_track):
                self._score_job_with_release_lock(
                    job,
                    submission,
                    strategy_path,
                    report_dir,
                )
        except Exception as exc:
            if job.cancel_event.is_set():
                return
            current = self.submission_repository.get(job.submission_id)
            if current is None:
                return
            self.submission_repository.save(
                replace(
                    current,
                    status=SubmissionStatus.FAILED,
                    metrics=None,
                    error_message=str(exc),
                    scored_at=_utc_now(),
                )
            )

    def _score_job_with_release_lock(
        self,
        job: _ActiveJob,
        submission: Any,
        strategy_path: Path,
        report_dir: Path,
    ) -> None:
        fingerprints = self.runner.current_fingerprints(
            strategy_path,
            submission.data_track,
        )
        config_snapshot = (
            _runner_config_snapshot(self.runner, submission.data_track)
            or submission.config_snapshot
        )
        if job.cancel_event.is_set():
            return
        current = self.submission_repository.get(job.submission_id)
        if current is None:
            return
        self.submission_repository.save(
            replace(
                current,
                status=SubmissionStatus.RUNNING,
                fingerprints=fingerprints,
                config_snapshot=config_snapshot,
                metrics=None,
                error_message=None,
                scored_at=None,
            )
        )
        if job.cancel_event.is_set():
            return
        metrics = self._run_score(
            job,
            strategy_path,
            report_dir,
            submission.data_track,
        )
        if metrics is None:
            artifacts = ReportArtifactReader().read(report_dir)
            metrics = SubmissionMetrics.from_summary(artifacts["summary"])
        if job.cancel_event.is_set():
            return
        current = self.submission_repository.get(job.submission_id)
        if current is None:
            return
        self.submission_repository.save(
            replace(
                current,
                status=SubmissionStatus.COMPLETED,
                metrics=metrics,
                error_message=None,
                scored_at=_utc_now(),
            )
        )

    def _release_read_lock(
        self,
        job: _ActiveJob,
        data_track: SubmissionDataTrack,
    ) -> Any:
        if self.release_lock_manager is None:
            return nullcontext()
        return self.release_lock_manager.read(
            data_track.value,
            should_cancel=job.cancel_event.is_set,
        )

    def _run_score(
        self,
        job: _ActiveJob,
        strategy_path: Path,
        report_dir: Path,
        data_track: Any,
    ) -> SubmissionMetrics | None:
        starter = getattr(self.runner, "start_score", None)
        if callable(starter):
            handle = starter(strategy_path, report_dir, data_track)
            with self._lock:
                job.handle = handle
                cancelled = job.cancel_event.is_set()
            if cancelled:
                _terminate_handle(handle)
                return None
            return handle.wait()
        return self.runner.score(strategy_path, report_dir, data_track)

    def _concurrency_limit(self) -> int:
        try:
            return max(1, int(self.config_repository.load().execution.max_concurrent_scoring))
        except Exception:
            return 1


def _runner_config_snapshot(
    runner: Any,
    data_track: SubmissionDataTrack,
) -> dict[str, Any] | None:
    snapshotter = getattr(runner, "current_config_snapshot", None)
    if not callable(snapshotter):
        return None
    if _callable_accepts_positional_arg(snapshotter):
        snapshot = snapshotter(data_track)
    else:
        snapshot = snapshotter()
    return dict(snapshot) if isinstance(snapshot, dict) else None


def _callable_accepts_positional_arg(value: Any) -> bool:
    try:
        parameters = inspect.signature(value).parameters.values()
    except (TypeError, ValueError):
        return True
    return any(
        parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        )
        for parameter in parameters
    )


def _terminate_handle(handle: Any | None) -> None:
    if handle is None:
        return
    terminator = getattr(handle, "terminate", None)
    if callable(terminator):
        terminator()
