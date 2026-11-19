import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "../../shared/api/generated/api-types";
import { normalizeDataTrack, type DataTrack } from "../../shared/submissions/dataTrack";
import {
  backfillShortProfitSubmissions,
  createTeam,
  createTeamCohort,
  deleteAdminSubmissions,
  deleteTeamCohort,
  fetchAdminCohortSubmissionRawError,
  fetchAdminCohortSubmissions,
  fetchAdminCohortSubmissionSource,
  fetchAdminDataReleases,
  fetchAdminFailures,
  fetchAdminSubmissionRawError,
  fetchAdminSubmissionSource,
  fetchAdminSession,
  fetchAdminSettings,
  fetchAdminSubmissions,
  fetchAdminTeams,
  loginAdmin,
  logoutAdmin,
  markAdminStaleSubmissions,
  revertAdminStaleMark,
  revertAdminSettingsHistory,
  rerunAdminCohortSubmissions,
  rerunAdminSubmissions,
  runTeamBulkAction,
  startAdminDataReleaseBuild,
  updateAdminSettings,
  updateTeam,
  updateTeamCohort,
  type AdminSettingsUpdatePayload,
  type CreateTeamCohortPayload,
  type DeleteSubmissionsPayload,
  type FetchAdminCohortSubmissionsParams,
  type FetchAdminSubmissionsParams,
  type RerunAdminSubmissionsPayload,
  type StartDataReleaseBuildPayload,
  type TeamBulkActionPayload,
  type UpdateTeamCohortPayload,
  type UpdateTeamPayload
} from "./api";

type SettingsResponse = components["schemas"]["AdminSettingsResponse"];
type TeamsResponse = components["schemas"]["AdminTeamsResponse"];
type AdminTeamResponse = components["schemas"]["AdminTeamRecord"];
type AdminTeamCohortResponse = components["schemas"]["AdminTeamCohortRecord"];
type AdminSubmissionsResponse = components["schemas"]["AdminSubmissionsResponse"];
type AdminSubmissionResponse = components["schemas"]["AdminSubmissionRecord"];
type DataReleaseBuildStateResponse = components["schemas"]["AdminDataReleaseBuildState"];
type DataReleaseBuildJobResponse = components["schemas"]["AdminDataReleaseBuildJob"];

export type HistoricalReleaseName = "learning_1" | "learning_2" | "learning_3";

export type AdminDataReleaseInfo = {
  releaseName: HistoricalReleaseName;
  start: string;
  end: string;
  outputRoot: string;
  status: "ready" | "missing";
  lastBuiltAt: string | null;
};

export type AdminDataReleaseTrackProgress = {
  releaseName: HistoricalReleaseName;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  phase: string;
  progressPercent: number;
  completedDatasets: number;
  totalDatasets: number;
  currentDataset: string | null;
  errorMessage: string | null;
};

export type AdminDataReleaseBuildJob = {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  releaseNames: HistoricalReleaseName[];
  progressPercent: number;
  tracks: AdminDataReleaseTrackProgress[];
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  currentReleaseName: HistoricalReleaseName | null;
  errorMessage: string | null;
};

export type AdminDataReleaseBuildState = {
  sourceAvailable: boolean;
  buildableReleaseNames: HistoricalReleaseName[];
  releases: AdminDataReleaseInfo[];
  job: AdminDataReleaseBuildJob | null;
};

export type AdminDatasetSettings = {
  trainStart: string;
  trainEnd: string;
  hiddenTestStart: string;
  hiddenTestEnd: string;
};

export type AdminScoringSettings = {
  sharpeWeight: number;
  sharpeTarget: number;
  annualReturnWeight: number;
  annualReturnTarget: number;
  drawdownWeight: number;
  drawdownLimit: number;
  turnoverWeight: number;
  turnoverLimit: number;
  shortProfitWeight: number;
  shortProfitTarget: number;
  minimumSliceTradingDays: number;
};

