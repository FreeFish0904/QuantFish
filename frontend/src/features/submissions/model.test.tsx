import "./test-setup";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";

import { deriveSubmitState, useSubmitStrategy, useSubmissionStatus } from "./model";

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const server = setupServer(
  http.post("/api/submissions", () =>
    HttpResponse.json({
      submission_id: "sub-123",
      team_id: "alpha-desk",
      team_name: "Alpha Desk",
      status: "queued",
      data_track: "hidden_test",
      submitted_at: "2026-06-18T12:00:00Z",
      scored_at: null,
      metrics: null,
      error_message: null
    })
  )
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("deriveSubmitState", () => {
  it("returns idle when nothing is happening", () => {
    expect(deriveSubmitState({ isSubmitting: false })).toBe("idle");
  });

  it("returns queued while submitting", () => {
    expect(deriveSubmitState({ isSubmitting: true })).toBe("queued");
  });

  it("returns queued while waiting for the status query", () => {
    expect(
      deriveSubmitState({ isSubmitting: false, hasSubmittedId: true, isStatusLoading: true })
    ).toBe("queued");
  });

  it("maps backend statuses to frontend states", () => {
    expect(deriveSubmitState({ isSubmitting: false, status: "queued" })).toBe("queued");
    expect(deriveSubmitState({ isSubmitting: false, status: "running" })).toBe("running");
    expect(deriveSubmitState({ isSubmitting: false, status: "completed" })).toBe("success");
    expect(deriveSubmitState({ isSubmitting: false, status: "failed" })).toBe("error");
  });

  it("returns error on submit or status errors", () => {
    expect(deriveSubmitState({ isSubmitting: false, hasSubmitError: true })).toBe("error");
    expect(deriveSubmitState({ isSubmitting: false, hasStatusError: true })).toBe("error");
  });
});

describe("useSubmitStrategy", () => {
  it("submits a strategy as multipart FormData and returns a submission summary", async () => {
    let submittedTrack: FormDataEntryValue | null = null;
    server.use(
      http.post("/api/submissions", async ({ request }) => {
        const formData = await request.formData();
        submittedTrack = formData.get("data_track");
        return HttpResponse.json({
          submission_id: "sub-123",
          submission_number: 1,
          submission_label: "#1",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "queued",
          data_track: "learning",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        });
      })
    );
    const { result } = renderHook(() => useSubmitStrategy(), {
      wrapper: createWrapper()
    });

    result.current.mutate({
      teamName: "Alpha Desk",
      password: "secret",
      file: new File(["print('hello')"], "alpha.py", { type: "text/x-python" }),
      dataTrack: "learning"
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.submission_id).toBe("sub-123");
    expect(result.current.data?.team_id).toBe("alpha-desk");
    expect(result.current.data?.data_track).toBe("learning");
    expect(submittedTrack).toBe("learning");
  });
});

describe("useSubmissionStatus", () => {
  it("polls while the submission is running and stops when completed", async () => {
    let calls = 0;
    server.use(
      http.get("/api/submissions/:id", () => {
        calls++;
        return HttpResponse.json({
          submission_id: "sub-123",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: calls < 3 ? "running" : "completed",
          data_track: "hidden_test",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          error_message: null
        });
      })
    );

    const { result } = renderHook(() => useSubmissionStatus("sub-123"), {
      wrapper: createWrapper()
    });

    await waitFor(() => expect(result.current.data?.status).toBe("completed"), {
      timeout: 5000
    });
    expect(calls).toBeGreaterThanOrEqual(3);
  });

  it("does not poll for terminal statuses", async () => {
    let calls = 0;
    server.use(
      http.get("/api/submissions/:id", () => {
        calls++;
        return HttpResponse.json({
          submission_id: "sub-123",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "hidden_test",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          error_message: null
        });
      })
    );

    const { result } = renderHook(() => useSubmissionStatus("sub-123"), {
      wrapper: createWrapper()
    });

    await waitFor(() => expect(result.current.data?.status).toBe("completed"));
    const callsAfterSuccess = calls;
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(calls).toBe(callsAfterSuccess);
  });
});
