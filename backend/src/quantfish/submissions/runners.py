from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from quantfish.observability import get_logger, log_event
from quantfish.platform_config import ConfigRepository
from quantfish.submissions.error_details import worker_failure_message
from quantfish.submissions.models import (
    ScoreFingerprints,
    SubmissionDataTrack,
    SubmissionMetrics,
    _submission_data_track,
)
from quantfish.submissions.staleness import (
    ScoreFingerprintContext,
    config_sha256,
    fingerprints_from_context,
    release_file_signatures,
    release_generation,
    sha256_release,
)
from quantfish.submissions.track_config import track_release_root, track_scoring_config

_LOGGER = get_logger("submissions.runner")
_STDERR_TAIL_CHARS = 2000


class BacktestSubmissionRunner:
    def __init__(
        self,
        settings: Any,
        fingerprint_context_cache_entries: int = 16,
    ):
        self.settings = settings
        self._fingerprint_context_lock = threading.RLock()
        self._fingerprint_context_cache_entries = max(
            1,
            int(fingerprint_context_cache_entries),
        )
        self._fingerprint_context_cache: OrderedDict[
            tuple[Any, ...],
            ScoreFingerprintContext,
        ] = OrderedDict()

    def current_fingerprint_context(
        self,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprintContext:
        track = _submission_data_track(data_track)
        config = self._load_config()
        catalog_path = _track_catalog_path(config, track)
        config_digest = config_sha256(config)
        engine_version = str(self.settings.engine_version)
        generation = release_generation(catalog_path)
        release_signature = release_file_signatures(catalog_path)
        cache_key = (
            track.value,
            config_digest,
            engine_version,
            catalog_path.resolve().as_posix(),
            release_signature,
        )
        with self._fingerprint_context_lock:
            cached = self._fingerprint_context_cache.get(cache_key)
            if cached is not None:
                self._fingerprint_context_cache.move_to_end(cache_key)
                return cached
            context = ScoreFingerprintContext(
                config_sha256=config_digest,
                hidden_catalog_sha256=sha256_release(catalog_path),
                engine_version=engine_version,
                data_track=track,
                release_generation=generation,
            )
            self._fingerprint_context_cache[cache_key] = context
            self._fingerprint_context_cache.move_to_end(cache_key)
            while len(self._fingerprint_context_cache) > self._fingerprint_context_cache_entries:
                self._fingerprint_context_cache.popitem(last=False)
            return context

    def current_release_generation(
        self,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> str | None:
        track = _submission_data_track(data_track)
        config = self._load_config()
        return release_generation(_track_catalog_path(config, track))

    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        return fingerprints_from_context(
            self.current_fingerprint_context(data_track),
            strategy_path,
        )

    def current_config_snapshot(
        self,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> dict[str, Any]:
        return track_scoring_config(self._load_config(), data_track).to_dict()

    def score(
        self,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> SubmissionMetrics:
        return self.start_score(strategy_path, report_dir, data_track).wait()

    def start_score(
        self,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreWorkerHandle:
        config = self._load_config()
        track = _submission_data_track(data_track)
        timeout = (
            int(config.execution.submission_timeout_seconds)
            if config.execution.submission_timeout_enabled
            else None
        )
        report_dir = report_dir.resolve()
        report_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            "-m",
            "quantfish.submissions.score_worker",
            "--config",
            Path(self.settings.config_path).resolve().as_posix(),
            "--strategy",
            strategy_path.resolve().as_posix(),
            "--report-dir",
            report_dir.as_posix(),
            "--data-track",
            track.value,
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=report_dir,
            env=_worker_environment(),
            start_new_session=True,
        )
        return ScoreWorkerHandle(process, command, timeout, report_dir)

    def _load_config(self) -> Any:
        return ConfigRepository(self.settings.config_path).load()


class ScoreWorkerHandle:
    def __init__(
        self,
        process: subprocess.Popen[str],
        command: list[str],
        timeout: int | None,
        report_dir: Path,
    ):
        self.process = process
        self.command = command
        self.timeout = timeout
        self.report_dir = report_dir

    def wait(self) -> SubmissionMetrics:
        try:
            stdout, stderr = self.process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired as exc:
            self.terminate()
            raise TimeoutError(f"scoring timed out after {self.timeout} seconds") from exc
        if self.process.returncode != 0:
            log_event(
                _LOGGER,
                logging.ERROR,
                "score_worker_failed",
                returncode=self.process.returncode,
                report_dir=self.report_dir.as_posix(),
                stderr_tail=_tail(stderr),
            )
            raise RuntimeError(worker_failure_message(self.report_dir) or "score worker failed")
        try:
            summary = json.loads(stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("score worker returned invalid JSON") from exc
        return SubmissionMetrics.from_summary(summary)

    def terminate(self) -> None:
        if self.process.poll() is not None:
            return
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            self.process.terminate()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                return
            time.sleep(0.05)
        if self.process.poll() is not None:
            return
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except (AttributeError, ProcessLookupError, PermissionError, OSError):
            self.process.kill()


def _tail(text: str | None) -> str | None:
    if not text:
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    return trimmed[-_STDERR_TAIL_CHARS:]


def _worker_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("QUANTFISH_")}


def _track_catalog_path(config: Any, data_track: SubmissionDataTrack) -> Path:
    return Path(track_release_root(config, data_track)) / "data_catalog.json"
