import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { paths } from "../../shared/api/generated/api-types";

export type BackendSubmissionDetail =
  paths["/api/submissions/{submission_id}"]["get"]["responses"][200]["content"]["application/json"];

export async function fetchSubmissionDetail(submissionId: string): Promise<BackendSubmissionDetail> {
  const { data, error, response } = await apiClient.GET("/api/submissions/{submission_id}", {
    params: { path: { submission_id: submissionId } }
  });

  if (error || !response.ok || data === undefined) {
    const message = await extractErrorMessage(response);
    throw new StudentApiError(response.status, message);
  }

  return data;
}
