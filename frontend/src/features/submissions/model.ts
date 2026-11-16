import { useMutation, useQuery } from "@tanstack/react-query";

import {
  fetchEnvironmentOptions,
  fetchSubmissionOptions,
  fetchSubmissionStatus,
  submitStrategy,
  type SubmitStrategyInput
} from "./api";

export type SubmitState = "idle" | "queued" | "running" | "success" | "error";

export type SubmitInput = SubmitStrategyInput;

const ACTIVE_POLL_STATUSES = new Set(["queued", "running"]);

export function useSubmitStrategy() {
  return useMutation({
    mutationFn: submitStrategy
  });
}

export function useSubmissionStatus(submissionId: string | undefined) {
  return useQuery({
    queryKey: ["submission", submissionId],
    queryFn: () => {
      if (!submissionId) {
        throw new Error("submissionId is required");
      }
      return fetchSubmissionStatus(submissionId);
    },
    enabled: Boolean(submissionId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && ACTIVE_POLL_STATUSES.has(status)) {
        return 2000;
      }
      return false;
    }
  });
}

export function useSubmissionOptions() {
  return useQuery({
    queryKey: ["submissions", "options"],
    queryFn: fetchSubmissionOptions,
    staleTime: 30_000
  });
}

export function useEnvironmentOptions() {
  return useQuery({
    queryKey: ["downloads", "environment-options"],
    queryFn: fetchEnvironmentOptions,
    staleTime: 30_000
  });
}

export function deriveSubmitState(args: {
  isSubmitting: boolean;
  status?: string;
  hasSubmitError?: boolean;
  hasStatusError?: boolean;
  isStatusLoading?: boolean;
  hasSubmittedId?: boolean;
}): SubmitState {
  const { isSubmitting, status, hasSubmitError, hasStatusError, isStatusLoading, hasSubmittedId } = args;

  if (hasSubmitError || hasStatusError) {
    return "error";
  }
  if (isSubmitting) {
    return "queued";
  }
  if (hasSubmittedId && isStatusLoading) {
    return "queued";
  }
  if (!status) {
    return "idle";
  }
  if (status === "running") {
    return "running";
  }
  if (status === "completed") {
    return "success";
  }
  if (status === "failed") {
    return "error";
  }
  return "queued";
}
