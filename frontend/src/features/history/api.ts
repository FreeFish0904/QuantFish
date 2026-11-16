import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { components } from "../../shared/api/generated/api-types";

export type SubmissionHistoryResponse = components["schemas"]["SubmissionListResponse"];
export type SubmissionHistorySummary = components["schemas"]["SubmissionSummary"];

export type FetchSubmissionHistoryParams = {
  limit: number;
  offset: number;
  search: string;
  status: string;
  dataTrack: string;
  teamId?: string | null;
  sortBy: string;
  sortDir: "asc" | "desc";
};

export async function fetchSubmissionHistory(
  params: FetchSubmissionHistoryParams
): Promise<SubmissionHistoryResponse> {
  const { data, error, response } = await apiClient.GET("/api/submissions", {
    params: {
      query: {
        limit: params.limit,
        offset: params.offset,
        search: params.search || undefined,
        status: params.status === "all" ? undefined : params.status,
        data_track: params.dataTrack === "all" ? undefined : params.dataTrack,
        team_id: params.teamId || undefined,
        sort_by: params.sortBy,
        sort_dir: params.sortDir
      }
    }
  });

  if (error || !data) {
    const response_ = response as Response;
    throw new StudentApiError(response_.status, await extractErrorMessage(response_));
  }

  return data;
}

export async function fetchSubmissionRawError(submissionId: string): Promise<string> {
  const response = await fetch(
    `${window.location.origin}/api/submissions/${encodeURIComponent(submissionId)}/raw-error`
  );
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return response.text();
}

export async function fetchSubmissionSource(submissionId: string): Promise<string> {
  const response = await fetch(
    `${window.location.origin}/api/submissions/${encodeURIComponent(submissionId)}/source`
  );
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return response.text();
}
