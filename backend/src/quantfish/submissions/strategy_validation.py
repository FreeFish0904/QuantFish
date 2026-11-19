"""Upload pre-check: tell a student whether a strategy runs *before* scoring.

`POST /api/submissions/validate` accepts the same file the submit form would
upload, but nothing is persisted and no score is produced. The work happens in
`quantfish.submissions.strategy_check`, a short-lived subprocess limited to the
last few trading dates, so a strategy with an infinite loop is killed by a
timeout instead of blocking the web process (the same isolation the scoring
path already relies on).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quantfish.observability import get_logger, log_event
from quantfish.submissions.models import SubmissionDataTrack, _submission_data_track
from quantfish.submissions.storage import SubmissionStorage

_LOGGER = get_logger("submissions.validation")

DEFAULT_MAX_TRADING_DATES = 20
DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_RATE_LIMIT = 6
DEFAULT_RATE_WINDOW_SECONDS = 60.0


class ValidationRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        noun = "second" if retry_after_seconds == 1 else "seconds"
        super().__init__(f"Too many pre-checks; try again in {retry_after_seconds} {noun}.")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class StrategyValidationResult:
    ok: bool
    code: str
    message: str
    data_track: SubmissionDataTrack
    trading_dates_checked: int | None = None
    signal_rows: int | None = None
    signal_dates: int | None = None
    first_signal_date: str | None = None
    last_signal_date: str | None = None
    sample_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    elapsed_ms: float = 0.0

    def to_payload(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "code": self.code,
            "message": self.message,
            "data_track": self.data_track.value,
            "trading_dates_checked": self.trading_dates_checked,
            "signal_rows": self.signal_rows,
            "signal_dates": self.signal_dates,
            "first_signal_date": self.first_signal_date,
            "last_signal_date": self.last_signal_date,
            "sample_codes": list(self.sample_codes),
            "warnings": list(self.warnings),
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True)
class _SubprocessOutcome:
    returncode: int | None = None
    stderr: str | None = None
    timed_out: bool = False


@dataclass
class _Attempts:
    timestamps: deque[float] = field(default_factory=deque)


class StrategyValidationService:
    def __init__(
        self,
        storage: SubmissionStorage,
        config_path: Path | str,
        *,
        max_trading_dates: int = DEFAULT_MAX_TRADING_DATES,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        rate_window_seconds: float = DEFAULT_RATE_WINDOW_SECONDS,
    ) -> None:
        self.storage = storage
        self.config_path = Path(config_path)
        self.max_trading_dates = max(1, int(max_trading_dates))
        self.timeout_seconds = float(timeout_seconds)
        self.rate_limit = max(1, int(rate_limit))
        self.rate_window_seconds = float(rate_window_seconds)
        self._attempts: dict[str, _Attempts] = {}
        self._attempts_lock = threading.Lock()

    def validate(
        self,
        *,
        team_id: str,
        filename: str,
        content: bytes,
        data_track: SubmissionDataTrack | str,
    ) -> StrategyValidationResult:
        track = _submission_data_track(data_track)
        self._register_attempt(team_id)
        # Reuse the upload rules (extension, size, UTF-8, `compile()`), so a
        # syntax error never costs a subprocess.
        self.storage.validate_strategy_upload(filename, content)

        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="quantfish-check-") as raw_dir:
            workdir = Path(raw_dir)
            strategy_path = workdir / "generate_signals.py"
            strategy_path.write_bytes(content)
            result_path = workdir / "result.json"
            outcome = self._run_check(strategy_path, result_path, track, workdir)
            payload = _read_payload(result_path)

        result = _result_from_payload(payload, outcome, track)
        log_event(
            _LOGGER,
            logging.INFO if result.ok else logging.WARNING,
            "strategy_validated",
            team_id=team_id,
            data_track=track.value,
            ok=result.ok,
            code=result.code,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return result

    def _register_attempt(self, team_id: str) -> None:
        now = time.monotonic()
        cutoff = now - self.rate_window_seconds
        with self._attempts_lock:
            entry = self._attempts.setdefault(team_id, _Attempts())
            while entry.timestamps and entry.timestamps[0] < cutoff:
                entry.timestamps.popleft()
            if len(entry.timestamps) >= self.rate_limit:
                oldest = entry.timestamps[0]
                raise ValidationRateLimitError(
                    max(1, round(self.rate_window_seconds - (now - oldest)))
                )
            entry.timestamps.append(now)

    def _run_check(
        self,
        strategy_path: Path,
        result_path: Path,
        track: SubmissionDataTrack,
        workdir: Path,
    ) -> _SubprocessOutcome:
        command = [
            sys.executable,
            "-m",
            "quantfish.submissions.strategy_check",
            "--config",
            self.config_path.resolve().as_posix(),
            "--strategy",
            strategy_path.as_posix(),
            "--result",
            result_path.as_posix(),
            "--data-track",
            track.value,
            "--max-trading-dates",
            str(self.max_trading_dates),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _SubprocessOutcome(
                timed_out=True,
                stderr=f"pre-check exceeded {self.timeout_seconds:.0f}s",
            )
        return _SubprocessOutcome(
            returncode=completed.returncode,
            stderr=completed.stderr,
        )


def _read_payload(result_path: Path) -> dict[str, Any]:
    if not result_path.exists():
        return {}
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _result_from_payload(
    payload: dict[str, Any],
    outcome: _SubprocessOutcome,
    track: SubmissionDataTrack,
) -> StrategyValidationResult:
    if payload:
        return StrategyValidationResult(
            ok=bool(payload.get("ok")),
            code=str(payload.get("code") or "unknown"),
            message=str(payload.get("message") or ""),
            data_track=track,
            trading_dates_checked=_as_int(payload.get("trading_dates_checked")),
            signal_rows=_as_int(payload.get("signal_rows")),
            signal_dates=_as_int(payload.get("signal_dates")),
            first_signal_date=_as_str(payload.get("first_signal_date")),
            last_signal_date=_as_str(payload.get("last_signal_date")),
            sample_codes=tuple(
                str(code) for code in payload.get("sample_codes") or () if code is not None
            ),
            warnings=tuple(str(item) for item in payload.get("warnings") or ()),
            elapsed_ms=float(payload.get("elapsed_ms") or 0.0),
        )
    if outcome.timed_out:
        return StrategyValidationResult(
            ok=False,
            code="timeout",
            message=outcome.stderr or "pre-check timed out",
            data_track=track,
        )
    return StrategyValidationResult(
        ok=False,
        code="check_failed",
        message=_tail(outcome.stderr) or "the pre-check process failed",
        data_track=track,
    )


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _tail(text: str | None, limit: int = 600) -> str | None:
    if not text:
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    return trimmed[-limit:]
