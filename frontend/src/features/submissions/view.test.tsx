import "./test-setup";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../../shared/i18n";
import { SubmissionView } from "./view";

function createWrapper(defaultLanguage: "en" | "zh" = "en") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <I18nProvider defaultLanguage={defaultLanguage}>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </I18nProvider>
    );
  };
}

describe("SubmissionView", () => {
  const server = setupServer(
    http.get("/api/session", () =>
      HttpResponse.json({
        authenticated: false,
        team_id: null,
        team_name: null
      })
    ),
    http.get("/api/submissions/options", () =>
      HttpResponse.json({
        available_data_tracks: [
          "hidden_test",
          "learning",
          "learning_1",
          "learning_2",
          "learning_3"
        ]
      })
    ),
    http.get("/api/downloads/environment-options", () =>
      HttpResponse.json({
        platforms: [
          {
            platform: "macos-arm64",
            label: "macOS Apple Silicon",
            architecture: "arm64",
            status: "available",
            size_bytes: 1024,
            updated_at: "2026-06-20T00:00:00+00:00",
            download_url: "/api/downloads/environment/macos-arm64.zip"
          },
          {
            platform: "windows-x86_64",
            label: "Windows 64-bit",
            architecture: "x86_64",
            status: "missing",
            size_bytes: null,
            updated_at: null,
            download_url: null
          }
        ]
      })
    )
  );

  beforeAll(() => server.listen());
  afterEach(() => {
    server.resetHandlers();
    vi.useRealTimers();
  });
  afterAll(() => server.close());

  it("collects team credentials and a strategy file before submit", async () => {
    let handlerCalled = false;
    let submittedTrack: FormDataEntryValue | null = null;
    server.use(
      http.get("/api/submissions/options", () =>
        HttpResponse.json({
          available_data_tracks: [
            "hidden_test",
            "learning",
            "learning_1",
            "learning_2",
            "learning_3"
          ]
        })
      ),
      http.post("/api/submissions", async ({ request }) => {
        handlerCalled = true;
        const formData = await request.formData();
        submittedTrack = formData.get("data_track");
        return HttpResponse.json({
          submission_id: "sub-123",
          submission_number: 1,
          submission_label: "#1",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "queued",
          data_track: "hidden_test",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        });
      }),
      http.get("/api/submissions/:id", () =>
        HttpResponse.json({
          submission_id: "sub-123",
          submission_number: 1,
          submission_label: "#1",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "hidden_test",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        })
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    const submitButton = screen.getByRole("button", { name: /submit strategy/i });
    expect(submitButton).toBeDisabled();
    expect(screen.getByText(/enter your team name and password to continue/i)).toBeInTheDocument();
    expect(screen.getByText(/choose python file/i)).toBeInTheDocument();
    expect(screen.getByText(/no file selected/i)).toBeInTheDocument();
    expect(await screen.findByLabelText(/hidden test/i)).not.toBeChecked();
    expect(screen.getByLabelText(/learning data/i)).toBeChecked();

    expect(screen.getByRole("link", { name: /download learning data/i })).toHaveAttribute(
      "href",
      "/api/downloads/learning-data.zip"
    );
    const environmentButton = screen.getByRole("button", {
      name: /download environment package/i
    });
    await userEvent.click(environmentButton);
    expect(screen.getByRole("menuitem", { name: /macOS Apple Silicon/i })).toHaveAttribute(
      "href",
      "/api/downloads/environment/macos-arm64.zip"
    );
    expect(screen.getByRole("menuitem", { name: /Windows 64-bit/i })).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.click(screen.getByRole("button", { name: /show password/i }));
    expect(screen.getByLabelText(/team password/i)).toHaveAttribute("type", "text");
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );

    expect(screen.getByText("alpha.py")).toBeInTheDocument();
    expect(screen.getByText(/ready to submit on learning data/i)).toBeInTheDocument();
    expect(submitButton).toBeEnabled();
    await userEvent.click(submitButton);

    await waitFor(() => expect(handlerCalled).toBe(true));
    expect(submittedTrack).toBe("learning");
  });

  it("submits the selected historical learning window unchanged", async () => {
    let submittedTrack: FormDataEntryValue | null = null;
    server.use(
      http.get("/api/submissions/options", () =>
        HttpResponse.json({
          available_data_tracks: [
            "hidden_test",
            "learning",
            "learning_1",
            "learning_2",
            "learning_3"
          ]
        })
      ),
      http.post("/api/submissions", async ({ request }) => {
        const formData = await request.formData();
        submittedTrack = formData.get("data_track");
        return HttpResponse.json({
          submission_id: "sub-window-2",
          submission_number: 2,
          submission_label: "#2",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "queued",
          data_track: "learning_2",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        });
      }),
      http.get("/api/submissions/:id", () =>
        HttpResponse.json({
          submission_id: "sub-window-2",
          submission_number: 2,
          submission_label: "#2",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "learning_2",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: "2026-06-18T12:01:00Z",
          metrics: null,
          score: null,
          error_message: null
        })
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    await userEvent.click(await screen.findByLabelText(/learning window 2/i));
    await userEvent.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );
    await userEvent.click(screen.getByRole("button", { name: /submit strategy/i }));

    await waitFor(() => expect(submittedTrack).toBe("learning_2"));
  });

  it("hides hidden test when the track is closed and submits learning data", async () => {
    let submittedTrack: FormDataEntryValue | null = null;
    server.use(
      http.get("/api/submissions/options", () =>
        HttpResponse.json({
          available_data_tracks: ["learning", "learning_1", "learning_2", "learning_3"]
        })
      ),
      http.post("/api/submissions", async ({ request }) => {
        const formData = await request.formData();
        submittedTrack = formData.get("data_track");
        return HttpResponse.json({
          submission_id: "sub-learning",
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
      }),
      http.get("/api/submissions/:id", () =>
        HttpResponse.json({
          submission_id: "sub-learning",
          submission_number: 1,
          submission_label: "#1",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "learning",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        })
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    expect(screen.queryByLabelText(/hidden test/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/learning data/i)).toBeChecked();

    await userEvent.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );
    await userEvent.click(screen.getByRole("button", { name: /submit strategy/i }));

    await waitFor(() => expect(submittedTrack).toBe("learning"));
  });

  it("uses the active participant session without posting credentials again", async () => {
    let submittedTeamName: FormDataEntryValue | null = "unexpected";
    let submittedPassword: FormDataEntryValue | null = "unexpected";
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        })
      ),
      http.post("/api/submissions", async ({ request }) => {
        const formData = await request.formData();
        submittedTeamName = formData.get("team_name");
        submittedPassword = formData.get("password");
        return HttpResponse.json({
          submission_id: "sub-456",
          submission_number: 2,
          submission_label: "#2",
          team_id: "team-alpha",
          team_name: "Alpha Desk",
          status: "queued",
          data_track: "hidden_test",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        });
      }),
      http.get("/api/submissions/:id", () =>
        HttpResponse.json({
          submission_id: "sub-456",
          submission_number: 2,
          submission_label: "#2",
          team_id: "team-alpha",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "hidden_test",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        })
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    expect(await screen.findByText(/submitting as Alpha Desk/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/team name/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/team password/i)).not.toBeInTheDocument();

    const submitButton = screen.getByRole("button", { name: /submit strategy/i });
    expect(submitButton).toBeDisabled();
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );

    expect(submitButton).toBeEnabled();
    await userEvent.click(submitButton);

    await waitFor(() => expect(submittedTeamName).toBeNull());
    expect(submittedPassword).toBeNull();
  });

  it("opens an accepted dialog, clears the file input, and blocks the next submit for two seconds", async () => {
    const user = userEvent.setup();
    let submissions = 0;
    server.use(
      http.post("/api/submissions", async () => {
        submissions++;
        return HttpResponse.json({
          submission_id: `sub-${submissions}`,
          submission_number: submissions,
          submission_label: `#${submissions}`,
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
      }),
      http.get("/api/submissions/:id", ({ params }) =>
        HttpResponse.json({
          submission_id: params.id,
          submission_number: 1,
          submission_label: "#1",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "learning",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        })
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    await user.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await user.type(screen.getByLabelText(/team password/i), "secret");
    const fileInput = screen.getByLabelText(/strategy file/i) as HTMLInputElement;
    await user.upload(fileInput, new File(["print('alpha')"], "alpha.py", { type: "text/x-python" }));

    expect(screen.getByText("alpha.py")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /submit strategy/i }));

    await waitFor(() => expect(submissions).toBeGreaterThan(0));
    const acceptedSubmissions = submissions;
    expect(
      await screen.findByRole("dialog", { name: /submission accepted/i })
    ).toBeInTheDocument();
    expect(screen.queryByText("alpha.py")).not.toBeInTheDocument();
    expect(fileInput.files).toHaveLength(0);

    await user.upload(fileInput, new File(["print('beta')"], "beta.py", { type: "text/x-python" }));
    expect(screen.getByText("beta.py")).toBeInTheDocument();
    const submitButton = screen.getByRole("button", { name: /submit strategy/i });
    expect(submitButton).toBeDisabled();

    await waitFor(() => expect(submitButton).toBeEnabled(), { timeout: 2500 });
    await user.click(submitButton);
    await waitFor(() => expect(submissions).toBeGreaterThan(acceptedSubmissions));
  });

  it("transitions from queued through running to success", async () => {
    let calls = 0;
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
      }),
      http.get("/api/submissions/:id", () => {
        calls++;
        const status = calls === 1 ? "running" : "completed";
        return HttpResponse.json({
          submission_id: "sub-123",
          submission_number: 1,
          submission_label: "#1",
          team_id: "alpha-desk",
          team_name: "Alpha Desk",
          status,
          data_track: "learning",
          submitted_at: "2026-06-18T12:00:00Z",
          scored_at: null,
          metrics: null,
          score: null,
          error_message: null
        });
      })
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    await userEvent.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );
    await userEvent.click(screen.getByLabelText(/learning data/i));
    await userEvent.click(screen.getByRole("button", { name: /submit strategy/i }));

    await waitFor(() => expect(submittedTrack).toBe("learning"));
    await waitFor(() =>
      expect(screen.getByText(/learning data is executing|learning data run has a score/i)).toBeInTheDocument()
    );
    await waitFor(() => expect(screen.getByText(/learning data run has a score/i)).toBeInTheDocument(), {
      timeout: 5000
    });
  });

  it("surfaces backend errors via ErrorState", async () => {
    server.use(
      http.post("/api/submissions", () =>
        HttpResponse.json({ detail: "Invalid credentials" }, { status: 401 })
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    await userEvent.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );
    await userEvent.click(screen.getByRole("button", { name: /submit strategy/i }));

    await waitFor(() => expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument());
  });

  it("surfaces backend cooldown errors via ErrorState", async () => {
    server.use(
      http.post("/api/submissions", () =>
        HttpResponse.json(
          { detail: "Please wait 2 seconds before submitting another strategy." },
          { status: 429 }
        )
      )
    );

    render(<SubmissionView />, { wrapper: createWrapper() });

    await userEvent.type(screen.getByLabelText(/team name/i), "alpha-desk");
    await userEvent.type(screen.getByLabelText(/team password/i), "secret");
    await userEvent.upload(
      screen.getByLabelText(/strategy file/i),
      new File(["print('alpha')"], "alpha.py", { type: "text/x-python" })
    );
    await userEvent.click(screen.getByRole("button", { name: /submit strategy/i }));

    await waitFor(() =>
      expect(screen.getByText(/please wait 2 seconds before submitting another strategy/i)).toBeInTheDocument()
    );
  });

  it("renders localized Chinese download controls", async () => {
    render(<SubmissionView />, { wrapper: createWrapper("zh") });

    expect(screen.getByRole("link", { name: /下载学习数据/ })).toHaveAttribute(
      "href",
      "/api/downloads/learning-data.zip"
    );
    await userEvent.click(screen.getByRole("button", { name: /下载环境包/ }));
    expect(screen.getByRole("menu", { name: "环境包" })).toBeInTheDocument();
    expect(screen.getByText(/Windows 64 位/)).toBeInTheDocument();
    expect(screen.getByText(/缺失/)).toBeInTheDocument();
  });
});
