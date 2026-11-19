import { apiClient } from "../../shared/api/client";
import { StudentApiError, extractErrorMessage } from "../../shared/api/errors";
import type { paths } from "../../shared/api/generated/api-types";
import type { DataTrack } from "../../shared/submissions/dataTrack";

type SubmissionOptionsResponse =
  paths["/api/submissions/options"]["get"]["responses"][200]["content"]["application/json"];
type SubmitStrategyResponse =
  paths["/api/submissions"]["post"]["responses"][200]["content"]["application/json"];
export type ValidateStrategyResponse =
  paths["/api/submissions/validate"]["post"]["responses"][200]["content"]["application/json"];

export type SubmitStrategyInput = {
  teamName?: string;
  password?: string;
  file: File;
  dataTrack: DataTrack;
};

export type EnvironmentPackageStatus = "available" | "stale" | "missing";

export type EnvironmentPackageOption = {
  platform: string;
  label: string;
  architecture: string;
  status: EnvironmentPackageStatus;
  size_bytes: number | null;
  updated_at: string | null;
  download_url: string | null;
};

export type EnvironmentOptionsResponse = {
  platforms: EnvironmentPackageOption[];
};

export type SubmissionOptions = SubmissionOptionsResponse;

export async function submitStrategy(input: SubmitStrategyInput): Promise<SubmitStrategyResponse> {
  const formData = new FormData();
  if (input.teamName) {
    formData.append("team_name", input.teamName);
  }
  if (input.password) {
    formData.append("password", input.password);
  }
  formData.append("file", input.file);
  formData.append("data_track", input.dataTrack);

  const response = await fetch(`${window.location.origin}/api/submissions`, {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }

  return (await response.json()) as SubmitStrategyResponse;
}

export async function validateStrategy(
  input: SubmitStrategyInput
): Promise<ValidateStrategyResponse> {
  const formData = new FormData();
  if (input.teamName) {
    formData.append("team_name", input.teamName);
  }
  if (input.password) {
    formData.append("password", input.password);
  }
  formData.append("file", input.file);
  formData.append("data_track", input.dataTrack);

  const response = await fetch(`${window.location.origin}/api/submissions/validate`, {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }

  return (await response.json()) as ValidateStrategyResponse;
}

export async function fetchSubmissionStatus(submissionId: string) {
  const { data, error, response } = await apiClient.GET(
    "/api/submissions/{submission_id}",
    {
      params: { path: { submission_id: submissionId } }
    }
  );

  if (error || !data) {
    const message = extractMessageFromError(error) ?? (await extractErrorMessage(response));
    throw new StudentApiError((response as Response).status, message);
  }

  return data;
}

export async function fetchSubmissionOptions(): Promise<SubmissionOptions> {
  const { data, error, response } = await apiClient.GET("/api/submissions/options");

  if (error || !data) {
    const message = extractMessageFromError(error) ?? (await extractErrorMessage(response));
    throw new StudentApiError((response as Response).status, message);
  }

  return data;
}

export async function fetchEnvironmentOptions(): Promise<EnvironmentOptionsResponse> {
  const response = await fetch("/api/downloads/environment-options");
  if (!response.ok) {
    throw new StudentApiError(response.status, await extractErrorMessage(response));
  }
  return (await response.json()) as EnvironmentOptionsResponse;
}

function extractMessageFromError(error: unknown): string | null {
  if (typeof error !== "object" || error === null) {
    return null;
  }
  const detail = (error as Record<string, unknown>).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => (typeof item === "object" && item !== null ? (item as { msg?: string }).msg : String(item))).filter(Boolean).join("; ");
  }
  const message = (error as Record<string, unknown>).message;
  if (typeof message === "string") {
    return message;
  }
  return null;
}
