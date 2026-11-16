import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { components } from "../../shared/api/generated/api-types";
import type { DataTrack } from "../../shared/submissions/dataTrack";

export type LeaderboardResponse = components["schemas"]["LeaderboardResponse"];
export type LeaderboardSummary = components["schemas"]["LeaderboardSummary"];
export type LeaderboardMetric = "sharpe" | "max_drawdown" | "calmar";

export type FetchLeaderboardParams = {
  limit: number;
  offset: number;
  search: string;
  sortBy: string;
  sortDir: "asc" | "desc";
  dataTrack: DataTrack;
  metric: LeaderboardMetric;
};

export async function fetchLeaderboard(
  params: FetchLeaderboardParams
): Promise<LeaderboardResponse> {
  const { data, error, response } = await apiClient.GET("/api/leaderboard", {
    params: {
      query: {
        limit: params.limit,
        offset: params.offset,
        search: params.search || undefined,
        sort_by: params.sortBy,
        sort_dir: params.sortDir,
        data_track: params.dataTrack,
        metric: params.metric
      }
    }
  });

  if (error || !data) {
    const response_ = response as Response;
    throw new StudentApiError(response_.status, await extractErrorMessage(response_));
  }

  return data;
}
