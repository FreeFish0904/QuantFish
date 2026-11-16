import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { components } from "../../shared/api/generated/api-types";

export type CompareResponse = components["schemas"]["CompareResponse"];

export type FetchCompareOptions = {
  includeGraphData?: boolean;
};

export async function fetchCompareSubmissions(
  submissionIds: string[],
  options: FetchCompareOptions = {}
): Promise<CompareResponse> {
  const { data, error, response } = await apiClient.GET("/api/compare", {
    params: {
      query: {
        include_graph_data: options.includeGraphData ?? false,
        submission_id: submissionIds
      }
    }
  });

  if (error || !data) {
    const message = response
      ? await extractErrorMessage(response)
      : "Could not load comparison";
    throw new StudentApiError(response?.status ?? 500, message);
  }

  return data;
}
