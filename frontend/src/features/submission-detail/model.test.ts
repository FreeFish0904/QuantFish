import { toSubmissionDetailDisplay, toSubmissionDetailModel } from "./model";
import type { BackendSubmissionDetail } from "./api";

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
    long_total_return: 0.244,
    average_short_exposure: -0.5,
    short_total_return: 0.06,
    annualized_short_profit: 0.12,
    win_rate: 0.58,
    trading_days: 120,
    compounded_total_return: 0.29,
    cagr: 0.31,
    compounded_max_drawdown: 0.06,
    compounded_calmar: 5.17,
    volatility: 0.21,
    sortino: 2.42,
    t_stat: 3.1,
    t_stat_p_value: 0.0019
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
      long_total_return: 0.244,
      average_short_exposure: -0.5,
      short_total_return: 0.06,
      win_rate: 0.58,
      trading_days: 120,
      average_position_count: 4.2,
      compounded_total_return: 0.29,
      cagr: 0.31,
      compounded_max_drawdown: 0.06,
      compounded_calmar: 5.17,
      volatility: 0.21,
      sortino: 2.42,
      t_stat: 3.1,
      t_stat_p_value: 0.0019
    }
  }
};

describe("toSubmissionDetailModel", () => {
  it("maps submission header fields", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.submissionId).toBe("sub-1");
    expect(model.submissionNumber).toBe(1);
    expect(model.submissionLabel).toBe("#1");
    expect(model.teamId).toBe("team-a");
    expect(model.teamName).toBe("Alpha Desk");
    expect(model.originalFilename).toBe("strategy.py");
    expect(model.status).toBe("completed");
    expect(model.dataTrack).toBe("learning");
    expect(model.submittedAt).toBe("2026-06-18T08:00:00Z");
    expect(model.scoredAt).toBe("2026-06-18T08:05:00Z");
    expect(model.isStale).toBe(false);
    expect("score" in model).toBe(false);
    expect("scoreCalculation" in model).toBe(false);
    expect("scoreBreakdown" in model).toBe(false);
    expect(model.executionParameters).toEqual(backendDetail.execution_parameters);
  });

  it("maps stale submission state", () => {
    const model = toSubmissionDetailModel({ ...backendDetail, stale: true });

    expect(model.isStale).toBe(true);
  });

  it("builds KPI cards from metrics", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.kpis).toHaveLength(4);
    expect(model.kpis.find((kpi) => kpi.id === "score")).toBeUndefined();
    expect(model.kpis.find((kpi) => kpi.id === "total-return")?.value).toBe("18.40%");
    expect(model.kpis.find((kpi) => kpi.id === "cagr")?.value).toBe("31.00%");
    expect(model.kpis.find((kpi) => kpi.id === "cagr")?.label).toBe("CAGR");
    expect(model.kpis.find((kpi) => kpi.id === "sharpe")?.value).toBe("1.82");
    expect(model.kpis.find((kpi) => kpi.id === "max-drawdown")?.value).toBe("4.00%");
    expect(model.kpis.find((kpi) => kpi.id === "max-drawdown")?.tone).toBe("danger");
  });

  it("falls back to the arithmetic annual return when a run predates CAGR", () => {
    const legacy = {
      ...backendDetail,
      metrics: { ...backendDetail.metrics, cagr: null }
    };
    const model = toSubmissionDetailModel(legacy);

    expect(model.kpis.find((kpi) => kpi.id === "cagr")?.value).toBe("52.00%");
  });

  it("renders the geometric basis rows with percent and ratio formatting", () => {
    const model = toSubmissionDetailModel(backendDetail);
    const rowValue = (metric: string) => model.metricRows.find((row) => row.metric === metric)?.value;
    const rowNote = (metric: string) => model.metricRows.find((row) => row.metric === metric)?.note;

    expect(rowValue("CAGR")).toBe("31.00%");
    expect(rowValue("Compounded Total Return")).toBe("29.00%");
    expect(rowValue("Compounded Max Drawdown")).toBe("6.00%");
    expect(rowValue("Compounded Calmar")).toBe("5.1700");
    expect(rowValue("Volatility")).toBe("21.00%");
    expect(rowValue("Sortino")).toBe("2.4200");
    expect(rowValue("t-stat")).toBe("3.1000");
    expect(rowValue("t-stat p-value")).toBe("0.0019");
    expect(rowNote("CAGR")).toBe("Geometric annualized");
    expect(rowNote("Sortino")).toBe("Downside risk-adjusted");
  });

  it("aligns graph artifacts into a single CNY performance series", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.performanceAvailability).toEqual({
      hasAlpha: true,
      hasBenchmark: true
    });
    expect(model.equityCurve).toEqual([
      {
        date: "2026-01-01",
        equity: 1_000_000,
        strategyEquityCny: 1_000_000,
        strategyPercentChange: 0,
        benchmark: 1_010_000,
        benchmarkPercentChange: expect.closeTo(0.01),
        alpha: 1_020_000,
        alphaPercentChange: expect.closeTo(0.02),
        drawdown: 0,
        dailyPnl: 20_000,
        buyCny: 300_000,
        sellCny: 100_000
      },
      {
        date: "2026-06-01",
        equity: 1_184_000,
        strategyEquityCny: 1_184_000,
        strategyPercentChange: expect.closeTo(0.184),
        benchmark: 990_000,
        benchmarkPercentChange: expect.closeTo(-0.01),
        alpha: 1_204_000,
        alphaPercentChange: expect.closeTo(0.204),
        drawdown: -0.04,
        dailyPnl: 184_000,
        buyCny: 50_000,
        sellCny: 75_000
      }
    ]);
  });

  it("keeps old graph artifacts readable when CNY additions are missing", () => {
    const model = toSubmissionDetailModel({
      ...backendDetail,
      artifacts: {
        graph_data: {
          equity: [{ date: "2026-01-01", equity: 1.1 }],
          drawdown: [{ date: "2026-01-01", drawdown: -0.01 }]
        }
      }
    });

    expect(model.performanceAvailability).toEqual({
      hasAlpha: false,
      hasBenchmark: false
    });
    expect(model.equityCurve).toEqual([
      {
        date: "2026-01-01",
        equity: 1.1,
        strategyEquityCny: 1.1,
        strategyPercentChange: expect.closeTo(0.1),
        benchmark: null,
        benchmarkPercentChange: null,
        alpha: null,
        alphaPercentChange: null,
        drawdown: -0.01,
        dailyPnl: 0,
        buyCny: 0,
        sellCny: 0
      }
    ]);
  });

  it("falls back to an empty curve when graph_data is missing", () => {
    const model = toSubmissionDetailModel({ ...backendDetail, artifacts: {} });

    expect(model.equityCurve).toEqual([]);
  });

  it("surfaces grouped result lines and defaults to the best final group", () => {
    const model = toSubmissionDetailModel({
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

    expect(model.bestGroupId).toBe("group_1");
    expect(model.groupSeries).toEqual([
      {
        color: expect.any(String),
        finalCumulativeReturn: 0.03,
        id: "group_1",
        isBest: true,
        label: "Group 1"
      },
      {
        color: expect.any(String),
        finalCumulativeReturn: 0.02,
        id: "group_2",
        isBest: false,
        label: "Group 2"
      }
    ]);
    expect(model.equityCurve[0].groupPercentChanges).toEqual({
      group_1: 0.01,
      group_2: 0.04
    });
  });

  it("keeps display metrics tied to the whole strategy when result groups exist", () => {
    const model = toSubmissionDetailModel({
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

    const display = toSubmissionDetailDisplay(model);

    expect(model).not.toHaveProperty("groupSummaries");
    expect("score" in display).toBe(false);
    expect("scoreCalculation" in display).toBe(false);
    expect("scoreBreakdown" in display).toBe(false);
    expect(display.kpis.find((kpi) => kpi.id === "score")).toBeUndefined();
    expect(display.kpis.find((kpi) => kpi.id === "total-return")?.value).toBe("18.40%");
    expect(display.metricRows.find((row) => row.metric === "Total Return")?.value).toBe("0.1840");
    expect(display.tradeSummaryRows.find((row) => row.label === "Win Rate")?.value).toBe("58.00%");
  });

  it("builds metric rows from artifacts.summary", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.metricRows.some((row) => row.metric === "Sharpe")).toBe(true);
    expect(model.metricRows.some((row) => row.metric === "Trading Days")).toBe(true);
    expect(model.metricRows.find((row) => row.metric === "Max Drawdown")?.value).toBe("4.00%");
  });

  it("adds metric note hints for known metrics and leaves unknown metrics blank", () => {
    const summary = backendDetail.artifacts.summary as Record<string, unknown>;
    const model = toSubmissionDetailModel({
      ...backendDetail,
      artifacts: {
        ...backendDetail.artifacts,
        summary: {
          ...summary,
          average_gross_exposure: 0.86,
          custom_metric: 0.4
        }
      }
    });

    expect(model.metricRows.find((row) => row.metric === "Average Turnover")?.note).toBe("Daily average");
    expect(model.metricRows.find((row) => row.metric === "Average Gross Exposure")?.note).toBe("Long + short");
    expect(model.metricRows.find((row) => row.metric === "Custom Metric")?.note).toBe("");
  });

  it("labels active total return as Alpha and beta with metric help keys", () => {
    const summary = backendDetail.artifacts.summary as Record<string, unknown>;
    const model = toSubmissionDetailModel({
      ...backendDetail,
      artifacts: {
        ...backendDetail.artifacts,
        summary: {
          ...summary,
          active_total_return: 0.204,
          beta: 1.18
        }
      }
    });

    expect(model.metricRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          helpKey: "alpha",
          metric: "Alpha",
          note: "Cumulative active return",
          value: "0.2040"
        }),
        expect.objectContaining({
          helpKey: "beta",
          metric: "Beta",
          note: "Benchmark beta",
          value: "1.1800"
        })
      ])
    );
  });

  it("renders Long Total Return above Short Total Return in metric rows", () => {
    const model = toSubmissionDetailModel(backendDetail);
    const metricRows = model.metricRows;

    const longIndex = metricRows.findIndex((row) => row.metric === "Long Total Return");
    const shortIndex = metricRows.findIndex((row) => row.metric === "Short Total Return");
    expect(longIndex).toBeGreaterThan(-1);
    expect(shortIndex).toBeGreaterThan(-1);
    expect(longIndex).toBeLessThan(shortIndex);
    expect(metricRows[longIndex]?.note).toBe("Long total return");
    expect(metricRows[shortIndex]?.note).toBe("Short total return");
  });

  it("builds trade summary rows from summary keys", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.tradeSummaryRows.some((row) => row.label === "Win Rate")).toBe(true);
    expect(model.tradeSummaryRows.some((row) => row.label === "Trading Days")).toBe(true);
  });

  it("formats yearly performance rows from the backend table", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.performanceRows).toEqual([
      {
        period: "2026",
        long: "0.500",
        short: "-0.500",
        longCount: "12",
        shortCount: "12",
        sharpe: "1.700000",
        totalReturn: "0.180000",
        annualizedReturn: "45.360000",
        turnover: "0.320",
        drawdown: "0.080",
        fitness: "1.800000",
        calmar: "2.250000"
      },
      {
        period: "all",
        long: "0.500",
        short: "-0.500",
        longCount: "12",
        shortCount: "12",
        sharpe: "—",
        totalReturn: "0.180000",
        annualizedReturn: "45.360000",
        turnover: "0.320",
        drawdown: "0.080",
        fitness: "—",
        calmar: "—"
      }
    ]);
  });

  it("builds benchmark-relative rows in reporting order", () => {
    const summary = backendDetail.artifacts.summary as Record<string, unknown>;
    const model = toSubmissionDetailModel({
      ...backendDetail,
      artifacts: {
        ...(backendDetail.artifacts ?? {}),
        summary: {
          ...summary,
          strategy_total_return: 0.184,
          strategy_annual_return: 0.42,
          benchmark_total_return: 0.061,
          benchmark_annual_return: 0.12,
          benchmark_cagr: 0.108,
          excess_total_return: 0.123,
          excess_annual_return: 0.3,
          excess_compounded_return: 0.114,
          excess_cagr: 0.281,
          excess_max_drawdown: 0.021,
          excess_win_rate: 0.541,
          excess_volatility: 0.083,
          excess_information_ratio: 3.614,
          excess_beta: 0.842,
          excess_observations: 120
        }
      }
    } as BackendSubmissionDetail);

    expect(model.benchmarkRelativeRows.map((row) => row.field)).toEqual([
      "strategy_total_return",
      "benchmark_total_return",
      "excess_total_return",
      "strategy_annual_return",
      "benchmark_annual_return",
      "excess_annual_return",
      "benchmark_cagr",
      "excess_compounded_return",
      "excess_cagr",
      "excess_volatility",
      "excess_information_ratio",
      "excess_beta",
      "excess_max_drawdown",
      "excess_win_rate",
      "excess_observations"
    ]);

    const row = (field: string) => model.benchmarkRelativeRows.find((item) => item.field === field);
    expect(row("benchmark_total_return")).toEqual({
      field: "benchmark_total_return",
      labelKey: "submissionDetail.benchmarkTotalReturn",
      note: "Arithmetic",
      value: "6.10%"
    });
    expect(row("excess_total_return")?.value).toBe("12.30%");
    expect(row("excess_total_return")?.note).toBe("Strategy − CSI 300");
    expect(row("excess_information_ratio")?.value).toBe("3.61");
    expect(row("excess_beta")?.value).toBe("0.842");
    expect(row("excess_max_drawdown")?.value).toBe("2.10%");
    expect(row("excess_observations")?.value).toBe("120");
  });

  it("keeps benchmark-relative fields out of the generic metric table", () => {
    const summary = backendDetail.artifacts.summary as Record<string, unknown>;
    const model = toSubmissionDetailModel({
      ...backendDetail,
      artifacts: {
        ...(backendDetail.artifacts ?? {}),
        summary: {
          ...summary,
          strategy_total_return: 0.184,
          benchmark_total_return: 0.061,
          excess_total_return: 0.123,
          excess_information_ratio: Number.NaN
        }
      }
    } as BackendSubmissionDetail);

    expect(model.metricRows.some((row) => row.metric.startsWith("Excess"))).toBe(false);
    expect(model.metricRows.some((row) => row.metric.startsWith("Benchmark"))).toBe(false);
    expect(model.metricRows.some((row) => row.metric.startsWith("Strategy"))).toBe(false);
    expect(model.metricRows.some((row) => row.value === "NaN")).toBe(false);
  });

  it("leaves benchmark-relative rows empty when the run has no excess metrics", () => {
    const model = toSubmissionDetailModel(backendDetail);

    expect(model.benchmarkRelativeRows).toEqual([]);
    expect(toSubmissionDetailDisplay(model).benchmarkRelativeRows).toEqual([]);
  });
});
