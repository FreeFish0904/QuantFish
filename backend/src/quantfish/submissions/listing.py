from __future__ import annotations

from dataclasses import dataclass
from functools import cmp_to_key
import math
from typing import Any, Callable, Iterable, Literal

from quantfish.submissions.models import Submission, SubmissionDataTrack, submission_label


SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True)
class SubmissionListParams:
    limit: int | None = None
    offset: int = 0
    search: str = ""
    sort_by: str = "submitted_at"
    sort_dir: SortDirection = "desc"
    status: str | None = None
    data_track: SubmissionDataTrack | None = None
    team_id: str | None = None
    team_ids: tuple[str, ...] | None = None
    excluded_team_ids: tuple[str, ...] = ()

    @property
    def is_active(self) -> bool:
        return (
            self.limit is not None
            or self.offset > 0
            or bool(self.search.strip())
            or self.sort_by != "submitted_at"
            or self.sort_dir != "desc"
            or self.status is not None
            or self.data_track is not None
            or self.team_id is not None
            or self.team_ids is not None
            or bool(self.excluded_team_ids)
        )


@dataclass(frozen=True)
class SubmissionPage:
    items: list[Submission]
    total_count: int
    limit: int | None
    offset: int

    @property
    def has_next(self) -> bool:
        if self.limit is None:
            return False
        return self.offset + self.limit < self.total_count

    def metadata(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "limit": self.limit,
            "offset": self.offset,
            "has_next": self.has_next,
        }


def parse_data_track(value: str | None) -> SubmissionDataTrack | None:
    if value in (None, "", "all"):
        return None
    return SubmissionDataTrack(value)


def parse_sort_dir(value: str | None) -> SortDirection:
    return "asc" if value == "asc" else "desc"


def data_tracks_matching_search(query: str) -> tuple[SubmissionDataTrack, ...]:
    normalized = query.strip().casefold()
    if not normalized:
        return ()
    return tuple(
        track
        for track in SubmissionDataTrack
        if normalized in _data_track_search_text(track).casefold()
    )


def submission_page(
    submissions: Iterable[Submission],
    *,
    team_names: dict[str, str],
    params: SubmissionListParams,
    score_for: Callable[[Submission], float | None] | None = None,
) -> SubmissionPage:
    rows = [
        submission
        for submission in submissions
        if _matches_filters(submission, team_names, params)
    ]
    rows = _sort_submissions(rows, team_names=team_names, params=params, score_for=score_for)
    total_count = len(rows)
    offset = max(0, params.offset)
    if params.limit is None:
        return SubmissionPage(items=rows[offset:], total_count=total_count, limit=None, offset=offset)
    limit = max(1, params.limit)
    return SubmissionPage(
        items=rows[offset : offset + limit],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )


def paginate_rows(
    rows: Iterable[dict[str, Any]],
    *,
    limit: int | None,
    offset: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = list(rows)
    total_count = len(ordered)
    safe_offset = max(0, offset)
    if limit is None:
        return ordered[safe_offset:], {
            "total_count": total_count,
            "limit": None,
            "offset": safe_offset,
            "has_next": False,
        }
    safe_limit = max(1, limit)
    return ordered[safe_offset : safe_offset + safe_limit], {
        "total_count": total_count,
        "limit": safe_limit,
        "offset": safe_offset,
        "has_next": safe_offset + safe_limit < total_count,
    }


def team_name_map(teams: Iterable[Any]) -> dict[str, str]:
    return {team.team_id: team.display_name for team in teams}


def _matches_filters(
    submission: Submission,
    team_names: dict[str, str],
    params: SubmissionListParams,
) -> bool:
    if params.status and submission.status.value != params.status:
        return False
    if params.data_track is not None and submission.data_track != params.data_track:
        return False
    if params.team_id is not None and submission.team_id != params.team_id:
        return False
    if params.team_ids is not None and submission.team_id not in params.team_ids:
        return False
    if submission.team_id in params.excluded_team_ids:
        return False
    query = params.search.strip().casefold()
    if not query:
        return True
    number = submission.submission_number or 0
    team_name = team_names.get(submission.team_id, submission.team_id)
    haystack = " ".join(
        [
            submission.submission_id,
            submission_label(number),
            submission.team_id,
            team_name,
            submission.status.value,
            submission.data_track.value,
            _data_track_search_text(submission.data_track),
            submission.original_filename,
        ]
    ).casefold()
    return query in haystack


def _sort_submissions(
    rows: list[Submission],
    *,
    team_names: dict[str, str],
    params: SubmissionListParams,
    score_for: Callable[[Submission], float | None] | None,
) -> list[Submission]:
    def compare(first: Submission, second: Submission) -> int:
        return _compare_sort_values(
            _submission_sort_value(
                first,
                team_names=team_names,
                sort_by=params.sort_by,
                score_for=score_for,
            ),
            _submission_sort_value(
                second,
                team_names=team_names,
                sort_by=params.sort_by,
                score_for=score_for,
            ),
            direction=params.sort_dir,
        )

    return sorted(rows, key=cmp_to_key(compare))


def _submission_sort_value(
    submission: Submission,
    *,
    team_names: dict[str, str],
    sort_by: str,
    score_for: Callable[[Submission], float | None] | None,
) -> Any:
    metrics = submission.metrics
    if sort_by in {"submission_number", "id"}:
        return submission.submission_number or 0
    if sort_by == "team_name":
        return team_names.get(submission.team_id, submission.team_id)
    if sort_by == "status":
        return submission.status.value
    if sort_by == "data_track":
        return submission.data_track.value
    if sort_by == "scored_at":
        return submission.scored_at
    if sort_by == "score":
        return score_for(submission) if score_for is not None else None
    if sort_by == "sharpe":
        return metrics.sharpe if metrics else None
    if sort_by == "calmar":
        return metrics.calmar if metrics else None
    if sort_by in {"total_return", "return"}:
        return metrics.total_return if metrics else None
    if sort_by in {"drawdown", "max_drawdown"}:
        return metrics.max_drawdown if metrics else None
    if sort_by == "filename":
        return submission.original_filename
    return submission.submitted_at


def _data_track_search_text(track: SubmissionDataTrack) -> str:
    return {
        SubmissionDataTrack.LEARNING: "learning data learning",
        SubmissionDataTrack.LEARNING_1: "learning window 1 learning_1 2010 2015",
        SubmissionDataTrack.LEARNING_2: "learning window 2 learning_2 2015 2020",
        SubmissionDataTrack.LEARNING_3: "learning window 3 learning_3 2020 2022",
        SubmissionDataTrack.HIDDEN_TEST: "hidden test hidden_test",
    }[track]


def _compare_sort_values(first: Any, second: Any, *, direction: SortDirection) -> int:
    first_missing = _missing_sort_value(first)
    second_missing = _missing_sort_value(second)
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


def _missing_sort_value(value: Any) -> bool:
    return value is None or (
        isinstance(value, float) and not math.isfinite(value)
    )
