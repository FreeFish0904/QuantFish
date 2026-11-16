import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../shared/i18n";
import { server } from "../../test/server";
import { HistoryView } from "./view";

function CompareRoute() {
  const location = useLocation();
  return <div data-testid="compare-page">{location.search}</div>;
}

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return (
    <I18nProvider defaultLanguage="en">
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/history"]}>
          <Routes>
            <Route element={children} path="/history" />
            <Route element={<div data-testid="detail-page">Detail</div>} path="/submissions/:submissionId" />
            <Route element={<CompareRoute />} path="/compare" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nProvider>
  );
}

const historyPayload = {
  submissions: [
    {
      submission_id: "alpha-old",
      submission_number: 1,
      submission_label: "#1",
      team_id: "team-alpha",
      team_name: "Alpha Desk",
      status: "completed",
      data_track: "hidden_test",
      stale: false,
      submitted_at: "2026-06-18T08:00:00Z",
      scored_at: "2026-06-18T08:05:00Z",
      metrics: {
        sharpe: 1.2,
        total_return: 0.08,
        annual_return: 0.08,
          max_drawdown: -0.05,
          average_turnover: 0.2,
          average_short_exposure: 0,
          calmar: 1.6
      },
      score: 33.5,
      error_message: null
    },
    {
      submission_id: "alpha-new",
      submission_number: 2,
      submission_label: "#2",
      team_id: "team-alpha",
      team_name: "Alpha Desk",
      status: "failed",
      data_track: "learning",
      stale: false,
      submitted_at: "2026-06-18T10:00:00Z",
      scored_at: "2026-06-18T10:02:00Z",
      metrics: null,
      score: null,
      error_message: "Strategy raised",
      raw_error: "Traceback (most recent call last):\nRuntimeError: Strategy raised"
    },
    {
      submission_id: "beta-best",
      submission_number: 3,
      submission_label: "#3",
      team_id: "team-beta",
      team_name: "Beta Fund",
      status: "completed",
      data_track: "hidden_test",
      stale: false,
      submitted_at: "2026-06-18T09:00:00Z",
      scored_at: "2026-06-18T09:05:00Z",
      metrics: {
        sharpe: 1.8,
        total_return: 0.12,
        annual_return: 0.12,
          max_drawdown: -0.04,
          average_turnover: 0.25,
          average_short_exposure: 0,
          calmar: 3.25
      },
      score: 52.083333333333336,
      error_message: null
    }
  ]
};

const detailPayload = {
  submission_id: "alpha-old",
  submission_number: 1,
  submission_label: "#1",
  team_id: "team-alpha",
  team_name: "Alpha Desk",
  status: "completed",
  data_track: "hidden_test",
  stale: false,
  submitted_at: "2026-06-18T08:00:00Z",
  scored_at: "2026-06-18T08:05:00Z",
  error_message: null,
  fingerprints: {
    config_sha256: "abc",
    hidden_catalog_sha256: "def",
    strategy_sha256: "ghi",
    engine_version: "1.0"
  },
  original_filename: "strategy.py",
  metrics: {
    sharpe: 1.2,
    total_return: 0.08,
    annual_return: 0.08,
    max_drawdown: -0.05,
    average_turnover: 0.2,
    average_short_exposure: 0
  },
  score: 33.5,
  score_breakdown: [],
  score_calculation:
    "Score = clamp(1.200 / 2.000, -1, 1) × 45.000 + clamp(0.080 / 0.300, -1, 1) × 35.000 - clamp(abs(-0.050) / 0.300, 0, 1) × 15.000 - clamp(0.200 / 3.000, 0, 1) × 5.000 - abs(0.000) × 50.000 = 33.500",
  artifacts: {
    graph_data: {
      equity: [{ date: "2026-01-01", equity: 1.08 }],
      drawdown: [{ date: "2026-01-01", drawdown: -0.05 }]
    },
    summary: {}
  }
};