export type AdminExecutionSettings = {
  commissionRate: number;
  slippageRate: number;
  sellStampDutyRate: number;
  maxLeverage: number;
  topK: number | null;
  longOnlyWeighting: string;
  longOnlyTargetCount: number;
  maxPositionWeight: number;
  maxParticipationRate: number;
  minListingDays: number;
  terminalStalePositionPolicy: string;
  allowedMarketTypes: number[];
  submissionsEnabled: boolean;
  hiddenTestEnabled: boolean;
  maxConcurrentScoring: number;
  submissionTimeoutSeconds: number;
  submissionTimeoutEnabled: boolean;
  longOnly: boolean;
};

export type AdminSettings = {
  courseName: string;
  dataset: AdminDatasetSettings;
  scoring: AdminScoringSettings;
  execution: AdminExecutionSettings;
  dataStart: string | null;
  scoringStart: string | null;
  scoringEnd: string | null;
  capital: number | null;
  groupCount: number | null;
  industryNeutralization: boolean;
  longOnlyBenchmark: string | null;
  longOnlyRiskFreeRate: number;
  longOnlyMinBetaObservations: number;
  pricePolicy: string | null;
  executionPrice: string | null;
  markPrice: string | null;
  rawDataRoot: string | null;
  learningOutputRoot: string | null;
  hiddenOutputRoot: string | null;
  learningEnd: string | null;
  hiddenStart: string | null;
  hiddenEnd: string | null;
  maxUploadBytes: number | null;
  scoringTimeoutSeconds: number | null;
  engineVersion: string | null;
  runtimeRoot: string | null;
  frontendDist: string | null;
  settingsHistory: AdminSettingsHistoryEntry[];
};

export type AdminSettingsHistoryEntry = {
  entryId: string;
  createdAt: string;
  entryType: "settings_change" | "stale_mark";
  configSha256: string | null;
  changedFields: string[];
  settings: Record<string, unknown>;
  staleMarked: boolean;
  affectedSubmissionIds: string[];
  affectedCount: number;
  revertedAt: string | null;
};

export type TeamRecord = {
  teamId: string;
  teamName: string;
  displayName: string;
  submissionCount: number;
  createdAt: string;
  status: string;
  password: string | null;
  cohortId: string | null;
  cohortName: string | null;
  historyVisible: boolean;
  submissionsEnabled: boolean;
};

export type TeamCohortRecord = {
  cohortId: string;
  name: string;
  teamIds: string[];
  historyVisible: boolean;
  submissionsEnabled: boolean;
  createdAt: string;
  updatedAt: string;
};

export type TeamCollections = {
  activeTeams: TeamRecord[];
  archivedTeams: TeamRecord[];
  teams: TeamRecord[];
  cohorts: TeamCohortRecord[];
};

export type AdminSubmissionRecord = {
  id: string;
  submissionNumber: number;
  submissionLabel: string;
  teamId: string;
  teamName: string;
  type: string;
  dataTrack: DataTrack;
  status: string;
  stale: boolean;
  selectable: boolean;
  score: number | null;
  filename: string;
  submittedAt: string;
  finishedAt: string | null;
  rawError: string | null;
  hasRawError: boolean;
  configSnapshot: Record<string, unknown> | null;
  filePaths: Record<string, string>;
};

export type AdminSubmissionsPage = {
  records: AdminSubmissionRecord[];
  totalCount: number;
  limit: number;
  offset: number;
  hasNext: boolean;
};

function stringOrEmpty(value: string | null | undefined): string {
  return value ?? "";
}

function numberOr(value: number | null | undefined, fallback: number): number {
  return typeof value === "number" ? value : fallback;
}

