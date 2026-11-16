import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";

import { I18nProvider } from "../../shared/i18n";
import type { components } from "../../shared/api/generated/api-types";
import { fetchLeaderboard } from "./api";
import { LeaderboardView } from "./view";

vi.mock("./api", () => ({
  fetchLeaderboard: vi.fn()
}));

const leaderboard: components["schemas"]["LeaderboardResponse"] = {
  rows: [
    {
      rank: 1,
      id: "sub-1",
      team_name: "Alpha Desk",
      status: "completed",
      stale: false,
      eligible: true,
      submitted_at: "2026-06-18T08:00:00Z",
      summary: { sharpe: 1.8, max_drawdown: -0.04, total_return: 0.12, calmar: 3 },
      score: 1.8,
      metric: "sharpe",
      metric_value: 1.8,
      badge: "gold"
    },
    {
      rank: 2,
      id: "sub-2",
      team_name: "Beta Fund",
      status: "completed",
      stale: false,
      eligible: true,
      submitted_at: "2026-06-18T07:00:00Z",
      summary: { sharpe: 1.4, max_drawdown: -0.08, total_return: 0.09, calmar: 2 },
      score: 1.4,
      metric: "sharpe",
      metric_value: 1.4,
      badge: "silver"
    },
    {
      rank: 3,
      id: "sub-3",
      team_name: "Gamma Lab",
      status: "running",
      stale: false,
      eligible: false,
      submitted_at: "2026-06-18T06:00:00Z",
      summary: { sharpe: 1.1, max_drawdown: -0.12, total_return: 0.06, calmar: 1 },
      score: 1.1,
      metric: "sharpe",
      metric_value: 1.1,
      badge: null
    }
  ],
  count: 3
};

const learningLeaderboard: components["schemas"]["LeaderboardResponse"] = {
  rows: [
    {
      rank: 1,
      id: "sub-learning",
      team_name: "Learning Lab",
      status: "completed",
      stale: false,
      eligible: true,
      submitted_at: "2026-06-18T09:00:00Z",
      summary: { sharpe: 2.2, max_drawdown: -0.03, total_return: 0.18, calmar: 4 },
      score: 2.2,
      metric: "sharpe",
      metric_value: 2.2,
      badge: "gold"
    }
  ],
  count: 1
};

function DetailRoute() {
  const { submissionId } = useParams();
  return <div data-testid="detail-page">{submissionId}</div>;
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return (
    <I18nProvider defaultLanguage="en">
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/leaderboard"]}>
          <Routes>
            <Route element={children} path="/leaderboard" />
            <Route element={<div data-testid="compare-page">Compare</div>} path="/compare" />
            <Route element={<DetailRoute />} path="/submissions/:submissionId" />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </I18nProvider>
  );
}

