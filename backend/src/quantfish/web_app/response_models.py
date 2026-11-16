from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from quantfish.data.release_jobs import HistoricalReleaseName


class _FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class LeaderboardSummary(_FrozenModel):
    rank: int
    id: str
    team_name: str
    status: str
    stale: bool
    eligible: bool
    submitted_at: str
    summary: dict[str, float | None]
    score: float
    metric: Literal["score", "sharpe", "max_drawdown", "calmar"] = "score"
    metric_value: float = 0.0
    badge: str | None


class LeaderboardResponse(_FrozenModel):
    rows: list[LeaderboardSummary]
    count: int
    total_count: int | None = None
    limit: int | None = None
    offset: int | None = None
    has_next: bool | None = None


class DashboardRunnerStatus(_FrozenModel):
    status: Literal["online", "offline"]
    queued: int
    running: int
    updated_at: str
    scoring_timeout_seconds: int | None = None
    submissions_enabled: bool


class DashboardResponse(_FrozenModel):
    submission_count: int
    team_count: int
    course_name: str | None = None
    scoring_timeout_seconds: int | None = None
    latest: list[LeaderboardSummary]
    status_counts: dict[str, int]
    runner_status: DashboardRunnerStatus


class SubmissionMetrics(_FrozenModel):
    total_return: float | None = None
    annual_return: float | None = None
    average_year_return: float | None = None
    worst_year_return: float | None = None
    sharpe: float | None = None
    max_drawdown: float | None = None
    average_turnover: float | None = None
    average_short_exposure: float | None = None
    long_total_return: float | None = None
    short_total_return: float | None = None
    annualized_short_profit: float | None = None
    calmar: float | None = None
    win_rate: float | None = None
    stale_position_days: int | None = None
    max_stale_gross_exposure: float | None = None
    average_stale_gross_exposure: float | None = None
    terminal_stale_position_count: int | None = None
    terminal_stale_gross_exposure: float | None = None
    trading_days: int | None = None
    raw_total_return: float | None = None
    raw_sharpe: float | None = None
    raw_max_drawdown: float | None = None
    raw_calmar: float | None = None
    risk_free_rate: float | None = None
    risk_free_daily_return: float | None = None
    beta: float | None = None
    tracking_error: float | None = None
    information_ratio: float | None = None
    active_total_return: float | None = None
    active_annual_return: float | None = None
    active_max_drawdown: float | None = None
    active_calmar: float | None = None


_DATA_TRACK_LITERAL = Literal[
    "hidden_test",
    "learning",
    "learning_1",
    "learning_2",
    "learning_3",
]


class SubmissionSummary(_FrozenModel):
    submission_id: str
    submission_number: int
    submission_label: str
    team_id: str
    team_name: str
    status: str
    data_track: _DATA_TRACK_LITERAL
    stale: bool = False
    submitted_at: str
    scored_at: str | None = None
    metrics: SubmissionMetrics | None = None
    score: float | None = None
    error_message: str | None = None
    raw_error: str | None = None
    has_raw_error: bool | None = None


class SubmissionScoreContribution(_FrozenModel):
    key: str
    label: str
    metric_value: float
    weight: float
    contribution: float


class SubmissionExecutionParameters(_FrozenModel):
    data_track: _DATA_TRACK_LITERAL
    data_start: str | None = None
    scoring_start: str | None = None
    scoring_end: str | None = None
    capital: int | float | None = None
    group_count: int | None = None
    industry_neutralization: bool | None = None
    price_policy: str | None = None
    execution_price: str | None = None
    mark_price: str | None = None
    long_only_benchmark: str | None = None
    long_only_risk_free_rate: float | None = None
    long_only_min_beta_observations: int | None = None
    commission_rate: float | None = None
    slippage_rate: float | None = None
    sell_stamp_duty_rate: float | None = None
    max_leverage: float | None = None
    top_k: int | None = None
    allowed_market_types: list[int] | None = None
    long_only: bool | None = None
    long_only_weighting: str | None = None
    long_only_target_count: int | None = None
    max_position_weight: float | None = None
    max_participation_rate: float | None = None
    min_listing_days: int | None = None
    terminal_stale_position_policy: str | None = None
    submission_timeout_enabled: bool | None = None
    submission_timeout_seconds: int | None = None


class SubmissionPerformanceRow(_FrozenModel):
    period: str
    long: float | None = None
    short: float | None = None
    long_count: int | None = None
    short_count: int | None = None
    sharpe: float | None = None
    total_return: float | None = None
    annualized_return: float | None = None
    turnover: float | None = None
    drawdown: float | None = None
    fitness: float | None = None
    calmar: float | None = None