function booleanOr(value: boolean | null | undefined, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

export function toAdminSettings(response: SettingsResponse): AdminSettings {
  return {
    courseName: response.course?.name ?? "Untitled course",
    dataset: {
      trainStart: stringOrEmpty(response.dataset?.train_start),
      trainEnd: stringOrEmpty(response.dataset?.train_end),
      hiddenTestStart: stringOrEmpty(response.dataset?.hidden_test_start),
      hiddenTestEnd: stringOrEmpty(response.dataset?.hidden_test_end)
    },
    scoring: {
      sharpeWeight: numberOr(response.scoring?.sharpe_weight, 0),
      sharpeTarget: numberOr(response.scoring?.sharpe_target, 0),
      annualReturnWeight: numberOr(response.scoring?.annual_return_weight, 0),
      annualReturnTarget: numberOr(response.scoring?.annual_return_target, 0),
      drawdownWeight: numberOr(response.scoring?.drawdown_weight, 0),
      drawdownLimit: numberOr(response.scoring?.drawdown_limit, 0),
      turnoverWeight: numberOr(response.scoring?.turnover_weight, 0),
      turnoverLimit: numberOr(response.scoring?.turnover_limit, 0),
      shortProfitWeight: numberOr(response.scoring?.short_profit_weight, 0),
      shortProfitTarget: numberOr(response.scoring?.short_profit_target, 0),
      minimumSliceTradingDays: numberOr(response.scoring?.minimum_slice_trading_days, 1)
    },
    execution: {
      commissionRate: numberOr(response.execution?.commission_rate, 0.0003),
      slippageRate: numberOr(response.execution?.slippage_rate, 0.0005),
      sellStampDutyRate: numberOr(response.execution?.sell_stamp_duty_rate, 0.0005),
      maxLeverage: numberOr(response.execution?.max_leverage, 1),
      topK: response.execution?.top_k ?? null,
      longOnlyWeighting: response.execution?.long_only_weighting ?? "rank_equal",
      longOnlyTargetCount: numberOr(response.execution?.long_only_target_count, 50),
      maxPositionWeight: numberOr(response.execution?.max_position_weight, 0.05),
      maxParticipationRate: numberOr(response.execution?.max_participation_rate, 0.1),
      minListingDays: numberOr(response.execution?.min_listing_days, 60),
      terminalStalePositionPolicy: response.execution?.terminal_stale_position_policy ?? "reject",
      allowedMarketTypes: response.execution?.allowed_market_types ?? [1, 4, 16, 32, 64],
      submissionsEnabled: booleanOr(response.execution?.submissions_enabled, true),
      hiddenTestEnabled: booleanOr(response.execution?.hidden_test_enabled, true),
      maxConcurrentScoring: numberOr(response.execution?.max_concurrent_scoring, 1),
      submissionTimeoutSeconds: numberOr(response.execution?.submission_timeout_seconds, 120),
      submissionTimeoutEnabled: booleanOr(response.execution?.submission_timeout_enabled, true),
      longOnly: booleanOr(response.execution?.long_only, true)
    },
    dataStart: response.backtest?.data_start ?? null,
    scoringStart: response.backtest?.scoring_start ?? null,
    scoringEnd: response.backtest?.scoring_end ?? null,
    capital: response.backtest?.capital ?? null,
    groupCount: response.backtest?.group_count ?? null,
    industryNeutralization: booleanOr(response.backtest?.industry_neutralization, false),
    longOnlyBenchmark: response.backtest?.long_only_benchmark ?? "hs300",
    longOnlyRiskFreeRate: numberOr(response.backtest?.long_only_risk_free_rate, 0.0175),
    longOnlyMinBetaObservations: numberOr(response.backtest?.long_only_min_beta_observations, 20),
    pricePolicy: response.backtest?.price_policy ?? null,
    executionPrice: response.backtest?.execution_price ?? null,
    markPrice: response.backtest?.mark_price ?? null,
    rawDataRoot: response.data_releases?.raw_data_root ?? null,
    learningOutputRoot: response.data_releases?.learning_output_root ?? null,
    hiddenOutputRoot: response.data_releases?.hidden_output_root ?? null,
    learningEnd: response.data_releases?.learning_end ?? null,
    hiddenStart: response.data_releases?.hidden_start ?? null,
    hiddenEnd: response.data_releases?.hidden_end ?? null,
    maxUploadBytes: response.execution_limits?.max_upload_bytes ?? null,
    scoringTimeoutSeconds: response.execution_limits?.scoring_timeout_seconds ?? null,
    engineVersion: response.execution_limits?.engine_version ?? null,
    runtimeRoot: response.runtime?.runtime_root ?? null,
    frontendDist: response.runtime?.frontend_dist ?? null,
    settingsHistory: (response.settings_history ?? []).map(toAdminSettingsHistoryEntry)
  };
}

export function toAdminDataReleaseBuildState(
  response: DataReleaseBuildStateResponse
): AdminDataReleaseBuildState {
  return {
    sourceAvailable: response.source_available,
    buildableReleaseNames: response.buildable_release_names,
    releases: response.releases.map((release) => ({
      releaseName: release.release_name,
      start: release.start,
      end: release.end,
      outputRoot: release.output_root,
      status: release.status,
      lastBuiltAt: release.last_built_at ?? null
    })),
    job: response.job ? toAdminDataReleaseBuildJob(response.job) : null
  };
}

function toAdminDataReleaseBuildJob(
  job: DataReleaseBuildJobResponse
): AdminDataReleaseBuildJob {
  return {
    jobId: job.job_id,
    status: job.status,
    releaseNames: job.release_names,
    progressPercent: job.progress_percent,
    tracks: job.tracks.map((track) => ({
      releaseName: track.release_name,
      status: track.status,
      phase: track.phase,
      progressPercent: track.progress_percent,
      completedDatasets: track.completed_datasets,
      totalDatasets: track.total_datasets,
      currentDataset: track.current_dataset ?? null,
      errorMessage: track.error_message ?? null
    })),
    createdAt: job.created_at,
    startedAt: job.started_at ?? null,
    finishedAt: job.finished_at ?? null,
    currentReleaseName: job.current_release_name ?? null,
    errorMessage: job.error_message ?? null
  };
}

function toAdminSettingsHistoryEntry(
  entry: NonNullable<SettingsResponse["settings_history"]>[number]
): AdminSettingsHistoryEntry {
  return {
    entryId: entry.entry_id,
    createdAt: entry.created_at,
    entryType: entry.entry_type ?? "settings_change",
    configSha256: entry.config_sha256 ?? null,
    changedFields: entry.changed_fields,
    settings: entry.settings,
    staleMarked: Boolean(entry.stale_marked),
    affectedSubmissionIds: entry.affected_submission_ids ?? [],
    affectedCount: entry.affected_count ?? entry.affected_submission_ids?.length ?? 0,
    revertedAt: entry.reverted_at ?? null
  };
}

function toTeamRecord(team: AdminTeamResponse): TeamRecord {
  return {
    teamId: team.team_id,
    teamName: team.team_name,
    displayName: team.display_name,
    submissionCount: team.submission_count,
    createdAt: team.created_at,
    status: team.status,
    password: team.password ?? null,
    cohortId: team.cohort_id ?? null,
    cohortName: team.cohort_name ?? null,
    historyVisible: booleanOr(team.history_visible, true),
    submissionsEnabled: booleanOr(team.submissions_enabled, true)
  };
}

function toTeamCohortRecord(cohort: AdminTeamCohortResponse): TeamCohortRecord {
  return {
    cohortId: cohort.cohort_id,
    name: cohort.name,
    teamIds: cohort.team_ids,
    historyVisible: cohort.history_visible,
    submissionsEnabled: cohort.submissions_enabled,
    createdAt: cohort.created_at,
    updatedAt: cohort.updated_at
  };
}

export function toTeamCollections(response: TeamsResponse): TeamCollections {
  const activeTeams = response.active_teams.map(toTeamRecord);
  const archivedTeams = response.archived_teams.map(toTeamRecord);
  return {
    activeTeams,
    archivedTeams,
    teams: response.teams.length > 0 ? response.teams.map(toTeamRecord) : [...activeTeams, ...archivedTeams],
    cohorts: (response.cohorts ?? []).map(toTeamCohortRecord)
  };
}

function toAdminSubmissionRecord(submission: AdminSubmissionResponse): AdminSubmissionRecord {
  const rawAwareSubmission = submission as AdminSubmissionResponse & { has_raw_error?: boolean };
  return {
    id: submission.submission_id,
    submissionNumber: submission.submission_number,
    submissionLabel: submission.submission_label,
    teamId: submission.team_id,
    teamName: submission.team_name,
    type: submission.type,
    dataTrack: normalizeDataTrack(submission.data_track),
    status: submission.status,
    stale: submission.stale,
    selectable: submission.selectable,
    score: submission.score ?? null,
    filename: submission.filename,
    submittedAt: submission.submitted_at,
    finishedAt: submission.finished_at ?? null,
    rawError: submission.raw_error ?? null,
    hasRawError: Boolean(rawAwareSubmission.has_raw_error || submission.raw_error),
    configSnapshot: submission.config_snapshot ?? null,
    filePaths: submission.file_paths
  };
}

export function toAdminSubmissionRecords(response: AdminSubmissionsResponse): AdminSubmissionRecord[] {
  return response.submissions.map(toAdminSubmissionRecord);
}

export function toAdminSubmissionPage(response: AdminSubmissionsResponse): AdminSubmissionsPage {
  const pageAwareResponse = response as AdminSubmissionsResponse & {
    total_count?: number;
    limit?: number;
    offset?: number;
    has_next?: boolean;
  };
  const records = toAdminSubmissionRecords(response);
  return {
    records,
    totalCount: pageAwareResponse.total_count ?? records.length,
    limit: pageAwareResponse.limit ?? records.length,
    offset: pageAwareResponse.offset ?? 0,
    hasNext: pageAwareResponse.has_next ?? false
  };
}

export function useAdminSession() {
  return useQuery({
    queryKey: ["admin", "session"],
    queryFn: fetchAdminSession
  });
}

export function useAdminLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: loginAdmin,
    onSuccess: (session) => {
      queryClient.setQueryData(["admin", "session"], session);
      queryClient.invalidateQueries({ queryKey: ["admin"] });
    }
  });
}

