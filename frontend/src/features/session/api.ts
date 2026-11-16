import { apiClient } from "../../shared/api/client";
import { extractErrorMessage, StudentApiError } from "../../shared/api/errors";
import type { paths } from "../../shared/api/generated/api-types";

type ParticipantSessionResponse =
  paths["/api/session"]["get"]["responses"][200]["content"]["application/json"];
type ParticipantLoginBody =
  paths["/api/session/login"]["post"]["requestBody"]["content"]["application/json"];

export type ParticipantSession = ParticipantSessionResponse;
export type ParticipantLoginPayload = ParticipantLoginBody;

async function throwApiError(response: unknown): Promise<never> {
  const res = response as Response;
  throw new StudentApiError(res.status, await extractErrorMessage(res));
}

export async function fetchParticipantSession(): Promise<ParticipantSessionResponse> {
  const { data, error, response } = await apiClient.GET("/api/session");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function loginParticipant(
  payload: ParticipantLoginPayload
): Promise<ParticipantSessionResponse> {
  const { data, error, response } = await apiClient.POST("/api/session/login", {
    body: payload
  });
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}

export async function logoutParticipant(): Promise<ParticipantSessionResponse> {
  const { data, error, response } = await apiClient.POST("/api/session/logout");
  if (error || !data) {
    return throwApiError(response);
  }
  return data;
}
