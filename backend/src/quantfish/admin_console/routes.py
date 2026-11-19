from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from quantfish.data.release_jobs import HistoricalReleaseName, ReleaseBuildAlreadyRunning
from quantfish.submissions.listing import (
    SubmissionListParams,
    parse_data_track,
    parse_sort_dir,
)
from quantfish.web_app.admin_auth import (
    clear_admin_session_cookie,
    require_admin_session,
    set_admin_session_cookie,
    verify_admin_password,
)
from quantfish.web_app.response_models import (
    AdminBackfillResponse,
    AdminDataReleaseBuildJob,
    AdminDataReleaseBuildState,
    AdminDeletionResponse,
    AdminRerunResponse,
    AdminSessionResponse,
    AdminSettingsResponse,
    AdminSubmissionsResponse,
    AdminTeamCohortRecord,
    AdminTeamRecord,
    AdminTeamsResponse,
    EnvironmentOptionsResponse,
)

router = APIRouter(tags=["admin"])
DEFAULT_ADMIN_SUBMISSION_LIST_LIMIT = 100


class TeamCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    team_name: str
    password: str


class AdminLoginRequest(BaseModel):
    password: str


class AdminSettingsUpdateRequest(BaseModel):
    dataset: dict[str, Any] | None = None
    backtest: dict[str, Any] | None = None
    scoring: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None


class TeamUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    team_name: str | None = None
    password: str | None = None


class TeamBulkActionRequest(BaseModel):
    team_ids: list[str]
    action: str


class TeamCohortCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str
    team_ids: list[str] = []
    history_visible: bool = True
    submissions_enabled: bool = True


class TeamCohortUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = None
    team_ids: list[str] | None = None
    history_visible: bool | None = None
    submissions_enabled: bool | None = None


class SubmissionDeleteRequest(BaseModel):
    submission_ids: list[str]
    force: bool = False


class SubmissionRerunRequest(BaseModel):
    scope: Literal["all", "selected"]
    submission_ids: list[str] | None = None


class DataReleaseBuildRequest(BaseModel):
    release_names: list[HistoricalReleaseName] = Field(min_length=1)


@router.post("/api/admin/login", response_model=AdminSessionResponse)
def admin_login(
    request: Request,
    response: Response,
    payload: AdminLoginRequest,
) -> dict[str, bool]:
    if not verify_admin_password(request, payload.password):
        raise HTTPException(status_code=401, detail="invalid admin password")
    set_admin_session_cookie(request, response)
    return {"authenticated": True}


@router.get("/api/admin/session", response_model=AdminSessionResponse)
def admin_session(request: Request) -> dict[str, bool]:
    try:
        require_admin_session(request)
    except HTTPException:
        return {"authenticated": False}
    return {"authenticated": True}


@router.post("/api/admin/logout", response_model=AdminSessionResponse)
def admin_logout(response: Response) -> dict[str, bool]:
    clear_admin_session_cookie(response)
    return {"authenticated": False}


@router.get("/api/admin/settings", response_model=AdminSettingsResponse)
def admin_settings(request: Request) -> dict[str, Any]:
    require_admin_session(request)
    return request.app.state.services.admin_service.settings_payload()


