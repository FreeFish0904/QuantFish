from __future__ import annotations

import math
from datetime import UTC, datetime
from functools import cmp_to_key
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request

from quantfish.leaderboard.ranking import (
    LeaderboardMetric,
    rank_best_per_team_objective_leaderboard,
    rank_leaderboard,
)
from quantfish.submissions.listing import paginate_rows, parse_sort_dir
from quantfish.submissions.models import SubmissionDataTrack
from quantfish.submissions.result_staleness import is_zero_result_stale
from quantfish.submissions.score_summary import score_summary_for_submission
from quantfish.web_app.response_models import DashboardResponse, LeaderboardResponse

router = APIRouter(tags=["leaderboard"])


@router.get("/api/leaderboard", response_model=LeaderboardResponse, response_model_exclude_unset=True)
def leaderboard(
    request: Request,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    data_track: Annotated[
        SubmissionDataTrack,
        Query(description="Submission data track to rank"),
    ] = SubmissionDataTrack.HIDDEN_TEST,
    metric: Annotated[
        LeaderboardMetric,
        Query(description="Objective metric to rank"),
    ] = "sharpe",
    ) -> dict[str, Any]:
    services = request.app.state.services
    stale_submission_ids = _active_stale_submission_ids(services)
    team_names = {
        team.team_id: team.display_name
        for team in services.team_repository.list_all()
    }
    records = [
        _leaderboard_record(
            services,
            submission,
            stale_submission_ids,
            team_names,
            required_summary_keys={metric},
        )
        for submission in _submissions(services, data_track=data_track)
    ]
    rows = [
        row.__dict__
        for row in rank_best_per_team_objective_leaderboard(
            records,
            metric=metric,
        )
    ]
    params_active = (
        limit is not None
        or (offset or 0) > 0
        or bool((search or "").strip())
        or sort_by is not None
        or sort_dir is not None
    )
    if not params_active:
        return {
            "rows": rows,
            "count": len(rows),
            "total_count": len(rows),
            "limit": None,
            "offset": 0,
            "has_next": False,
        }
    filtered = _filter_leaderboard_rows(rows, search or "")
    sorted_rows = _sort_leaderboard_rows(
        filtered,
        sort_by=sort_by or "rank",
        sort_dir=parse_sort_dir(sort_dir) if sort_dir is not None else "asc",
    )
    page_rows, metadata = paginate_rows(sorted_rows, limit=limit, offset=offset or 0)
    return {"rows": page_rows, "count": metadata["total_count"], **metadata}


@router.get("/api/dashboard", response_model=DashboardResponse)
def dashboard(request: Request) -> dict[str, Any]:
    services = request.app.state.services
    visible_submissions = _submissions(services)
    hidden_submissions = [
        submission
        for submission in visible_submissions
        if submission.data_track == SubmissionDataTrack.HIDDEN_TEST
    ]
    stale_submission_ids = _active_stale_submission_ids(services)
    team_names = {
        team.team_id: team.display_name
        for team in services.team_repository.list_all()
    }
    records = [
        _leaderboard_record(services, submission, stale_submission_ids, team_names)
        for submission in hidden_submissions
    ]
    ranked = [
        row.__dict__
        for row in rank_leaderboard(
            records,
            weights=services.admin_service.scoring_weights(),
        )
    ]
    settings = services.admin_service.settings_payload()
    course = settings.get("course") or {}
    visible_team_ids = _visible_history_team_ids(services)
    status_counts = _status_counts(visible_submissions)
    runner_status = _runner_status(settings, status_counts)
    return {
        "submission_count": len(visible_submissions),
        "team_count": len(visible_team_ids),
        "course_name": course.get("name"),
        "scoring_timeout_seconds": runner_status["scoring_timeout_seconds"],
        "latest": _latest_rows(ranked),
        "status_counts": status_counts,
        "runner_status": runner_status,
    }


def _submissions(
    services: Any,
    data_track: SubmissionDataTrack | None = None,
) -> list[Any]:
    if data_track is not None:
        list_for_track = getattr(services.submission_repository, "list_for_track", None)
        if callable(list_for_track):
            return _visible_submissions(services, list_for_track(data_track))
    submissions = services.submission_repository.list_all()
    visible = _visible_submissions(services, submissions)
    if data_track is None:
        return visible
    return [submission for submission in visible if submission.data_track == data_track]


def _visible_submissions(services: Any, submissions: list[Any]) -> list[Any]:
    filter_visible = getattr(
        getattr(services, "team_cohort_service", None),
        "filter_visible_submissions",
        None,
    )
    if not callable(filter_visible):
        return submissions
    return filter_visible(submissions)


def _visible_history_team_ids(services: Any) -> set[str]:
    all_team_ids = {team.team_id for team in services.team_repository.list_all()}
    visible_ids = getattr(
        getattr(services, "team_cohort_service", None),
        "visible_history_team_ids",
        None,
    )
    if not callable(visible_ids):
        return all_team_ids
    return visible_ids(all_team_ids)


def _leaderboard_record(
    services: Any,
    submission: Any,
    stale_submission_ids: set[str],
    team_names: dict[str, str] | None = None,
    required_summary_keys: set[str] | None = None,
) -> dict[str, Any]:
    summary = _leaderboard_summary(
        services,
        submission,
        required_keys=required_summary_keys or set(),
    )
    stale = _is_submission_stale(submission, stale_submission_ids, summary)
    names = team_names or {}
    return {
        "id": submission.submission_id,
        "team_id": submission.team_id,
        "team_name": names.get(submission.team_id, submission.team_id),
        "status": submission.status.value,
        "stale": stale,
        "submitted_at": submission.submitted_at,
        "summary": summary,
    }


