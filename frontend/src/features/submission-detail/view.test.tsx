import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ReactNode } from "react";
import { vi } from "vitest";

import { I18nProvider } from "../../shared/i18n";
import { StudentApiError } from "../../shared/api/errors";
import { SubmissionDetailView } from "./view";
import * as api from "./api";
import type { BackendSubmissionDetail } from "./api";

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<object>("react-router-dom");
  return {
    ...actual,
    useParams: () => ({ submissionId: "sub-1" })
  };
});

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } }
});

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <I18nProvider defaultLanguage="en">
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </I18nProvider>
  );
}

function withLongOnlyMode(
  detail: BackendSubmissionDetail,
  longOnly: boolean
): BackendSubmissionDetail {
  return {
    ...detail,
    execution_parameters: detail.execution_parameters
      ? {
          ...detail.execution_parameters,
          long_only: longOnly
        }
      : detail.execution_parameters
  };
}

const backendDetail: BackendSubmissionDetail = {
  submission_id: "sub-1",
  submission_number: 1,
  submission_label: "#1",
  team_id: "team-a",
  team_name: "Alpha Desk",
  status: "completed",
  data_track: "learning",
  submitted_at: "2026-06-18T08:00:00Z",
  scored_at: "2026-06-18T08:05:00Z",
  stale: false,
  error_message: null,
  fingerprints: {
    config_sha256: "abc",
    hidden_catalog_sha256: "def",
    strategy_sha256: "ghi",
    engine_version: "1.0"
  },
  original_filename: "strategy.py",
  pdf_report_available: true,
  metrics: {
    total_return: 0.184,
    annual_return: 0.52,
    sharpe: 1.82,
    max_drawdown: -0.04,
    average_turnover: 0.18,
    average_short_exposure: -0.5,
    short_total_return: 0.06,
    annualized_short_profit: 0.12,
    win_rate: 0.58,
    trading_days: 120
  },
  score: 53.65,
  score_breakdown: [
    {
      key: "sharpe",
      label: "Sharpe",
      metric_value: 1.82,
      weight: 45,
      contribution: 40.95
    },
    {
      key: "annual_return",
      label: "Annual return",
      metric_value: 0.52,
      weight: 35,
      contribution: 35
    },
    {
      key: "drawdown_penalty",
      label: "Drawdown penalty",
      metric_value: -0.04,
      weight: 15,
      contribution: -2
    },
    {
      key: "turnover_penalty",
      label: "Turnover penalty",
      metric_value: 0.18,
      weight: 5,
      contribution: -0.3
    },
    {
      key: "short_profit_penalty",
      label: "Short profit penalty",
      metric_value: 0.12,
      weight: 50,
      contribution: -20
    }
  ],
  score_calculation:
    "Score = clamp(1.820 / 2.000, -1, 1) × 45.000 + clamp(0.520 / 0.300, -1, 1) × 35.000 - clamp(abs(-0.040) / 0.300, 0, 1) × 15.000 - clamp(0.180 / 3.000, 0, 1) × 5.000 - clamp(0.120 / 0.300, 0, 1) × 50.000 = 53.650",
  performance_table: [
    {
      period: "2026",
      long: 0.5,
      short: -0.5,
      long_count: 12,
      short_count: 12,
      sharpe: 1.7,
      total_return: 0.18,
      annualized_return: 45.36,
      turnover: 0.32,
      drawdown: 0.08,
      fitness: 1.8,
      calmar: 2.25
    },
    {
      period: "all",
      long: 0.5,
      short: -0.5,
      long_count: 12,
      short_count: 12,
      sharpe: null,
      total_return: 0.18,
      annualized_return: 45.36,
      turnover: 0.32,
      drawdown: 0.08,
      fitness: null,
      calmar: null
    }
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
    allowed_market_types: [1, 64],
    long_only: false,
    submission_timeout_enabled: false,
    submission_timeout_seconds: 120
  },
  artifacts: {
    graph_data: {
      equity: [
        { date: "2026-01-01", equity: 1 },
        { date: "2026-06-01", equity: 1.184 }
      ],
      equity_cny: [
        { date: "2026-01-01", equity_cny: 1_000_000 },
        { date: "2026-06-01", equity_cny: 1_184_000 }
      ],
      drawdown: [
        { date: "2026-01-01", drawdown: 0 },
        { date: "2026-06-01", drawdown: -0.04 }
      ],
      benchmark: [
        { date: "2026-01-01", benchmark_return: 0.01, benchmark_equity: 1.01, benchmark_cny: 1_010_000 },
        { date: "2026-06-01", benchmark_return: -0.02, benchmark_equity: 0.99, benchmark_cny: 990_000 }
      ],
      alpha: [
        { date: "2026-01-01", alpha_return: 0.02, alpha_equity: 1.02, alpha_cny: 1_020_000 },
        { date: "2026-06-01", alpha_return: 0.184, alpha_equity: 1.204, alpha_cny: 1_204_000 }
      ],
      daily_pnl: [
        { date: "2026-01-01", pnl_cny: 20_000, daily_return: 0.02 },
        { date: "2026-06-01", pnl_cny: 184_000, daily_return: 0.184 }
      ],
      trade_volume: [
        { date: "2026-01-01", buy_cny: 300_000, sell_cny: 100_000 },
        { date: "2026-06-01", buy_cny: 50_000, sell_cny: 75_000 }
      ]
    },
    summary: {
      total_return: 0.184,
      annual_return: 0.52,
      sharpe: 1.82,
      max_drawdown: -0.04,
      average_turnover: 0.18,
      average_short_exposure: -0.5,
      win_rate: 0.58,
      trading_days: 120,
      average_position_count: 4.2
    }
  }
};

