import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { paths } from "../../shared/api/generated/api-types";

type DashboardResponse = paths["/api/dashboard"]["get"]["responses"][200]["content"]["application/json"];

export async function fetchDashboard(): Promise<DashboardResponse> {
  const { data, error, response } = await apiClient.GET("/api/dashboard");
  if (error || !data) {
    const response_ = response as Response;
    throw new StudentApiError(response_.status, await extractErrorMessage(response_));
  }
  return data;
}