describe("HistoryView", () => {
  it("renders loading state", () => {
    server.use(http.get("/api/submissions", () => new Promise(() => {})));

    render(<HistoryView />, { wrapper });

    expect(screen.getByText("Loading history")).toBeInTheDocument();
  });

  it("renders error state with retry", async () => {
    server.use(
      http.get("/api/submissions", () =>
        HttpResponse.json({ message: "Server error" }, { status: 500 })
      )
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findByText("Could not load history")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows all uploads, filters them, and links labels to submission detail", async () => {
    server.use(http.get("/api/submissions", () => HttpResponse.json(historyPayload)));

    render(<HistoryView />, { wrapper });

    expect(await screen.findAllByText("Alpha Desk")).toHaveLength(2);
    expect(screen.getByText("Beta Fund")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /calmar score/i })).toBeInTheDocument();
    expect(screen.getByText("3.250")).toBeInTheDocument();
    expect(screen.queryByText("52.083")).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /track/i })).toBeInTheDocument();
    expect(screen.getAllByText(/hidden test/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/learning data/i).length).toBeGreaterThanOrEqual(1);

    const table = screen.getByRole("table", { name: /history/i });
    const rows = within(table).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("#2");
    expect(rows[1]).not.toHaveTextContent("alpha-new");

    await userEvent.type(screen.getByRole("searchbox", { name: /search history/i }), "beta");
    expect(screen.queryByText("Alpha Desk")).not.toBeInTheDocument();
    expect(screen.getByText("Beta Fund")).toBeInTheDocument();

    await userEvent.clear(screen.getByRole("searchbox", { name: /search history/i }));
    await userEvent.selectOptions(screen.getByLabelText(/filter by status/i), "failed");
    expect(screen.getByRole("link", { name: /view #2/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /view #3/i })).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText(/filter by status/i), "all");
    await userEvent.selectOptions(screen.getByLabelText(/filter by track/i), "learning");
    expect(screen.getByRole("link", { name: /view #2/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /view #1/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /view #3/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: /view #2/i }));
    await waitFor(() => expect(screen.getByTestId("detail-page")).toBeInTheDocument());
  });

  it("requests only the visible history page with global filters", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("/api/submissions", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        if (url.searchParams.get("search") === "beta") {
          return HttpResponse.json({
            submissions: [historyPayload.submissions[2]],
            total_count: 1,
            limit: 10,
            offset: 0,
            has_next: false
          });
        }
        if (url.searchParams.get("offset") === "10") {
          return HttpResponse.json({
            submissions: [historyPayload.submissions[2]],
            total_count: 11,
            limit: 10,
            offset: 10,
            has_next: false
          });
        }
        return HttpResponse.json({
          submissions: historyPayload.submissions.slice(0, 1),
          total_count: 11,
          limit: 10,
          offset: 0,
          has_next: true
        });
      })
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();
    expect(requests[0].searchParams.get("limit")).toBe("10");
    expect(requests[0].searchParams.get("offset")).toBe("0");
    expect(requests[0].searchParams.get("sort_by")).toBe("submitted_at");
    expect(requests[0].searchParams.get("sort_dir")).toBe("desc");

    await userEvent.click(screen.getByRole("button", { name: /next page/i }));
    await waitFor(() => {
      expect(requests.at(-1)?.searchParams.get("offset")).toBe("10");
    });

    await userEvent.type(screen.getByRole("searchbox", { name: /search history/i }), "beta");
    await waitFor(() => {
      const latest = requests.at(-1);
      expect(latest?.searchParams.get("search")).toBe("beta");
      expect(latest?.searchParams.get("offset")).toBe("0");
    });

    await userEvent.click(screen.getByRole("button", { name: /sort by calmar score/i }));
    await waitFor(() => {
      const latest = requests.at(-1);
      expect(latest?.searchParams.get("sort_by")).toBe("calmar");
      expect(latest?.searchParams.get("sort_dir")).toBe("asc");
    });
  });

  it("restores stored history filters before the first submissions request", async () => {
    const requests: URL[] = [];
    window.localStorage.setItem(
      "quantfish-history-preferences",
      JSON.stringify({
        status: "failed",
        dataTrack: "learning",
        myAccountOnly: true,
        sort: { key: "calmar", direction: "asc" }
      })
    );
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        })
      ),
      http.get("/api/submissions", ({ request }) => {
        const url = new URL(request.url);
        requests.push(url);
        return HttpResponse.json({
          submissions: [historyPayload.submissions[1]],
          total_count: 1,
          limit: 10,
          offset: 0,
          has_next: false
        });
      })
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findByRole("link", { name: /view #2/i })).toBeInTheDocument();
    expect(requests[0].searchParams.get("status")).toBe("failed");
    expect(requests[0].searchParams.get("data_track")).toBe("learning");
    expect(requests[0].searchParams.get("sort_by")).toBe("calmar");
    expect(requests[0].searchParams.get("sort_dir")).toBe("asc");
    expect(screen.getByLabelText(/filter by status/i)).toHaveValue("failed");
    expect(screen.getByLabelText(/filter by track/i)).toHaveValue("learning");
    await waitFor(() => {
      expect(screen.getByRole("checkbox", { name: /my submissions only/i })).toBeChecked();
      expect(requests.some((url) => url.searchParams.get("team_id") === "team-alpha")).toBe(true);
    });
  });

  it("stores history filter and sort changes", async () => {
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        })
      ),
      http.get("/api/submissions", () =>
        HttpResponse.json({
          submissions: historyPayload.submissions,
          total_count: 3,
          limit: 10,
          offset: 0,
          has_next: false
        })
      )
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findAllByText("Alpha Desk")).toHaveLength(2);

    await userEvent.selectOptions(screen.getByLabelText(/filter by status/i), "failed");
    await userEvent.selectOptions(screen.getByLabelText(/filter by track/i), "learning_2");
    await userEvent.click(screen.getByRole("checkbox", { name: /my submissions only/i }));
    await userEvent.click(screen.getByRole("button", { name: /sort by calmar score/i }));

    expect(JSON.parse(window.localStorage.getItem("quantfish-history-preferences") ?? "{}")).toEqual({
      status: "failed",
      dataTrack: "learning_2",
      myAccountOnly: true,
      sort: { key: "calmar", direction: "asc" }
    });
  });

  it("toggles history to only show the logged-in account submissions", async () => {
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        })
      ),
      http.get("/api/submissions", () => HttpResponse.json(historyPayload))
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findAllByText("Alpha Desk")).toHaveLength(2);
    expect(screen.getByText("Beta Fund")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /my submissions only/i }));

    expect(screen.getAllByText("Alpha Desk")).toHaveLength(2);
    expect(screen.queryByText("Beta Fund")).not.toBeInTheDocument();
    expect(screen.getByText("2 uploads shown")).toBeInTheDocument();
  });

  it("opens raw error details for failed history submissions", async () => {
    server.use(http.get("/api/submissions", () => HttpResponse.json(historyPayload)));

    render(<HistoryView />, { wrapper });

    const errorButton = await screen.findByRole("button", { name: /view error for #2/i });
    await userEvent.click(errorButton);

    const dialog = screen.getByRole("dialog", { name: /raw error for #2/i });
    expect(within(dialog).getByText(/RuntimeError: Strategy raised/i)).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: /close/i }));
    expect(screen.queryByRole("dialog", { name: /raw error for #2/i })).not.toBeInTheDocument();
  });

  it("fetches history raw error text only when the dialog opens", async () => {
    let rawErrorCalls = 0;
    server.use(
      http.get("/api/submissions", () =>
        HttpResponse.json({
          submissions: [
            {
              ...historyPayload.submissions[1],
              raw_error: undefined,
              has_raw_error: true
            }
          ],
          total_count: 1,
          limit: 10,
          offset: 0,
          has_next: false
        })
      ),
      http.get("/api/submissions/:submissionId/raw-error", ({ params }) => {
        rawErrorCalls += 1;
        expect(params.submissionId).toBe("alpha-new");
        return HttpResponse.text("Lazy traceback");
      })
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findByRole("button", { name: /view error for #2/i })).toBeInTheDocument();
    expect(rawErrorCalls).toBe(0);

    await userEvent.click(screen.getByRole("button", { name: /view error for #2/i }));

    const dialog = await screen.findByRole("dialog", { name: /raw error for #2/i });
    expect(within(dialog).getByText(/Lazy traceback/i)).toBeInTheDocument();
    expect(rawErrorCalls).toBe(1);
  });

  it("shows code viewing only for owned rows and fetches source lazily", async () => {
    let sourceCalls = 0;
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: true,
          team_id: "team-alpha",
          team_name: "Alpha Desk"
        })
      ),
      http.get("/api/submissions", () => HttpResponse.json(historyPayload)),
      http.get("/api/submissions/:submissionId/source", ({ params }) => {
        sourceCalls += 1;
        expect(params.submissionId).toBe("alpha-old");
        return HttpResponse.text("def alpha_strategy(data):\n    return []\n");
      })
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findAllByText("Alpha Desk")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /view code for #1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view code for #2/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view code for #3/i })).not.toBeInTheDocument();
    expect(sourceCalls).toBe(0);

    await userEvent.click(screen.getByRole("button", { name: /view code for #1/i }));

    const dialog = await screen.findByRole("dialog", { name: /source code for #1/i });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveTextContent("def alpha_strategy");
    const highlightedCode = within(dialog).getByLabelText(/python source code/i);
    expect(highlightedCode).toHaveAttribute("data-language", "python");
    expect(within(highlightedCode).getByText("def")).toHaveAttribute("data-token", "keyword");
    expect(within(highlightedCode).getByText("alpha_strategy")).toHaveAttribute("data-token", "function");
    expect(sourceCalls).toBe(1);
  });

  it("does not render code buttons for logged-out history users", async () => {
    server.use(
      http.get("/api/session", () =>
        HttpResponse.json({
          authenticated: false,
          team_id: null,
          team_name: null
        })
      ),
      http.get("/api/submissions", () => HttpResponse.json(historyPayload))
    );

    render(<HistoryView />, { wrapper });

    expect(await screen.findAllByText("Alpha Desk")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /view code/i })).not.toBeInTheDocument();
  });

  it("lets completed history rows drive comparison", async () => {
    server.use(http.get("/api/submissions", () => HttpResponse.json(historyPayload)));

    render(<HistoryView />, { wrapper });

    expect(await screen.findAllByText("Alpha Desk")).toHaveLength(2);

    const compareButton = screen.getByRole("button", { name: /compare selected/i });
    expect(compareButton).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /select #2/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("checkbox", { name: /select #1/i }));
    expect(compareButton).toBeDisabled();

    await userEvent.click(screen.getByRole("checkbox", { name: /select #3/i }));
    expect(compareButton).toBeEnabled();

    await userEvent.click(compareButton);
    await waitFor(() => {
      expect(screen.getByTestId("compare-page")).toHaveTextContent(
        "?submission_id=alpha-old&submission_id=beta-best"
      );
    });
  });

  it("shows stale history rows and excludes them from comparison", async () => {
    server.use(
      http.get("/api/submissions", () =>
        HttpResponse.json({
          submissions: [
            {
              ...historyPayload.submissions[0],
              stale: true
            },
            historyPayload.submissions[2]
          ]
        })
      )
    );

    render(<HistoryView />, { wrapper });

    const table = await screen.findByRole("table", { name: /history/i });
    const rows = within(table).getAllByRole("row");
    const staleRow = rows.find((row) => row.textContent?.includes("#1"));
    expect(staleRow).toBeDefined();
    expect(staleRow).toHaveTextContent("Stale");
    expect(screen.getByRole("checkbox", { name: /select #1/i })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /select #3/i })).toBeEnabled();
  });

  it("prefetches completed submission detail on visible row link hover", async () => {
    let detailCalls = 0;
    server.use(
      http.get("/api/submissions", () => HttpResponse.json(historyPayload)),
      http.get("/api/submissions/:submissionId", ({ params }) => {
        detailCalls += 1;
        return HttpResponse.json({ ...detailPayload, submission_id: params.submissionId });
      })
    );

    render(<HistoryView />, { wrapper });

    const firstLink = await screen.findByRole("link", { name: /view #1/i });
    expect(detailCalls).toBe(0);

    await userEvent.hover(firstLink);

    await waitFor(() => {
      expect(detailCalls).toBe(1);
    });
  });

  it("renders empty state", async () => {
    server.use(http.get("/api/submissions", () => HttpResponse.json({ submissions: [] })));

    render(<HistoryView />, { wrapper });

    expect(await screen.findByText("No upload history")).toBeInTheDocument();
  });
});
