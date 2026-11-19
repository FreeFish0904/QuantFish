from __future__ import annotations

import importlib.util
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from quantfish.backtest.pdf_report_version import pdf_report_is_current, pdf_report_path
from quantfish.leaderboard.ranking import (
    ScoringWeights,
    calculate_leaderboard_score,
    score_calculation_text,
    score_contributions,
)
from quantfish.leaderboard.sql_scoring import score_sort_expression
from quantfish.submissions.artifacts import report_artifacts_available
from quantfish.submissions.benchmark_graph import complete_hs300_benchmark_artifacts
from quantfish.submissions.error_details import raw_submission_error, submission_has_raw_error
from quantfish.submissions.listing import (
    SubmissionListParams,
    parse_data_track,
    parse_sort_dir,
    team_name_map,
)
from quantfish.submissions.models import (
    Submission,
    SubmissionMetrics,
    SubmissionStatus,
    submission_detail_payload,
    submission_list_payload,
)
from quantfish.submissions.participant_session import require_participant_session
from quantfish.submissions.result_staleness import is_zero_result_stale
from quantfish.submissions.score_summary import score_summary_for_submission
from quantfish.submissions.service import SubmissionCohortDisabledError, SubmissionCooldownError
from quantfish.submissions.strategy_validation import ValidationRateLimitError
from quantfish.submissions.track_visibility import (
    default_public_data_track,
    ensure_public_data_track_enabled,
    public_data_tracks,
)
from quantfish.web_app.response_models import (
    StrategyValidationResponse,
    SubmissionDetail,
    SubmissionListResponse,
    SubmissionOptionsResponse,
    SubmissionSummary,
)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])
DEFAULT_SUBMISSION_LIST_LIMIT = 100


def _team_name(services: Any, team_id: str) -> str:
    team = services.team_repository.get(team_id)
    return team.display_name if team else team_id


