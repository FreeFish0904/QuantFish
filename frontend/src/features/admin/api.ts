import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { paths } from "../../shared/api/generated/api-types";

type AdminSessionResponse =
  paths["/api/admin/session"]["get"]["responses"][200]["content"]["application/json"];
type AdminLoginBody =
  paths["/api/admin/login"]["post"]["requestBody"]["content"]["application/json"];
type SettingsResponse =
  paths["/api/admin/settings"]["get"]["responses"][200]["content"]["application/json"];
type SettingsUpdateBody =
  paths["/api/admin/settings"]["patch"]["requestBody"]["content"]["application/json"];
type DataReleaseBuildStateResponse =
  paths["/api/admin/data-releases"]["get"]["responses"][200]["content"]["application/json"];
type DataReleaseBuildBody =
  paths["/api/admin/data-releases/build"]["post"]["requestBody"]["content"]["application/json"];
type DataReleaseBuildJobResponse =
  paths["/api/admin/data-releases/build"]["post"]["responses"][202]["content"]["application/json"];
type SettingsHistoryRevertResponse =
  paths["/api/admin/settings-history/{entry_id}/revert"]["post"]["responses"][200]["content"]["application/json"];
type StaleMarkResponse =
  paths["/api/admin/stale-marks"]["post"]["responses"][200]["content"]["application/json"];
type StaleMarkRevertResponse =
  paths["/api/admin/stale-marks/{entry_id}/revert"]["post"]["responses"][200]["content"]["application/json"];
type TeamsResponse =
  paths["/api/admin/teams"]["get"]["responses"][200]["content"]["application/json"];
type TeamCreateBody =
  paths["/api/admin/teams"]["post"]["requestBody"]["content"]["application/json"];
type TeamCreateResponse =
  paths["/api/admin/teams"]["post"]["responses"][200]["content"]["application/json"];
type TeamUpdateBody =
  paths["/api/admin/teams/{team_id}"]["patch"]["requestBody"]["content"]["application/json"];
type TeamUpdateResponse =
  paths["/api/admin/teams/{team_id}"]["patch"]["responses"][200]["content"]["application/json"];
type TeamBulkActionBody =
  paths["/api/admin/teams/bulk-action"]["post"]["requestBody"]["content"]["application/json"];
type TeamBulkActionResponse =
  paths["/api/admin/teams/bulk-action"]["post"]["responses"][200]["content"]["application/json"];
type TeamCohortCreateBody =
  paths["/api/admin/team-cohorts"]["post"]["requestBody"]["content"]["application/json"];
type TeamCohortCreateResponse =
  paths["/api/admin/team-cohorts"]["post"]["responses"][200]["content"]["application/json"];
type TeamCohortUpdateBody =
  paths["/api/admin/team-cohorts/{cohort_id}"]["patch"]["requestBody"]["content"]["application/json"];
type TeamCohortUpdateResponse =
  paths["/api/admin/team-cohorts/{cohort_id}"]["patch"]["responses"][200]["content"]["application/json"];
type TeamCohortDeleteResponse =
  paths["/api/admin/team-cohorts/{cohort_id}"]["delete"]["responses"][200]["content"]["application/json"];
type AdminSubmissionsResponse =
  paths["/api/admin/submissions"]["get"]["responses"][200]["content"]["application/json"];
type AdminCohortSubmissionsResponse =
  paths["/api/admin/team-cohorts/{cohort_id}/submissions"]["get"]["responses"][200]["content"]["application/json"];
type DeleteSubmissionsBody =
  paths["/api/admin/submissions/delete"]["post"]["requestBody"]["content"]["application/json"];
type DeleteSubmissionsResponse =
  paths["/api/admin/submissions/delete"]["post"]["responses"][200]["content"]["application/json"];
type RerunSubmissionsBody =
  paths["/api/admin/submissions/rerun"]["post"]["requestBody"]["content"]["application/json"];
type RerunSubmissionsResponse =
  paths["/api/admin/submissions/rerun"]["post"]["responses"][200]["content"]["application/json"];
type RerunCohortSubmissionsResponse =
  paths["/api/admin/team-cohorts/{cohort_id}/submissions/rerun"]["post"]["responses"][200]["content"]["application/json"];
type BackfillShortProfitResponse =
  paths["/api/admin/submissions/backfill-short-profit"]["post"]["responses"][200]["content"]["application/json"];

export type AdminLoginPayload = AdminLoginBody;
export type AdminSettingsUpdatePayload = SettingsUpdateBody;
export type StartDataReleaseBuildPayload = DataReleaseBuildBody;
export type CreateTeamPayload = TeamCreateBody;
export type UpdateTeamPayload = {
  teamId: string;
  team: TeamUpdateBody;
};
export type TeamBulkActionPayload = TeamBulkActionBody;
export type CreateTeamCohortPayload = TeamCohortCreateBody;
export type UpdateTeamCohortPayload = {
  cohortId: string;
  cohort: TeamCohortUpdateBody;
};
export type DeleteSubmissionsPayload = DeleteSubmissionsBody;
export type RerunAdminSubmissionsPayload = RerunSubmissionsBody;

export type FetchAdminSubmissionsParams = {
  limit: number;
  offset: number;
  search: string;
  status: string;
  sortBy: string;
  sortDir: "asc" | "desc";
};

export type FetchAdminCohortSubmissionsParams = FetchAdminSubmissionsParams;

function resolveHttpResponse(response: unknown): Response {
  return response as Response;
}

async function throwApiError(response: unknown): Promise<never> {
  const res = resolveHttpResponse(response);
  throw new StudentApiError(res.status, await extractErrorMessage(res));
}