export function useAdminLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: logoutAdmin,
    onSuccess: (session) => {
      queryClient.setQueryData(["admin", "session"], session);
      queryClient.removeQueries({ queryKey: ["admin", "settings"] });
      queryClient.removeQueries({ queryKey: ["admin", "data-releases"] });
      queryClient.removeQueries({ queryKey: ["admin", "teams"] });
      queryClient.removeQueries({ queryKey: ["admin", "submissions"] });
    }
  });
}

export function useAdminSettings(enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["admin", "settings"],
    queryFn: fetchAdminSettings,
    select: toAdminSettings
  });
}

export function useAdminDataReleases(enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["admin", "data-releases"],
    queryFn: fetchAdminDataReleases,
    select: toAdminDataReleaseBuildState,
    refetchInterval: (query) => {
      const status = query.state.data?.job?.status;
      return status === "queued" || status === "running" ? 1000 : false;
    }
  });
}

export function useStartAdminDataReleaseBuild() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: StartDataReleaseBuildPayload) =>
      startAdminDataReleaseBuild(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "data-releases"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useUpdateAdminSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminSettingsUpdatePayload) => updateAdminSettings(payload),
    onSuccess: (response) => {
      queryClient.setQueryData(["admin", "settings"], response);
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useRevertAdminSettingsHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => revertAdminSettingsHistory(entryId),
    onSuccess: (response) => {
      queryClient.setQueryData(["admin", "settings"], response);
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useMarkAdminStaleSubmissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markAdminStaleSubmissions,
    onSuccess: (response) => {
      queryClient.setQueryData(["admin", "settings"], response);
      queryClient.invalidateQueries({ queryKey: ["admin", "submissions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useRevertAdminStaleMark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (entryId: string) => revertAdminStaleMark(entryId),
    onSuccess: (response) => {
      queryClient.setQueryData(["admin", "settings"], response);
      queryClient.invalidateQueries({ queryKey: ["admin", "submissions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useAdminTeams(enabled = true) {
  return useQuery({
    enabled,
    queryKey: ["admin", "teams"],
    queryFn: fetchAdminTeams,
    select: toTeamCollections
  });
}

export function useCreateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createTeam,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "teams"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useUpdateTeam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateTeamPayload) => updateTeam(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "teams"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

export function useTeamBulkAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TeamBulkActionPayload) => runTeamBulkAction(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "teams"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  });
}

function invalidateTeamCohortQueries(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["admin", "teams"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "submissions"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "team-cohorts"] });
  queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
  queryClient.invalidateQueries({ queryKey: ["submission-history"] });
  queryClient.invalidateQueries({ queryKey: ["compare"] });
}

function invalidateSubmissionResultQueries(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ["admin", "submissions"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "team-cohorts"] });
  queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
  queryClient.invalidateQueries({ queryKey: ["submission-history"] });
  queryClient.invalidateQueries({ queryKey: ["submission-detail"] });
  queryClient.invalidateQueries({ queryKey: ["compare"] });
}

export function useCreateTeamCohort() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTeamCohortPayload) => createTeamCohort(payload),
    onSuccess: () => invalidateTeamCohortQueries(queryClient)
  });
}