describe("LeaderboardView", () => {
  it("renders loading state", () => {
    vi.mocked(fetchLeaderboard).mockReturnValue(new Promise(() => {}));
    render(<LeaderboardView />, { wrapper });

    expect(screen.getByText("Loading leaderboard")).toBeInTheDocument();
  });

  it("renders error state with retry", async () => {
    vi.mocked(fetchLeaderboard).mockRejectedValue(new Error("Network error"));
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Could not load leaderboard")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders leaderboard, filters by search, sorts and compares selected rows", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue(leaderboard);
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();
    expect(screen.getByText("Beta Fund")).toBeInTheDocument();
    expect(screen.getByText("Gamma Lab")).toBeInTheDocument();
    expect(screen.getByText(/live scoring/i)).toBeInTheDocument();

    await userEvent.type(screen.getByRole("searchbox", { name: /search teams/i }), "beta");
    expect(screen.queryByText("Alpha Desk")).not.toBeInTheDocument();
    expect(screen.getByText("Beta Fund")).toBeInTheDocument();

    await userEvent.clear(screen.getByRole("searchbox", { name: /search teams/i }));
    await userEvent.click(screen.getByRole("button", { name: /sort by sharpe/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "metric_value", sortDir: "desc", offset: 0 })
      );
    });
    await userEvent.click(screen.getByRole("button", { name: /sort by sharpe/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "metric_value", sortDir: "asc", offset: 0 })
      );
    });
    const rows = within(screen.getByRole("table", { name: /hidden test sharpe ranking/i })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Gamma Lab");

    await userEvent.click(screen.getByRole("checkbox", { name: /select alpha desk/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /select beta fund/i }));
    await userEvent.click(screen.getByRole("button", { name: /compare selected/i }));

    expect(screen.getByTestId("compare-page")).toBeInTheDocument();
  });

  it("links leaderboard entries to the exact submission detail page", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue(leaderboard);
    render(<LeaderboardView />, { wrapper });

    const alphaLink = await screen.findByRole("link", {
      name: /view alpha desk submission/i
    });
    expect(alphaLink).toHaveAttribute("href", "/submissions/sub-1");

    await userEvent.click(alphaLink);

    await waitFor(() => {
      expect(screen.getByTestId("detail-page")).toHaveTextContent("sub-1");
    });
  });

  it("shows stale status for stale completed leaderboard results", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue({
      rows: [
        {
          ...leaderboard.rows[0],
          stale: true,
          eligible: false,
          badge: null
        }
      ],
      count: 1
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findAllByText(/stale/i)).toHaveLength(2);
    expect(screen.queryByText(/scored/i)).not.toBeInTheDocument();
  });

  it("renders pagination controls", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue({
      rows: leaderboard.rows.slice(0, 1),
      count: 1
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText(/page 1 of 1/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /previous page/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next page/i })).toBeDisabled();
  });

  it("requests leaderboard pages and global search from the API", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue({
      rows: leaderboard.rows.slice(0, 1),
      count: 11,
      total_count: 11,
      limit: 10,
      offset: 0,
      has_next: true
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();
    expect(fetchLeaderboard).toHaveBeenLastCalledWith({
      limit: 10,
      offset: 0,
      search: "",
      sortBy: "rank",
      sortDir: "asc",
      dataTrack: "hidden_test",
      metric: "sharpe"
    });

    await userEvent.click(screen.getByRole("button", { name: /next page/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ limit: 10, offset: 10 })
      );
    });

    await userEvent.type(screen.getByRole("searchbox", { name: /search teams/i }), "beta");
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "beta", offset: 0 })
      );
    });
  });

  it("sorts each visible leaderboard field through the API", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue({
      rows: leaderboard.rows,
      count: 3,
      total_count: 3,
      limit: 10,
      offset: 0,
      has_next: false
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /sort by team/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "team_name", sortDir: "asc", offset: 0 })
      );
    });

    await userEvent.click(screen.getByRole("button", { name: /sort by status/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "status", sortDir: "asc", offset: 0 })
      );
    });

    await userEvent.click(screen.getByRole("button", { name: /sort by submitted/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "submitted_at", sortDir: "desc", offset: 0 })
      );
    });

    await userEvent.click(screen.getByRole("button", { name: /sort by rank/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "rank", sortDir: "asc", offset: 0 })
      );
    });
  });

  it("shows all five track rankings and switches between them", async () => {
    vi.mocked(fetchLeaderboard).mockImplementation(async (params) => {
      if (params.dataTrack.startsWith("learning")) {
        return learningLeaderboard;
      }
      return {
        rows: leaderboard.rows.slice(0, 2),
        count: 11,
        total_count: 11,
        limit: 10,
        offset: params.offset,
        has_next: params.offset === 0
      };
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();
    expect(fetchLeaderboard).toHaveBeenLastCalledWith(
      expect.objectContaining({ dataTrack: "hidden_test", offset: 0 })
    );
    const trackTabs = screen.getByRole("group", { name: /leaderboard track/i });
    expect(within(trackTabs).getAllByRole("button").map((button) => button.textContent)).toEqual([
      "Hidden test",
      "Learning data",
      "Learning window 1 (2010–2015)",
      "Learning window 2 (2015–2020)",
      "Learning window 3 (2020–2022)"
    ]);
    expect(within(trackTabs).getByRole("button", { name: "Hidden test" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );

    await userEvent.click(screen.getByRole("checkbox", { name: /select alpha desk/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /select beta fund/i }));
    expect(screen.getByRole("button", { name: /compare selected/i })).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: /next page/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "hidden_test", offset: 10 })
      );
    });

    await userEvent.click(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning data"
      })
    );
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "learning", metric: "sharpe", offset: 0 })
      );
    });
    expect(await screen.findByText("Learning Lab")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Desk")).not.toBeInTheDocument();
    expect(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning data"
      })
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /compare selected/i })).toBeDisabled();

    await userEvent.click(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning window 2 (2015–2020)"
      })
    );
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "learning_2", metric: "sharpe", offset: 0 })
      );
    });
    expect(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning window 2 (2015–2020)"
      })
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("restores stored leaderboard controls before the first request", async () => {
    window.localStorage.setItem(
      "quantfish-leaderboard-preferences",
      JSON.stringify({ activeTrack: "learning", activeMetric: "calmar" })
    );
    vi.mocked(fetchLeaderboard).mockResolvedValue({
      rows: [
        {
          ...learningLeaderboard.rows[0],
          metric: "calmar",
          metric_value: 4
        }
      ],
      count: 1,
      total_count: 1,
      limit: 10,
      offset: 0,
      has_next: false
    });

    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Learning Lab")).toBeInTheDocument();
    expect(fetchLeaderboard).toHaveBeenLastCalledWith(
      expect.objectContaining({ dataTrack: "learning", metric: "calmar", offset: 0 })
    );
    expect(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning data"
      })
    ).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("tab", { name: /calmar/i })).toHaveAttribute("aria-selected", "true");
  });

  it("stores leaderboard control changes", async () => {
    vi.mocked(fetchLeaderboard).mockImplementation(async (params) => {
      if (params.dataTrack === "learning") {
        return learningLeaderboard;
      }
      return leaderboard;
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();

    await userEvent.click(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning data"
      })
    );
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "learning", metric: "sharpe", offset: 0 })
      );
    });
    expect(JSON.parse(window.localStorage.getItem("quantfish-leaderboard-preferences") ?? "{}")).toEqual({
      activeTrack: "learning",
      activeMetric: "sharpe"
    });

    await userEvent.click(screen.getByRole("tab", { name: /calmar/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "learning", metric: "calmar", offset: 0 })
      );
    });
    expect(JSON.parse(window.localStorage.getItem("quantfish-leaderboard-preferences") ?? "{}")).toEqual({
      activeTrack: "learning",
      activeMetric: "calmar"
    });
  });

  it("switches between objective metric leaderboard tabs", async () => {
    vi.mocked(fetchLeaderboard).mockResolvedValue(leaderboard);
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();
    expect(fetchLeaderboard).toHaveBeenLastCalledWith(
      expect.objectContaining({ metric: "sharpe" })
    );

    await userEvent.click(screen.getByRole("tab", { name: /maxdd/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "hidden_test", metric: "max_drawdown", offset: 0 })
      );
    });
    expect(screen.getByRole("tab", { name: /maxdd/i })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("button", { name: /sort by maxdd/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ sortBy: "metric_value", sortDir: "asc", offset: 0 })
      );
    });

    await userEvent.click(screen.getByRole("tab", { name: /calmar/i }));
    await waitFor(() => {
      expect(fetchLeaderboard).toHaveBeenLastCalledWith(
        expect.objectContaining({ dataTrack: "hidden_test", metric: "calmar", offset: 0 })
      );
    });
    const calmarRows = within(screen.getByRole("table", { name: /hidden test calmar ranking/i })).getAllByRole("row");
    expect(calmarRows[1]).toHaveTextContent("3.0");
    expect(calmarRows[1]).not.toHaveTextContent("1.80");
  });

  it("renders missing Calmar as a dash", async () => {
    window.localStorage.setItem(
      "quantfish-leaderboard-preferences",
      JSON.stringify({ activeTrack: "hidden_test", activeMetric: "calmar" })
    );
    vi.mocked(fetchLeaderboard).mockResolvedValue({
      rows: [
        {
          rank: 1,
          id: "sub-smooth",
          team_name: "Smooth Return",
          status: "completed",
          stale: false,
          eligible: false,
          submitted_at: "2026-06-18T08:00:00Z",
          summary: { annual_return: 0.2, max_drawdown: 0, calmar: null },
          score: 0,
          metric: "calmar",
          metric_value: 0,
          badge: null
        }
      ],
      count: 1
    });
    render(<LeaderboardView />, { wrapper });

    const rows = within(await screen.findByRole("table", { name: /hidden test calmar ranking/i })).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("Smooth Return");
    expect(rows[1]).toHaveTextContent("—");
    expect(rows[1]).not.toHaveTextContent("0.0");
  });

  it("does not show hidden rows while learning rankings are still loading", async () => {
    vi.mocked(fetchLeaderboard).mockImplementation((params) => {
      if (params.dataTrack === "learning") {
        return new Promise(() => {});
      }
      return Promise.resolve(leaderboard);
    });
    render(<LeaderboardView />, { wrapper });

    expect(await screen.findByText("Alpha Desk")).toBeInTheDocument();

    await userEvent.click(
      within(screen.getByRole("group", { name: /leaderboard track/i })).getByRole("button", {
        name: "Learning data"
      })
    );

    expect(screen.getByText("Loading leaderboard")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Desk")).not.toBeInTheDocument();
    expect(screen.queryByText("Beta Fund")).not.toBeInTheDocument();
  });
});
