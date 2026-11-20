"""Failure triage: group recent failed submissions by cause.

The database only keeps `str(exc)`, and `worker_failure.json` in each report
directory keeps a machine-readable code. This module joins both into the view
an instructor needs after a class uploads: how many runs failed, which causes
dominate, and which submissions to look at first.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from quantfish.submissions.error_details import (
    WORKER_FAILURE_FILE,
    submission_has_raw_error,
)
from quantfish.submissions.models import Submission, SubmissionStatus

CATEGORY_TIMEOUT = "timeout"
CATEGORY_STALE_POSITIONS = "stale_positions"
CATEGORY_INVALID_SIGNALS = "invalid_signals"
CATEGORY_WORKER_CRASH = "worker_crash"
CATEGORY_DATA_RELEASE = "data_release"
CATEGORY_OTHER = "other"

CATEGORY_PRIORITY = (
    CATEGORY_TIMEOUT,
    CATEGORY_STALE_POSITIONS,
    CATEGORY_INVALID_SIGNALS,
    CATEGORY_WORKER_CRASH,
    CATEGORY_DATA_RELEASE,
    CATEGORY_OTHER,
)

_MESSAGE_RULES = (
    (CATEGORY_TIMEOUT, ("timed out", "timeout")),
    (CATEGORY_STALE_POSITIONS, ("stale position", "terminal stale")),
    (CATEGORY_INVALID_SIGNALS, ("signal", "generate_signals")),
    (CATEGORY_WORKER_CRASH, ("score worker",)),
    (CATEGORY_DATA_RELEASE, ("release", "data_catalog", "catalog")),
)

_WORKER_CODE_CATEGORIES = {
    "terminal_stale_positions": CATEGORY_STALE_POSITIONS,
    "score_worker_failed": CATEGORY_WORKER_CRASH,
}

_MESSAGE_LIMIT = 300
_ERROR_SNIPPET_LIMIT = 200


@dataclass(frozen=True)
class FailureSample:
    submission_id: str
    submission_number: int | None
    team_id: str
    team_name: str
    data_track: str
    submitted_at: str
    category: str
    error_message: str | None
    has_raw_log: bool
    worker_code: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "submission_id": self.submission_id,
            "submission_number": self.submission_number,
            "team_id": self.team_id,
            "team_name": self.team_name,
            "data_track": self.data_track,
            "submitted_at": self.submitted_at,
            "category": self.category,
            "error_message": self.error_message,
            "has_raw_log": self.has_raw_log,
            "worker_code": self.worker_code,
        }


@dataclass(frozen=True)
class FailureCategory:
    category: str
    count: int
    sample_submission_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "count": self.count,
            "sample_submission_ids": list(self.sample_submission_ids),
        }


@dataclass(frozen=True)
class FailureSummary:
    since: str
    window_days: int
    total_submissions: int
    failed_submissions: int
    status_counts: dict[str, int]
    categories: tuple[FailureCategory, ...]
    recent_failures: tuple[FailureSample, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "since": self.since,
            "window_days": self.window_days,
            "total_submissions": self.total_submissions,
            "failed_submissions": self.failed_submissions,
            "status_counts": dict(self.status_counts),
            "categories": [item.to_payload() for item in self.categories],
            "recent_failures": [item.to_payload() for item in self.recent_failures],
        }


def build_failure_summary(
    submissions: Iterable[Submission],
    *,
    team_names: Mapping[str, str],
    since: datetime,
    window_days: int,
    limit: int = 20,
) -> FailureSummary:
    window = [
        submission
        for submission in submissions
        if _submitted_at(submission) is not None and _submitted_at(submission) >= since
    ]
    status_counts: dict[str, int] = {}
    for submission in window:
        key = submission.status.value
        status_counts[key] = status_counts.get(key, 0) + 1

    failures = [item for item in window if item.status == SubmissionStatus.FAILED]
    failures.sort(
        key=lambda submission: _submitted_at(submission) or since,
        reverse=True,
    )
    samples = [_failure_sample(submission, team_names=team_names) for submission in failures]
    return FailureSummary(
        since=since.isoformat(),
        window_days=window_days,
        total_submissions=len(window),
        failed_submissions=len(failures),
        status_counts=dict(sorted(status_counts.items())),
        categories=_categories(samples),
        recent_failures=tuple(samples[: max(0, limit)]),
    )


def classify_failure(error_message: str | None, worker_code: str | None) -> str:
    if worker_code in _WORKER_CODE_CATEGORIES:
        return _WORKER_CODE_CATEGORIES[worker_code]
    text = (error_message or "").lower()
    if not text:
        return CATEGORY_WORKER_CRASH if worker_code else CATEGORY_OTHER
    for category, needles in _MESSAGE_RULES:
        if any(needle in text for needle in needles):
            return category
    return CATEGORY_OTHER


def _failure_sample(
    submission: Submission,
    *,
    team_names: Mapping[str, str],
) -> FailureSample:
    worker_code = _worker_failure_code(submission.report_dir)
    error_message = (submission.error_message or "").strip() or None
    return FailureSample(
        submission_id=submission.submission_id,
        submission_number=submission.submission_number,
        team_id=submission.team_id,
        team_name=team_names.get(submission.team_id, submission.team_id),
        data_track=submission.data_track.value,
        submitted_at=submission.submitted_at,
        category=classify_failure(error_message, worker_code),
        error_message=_snippet(error_message),
        has_raw_log=submission_has_raw_error(submission),
        worker_code=worker_code,
    )


def _categories(samples: list[FailureSample]) -> tuple[FailureCategory, ...]:
    grouped: dict[str, list[str]] = {}
    for sample in samples:
        grouped.setdefault(sample.category, []).append(sample.submission_id)
    return tuple(
        FailureCategory(
            category=category,
            count=len(grouped[category]),
            sample_submission_ids=tuple(grouped[category][:5]),
        )
        for category in CATEGORY_PRIORITY
        if category in grouped
    )


def _worker_failure_code(report_dir: str | Path | None) -> str | None:
    if not report_dir:
        return None
    path = Path(str(report_dir)) / WORKER_FAILURE_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    code = payload.get("code") if isinstance(payload, dict) else None
    return str(code) if code else None


def _submitted_at(submission: Submission) -> datetime | None:
    try:
        return datetime.fromisoformat(submission.submitted_at)
    except (TypeError, ValueError):
        return None


def _snippet(message: str | None) -> str | None:
    if not message:
        return None
    collapsed = " ".join(message.split())
    return collapsed[:_ERROR_SNIPPET_LIMIT]
