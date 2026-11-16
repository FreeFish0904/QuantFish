import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";

import { I18nProvider } from "../../shared/i18n";
import { server } from "../../test/server";
import { DashboardView } from "./view";

function Wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return (
    <I18nProvider defaultLanguage="en">
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </I18nProvider>
  );
}

const dashboardPayload = {
  course_name: "QClass 2026",
  scoring_timeout_seconds: 300,
  latest: [
    {
      badge: null,
      score: 94.25,
      eligible: true,
      id: "sub-1",
      rank: 1,
      stale: false,
      status: "completed",
      submitted_at: "2026-06-18T08:30:00Z",
      summary: { max_drawdown: -0.05, sharpe: 1.42 },
      team_name: "Alpha Desk"
    }
  ],
  status_counts: { queued: 1, running: 2, completed: 7 },
  runner_status: {
    status: "online",
    queued: 1,
    running: 2,
    updated_at: "2026-06-18T08:35:00+00:00",
    scoring_timeout_seconds: 300,
    submissions_enabled: true
  },
  submission_count: 10,
  team_count: 5
};

describe("DashboardView", () => {
  it("renders loading state", () => {
    server.use(
      http.get("/api/dashboard", () => HttpResponse.json(dashboardPayload))
    );

    render(<DashboardView />, { wrapper: Wrapper });
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
  });

  it("renders error state with retry", async () => {
    server.use(
      http.get("/api/dashboard", () =>
        HttpResponse.json({ message: "Server error" }, { status: 500 })
      )
    );

    render(<DashboardView />, { wrapper: Wrapper });

    await waitFor(
      () => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getByText(/could not load dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/server error/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => expect(screen.getByText(/server error/i)).toBeInTheDocument());
  });

  it("renders populated state", async () => {
    server.use(
      http.get("/api/dashboard", () => HttpResponse.json(dashboardPayload))
    );

    render(<DashboardView />, { wrapper: Wrapper });

    await waitFor(
      () => {
        expect(screen.getByRole("heading", { name: /student cockpit/i })).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getByText(/QClass 2026/)).toBeInTheDocument();
    expect(screen.queryByText(/hidden test track/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /track/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /^score$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /^rank$/i })).not.toBeInTheDocument();
    expect(screen.getByText("Alpha Desk")).toBeInTheDocument();
    expect(screen.getByText(/scoring online/i)).toBeInTheDocument();
    expect(screen.queryByText(/\{count\}/)).not.toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText(/1 queued/i)).toBeInTheDocument();
    expect(screen.getByText(/2 running/i)).toBeInTheDocument();

    const latestBox = screen.getByTestId("latest-submissions-box");
    const liveBox = screen.getByTestId("live-status-box");
    expect(latestBox).toBeInTheDocument();
    expect(liveBox).toBeInTheDocument();
    expect(latestBox).not.toContainElement(screen.getByRole("heading", { name: /latest submissions/i }));
    expect(liveBox).not.toContainElement(screen.getByRole("heading", { name: /live status/i }));
  });
});
