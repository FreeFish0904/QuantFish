import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../shared/i18n";
import { server } from "../../test/server";
import { CompareView } from "./view";

describe("CompareView", () => {
  const labels = {
    alignedEquity: /aligned cumulative return|对齐累计收益/i,
    compareSubmissions: /compare submissions|对比提交/i,
    detailedGraphSubmission: /detailed graph submission|选择要查看详细图表的提交/i,
    detailedGraphs: /detailed graphs|详细图表/i,
    detailedPerformance: /detailed performance|详细表现/i,
    resultGroupPerformance: /result group cumulative returns|结果分组累计收益/i,
    loadingComparison: /loading comparison|加载对比中/i,
    selectTwoSubmissions: /select two submissions|选择两条提交/i
  };

  function Wrapper({ initialEntries }: { initialEntries: string[] }) {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } }
    });

    return (
      <I18nProvider defaultLanguage="en">
        <QueryClientProvider client={client}>
          <MemoryRouter initialEntries={initialEntries}>
            <Routes>
              <Route element={<CompareView />} path="/compare" />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </I18nProvider>
    );
  }

  it("prompts to select submissions when fewer than two ids are provided", () => {
    render(<Wrapper initialEntries={["/compare"]} />);

    expect(screen.getByText(labels.selectTwoSubmissions)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to leaderboard/i })).toHaveAttribute(
      "href",
      "/leaderboard"
    );
  });

  it("reads submission_id query params and loads comparison data", async () => {
    render(<Wrapper initialEntries={["/compare?submission_id=sub-1&submission_id=sub-2"]} />);

    expect(screen.getByText(labels.loadingComparison)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: labels.compareSubmissions })).toBeInTheDocument();
    }, { timeout: 10_000 });

    expect(screen.getAllByText(/team a/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/team b/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/submitted by team a/i)).toBeInTheDocument();
    expect(screen.queryByText(/submitted by team-1/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to leaderboard/i })).toHaveAttribute(
      "href",
      "/leaderboard"
    );
  });

  it("keeps simple charts by default and loads detailed graph data only after toggle", async () => {
    const includeGraphDataValues: string[] = [];
    server.use(
      http.get("/api/compare", ({ request }) => {
        const url = new URL(request.url);
        const includeGraphData = url.searchParams.get("include_graph_data") ?? "false";
        includeGraphDataValues.push(includeGraphData);
        const rich = includeGraphData === "true";
        return HttpResponse.json({
          submissions: [1, 2].map((id) => ({
            submission_id: `sub-${id}`,
            submission_number: id,
            submission_label: `#${id}`,
            team_id: `team-${id}`,
            team_name: `Team ${id === 1 ? "A" : "B"}`,
            status: "completed",
            data_track: id === 2 ? "learning" : "hidden_test",
            metrics: {
              total_return: 0.1 * id,
              sharpe: 1.0 + id * 0.2,
              max_drawdown: -0.05 * id
            },
            equity: [
              { date: "2024-01-01", equity: 100000 },
              { date: "2024-01-02", equity: 100000 + 1000 * id }
            ],
            drawdown: [
              { date: "2024-01-01", drawdown: 0 },
              { date: "2024-01-02", drawdown: -0.01 * id }
            ],
            execution_parameters: {
              data_track: id === 2 ? "learning" : "hidden_test",
              data_start: "2015-01-01",
              scoring_start: "2023-01-01",
              scoring_end: "2025-12-31",
              capital: id === 1 ? 1_000_000 : 2_000_000,
              group_count: 5,
              price_policy: "front_adjusted",
              execution_price: "vwap",
              mark_price: "close",
              commission_rate: 0.001,
              slippage_rate: 0.0005,
              max_leverage: id === 1 ? 1 : 1.5,
              top_k: id === 1 ? null : 20,
              long_only: id === 2,
              submission_timeout_enabled: id === 2,
              submission_timeout_seconds: 120
            },
            ...(rich
              ? {
                  graph_data: {
                    equity: [
                      { date: "2024-01-01", equity: 1 },
                      { date: "2024-01-02", equity: 1.01 }
                    ],
                    equity_cny: [
                      { date: "2024-01-01", equity_cny: 1_000_000 },
                      { date: "2024-01-02", equity_cny: 1_010_000 }
                    ],
                    drawdown: [
                      { date: "2024-01-01", drawdown: 0 },
                      { date: "2024-01-02", drawdown: -0.01 }
                    ],
                    benchmark: [{ date: "2024-01-02", benchmark_return: 0.005, benchmark_cny: 1_005_000 }],
                    alpha: [{ date: "2024-01-02", alpha_return: 0.005, alpha_cny: 1_012_000 }],
                    daily_pnl: [{ date: "2024-01-02", pnl_cny: 10_000, daily_return: 0.01 }],
                    trade_volume: [{ date: "2024-01-02", buy_cny: 30_000, sell_cny: 10_000 }],
                    group_cumulative: [
                      { date: "2024-01-01", group: "group_1", cumulative_return: 0.02 },
                      { date: "2024-01-02", group: "group_1", cumulative_return: 0.03 },
                      { date: "2024-01-01", group: "group_2", cumulative_return: -0.01 },
                      { date: "2024-01-02", group: "group_2", cumulative_return: 0.01 }
                    ]
                  }
                }
              : {})
          }))
        });
      })
    );

    render(<Wrapper initialEntries={["/compare?submission_id=sub-1&submission_id=sub-2"]} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: labels.compareSubmissions })).toBeInTheDocument();
    }, { timeout: 10_000 });

    expect(includeGraphDataValues).toEqual(["false"]);
    expect(screen.getByText(/track: hidden test/i)).toBeInTheDocument();
    expect(screen.getByText(/track: learning data/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: labels.alignedEquity })).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: labels.detailedPerformance })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: labels.detailedGraphs }));

    await waitFor(() => {
      expect(includeGraphDataValues).toContain("true");
    });
    expect(screen.getByLabelText(labels.detailedGraphSubmission)).toBeInTheDocument();
    const detailedChart = screen.getByRole("img", { name: labels.detailedPerformance });
    const groupChart = screen.getByRole("img", { name: labels.resultGroupPerformance });

    expect(detailedChart).toBeInTheDocument();
    expect(groupChart).toBeInTheDocument();
    expect(within(detailedChart).getByText("Strategy")).toBeInTheDocument();
    expect(within(detailedChart).getByText("Cumulative return %")).toBeInTheDocument();
    expect(within(detailedChart).queryByText("Group 1 (best)")).not.toBeInTheDocument();
    expect(within(detailedChart).queryByText("Group 2")).not.toBeInTheDocument();
    expect(within(groupChart).getByText("Group 1 (best)")).toBeInTheDocument();
    expect(within(groupChart).getByText("Group 2")).toBeInTheDocument();
    expect(within(groupChart).queryByText("Strategy")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /execution parameters/i })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("CNY 1,000,000");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("All");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("Disabled");
    expect(screen.getByRole("checkbox", { name: "CSI 300" })).not.toBeChecked();
    expect(screen.getAllByText("CSI 300")).toHaveLength(1);

    await userEvent.click(screen.getByRole("checkbox", { name: "CSI 300" }));
    expect(screen.getByRole("checkbox", { name: "CSI 300" })).toBeChecked();
    expect(screen.getAllByText("CSI 300").length).toBeGreaterThan(1);

    await userEvent.selectOptions(screen.getByLabelText(labels.detailedGraphSubmission), "sub-2");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("CNY 2,000,000");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("20");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("Yes");
  });

  it("hides alpha in detailed graphs for long-short submissions", async () => {
    server.use(
      http.get("/api/compare", ({ request }) => {
        const url = new URL(request.url);
        const rich = url.searchParams.get("include_graph_data") === "true";
        return HttpResponse.json({
          submissions: [1, 2].map((id) => ({
            submission_id: `sub-${id}`,
            submission_number: id,
            submission_label: `#${id}`,
            team_id: `team-${id}`,
            team_name: `Team ${id}`,
            status: "completed",
            data_track: "learning",
            metrics: {
              total_return: 0.1 * id,
              sharpe: 1.0 + id * 0.2,
              max_drawdown: -0.05 * id
            },
            equity: [
              { date: "2024-01-01", equity: 100000 },
              { date: "2024-01-02", equity: 101000 }
            ],
            drawdown: [
              { date: "2024-01-01", drawdown: 0 },
              { date: "2024-01-02", drawdown: -0.01 }
            ],
            execution_parameters: {
              data_track: "learning",
              data_start: "2015-01-01",
              scoring_start: "2023-01-01",
              scoring_end: "2025-12-31",
              capital: 1_000_000,
              group_count: 5,
              price_policy: "front_adjusted",
              execution_price: "vwap",
              mark_price: "close",
              commission_rate: 0.001,
              slippage_rate: 0.0005,
              max_leverage: 1,
              top_k: null,
              long_only: false,
              submission_timeout_enabled: false,
              submission_timeout_seconds: 120
            },
            ...(rich
              ? {
                  graph_data: {
                    equity: [
                      { date: "2024-01-01", equity: 1 },
                      { date: "2024-01-02", equity: 1.01 }
                    ],
                    equity_cny: [
                      { date: "2024-01-01", equity_cny: 1_000_000 },
                      { date: "2024-01-02", equity_cny: 1_010_000 }
                    ],
                    drawdown: [
                      { date: "2024-01-01", drawdown: 0 },
                      { date: "2024-01-02", drawdown: -0.01 }
                    ],
                    benchmark: [{ date: "2024-01-02", benchmark_return: 0.005, benchmark_cny: 1_005_000 }],
                    alpha: [{ date: "2024-01-02", alpha_return: 0.005, alpha_cny: 1_012_000 }],
                    daily_pnl: [{ date: "2024-01-02", pnl_cny: 10_000, daily_return: 0.01 }],
                    trade_volume: [{ date: "2024-01-02", buy_cny: 30_000, sell_cny: 10_000 }]
                  }
                }
              : {})
          }))
        });
      })
    );

    render(<Wrapper initialEntries={["/compare?submission_id=sub-1&submission_id=sub-2"]} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: labels.compareSubmissions })).toBeInTheDocument();
    }, { timeout: 10_000 });

    await userEvent.click(screen.getByRole("checkbox", { name: labels.detailedGraphs }));

    await waitFor(() => {
      expect(screen.getByRole("img", { name: labels.detailedPerformance })).toBeInTheDocument();
    });

    expect(screen.queryByRole("checkbox", { name: "Alpha" })).not.toBeInTheDocument();
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
    expect(screen.queryByText(/available for newly scored or rescored submissions/i)).not.toBeInTheDocument();
  });
});