export function useUpdateTeamCohort() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UpdateTeamCohortPayload) => updateTeamCohort(payload),
    onSuccess: () => invalidateTeamCohortQueries(queryClient)
  });
}

export function useDeleteTeamCohort() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cohortId: string) => deleteTeamCohort(cohortId),
    onSuccess: () => invalidateTeamCohortQueries(queryClient)
  });
}

export function useAdminSubmissions(
  enabled = true,
  params: FetchAdminSubmissionsParams
) {
  return useQuery({
    enabled,
    queryKey: ["admin", "submissions", params],
    queryFn: () => fetchAdminSubmissions(params),
    select: toAdminSubmissionPage,
    placeholderData: keepPreviousData
  });
}

export function useAdminFailures(enabled = true, days = 7) {
  return useQuery({
    enabled,
    queryKey: ["admin", "failures", days],
    queryFn: () => fetchAdminFailures({ days }),
    staleTime: 30_000
  });
}

export function useAdminCohortSubmissions(
  enabled = true,
  cohortId: string,
  params: FetchAdminCohortSubmissionsParams
) {
  return useQuery({
    enabled: enabled && cohortId.length > 0,
    queryKey: ["admin", "team-cohorts", cohortId, "submissions", params],
    queryFn: () => fetchAdminCohortSubmissions(cohortId, params),
    select: toAdminSubmissionPage,
    placeholderData: keepPreviousData
  });
}