@router.patch("/api/admin/settings", response_model=AdminSettingsResponse)
def update_admin_settings(
    request: Request,
    payload: AdminSettingsUpdateRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.update_settings(
            dataset=payload.dataset,
            backtest=payload.backtest,
            scoring=payload.scoring,
            execution=payload.execution,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/api/admin/data-releases",
    response_model=AdminDataReleaseBuildState,
)
def admin_data_releases(request: Request) -> dict[str, Any]:
    require_admin_session(request)
    return request.app.state.services.data_release_build_service.status_payload()


@router.post(
    "/api/admin/data-releases/build",
    response_model=AdminDataReleaseBuildJob,
    status_code=202,
)
def build_admin_data_releases(
    request: Request,
    payload: DataReleaseBuildRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.data_release_build_service.start(
            payload.release_names
        )
    except ReleaseBuildAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/api/admin/settings-history/{entry_id}/revert", response_model=AdminSettingsResponse)
def revert_admin_settings_history(
    request: Request,
    entry_id: str,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.revert_settings_history(entry_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="settings history entry not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/admin/stale-marks", response_model=AdminSettingsResponse)
def mark_completed_submissions_stale(request: Request) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.mark_completed_submissions_stale()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/admin/stale-marks/{entry_id}/revert", response_model=AdminSettingsResponse)
def revert_admin_stale_mark(
    request: Request,
    entry_id: str,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.revert_stale_mark(entry_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="stale mark not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/admin/teams", response_model=AdminTeamsResponse)
def admin_teams(request: Request) -> dict[str, Any]:
    require_admin_session(request)
    return request.app.state.services.admin_service.list_teams()


@router.post("/api/admin/teams", response_model=AdminTeamRecord)
def create_team(
    request: Request,
    payload: TeamCreateRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.create_team(
            team_name=payload.team_name,
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/api/admin/teams/{team_id}", response_model=AdminTeamRecord)
def update_team(
    request: Request,
    team_id: str,
    payload: TeamUpdateRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.update_team(
            team_id,
            team_name=payload.team_name,
            password=payload.password,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="team not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/admin/teams/bulk-action")
def bulk_team_action(
    request: Request,
    payload: TeamBulkActionRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.bulk_team_action(
            payload.team_ids,
            payload.action,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/admin/team-cohorts", response_model=AdminTeamCohortRecord)
def create_team_cohort(
    request: Request,
    payload: TeamCohortCreateRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.create_team_cohort(
            name=payload.name,
            team_ids=payload.team_ids,
            history_visible=payload.history_visible,
            submissions_enabled=payload.submissions_enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/api/admin/team-cohorts/{cohort_id}", response_model=AdminTeamCohortRecord)
def update_team_cohort(
    request: Request,
    cohort_id: str,
    payload: TeamCohortUpdateRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.update_team_cohort(
            cohort_id,
            name=payload.name,
            team_ids=payload.team_ids,
            history_visible=payload.history_visible,
            submissions_enabled=payload.submissions_enabled,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="cohort not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/api/admin/team-cohorts/{cohort_id}")
def delete_team_cohort(request: Request, cohort_id: str) -> dict[str, bool]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.delete_team_cohort(cohort_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="cohort not found") from exc


@router.get(
    "/api/admin/team-cohorts/{cohort_id}/submissions",
    response_model=AdminSubmissionsResponse,
    response_model_exclude_unset=True,
)
def admin_team_cohort_submissions(
    request: Request,
    cohort_id: str,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int | None, Query(ge=0)] = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    status: str | None = None,
    data_track: str | None = None,
) -> dict[str, Any]:
    require_admin_session(request)
    no_explicit_sort = sort_by is None and sort_dir is None
    params = SubmissionListParams(
        limit=limit or DEFAULT_ADMIN_SUBMISSION_LIST_LIMIT,
        offset=offset or 0,
        search=search or "",
        sort_by="submission_number" if no_explicit_sort else sort_by or "submitted_at",
        sort_dir="asc" if no_explicit_sort else parse_sort_dir(sort_dir),
        status=None if status in (None, "", "all") else status,
        data_track=parse_data_track(data_track),
    )
    try:
        return request.app.state.services.admin_service.list_cohort_submission_page(
            cohort_id,
            params,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="cohort not found") from exc


@router.get(
    "/api/admin/team-cohorts/{cohort_id}/submissions/{submission_id}/source",
    response_class=PlainTextResponse,
    response_model=str,
)
def admin_team_cohort_submission_source(
    request: Request,
    cohort_id: str,
    submission_id: str,
) -> str:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.cohort_submission_source(
            cohort_id,
            submission_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="submission not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="submission source not found") from exc


@router.get(
    "/api/admin/team-cohorts/{cohort_id}/submissions/{submission_id}/raw-error",
    response_class=PlainTextResponse,
    response_model=str,
)
def admin_team_cohort_submission_raw_error(
    request: Request,
    cohort_id: str,
    submission_id: str,
) -> str:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.cohort_submission_raw_error(
            cohort_id,
            submission_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="submission not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="submission raw error not found") from exc


@router.post(
    "/api/admin/team-cohorts/{cohort_id}/submissions/rerun",
    response_model=AdminRerunResponse,
)
def rerun_admin_team_cohort_submissions(
    request: Request,
    cohort_id: str,
    payload: SubmissionRerunRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.rerun_cohort_submissions(
            cohort_id,
            scope=payload.scope,
            submission_ids=payload.submission_ids or [],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="cohort not found") from exc


@router.get("/api/admin/submissions", response_model=AdminSubmissionsResponse, response_model_exclude_unset=True)
def admin_submissions(
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
    require_admin_session(request)
    no_explicit_sort = sort_by is None and sort_dir is None
    params = SubmissionListParams(
        limit=limit or DEFAULT_ADMIN_SUBMISSION_LIST_LIMIT,
        offset=offset or 0,
        search=search or "",
        sort_by="submission_number" if no_explicit_sort else sort_by or "submitted_at",
        sort_dir="asc" if no_explicit_sort else parse_sort_dir(sort_dir),
        status=None if status in (None, "", "all") else status,
        data_track=parse_data_track(data_track),
        team_id=None if team_id in (None, "", "all") else team_id,
    )
    return request.app.state.services.admin_service.list_admin_submission_page(params)


@router.post(
    "/api/admin/submissions/backfill-short-profit",
    response_model=AdminBackfillResponse,
)
def backfill_short_profit_submissions(request: Request) -> dict[str, Any]:
    require_admin_session(request)
    return request.app.state.services.admin_service.backfill_short_profit_metrics()


@router.post("/api/admin/submissions/rerun", response_model=AdminRerunResponse)
def rerun_admin_submissions(
    request: Request,
    payload: SubmissionRerunRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    return request.app.state.services.admin_service.rerun_submissions(
        scope=payload.scope,
        submission_ids=payload.submission_ids or [],
    )


@router.get(
    "/api/admin/submissions/{submission_id}/source",
    response_class=PlainTextResponse,
    response_model=str,
)
def admin_submission_source(request: Request, submission_id: str) -> str:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.submission_source(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="submission not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="submission source not found") from exc


@router.get(
    "/api/admin/submissions/{submission_id}/raw-error",
    response_class=PlainTextResponse,
    response_model=str,
)
def admin_submission_raw_error(request: Request, submission_id: str) -> str:
    require_admin_session(request)
    try:
        return request.app.state.services.admin_service.submission_raw_error(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="submission not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="submission raw error not found") from exc


@router.post("/api/admin/submissions/delete", response_model=AdminDeletionResponse)
def delete_admin_submissions(
    request: Request,
    payload: SubmissionDeleteRequest,
) -> dict[str, Any]:
    require_admin_session(request)
    return request.app.state.services.admin_service.delete_submissions(
        payload.submission_ids,
        force=payload.force,
    )


@router.get(
    "/api/downloads/starter-strategy.py",
    response_class=PlainTextResponse,
    response_model=str,
)
def starter_strategy(request: Request) -> str:
    return request.app.state.services.admin_service.starter_strategy_text()


@router.get(
    "/api/downloads/quickstart.txt",
    response_class=PlainTextResponse,
    response_model=str,
)
def quickstart(request: Request) -> str:
    return request.app.state.services.admin_service.quickstart_text()


@router.get(
    "/api/downloads/learning-data.zip",
    response_class=FileResponse,
)
def learning_data_download(request: Request) -> FileResponse:
    path = request.app.state.services.student_export_service.learning_data_zip_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="learning data export is not available")
    return FileResponse(
        path,
        media_type="application/zip",
        filename="quantfish-learning-data.zip",
    )


@router.get(
    "/api/downloads/environment-options",
    response_model=EnvironmentOptionsResponse,
)
def environment_options(request: Request) -> dict[str, Any]:
    return request.app.state.services.student_export_service.environment_options()


@router.get(
    "/api/downloads/environment/{platform}.zip",
    response_class=FileResponse,
)
def environment_download(request: Request, platform: str) -> FileResponse:
    service = request.app.state.services.student_export_service
    options = {
        option["platform"]: option
        for option in service.environment_options().get("platforms", [])
    }
    option = options.get(platform)
    path = service.environment_zip_path(platform)
    if option is None or option.get("status") != "available" or not path.exists():
        raise HTTPException(status_code=404, detail=f"environment package is not available: {platform}")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"quantfish-environment-{platform}.zip",
    )