class SubmissionDetail(SubmissionSummary):
    fingerprints: dict[str, str] | None = None
    original_filename: str
    artifacts: dict[str, Any]
    execution_parameters: SubmissionExecutionParameters | None = None
    performance_table: list[SubmissionPerformanceRow]
    score_breakdown: list[SubmissionScoreContribution]
    score_calculation: str | None = None
    pdf_report_available: bool = False


class SubmissionListResponse(_FrozenModel):
    submissions: list[SubmissionSummary]
    total_count: int | None = None
    limit: int | None = None
    offset: int | None = None
    has_next: bool | None = None


class SubmissionOptionsResponse(_FrozenModel):
    available_data_tracks: list[_DATA_TRACK_LITERAL]


class CompareSubmission(_FrozenModel):
    submission_id: str
    submission_number: int
    submission_label: str
    team_id: str
    team_name: str
    status: str
    data_track: _DATA_TRACK_LITERAL
    metrics: SubmissionMetrics | None = None
    equity: list[dict[str, Any]]
    drawdown: list[dict[str, Any]]
    graph_data: dict[str, Any] | None = None
    execution_parameters: SubmissionExecutionParameters | None = None


class CompareResponse(_FrozenModel):
    submissions: list[CompareSubmission]


class TeamPublic(_FrozenModel):
    team_id: str
    display_name: str
    team_name: str | None = None
    password: str | None = None


class AdminTeamRecord(_FrozenModel):
    team_id: str
    team_name: str
    display_name: str
    submission_count: int
    created_at: str
    status: str
    password: str | None = None
    cohort_id: str | None = None
    cohort_name: str | None = None
    history_visible: bool = True
    submissions_enabled: bool = True


class AdminTeamCohortRecord(_FrozenModel):
    cohort_id: str
    name: str
    team_ids: list[str]
    history_visible: bool
    submissions_enabled: bool
    created_at: str
    updated_at: str


class AdminTeamsResponse(_FrozenModel):
    teams: list[AdminTeamRecord] = []
    active_teams: list[AdminTeamRecord] = []
    archived_teams: list[AdminTeamRecord] = []
    cohorts: list[AdminTeamCohortRecord] = []


class AdminSessionResponse(_FrozenModel):
    authenticated: bool


class ParticipantSessionResponse(_FrozenModel):
    authenticated: bool
    team_id: str | None = None
    team_name: str | None = None


class AdminCourseConfig(_FrozenModel):
    name: str | None = None


class AdminDataReleasesConfig(_FrozenModel):
    raw_data_root: str | None = None
    learning_output_root: str | None = None
    hidden_output_root: str | None = None
    learning_start: str | None = None
    learning_end: str | None = None
    hidden_start: str | None = None
    hidden_end: str | None = None
    learning_1_output_root: str | None = None
    learning_1_start: str | None = None
    learning_1_end: str | None = None
    learning_2_output_root: str | None = None
    learning_2_start: str | None = None
    learning_2_end: str | None = None
    learning_3_output_root: str | None = None
    learning_3_start: str | None = None
    learning_3_end: str | None = None


class AdminDatasetConfig(_FrozenModel):
    train_start: str | None = None
    train_end: str | None = None
    hidden_test_start: str | None = None
    hidden_test_end: str | None = None


class AdminBacktestConfig(_FrozenModel):
    data_start: str | None = None
    scoring_start: str | None = None
    scoring_end: str | None = None
    capital: int | None = None
    group_count: int | None = None
    industry_neutralization: bool | None = None
    price_policy: str | None = None
    execution_price: str | None = None
    mark_price: str | None = None
    long_only_benchmark: str | None = None
    long_only_risk_free_rate: float | None = None
    long_only_min_beta_observations: int | None = None


class AdminExecutionLimits(_FrozenModel):
    max_upload_bytes: int | None = None
    scoring_timeout_seconds: int | None = None
    engine_version: str | None = None


class AdminScoringConfig(_FrozenModel):
    sharpe_weight: float | None = None
    sharpe_target: float | None = None
    annual_return_weight: float | None = None
    annual_return_target: float | None = None
    drawdown_weight: float | None = None
    drawdown_limit: float | None = None
    turnover_weight: float | None = None
    turnover_limit: float | None = None
    short_profit_weight: float | None = None
    short_profit_target: float | None = None
    minimum_slice_trading_days: int | None = None