export async function loginAdmin(payload: AdminLoginPayload): Promise<AdminSessionResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/login", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminSession(): Promise<AdminSessionResponse> {
  const { data, error, response } = await apiClient.GET("/api/admin/session");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function logoutAdmin(): Promise<AdminSessionResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/logout");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminSettings(): Promise<SettingsResponse> {
  const { data, error, response } = await apiClient.GET("/api/admin/settings");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function updateAdminSettings(payload: AdminSettingsUpdatePayload): Promise<SettingsResponse> {
  const { data, error, response } = await apiClient.PATCH("/api/admin/settings", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminDataReleases(): Promise<DataReleaseBuildStateResponse> {
  const { data, error, response } = await apiClient.GET("/api/admin/data-releases");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function startAdminDataReleaseBuild(
  payload: StartDataReleaseBuildPayload
): Promise<DataReleaseBuildJobResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/data-releases/build", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function revertAdminSettingsHistory(entryId: string): Promise<SettingsHistoryRevertResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/settings-history/{entry_id}/revert", {
    params: { path: { entry_id: entryId } }
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function markAdminStaleSubmissions(): Promise<StaleMarkResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/stale-marks");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function revertAdminStaleMark(entryId: string): Promise<StaleMarkRevertResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/stale-marks/{entry_id}/revert", {
    params: { path: { entry_id: entryId } }
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminTeams(): Promise<TeamsResponse> {
  const { data, error, response } = await apiClient.GET("/api/admin/teams");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function createTeam(payload: CreateTeamPayload): Promise<TeamCreateResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/teams", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function updateTeam(payload: UpdateTeamPayload): Promise<TeamUpdateResponse> {
  const { data, error, response } = await apiClient.PATCH("/api/admin/teams/{team_id}", {
    params: { path: { team_id: payload.teamId } },
    body: payload.team
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function runTeamBulkAction(payload: TeamBulkActionPayload): Promise<TeamBulkActionResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/teams/bulk-action", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function createTeamCohort(payload: CreateTeamCohortPayload): Promise<TeamCohortCreateResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/team-cohorts", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function updateTeamCohort(payload: UpdateTeamCohortPayload): Promise<TeamCohortUpdateResponse> {
  const { data, error, response } = await apiClient.PATCH("/api/admin/team-cohorts/{cohort_id}", {
    params: { path: { cohort_id: payload.cohortId } },
    body: payload.cohort
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function deleteTeamCohort(cohortId: string): Promise<TeamCohortDeleteResponse> {
  const { data, error, response } = await apiClient.DELETE("/api/admin/team-cohorts/{cohort_id}", {
    params: { path: { cohort_id: cohortId } }
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminSubmissions(
  params: FetchAdminSubmissionsParams
): Promise<AdminSubmissionsResponse> {
  const { data, error, response } = await apiClient.GET("/api/admin/submissions", {
    params: {
      query: {
        limit: params.limit,
        offset: params.offset,
        search: params.search || undefined,
        status: params.status === "all" ? undefined : params.status,
        sort_by: params.sortBy,
        sort_dir: params.sortDir
      }
    }
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminCohortSubmissions(
  cohortId: string,
  params: FetchAdminCohortSubmissionsParams
): Promise<AdminCohortSubmissionsResponse> {
  const { data, error, response } = await apiClient.GET("/api/admin/team-cohorts/{cohort_id}/submissions", {
    params: {
      path: { cohort_id: cohortId },
      query: {
        limit: params.limit,
        offset: params.offset,
        search: params.search || undefined,
        status: params.status === "all" ? undefined : params.status,
        sort_by: params.sortBy,
        sort_dir: params.sortDir
      }
    }
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function fetchAdminSubmissionSource(submissionId: string): Promise<string> {
  const response = await fetch(
    `${window.location.origin}/api/admin/submissions/${encodeURIComponent(submissionId)}/source`
  );
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return response.text();
}

export async function fetchAdminCohortSubmissionSource(cohortId: string, submissionId: string): Promise<string> {
  const response = await fetch(
    `${window.location.origin}/api/admin/team-cohorts/${encodeURIComponent(cohortId)}/submissions/${encodeURIComponent(submissionId)}/source`
  );
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return response.text();
}

export async function fetchAdminSubmissionRawError(submissionId: string): Promise<string> {
  const response = await fetch(
    `${window.location.origin}/api/admin/submissions/${encodeURIComponent(submissionId)}/raw-error`
  );
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return response.text();
}

export async function fetchAdminCohortSubmissionRawError(cohortId: string, submissionId: string): Promise<string> {
  const response = await fetch(
    `${window.location.origin}/api/admin/team-cohorts/${encodeURIComponent(cohortId)}/submissions/${encodeURIComponent(submissionId)}/raw-error`
  );
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return response.text();
}

export async function deleteAdminSubmissions(
  payload: DeleteSubmissionsPayload
): Promise<DeleteSubmissionsResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/submissions/delete", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function rerunAdminSubmissions(
  payload: RerunAdminSubmissionsPayload
): Promise<RerunSubmissionsResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/submissions/rerun", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function rerunAdminCohortSubmissions(
  cohortId: string,
  payload: RerunAdminSubmissionsPayload
): Promise<RerunCohortSubmissionsResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/team-cohorts/{cohort_id}/submissions/rerun", {
    params: { path: { cohort_id: cohortId } },
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function backfillShortProfitSubmissions(): Promise<BackfillShortProfitResponse> {
  const { data, error, response } = await apiClient.POST("/api/admin/submissions/backfill-short-profit");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}