describe("SubmissionDetailView", () => {
  beforeEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  it("renders a loading state", () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockReturnValue(new Promise(() => {}));

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    expect(screen.getByText(/loading submission/i)).toBeInTheDocument();
  });

  it("renders an error state with retry", async () => {
    const fetchMock = vi
      .spyOn(api, "fetchSubmissionDetail")
      .mockRejectedValue(new StudentApiError(500, "Server error"));

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/could not load submission/i);
    });

    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders submission header, KPIs, chart, and tables without old score panels", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue(backendDetail);

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByText(/alpha desk/i)).toBeInTheDocument();
    expect(screen.getByText(/strategy.py/i)).toBeInTheDocument();
    expect(screen.getByText(/track: learning data/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /cumulative return and drawdown/i })).toBeInTheDocument();
    expect(screen.getByText("%")).toBeInTheDocument();
    expect(screen.getByText("Strategy")).toBeInTheDocument();
    expect(screen.getByText("Cumulative return %")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "CSI 300" })).not.toBeChecked();
    expect(screen.getAllByText("CSI 300")).toHaveLength(1);
    expect(screen.getByText("Daily P&L")).toBeInTheDocument();
    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText("Sell")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("checkbox", { name: "Alpha" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /execution parameters/i })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("CNY 1,000,000");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("0.1%");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("0.05%");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("1x");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("All");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent(
      "1 Shanghai A-share market (excl. STAR Market), 64 Beijing A-share market"
    );
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("No");
    expect(screen.getByRole("table", { name: /execution parameters/i })).toHaveTextContent("Disabled");
    expect(screen.getByRole("heading", { name: /yearly performance/i })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /yearly performance/i })).toHaveTextContent("long(num)");
    expect(screen.getByRole("table", { name: /yearly performance/i })).toHaveTextContent("2026");
    expect(screen.getByRole("table", { name: /yearly performance/i })).toHaveTextContent("2.250000");
    expect(screen.queryByText("Score")).not.toBeInTheDocument();
    expect(screen.queryByText("53.650")).not.toBeInTheDocument();
    expect(screen.queryByText("Short profit penalty")).not.toBeInTheDocument();
    expect(screen.queryByText("Contribution")).not.toBeInTheDocument();
    expect(screen.queryByText("+40.950")).not.toBeInTheDocument();
    expect(screen.queryByText("-20.000")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /score calculation/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/clamp\(0\.120 \/ 0\.300, 0, 1\) × 50\.000/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Win Rate").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Sharpe").length).toBeGreaterThanOrEqual(1);
  });

  it("renders metric rows without bracket placeholders when a metric has no note", async () => {
    const summary = backendDetail.artifacts.summary as Record<string, unknown>;
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...backendDetail,
      artifacts: {
        ...backendDetail.artifacts,
        summary: {
          ...summary,
          custom_metric: 0.86
        }
      }
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByText("Custom Metric")).toBeInTheDocument();
    expect(screen.queryByText("[]")).not.toBeInTheDocument();
  });

  it("warns when a submission was scored against stale settings or data", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...backendDetail,
      stale: true
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByText(/settings or data release changed/i)).toBeInTheDocument();
  });

  it("hides alpha controls for long-short submissions because equity already represents alpha", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue(backendDetail);

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.queryByRole("checkbox", { name: "Alpha" })).not.toBeInTheDocument();
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
    expect(screen.queryByText(/available for newly scored or rescored submissions/i)).not.toBeInTheDocument();
  });

  it("updates the chart range and toggles benchmark and alpha for long-only submissions", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue(withLongOnlyMode(backendDetail, true));

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByText("Active total return")).toBeInTheDocument();
    expect(screen.getByText("Active CAGR")).toBeInTheDocument();
    expect(screen.getByText("Information ratio (active Sharpe)")).toBeInTheDocument();
    expect(screen.getByText("Active max drawdown")).toBeInTheDocument();
    expect(
      screen.getByText(/Strategy curve shows raw portfolio return, while the Alpha curve shows active return/i)
    ).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /1yr/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ytd/i })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /1yr/i }));
    expect(screen.getByRole("button", { name: /1yr/i })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: /all/i }));
    expect(screen.getByRole("button", { name: /all/i })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("checkbox", { name: "CSI 300" }));
    expect(screen.getByRole("checkbox", { name: "CSI 300" })).toBeChecked();
    expect(screen.getAllByText("CSI 300").length).toBeGreaterThan(1);

    await userEvent.click(screen.getByRole("checkbox", { name: "Alpha" }));
    expect(screen.getByRole("checkbox", { name: "Alpha" })).toBeChecked();
    expect(screen.getAllByText("Alpha").length).toBeGreaterThan(1);
  });

  it("shows Alpha and Beta metric help tooltips for long-only active metrics", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...withLongOnlyMode(backendDetail, true),
      artifacts: {
        ...backendDetail.artifacts,
        summary: {
          ...(backendDetail.artifacts.summary as Record<string, unknown>),
          active_total_return: 0.204,
          beta: 1.18,
          risk_free_rate: 0.0175,
          risk_free_daily_return: 0.0175 / 252
        }
      }
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    const metricTable = screen.getByRole("table", { name: /metric table/i });
    expect(within(metricTable).getByText("Alpha")).toBeInTheDocument();
    expect(within(metricTable).getByText("Beta")).toBeInTheDocument();

    const alphaHelp = within(metricTable).getByRole("button", { name: /show help for Alpha/i });
    const betaHelp = within(metricTable).getByRole("button", { name: /show help for Beta/i });

    await userEvent.hover(alphaHelp);
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "alpha_return = (strategy_return - rf_daily) - beta * (benchmark_return - rf_daily)"
    );
    expect(screen.getByRole("tooltip")).toHaveTextContent("Default benchmark: HS300");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Default annual risk-free rate: 1.75%");

    await userEvent.hover(screen.getByRole("tooltip"));
    expect(screen.getByRole("tooltip")).toBeInTheDocument();

    alphaHelp.focus();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await userEvent.hover(betaHelp);
    expect(screen.getByRole("tooltip")).toHaveTextContent(
      "beta = cov(strategy_return - rf_daily, benchmark_return - rf_daily) / var(benchmark_return - rf_daily)"
    );
    expect(screen.getByRole("tooltip")).toHaveTextContent("Minimum aligned observations");
  });

  it("renders result groups below the equity chart and keeps whole-strategy metrics", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...backendDetail,
      artifacts: {
        ...backendDetail.artifacts,
        graph_data: {
          ...(backendDetail.artifacts.graph_data as Record<string, unknown>),
          group_cumulative: [
            { date: "2026-01-01", group: "group_1", cumulative_return: 0.01 },
            { date: "2026-06-01", group: "group_1", cumulative_return: 0.03 },
            { date: "2026-01-01", group: "group_2", cumulative_return: 0.04 },
            { date: "2026-06-01", group: "group_2", cumulative_return: 0.02 }
          ]
        }
      }
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    const equityChart = screen.getByRole("img", { name: /cumulative return and drawdown/i });
    const groupChart = screen.getByRole("img", { name: /result group cumulative returns/i });

    expect(within(equityChart).queryByText("Group 1 (best)")).not.toBeInTheDocument();
    expect(within(equityChart).queryByText("Group 2")).not.toBeInTheDocument();
    expect(within(groupChart).getByText("Group 1 (best)")).toBeInTheDocument();
    expect(within(groupChart).getByText("Group 2")).toBeInTheDocument();
    expect(within(groupChart).queryByText("Strategy")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /result groups/i })).not.toBeInTheDocument();
    expect(screen.getByText("18.40%")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /metric table/i })).toHaveTextContent("0.1840");
    expect(screen.getByRole("table", { name: /trade summary/i })).toHaveTextContent("58.00%");
    expect(screen.queryByText("3.02%")).not.toBeInTheDocument();
    expect(screen.queryByText("1.88%")).not.toBeInTheDocument();
  });

  it("disables alpha and explains old graph artifacts without benchmark data", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...withLongOnlyMode(backendDetail, true),
      artifacts: {
        graph_data: {
          equity: [{ date: "2026-01-01", equity: 1.1 }],
          drawdown: [{ date: "2026-01-01", drawdown: -0.01 }]
        }
      }
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByRole("checkbox", { name: "CSI 300" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: "Alpha" })).toBeDisabled();
    expect(screen.getByText(/available for newly scored or rescored submissions/i)).toBeInTheDocument();
  });

  it("shows unavailable execution parameters for old submissions without snapshots", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...backendDetail,
      execution_parameters: null
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByText(/execution parameters are unavailable/i)).toBeInTheDocument();
  });

  it("shows an empty yearly performance state for older reports without the artifact", async () => {
    vi.spyOn(api, "fetchSubmissionDetail").mockResolvedValue({
      ...backendDetail,
      performance_table: []
    });

    render(<SubmissionDetailView />, { wrapper: Wrapper });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "#1" })).toBeInTheDocument();
    });

    expect(screen.getByRole("heading", { name: /yearly performance/i })).toBeInTheDocument();
    expect(screen.getByText(/yearly performance is available after a submission is newly scored or rescored/i)).toBeInTheDocument();
  });
});