class AdminExecutionConfig(_FrozenModel):
    commission_rate: float | None = None
    slippage_rate: float | None = None
    sell_stamp_duty_rate: float | None = None
    max_leverage: float | None = None
    top_k: int | None = None
    allowed_market_types: list[int] | None = None
    submissions_enabled: bool | None = None
    hidden_test_enabled: bool | None = None
    max_concurrent_scoring: int | None = None
    submission_timeout_seconds: int | None = None
    submission_timeout_enabled: bool | None = None
    long_only: bool | None = None
    long_only_weighting: str | None = None
    long_only_target_count: int | None = None
    max_position_weight: float | None = None
    max_participation_rate: float | None = None
    min_listing_days: int | None = None
    terminal_stale_position_policy: str | None = None


class AdminRuntimeConfig(_FrozenModel):
    runtime_root: str | None = None
    frontend_dist: str | None = None


class AdminSettingsHistoryEntry(_FrozenModel):
    entry_id: str
    created_at: str
    entry_type: Literal["settings_change", "stale_mark"] = "settings_change"
    config_sha256: str | None = None
    changed_fields: list[str]
    settings: dict[str, Any]
    stale_marked: bool = False
    affected_submission_ids: list[str] = Field(default_factory=list)
    affected_count: int = 0
    reverted_at: str | None = None


class AdminSettingsResponse(_FrozenModel):
    course: AdminCourseConfig | None = None
    dataset: AdminDatasetConfig | None = None
    data_releases: AdminDataReleasesConfig | None = None
    backtest: AdminBacktestConfig | None = None
    scoring: AdminScoringConfig | None = None
    execution: AdminExecutionConfig | None = None
    execution_limits: AdminExecutionLimits | None = None
    runtime: AdminRuntimeConfig | None = None
    settings_history: list[AdminSettingsHistoryEntry] = Field(default_factory=list)


class AdminDataReleaseInfo(_FrozenModel):
    release_name: HistoricalReleaseName
    start: str
    end: str
    output_root: str
    status: Literal["ready", "missing"]
    last_built_at: str | None = None


class AdminDataReleaseTrackProgress(_FrozenModel):
    release_name: HistoricalReleaseName
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    phase: str
    progress_percent: float
    completed_datasets: int
    total_datasets: int
    current_dataset: str | None = None
    error_message: str | None = None


class AdminDataReleaseBuildJob(_FrozenModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    release_names: list[HistoricalReleaseName]
    progress_percent: float
    tracks: list[AdminDataReleaseTrackProgress]
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    current_release_name: HistoricalReleaseName | None = None
    error_message: str | None = None


class AdminDataReleaseBuildState(_FrozenModel):
    source_available: bool
    buildable_release_names: list[HistoricalReleaseName]
    releases: list[AdminDataReleaseInfo]
    job: AdminDataReleaseBuildJob | None = None


class AdminSubmissionRecord(_FrozenModel):
    submission_id: str
    submission_number: int
    submission_label: str
    team_id: str
    team_name: str
    type: str
    data_track: _DATA_TRACK_LITERAL
    status: str
    stale: bool
    selectable: bool
    score: float | None = None
    filename: str
    submitted_at: str
    finished_at: str | None = None
    raw_error: str | None = None
    has_raw_error: bool | None = None
    config_snapshot: dict[str, Any] | None = None
    file_paths: dict[str, str]


class AdminSubmissionsResponse(_FrozenModel):
    submissions: list[AdminSubmissionRecord]
    total_count: int | None = None
    limit: int | None = None
    offset: int | None = None
    has_next: bool | None = None


class AdminBackfillResponse(_FrozenModel):
    queued: int
    submission_ids: list[str]


class AdminRerunResponse(_FrozenModel):
    queued: int
    skipped: int
    queued_submission_ids: list[str]
    skipped_submission_ids: list[str]


class AdminDeletionResponse(_FrozenModel):
    deleted: int
    skipped: int
    deleted_submission_ids: list[str]
    skipped_submission_ids: list[str]
    deleted_file_paths: list[str]


class EnvironmentDownloadOption(_FrozenModel):
    platform: str
    label: str
    architecture: str
    status: Literal["available", "stale", "missing"]
    size_bytes: int | None = None
    updated_at: str | None = None
    download_url: str | None = None


class EnvironmentOptionsResponse(_FrozenModel):
    platforms: list[EnvironmentDownloadOption]