export function useAdminCohortSubmissionSource(cohortId: string) {
  return useMutation<string, Error, string>({
    mutationFn: (submissionId: string) => fetchAdminCohortSubmissionSource(cohortId, submissionId)
  });
}

export function useAdminCohortSubmissionRawError(cohortId: string) {
  return useMutation<string, Error, string>({
    mutationFn: (submissionId: string) => fetchAdminCohortSubmissionRawError(cohortId, submissionId)
  });
}

export function useDeleteAdminSubmissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DeleteSubmissionsPayload) => deleteAdminSubmissions(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "submissions"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "team-cohorts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useRerunAdminSubmissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RerunAdminSubmissionsPayload) => rerunAdminSubmissions(payload),
    onSuccess: () => invalidateSubmissionResultQueries(queryClient)
  });
}

export function useRerunAdminCohortSubmissions(cohortId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RerunAdminSubmissionsPayload) =>
      rerunAdminCohortSubmissions(cohortId, payload),
    onSuccess: () => invalidateSubmissionResultQueries(queryClient)
  });
}

export function useBackfillShortProfitSubmissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: backfillShortProfitSubmissions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "submissions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["leaderboard"] });
    }
  });
}

export function useAdminSubmissionSource() {
  return useMutation({
    mutationFn: (submissionId: string) => fetchAdminSubmissionSource(submissionId)
  });
}

export function useAdminSubmissionRawError() {
  return useMutation({
    mutationFn: (submissionId: string) => fetchAdminSubmissionRawError(submissionId)
  });
}