def _leaderboard_summary(
    services: Any,
    submission: Any,
    *,
    required_keys: set[str] | None = None,
) -> dict[str, Any]:
    metrics = getattr(submission, "metrics", None)
    if metrics is not None and _has_current_scoring_metrics(metrics):
        stored = metrics.to_dict()
        if _has_required_summary_keys(stored, required_keys or set()):
            return stored
    return score_summary_for_submission(
        submission,
        getattr(services, "artifact_reader", None),
    )


def _has_current_scoring_metrics(metrics: Any) -> bool:
    return getattr(metrics, "annualized_short_profit", None) is not None


def _has_required_summary_keys(
    summary: dict[str, Any],
    required_keys: set[str],
) -> bool:
    return all(summary.get(key) is not None for key in required_keys)


def _active_stale_submission_ids(services: Any) -> set[str]:
    stale_ids = getattr(
        getattr(services, "admin_service", None),
        "active_stale_submission_ids",
        None,
    )
    if not callable(stale_ids):
        return set()
    return set(stale_ids())


def _is_submission_stale(
    submission: Any,
    stale_submission_ids: set[str],
    summary: dict[str, Any] | None = None,
) -> bool:
    if submission.status.value != "completed":
        return False
    return submission.submission_id in stale_submission_ids or is_zero_result_stale(
        submission,
        summary,
    )


def _status_counts(submissions: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for submission in submissions:
        counts[submission.status.value] = counts.get(submission.status.value, 0) + 1
    return counts


def _repository_status_counts(
    services: Any,
    submissions: list[Any],
) -> dict[str, int]:
    status_counts = getattr(services.submission_repository, "status_counts", None)
    if callable(status_counts):
        return status_counts()
    return _status_counts(submissions)


def _repository_submission_count(
    services: Any,
    submissions: list[Any],
) -> int:
    count_all = getattr(services.submission_repository, "count_all", None)
    if callable(count_all):
        return count_all()
    return len(submissions)


def _runner_status(
    settings: dict[str, Any],
    status_counts: dict[str, int],
) -> dict[str, Any]:
    execution = settings.get("execution") or {}
    submissions_enabled = bool(execution.get("submissions_enabled", True))
    timeout_enabled = bool(execution.get("submission_timeout_enabled", True))
    timeout_seconds = execution.get("submission_timeout_seconds")
    return {
        "status": "online" if submissions_enabled else "offline",
        "queued": status_counts.get("queued", 0),
        "running": status_counts.get("running", 0),
        "updated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "scoring_timeout_seconds": (
            int(timeout_seconds) if timeout_enabled and timeout_seconds is not None else None
        ),
        "submissions_enabled": submissions_enabled,
    }


def _latest_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: str(row.get("submitted_at", "")),
        reverse=True,
    )[:5]


def _filter_leaderboard_rows(rows: list[dict[str, Any]], search: str) -> list[dict[str, Any]]:
    query = search.strip().casefold()
    if not query:
        return rows
    return [
        row
        for row in rows
        if query in " ".join(
            [
                str(row.get("id", "")),
                str(row.get("team_name", "")),
                str(row.get("status", "")),
            ]
        ).casefold()
    ]


def _sort_leaderboard_rows(
    rows: list[dict[str, Any]],
    *,
    sort_by: str,
    sort_dir: str,
) -> list[dict[str, Any]]:
    def compare(first: dict[str, Any], second: dict[str, Any]) -> int:
        return _compare_leaderboard_sort_values(
            _leaderboard_sort_value(first, sort_by),
            _leaderboard_sort_value(second, sort_by),
            direction=sort_dir,
        )

    return sorted(rows, key=cmp_to_key(compare))


def _leaderboard_sort_value(row: dict[str, Any], sort_by: str) -> Any:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    if sort_by in {"rank", "score", "submitted_at", "status", "team_name"}:
        return row.get(sort_by)
    if sort_by == "sharpe":
        return summary.get("sharpe")
    if sort_by in {"drawdown", "max_drawdown"}:
        value = summary.get("max_drawdown")
        return abs(value) if isinstance(value, (int, float)) else value
    if sort_by == "calmar":
        return _summary_calmar_value(summary)
    if sort_by == "metric_value":
        value = row.get("metric_value")
        if row.get("metric") == "max_drawdown" and isinstance(value, (int, float)):
            return abs(value)
        return value
    return row.get("rank")


def _summary_calmar_value(summary: dict[str, Any]) -> float | None:
    stored = summary.get("calmar")
    if isinstance(stored, (int, float)) and math.isfinite(stored):
        return float(stored)
    if "calmar" in summary:
        return None
    annual_return = summary.get("annual_return")
    max_drawdown = summary.get("max_drawdown")
    if (
        isinstance(annual_return, (int, float))
        and math.isfinite(annual_return)
        and isinstance(max_drawdown, (int, float))
        and math.isfinite(max_drawdown)
    ):
        drawdown = abs(max_drawdown)
        return annual_return / drawdown if drawdown > 0 else None
    return None


def _compare_leaderboard_sort_values(
    first: Any,
    second: Any,
    *,
    direction: str,
) -> int:
    first_missing = _missing_leaderboard_sort_value(first)
    second_missing = _missing_leaderboard_sort_value(second)
    if first_missing or second_missing:
        if first_missing and second_missing:
            return 0
        return 1 if first_missing else -1

    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        result = (first > second) - (first < second)
    else:
        first_text = str(first).casefold()
        second_text = str(second).casefold()
        result = (first_text > second_text) - (first_text < second_text)

    return -result if direction == "desc" else result


def _missing_leaderboard_sort_value(value: Any) -> bool:
    return value is None or (
        isinstance(value, float) and not math.isfinite(value)
    )