@router.post("", response_model=SubmissionSummary)
async def submit_strategy(
    request: Request,
    team_name: str | None = Form(None),
    password: str | None = Form(None),
    data_track: str | None = Form(None),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    services = request.app.state.services
    try:
        content = await file.read()
        track = ensure_public_data_track_enabled(
            services,
            data_track or default_public_data_track(services),
        )
        if _has_supplied_credentials(team_name, password):
            if team_name is None or password is None or not team_name.strip() or not password:
                raise HTTPException(
                    status_code=400,
                    detail="team name and password are required together",
                )
            submission = services.submission_service.submit_strategy(
                team_name=team_name,
                password=password,
                filename=file.filename or "strategy.py",
                content=content,
                data_track=track,
            )
        else:
            session = require_participant_session(request)
            submission = services.submission_service.submit_strategy_for_team(
                team_id=session.team_id,
                filename=file.filename or "strategy.py",
                content=content,
                data_track=track,
            )
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except SubmissionCohortDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SubmissionCooldownError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _submission_summary_payload(
        submission,
        team_name=_team_name(services, submission.team_id),
        stale=_submission_stale(services, submission),
        weights=services.admin_service.scoring_weights(),
        artifact_reader=services.artifact_reader,
    )


def _has_supplied_credentials(team_name: str | None, password: str | None) -> bool:
    return team_name is not None or password is not None


@router.post("/validate", response_model=StrategyValidationResponse)
async def validate_strategy(
    request: Request,
    team_name: str | None = Form(None),
    password: str | None = Form(None),
    data_track: str | None = Form(None),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Dry-run an upload without storing a submission or producing a score."""
    services = request.app.state.services
    content = await file.read()
    try:
        team_id = _validation_team_id(services, request, team_name, password)
        track = ensure_public_data_track_enabled(
            services,
            data_track or default_public_data_track(services),
        )
        result = services.strategy_validation_service.validate(
            team_id=team_id,
            filename=file.filename or "strategy.py",
            content=content,
            data_track=track,
        )
    except ValidationRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_payload()


def _validation_team_id(
    services: Any,
    request: Request,
    team_name: str | None,
    password: str | None,
) -> str:
    if _has_supplied_credentials(team_name, password):
        if not team_name or not password or not team_name.strip():
            raise HTTPException(
                status_code=400,
                detail="team name and password are required together",
            )
        team = services.team_repository.resolve_login(team_name)
        if (
            team is None
            or team.archived_at is not None
            or not services.team_repository.verify_password(team_name, password)
        ):
            raise HTTPException(status_code=401, detail="invalid team credentials")
        return team.team_id
    session = require_participant_session(request)
    return session.team_id


@router.get("", response_model=SubmissionListResponse, response_model_exclude_unset=True)
def list_submissions(
    request: Request,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    status: str | None = None,
    data_track: str | None = None,
    team_id: str | None = None,
) -> dict[str, Any]:
    services = request.app.state.services
    weights = services.admin_service.scoring_weights()
    team_names = team_name_map(services.team_repository.list_all())
    no_explicit_sort = sort_by is None and sort_dir is None
    params = SubmissionListParams(
        limit=limit or DEFAULT_SUBMISSION_LIST_LIMIT,
        offset=offset or 0,
        search=search or "",
        sort_by="submission_number" if no_explicit_sort else sort_by or "submitted_at",
        sort_dir="asc" if no_explicit_sort else parse_sort_dir(sort_dir),
        status=None if status in (None, "", "all") else status,
        data_track=parse_data_track(data_track),
        team_id=None if team_id in (None, "", "all") else team_id,
        excluded_team_ids=_hidden_history_team_ids(services),
    )
    score_expression, score_values = score_sort_expression(weights)
    page = services.submission_repository.list_page(
        params,
        team_names=team_names,
        score_for=lambda submission: _score_from_summary(
            submission,
            submission.metrics.to_dict() if submission.metrics else {},
            weights,
        ),
        sql_sort_expressions={"score": (score_expression, score_values)},
    )
    rows = page.items
    stale_submission_ids = _active_stale_submission_ids(services)
    payload = {
        "submissions": [
            _submission_summary_payload(
                submission,
                team_name=team_names.get(submission.team_id, submission.team_id),
                stale=_submission_stale(
                    services,
                    submission,
                    stale_submission_ids,
                ),
                weights=weights,
                artifact_reader=services.artifact_reader,
                include_raw_error=False,
            )
            for submission in rows
        ]
    }
    payload.update(page.metadata())
    return payload


@router.get("/options", response_model=SubmissionOptionsResponse)
def submission_options(request: Request) -> dict[str, Any]:
    return {
        "available_data_tracks": [
            track.value
            for track in public_data_tracks(request.app.state.services)
        ]
    }


@router.get(
    "/{submission_id}/raw-error",
    response_class=PlainTextResponse,
    response_model=str,
)
def submission_raw_error(request: Request, submission_id: str) -> str:
    services = request.app.state.services
    session = require_participant_session(request)
    submission = services.submission_repository.get(submission_id)
    if submission is None or not _submission_visible(services, submission):
        raise HTTPException(status_code=404, detail="submission not found")
    if submission.team_id != session.team_id:
        raise HTTPException(status_code=403, detail="submission belongs to another team")
    error = raw_submission_error(submission)
    if error is None:
        raise HTTPException(status_code=404, detail="submission raw error not found")
    return error


@router.get(
    "/{submission_id}/source",
    response_class=PlainTextResponse,
    response_model=str,
)
def submission_source(request: Request, submission_id: str) -> str:
    services = request.app.state.services
    session = require_participant_session(request)
    submission = services.submission_repository.get(submission_id)
    if submission is None or not _submission_visible(services, submission):
        raise HTTPException(status_code=404, detail="submission not found")
    try:
        return services.submission_service.submission_source_for_team(
            submission_id,
            session.team_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="submission not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="submission source not found") from exc


@router.get("/{submission_id}", response_model=SubmissionDetail)
def submission_detail(request: Request, submission_id: str) -> dict[str, Any]:
    services = request.app.state.services
    submission = services.submission_repository.get(submission_id)
    if submission is None or not _submission_visible(services, submission):
        raise HTTPException(status_code=404, detail="submission not found")
    artifacts = {}
    report_dir = Path(submission.report_dir)
    if report_dir.exists() and (
        submission.status == SubmissionStatus.COMPLETED
        or report_artifacts_available(report_dir)
    ):
        artifacts = services.artifact_reader.read(report_dir, include_parquet=False)
        artifacts = _complete_hs300_benchmark_artifacts(services, submission, artifacts)
    weights = services.admin_service.scoring_weights()
    score_summary = _score_summary(submission, artifacts)
    score = _score_from_summary(submission, score_summary, weights)
    payload = submission_detail_payload(
        submission,
        team_name=_team_name(services, submission.team_id),
        artifacts=artifacts,
        score=score,
        stale=_submission_stale(services, submission, summary=score_summary),
        raw_error=None,
    )
    if score_summary:
        payload["metrics"] = SubmissionMetrics.from_summary(score_summary).to_dict()
    contributions = score_contributions(score_summary, weights)
    payload["score_breakdown"] = [
        asdict(contribution)
        for contribution in contributions
    ]
    payload["score_calculation"] = (
        score_calculation_text(score_summary, weights) if score is not None else None
    )
    payload["pdf_report_available"] = _pdf_report_available(report_dir)
    return payload


@router.get("/{submission_id}/report")
def download_pdf_report(request: Request, submission_id: str):
    """Download PDF backtest report for a completed submission."""
    services = request.app.state.services
    submission = services.submission_repository.get(submission_id)
    if submission is None or not _submission_visible(services, submission):
        raise HTTPException(status_code=404, detail="submission not found")
    if submission.status != SubmissionStatus.COMPLETED:
        raise HTTPException(status_code=404, detail="report is not available: submission not completed")

    report_dir = Path(submission.report_dir)

    if pdf_report_is_current(report_dir):
        return FileResponse(
            pdf_report_path(report_dir),
            media_type="application/pdf",
            filename=f"report_{submission.submission_number or submission_id[:8]}.pdf",
        )

    try:
        from quantfish.backtest.pdf_report import generate_pdf_report
        team_name = _team_name(services, submission.team_id)
        generated = generate_pdf_report(submission, report_dir, team_name=team_name)

        return FileResponse(
            generated,
            media_type="application/pdf",
            filename=f"report_{submission.submission_number or submission_id[:8]}.pdf",
        )
    except ModuleNotFoundError as exc:
        # Report support is optional: keep serving a cached build rather than fail
        # the download when the host has no weasyprint/jinja2 to refresh it.
        cached = pdf_report_path(report_dir)
        if cached.is_file():
            return FileResponse(
                cached,
                media_type="application/pdf",
                filename=f"report_{submission.submission_number or submission_id[:8]}.pdf",
            )
        raise HTTPException(
            status_code=503,
            detail=(
                "PDF report support is not installed; install the optional "
                "extra with `pip install 'quantfish[pdf]'`"
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"failed to generate report: {exc}",
        ) from exc


def _pdf_report_available(report_dir: Path) -> bool:
    """True when a current PDF exists or the optional PDF dependencies are installed."""

    if pdf_report_path(report_dir).is_file():
        return True
    return (
        importlib.util.find_spec("weasyprint") is not None
        and importlib.util.find_spec("jinja2") is not None
    )


def _score_summary(submission: Any, artifacts: dict[str, Any]) -> dict[str, Any]:
    summary = artifacts.get("summary")
    if isinstance(summary, dict) and summary:
        return summary
    if submission.metrics is not None:
        return submission.metrics.to_dict()
    return {}


def _complete_hs300_benchmark_artifacts(
    services: Any,
    submission: Any,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    config_repository = getattr(
        getattr(services, "submission_service", None),
        "config_repository",
        None,
    )
    if config_repository is None:
        return artifacts
    return complete_hs300_benchmark_artifacts(
        artifacts,
        config_repository.load(),
        submission.data_track,
    )


def _submission_summary_payload(
    submission: Any,
    *,
    team_name: str,
    stale: bool,
    weights: ScoringWeights,
    artifact_reader: Any | None = None,
    include_raw_error: bool = True,
) -> dict[str, Any]:
    score_summary = score_summary_for_submission(submission, artifact_reader)
    effective_stale = stale or is_zero_result_stale(submission, score_summary)
    payload = submission_list_payload(
        submission,
        team_name=team_name,
        score=_score_from_summary(submission, score_summary, weights),
        stale=effective_stale,
        raw_error=raw_submission_error(submission) if include_raw_error else None,
    )
    if not include_raw_error:
        payload.pop("raw_error", None)
        payload["has_raw_error"] = submission_has_raw_error(submission)
    if score_summary:
        payload["metrics"] = SubmissionMetrics.from_summary(score_summary).to_dict()
    return payload


def _active_stale_submission_ids(services: Any) -> set[str]:
    stale_ids = getattr(
        getattr(services, "admin_service", None),
        "active_stale_submission_ids",
        None,
    )
    if not callable(stale_ids):
        return set()
    return set(stale_ids())


def _hidden_history_team_ids(services: Any) -> tuple[str, ...]:
    hidden_ids = getattr(
        getattr(services, "team_cohort_service", None),
        "hidden_history_team_ids",
        None,
    )
    if not callable(hidden_ids):
        return ()
    return tuple(sorted(hidden_ids()))


def _submission_visible(services: Any, submission: Submission) -> bool:
    visible = getattr(
        getattr(services, "team_cohort_service", None),
        "is_submission_visible",
        None,
    )
    return True if not callable(visible) else bool(visible(submission))


def _submission_stale(
    services: Any,
    submission: Submission,
    stale_submission_ids: set[str] | None = None,
    summary: dict[str, Any] | None = None,
) -> bool:
    if submission.status != SubmissionStatus.COMPLETED:
        return False
    stale_ids = stale_submission_ids if stale_submission_ids is not None else _active_stale_submission_ids(services)
    return submission.submission_id in stale_ids or is_zero_result_stale(
        submission,
        summary,
    )


def _score_from_summary(
    submission: Any,
    summary: dict[str, Any],
    weights: ScoringWeights,
) -> float | None:
    if not summary:
        return None
    return calculate_leaderboard_score(summary, weights)
