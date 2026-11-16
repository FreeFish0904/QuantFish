from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from quantfish.admin_console.routes import router as admin_router
from quantfish.admin_console.service import AdminConsoleService
from quantfish.admin_console.settings_history import AdminSettingsHistoryRepository
from quantfish.data.release_jobs import DataReleaseBuildService
from quantfish.data.release_lock import ReleaseLockManager
from quantfish.leaderboard.routes import router as leaderboard_router
from quantfish.platform_config import ConfigRepository
from quantfish.result_comparison.routes import router as comparison_router
from quantfish.result_comparison.service import ComparisonService
from quantfish.student_exports.service import StudentExportService
from quantfish.submissions.artifacts import ReportArtifactReader
from quantfish.submissions.dispatcher import SubmissionScoringDispatcher
from quantfish.submissions.repositories import SubmissionRepository, TeamRepository
from quantfish.submissions.routes import router as submissions_router
from quantfish.submissions.runners import BacktestSubmissionRunner
from quantfish.submissions.session_routes import router as participant_session_router
from quantfish.submissions.service import SubmissionRunner, SubmissionService
from quantfish.submissions.storage import SubmissionStorage
from quantfish.team_cohorts import TeamCohortRepository, TeamCohortService
from quantfish.web_app.schemas import HealthResponse
from quantfish.web_app.settings import WebSettings


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):  # type: ignore[no-untyped-def]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or not _should_fall_back_to_index(path, scope):
                raise
            return await super().get_response("index.html", scope)


@dataclass(frozen=True)
class AppServices:
    settings: WebSettings
    team_repository: TeamRepository
    team_cohort_repository: TeamCohortRepository
    team_cohort_service: TeamCohortService
    submission_repository: SubmissionRepository
    storage: SubmissionStorage
    artifact_reader: ReportArtifactReader
    submission_runner: SubmissionRunner
    scoring_dispatcher: SubmissionScoringDispatcher
    submission_service: SubmissionService
    comparison_service: ComparisonService
    admin_service: AdminConsoleService
    student_export_service: StudentExportService
    data_release_build_service: DataReleaseBuildService


def create_app(
    settings: WebSettings | None = None,
    *,
    submission_runner: SubmissionRunner | None = None,
) -> FastAPI:
    resolved = settings or WebSettings()
    missing_credentials = _missing_app_credentials(resolved)
    if missing_credentials:
        raise ValueError(
            "web app construction requires explicit credentials; missing: "
            + ", ".join(missing_credentials)
        )
    resolved.ensure_runtime_dirs()
    app = FastAPI(
        title="QuantFish Classroom Platform",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.state.services = _build_services(resolved, submission_runner=submission_runner)

    if resolved.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(resolved.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            app="QuantFish",
            status="ok",
            engine_version=resolved.engine_version,
        )

    _include_routes(app)
    _mount_frontend(app, resolved.frontend_dist)
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    app.state.services.scoring_dispatcher.start()
    try:
        yield
    finally:
        app.state.services.data_release_build_service.stop()
        app.state.services.scoring_dispatcher.stop()


def _build_services(
    settings: WebSettings,
    *,
    submission_runner: SubmissionRunner | None = None,
) -> AppServices:
    team_repository = TeamRepository(settings.runtime_root)
    team_cohort_repository = TeamCohortRepository(settings.runtime_root)
    team_cohort_service = TeamCohortService(team_cohort_repository, team_repository)
    submission_repository = SubmissionRepository(settings.runtime_root)
    storage = SubmissionStorage(
        settings.runtime_root,
        max_upload_bytes=settings.max_upload_bytes,
    )
    artifact_reader = ReportArtifactReader()
    runner = submission_runner or BacktestSubmissionRunner(settings)
    config_repository = ConfigRepository(settings.config_path)
    release_lock_manager = ReleaseLockManager(
        settings.runtime_root / "locks" / "data-releases"
    )
    settings_history_repository = AdminSettingsHistoryRepository(settings.runtime_root)
    student_export_service = StudentExportService(settings, config_repository)
    submission_service = SubmissionService(
        team_repository,
        submission_repository,
        storage,
        runner,
        config_repository,
        team_cohort_service=team_cohort_service,
        submission_cooldown_seconds=settings.submission_cooldown_seconds,
    )
    scoring_dispatcher = SubmissionScoringDispatcher(
        submission_repository,
        runner,
        config_repository,
        release_lock_manager=release_lock_manager,
    )
    submission_service.set_scoring_dispatcher(scoring_dispatcher)
    comparison_service = ComparisonService(
        submission_repository,
        team_repository,
        artifact_reader,
        team_cohort_service=team_cohort_service,
    )
    admin_service = AdminConsoleService(
        settings,
        team_repository,
        storage,
        submission_repository,
        runner,
        scoring_dispatcher,
        student_export_service,
        artifact_reader=artifact_reader,
        settings_history_repository=settings_history_repository,
        team_cohort_service=team_cohort_service,
    )
    data_release_build_service = DataReleaseBuildService(
        config_repository,
        release_lock_manager=release_lock_manager,
    )
    return AppServices(
        settings=settings,
        team_repository=team_repository,
        team_cohort_repository=team_cohort_repository,
        team_cohort_service=team_cohort_service,
        submission_repository=submission_repository,
        storage=storage,
        artifact_reader=artifact_reader,
        submission_runner=runner,
        scoring_dispatcher=scoring_dispatcher,
        submission_service=submission_service,
        comparison_service=comparison_service,
        admin_service=admin_service,
        student_export_service=student_export_service,
        data_release_build_service=data_release_build_service,
    )


def _include_routes(app: FastAPI) -> None:
    for router in (
        admin_router,
        participant_session_router,
        submissions_router,
        leaderboard_router,
        comparison_router,
    ):
        app.include_router(router)


def _mount_frontend(app: FastAPI, frontend_dist: Path) -> None:
    if frontend_dist.exists():
        app.mount("/", SpaStaticFiles(directory=frontend_dist, html=True), name="frontend")


def _should_fall_back_to_index(path: str, scope) -> bool:  # type: ignore[no-untyped-def]
    if scope.get("method") not in {"GET", "HEAD"}:
        return False
    if path == "api" or path.startswith("api/"):
        return False
    return "." not in Path(path).name


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the QuantFish classroom web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--runtime-root", default="runs/web_platform")
    parser.add_argument("--config", default="config/platform.yaml")
    parser.add_argument("--frontend-dist", default="frontend/dist")
    args = parser.parse_args(argv)

    import uvicorn

    settings = WebSettings(
        runtime_root=Path(args.runtime_root),
        config_path=Path(args.config),
        frontend_dist=Path(args.frontend_dist),
    )
    missing_credentials = _missing_app_credentials(settings)
    if missing_credentials:
        parser.error(
            "web startup requires explicit credentials; missing: "
            + ", ".join(missing_credentials)
        )
    uvicorn.run(create_app(settings), host=args.host, port=args.port)


def _missing_app_credentials(settings: WebSettings) -> tuple[str, ...]:
    required = (
        ("QUANTFISH_ADMIN_PASSWORD", settings.admin_password),
        ("QUANTFISH_ADMIN_SESSION_SECRET", settings.admin_session_secret),
        (
            "QUANTFISH_PARTICIPANT_SESSION_SECRET",
            settings.participant_session_secret,
        ),
    )
    return tuple(
        name
        for name, value in required
        if not isinstance(value, str) or not value.strip()
    )


if __name__ == "__main__":
    main()
