import { http, HttpResponse } from "msw";

import type { components } from "../shared/api/generated/api-types";

type LeaderboardSummary = components["schemas"]["LeaderboardSummary"];
type SubmissionSummary = components["schemas"]["SubmissionSummary"];
type SubmissionDetail = components["schemas"]["SubmissionDetail"];
type CompareSubmission = components["schemas"]["CompareSubmission"];
type AdminTeamRecord = components["schemas"]["AdminTeamRecord"];

const now = new Date().toISOString();

const DEMO_CAPITAL = 1_000_000;
const DEMO_START_DATE = new Date("2024-01-02T00:00:00Z");
const DEMO_TRADING_DAYS = 242;
const DEMO_GROUPS = ["g1", "g2", "g3", "g4", "g5"];

function demoTradingDates(): string[] {
  const dates: string[] = [];
  const cursor = new Date(DEMO_START_DATE);
  while (dates.length < DEMO_TRADING_DAYS) {
    const weekday = cursor.getUTCDay();
    if (weekday !== 0 && weekday !== 6) {
      dates.push(cursor.toISOString().slice(0, 10));
    }
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return dates;
}

/** Deterministic LCG so demo screenshots and fixtures never flake. */
function seededRandom(seed: number): () => number {
  let state = seed % 2147483647;
  return () => {
    state = (state * 48271) % 2147483647;
    return state / 2147483647;
  };
}

type DemoGraphData = {
  equity: Array<{ date: string; equity: number }>;
  equity_cny: Array<{ date: string; equity_cny: number }>;
  drawdown: Array<{ date: string; drawdown: number }>;
  benchmark: Array<{ date: string; benchmark_cny: number }>;
  alpha: Array<{ date: string; alpha_cny: number }>;
  daily_pnl: Array<{ date: string; pnl_cny: number }>;
  trade_volume: Array<{ date: string; buy_cny: number; sell_cny: number }>;
  group_cumulative: Array<{ date: string; group: string; cumulative_return: number }>;
};

function buildDemoGraphData(seed = 7): DemoGraphData {
  const random = seededRandom(seed);
  const dated = demoTradingDates();
  const data: DemoGraphData = {
    equity: [],
    equity_cny: [],
    drawdown: [],
    benchmark: [],
    alpha: [],
    daily_pnl: [],
    trade_volume: [],
    group_cumulative: []
  };
  const groupReturns = DEMO_GROUPS.map(() => 0);
  let strategy = 1;
  let benchmark = 1;
  let peak = 1;

  dated.forEach((date) => {
    const marketReturn = (random() - 0.5) * 0.018;
    const excess = 0.00062 + (random() - 0.5) * 0.006;
    benchmark *= 1 + marketReturn;
    const nextStrategy = strategy * (1 + marketReturn + excess);
    peak = Math.max(peak, nextStrategy);

    data.equity.push({ date, equity: Number(nextStrategy.toFixed(6)) });
    data.equity_cny.push({ date, equity_cny: Math.round(nextStrategy * DEMO_CAPITAL) });
    data.drawdown.push({ date, drawdown: Number((nextStrategy / peak - 1).toFixed(6)) });
    data.benchmark.push({ date, benchmark_cny: Math.round(benchmark * DEMO_CAPITAL) });
    data.alpha.push({
      date,
      alpha_cny: Math.round((nextStrategy - benchmark) * DEMO_CAPITAL)
    });
    data.daily_pnl.push({
      date,
      pnl_cny: Math.round((nextStrategy - strategy) * DEMO_CAPITAL)
    });
    const turnover = 0.03 + random() * 0.04;
    data.trade_volume.push({
      date,
      buy_cny: Math.round(turnover * nextStrategy * DEMO_CAPITAL),
      sell_cny: Math.round(turnover * 0.92 * nextStrategy * DEMO_CAPITAL)
    });
    DEMO_GROUPS.forEach((group, groupIndex) => {
      // Group 1 is the short leg and group 5 the long leg, mirroring the engine.
      const tier = groupIndex - 2;
      groupReturns[groupIndex] += marketReturn * 0.35 + tier * 0.00022 + (random() - 0.5) * 0.006;
      data.group_cumulative.push({
        date,
        group,
        cumulative_return: Number(groupReturns[groupIndex].toFixed(6))
      });
    });
    strategy = nextStrategy;
  });

  return data;
}

const demoGraphData = buildDemoGraphData(7);
const demoCompareGraphData = buildDemoGraphData(11);

const leaderboardSummarySample = (rank: number): LeaderboardSummary => ({
  rank,
  id: `sub-${rank}`,
  team_name: `Team ${String.fromCharCode(64 + rank)}`,
  status: rank === 3 ? "failed" : "completed",
  stale: false,
  eligible: true,
  submitted_at: "2024-01-15T09:30:00Z",
  summary: {
    sharpe: 1.2 + rank * 0.1,
    max_drawdown: -0.05 * rank,
    total_return: 0.08 * rank,
  },
  score: 0.95 - rank * 0.05,
  metric: "sharpe",
  metric_value: 1.2 + rank * 0.1,
  badge: rank === 1 ? "gold" : null,
});

const submissionSummarySample = (id = 1): SubmissionSummary => ({
  submission_id: `sub-${id}`,
  submission_number: id,
  submission_label: `#${id}`,
  team_id: `team-${id}`,
  team_name: `Team ${String.fromCharCode(64 + id)}`,
  status: id === 3 ? "failed" : "completed",
  data_track: id === 2 ? "learning" : "hidden_test",
  stale: false,
  submitted_at: "2024-01-15T09:30:00Z",
  scored_at: "2024-01-15T09:35:00Z",
  metrics: {
    total_return: 0.15,
    annual_return: 0.12,
    sharpe: 1.5,
    max_drawdown: -0.08,
    average_turnover: 0.25,
    win_rate: 0.6,
    trading_days: 252,
  },
  score: id === 3 ? null : 0.825,
  error_message: null,
});

const submissionDetailSample: SubmissionDetail = {
  submission_id: "sub-1",
  submission_number: 1,
  submission_label: "#1",
  team_id: "team-1",
  team_name: "Team A",
  status: "completed",
  data_track: "hidden_test",
  stale: false,
  submitted_at: "2024-01-15T09:30:00Z",
  scored_at: "2024-01-15T09:35:00Z",
  metrics: {
    total_return: 0.15,
    annual_return: 0.12,
    sharpe: 1.5,
    max_drawdown: -0.08,
    average_turnover: 0.25,
    average_short_exposure: -0.5,
    long_total_return: 0.2,
    short_total_return: 0.06,
    annualized_short_profit: 0.12,
    win_rate: 0.6,
    trading_days: 252,
    compounded_total_return: 0.1489,
    cagr: 0.1489,
    compounded_max_drawdown: 0.085,
    compounded_calmar: 1.75,
    volatility: 0.099,
    sortino: 2.1,
    t_stat: 1.5,
    t_stat_p_value: 0.1336,
  },
  score: 23.333333333333332,
  error_message: null,
  fingerprints: { file: "sha256:abc123" },
  original_filename: "strategy.py",
  pdf_report_available: true,
  score_breakdown: [
    {
      key: "sharpe",
      label: "Sharpe",
      metric_value: 1.5,
      weight: 45,
      contribution: 33.75,
    },
    {
      key: "annual_return",
      label: "Annual return",
      metric_value: 0.12,
      weight: 35,
      contribution: 14,
    },
    {
      key: "drawdown_penalty",
      label: "Drawdown penalty",
      metric_value: -0.08,
      weight: 15,
      contribution: -4,
    },
    {
      key: "turnover_penalty",
      label: "Turnover penalty",
      metric_value: 0.25,
      weight: 5,
      contribution: -0.4166666666666667,
    },
    {
      key: "short_profit_penalty",
      label: "Short profit penalty",
      metric_value: 0.12,
      weight: 50,
      contribution: -20,
    },
  ],
  score_calculation:
    "Score = clamp(1.500 / 2.000, -1, 1) × 45.000 + clamp(0.120 / 0.300, -1, 1) × 35.000 - clamp(abs(-0.080) / 0.300, 0, 1) × 15.000 - clamp(0.250 / 3.000, 0, 1) × 5.000 - clamp(0.120 / 0.300, 0, 1) × 50.000 = 23.333",
  performance_table: [
    {
      period: "2024",
      long: 0.5,
      short: -0.5,
      long_count: 12,
      short_count: 12,
      sharpe: 1.5,
      total_return: 0.12,
      annualized_return: 30.24,
      turnover: 0.25,
      drawdown: 0.08,
      fitness: 1.6,
      calmar: 1.5,
    },
    {
      period: "all",
      long: 0.5,
      short: -0.5,
      long_count: 12,
      short_count: 12,
      sharpe: 1.5,
      total_return: 0.12,
      annualized_return: 30.24,
      turnover: 0.25,
      drawdown: 0.08,
      fitness: 1.6,
      calmar: 1.5,
    },
  ],
  artifacts: {
    graph_data: demoGraphData,
  },
};

const compareSubmissionSample = (id: number): CompareSubmission => ({
  submission_id: `sub-${id}`,
  submission_number: id,
  submission_label: `#${id}`,
  team_id: `team-${id}`,
  team_name: `Team ${String.fromCharCode(64 + id)}`,
  status: "completed",
  data_track: id === 2 ? "learning" : "hidden_test",
  metrics: {
    total_return: 0.1 * id,
    sharpe: 1.0 + id * 0.2,
    max_drawdown: -0.05 * id,
  },
  equity: demoCompareGraphData.equity_cny.map((point) => ({
    date: point.date,
    equity: point.equity_cny * (1 + (id - 1) * 0.02)
  })),
  drawdown: demoCompareGraphData.drawdown.map((point) => ({
    date: point.date,
    drawdown: point.drawdown * id
  })),
  execution_parameters: {
    data_track: id === 2 ? "learning" : "hidden_test",
    data_start: "2015-01-01",
    scoring_start: "2023-01-01",
    scoring_end: "2025-12-31",
    capital: 1_000_000,
    group_count: 5,
    industry_neutralization: false,
    price_policy: "front_adjusted",
    execution_price: "vwap",
    mark_price: "close",
    long_only_benchmark: "hs300",
    long_only_risk_free_rate: 0.0175,
    long_only_min_beta_observations: 20,
    commission_rate: 0.001,
    slippage_rate: 0.0005,
    max_leverage: 1,
    top_k: null,
    long_only: false,
    long_only_weighting: "rank_equal",
    long_only_target_count: 50,
    max_position_weight: 0.05,
    max_participation_rate: 0.1,
    min_listing_days: 60,
    submission_timeout_enabled: false,
    submission_timeout_seconds: 120,
  },
});

const teamPublicSample = (id: number): AdminTeamRecord => ({
  team_id: `team-${id}`,
  team_name: `Team ${String.fromCharCode(64 + id)}`,
  display_name: `Team ${String.fromCharCode(64 + id)}`,
  submission_count: id,
  created_at: "2024-01-15T09:30:00Z",
  status: "active",
  password: null,
  cohort_id: null,
  cohort_name: null,
  history_visible: true,
  submissions_enabled: true,
});

export const handlers = [
  http.get("/api/dashboard", () =>
    HttpResponse.json({
      course_name: "QuantFish 2024",
      scoring_timeout_seconds: 300,
      submission_count: 12,
      team_count: 5,
      latest: [leaderboardSummarySample(1), leaderboardSummarySample(2), leaderboardSummarySample(3)],
      status_counts: { queued: 2, running: 2, completed: 8, failed: 2 },
      runner_status: {
        status: "online",
        queued: 2,
        running: 2,
        updated_at: now,
        scoring_timeout_seconds: 300,
        submissions_enabled: true,
      },
    })
  ),

  http.get("/api/admin/session", () =>
    HttpResponse.json({
      authenticated: true,
    })
  ),

  http.get("/api/session", () =>
    HttpResponse.json({
      authenticated: false,
      team_id: null,
      team_name: null,
    })
  ),

  http.post("/api/session/login", async () =>
    HttpResponse.json({
      authenticated: true,
      team_id: "team-1",
      team_name: "Team A",
    })
  ),

  http.post("/api/session/logout", async () =>
    HttpResponse.json({
      authenticated: false,
      team_id: null,
      team_name: null,
    })
  ),

  http.post("/api/admin/login", async () =>
    HttpResponse.json({
      authenticated: true,
    })
  ),

  http.post("/api/admin/logout", async () =>
    HttpResponse.json({
      authenticated: false,
    })
  ),

  http.get("/api/admin/settings", () => {
    return HttpResponse.json({
      course: { name: "QuantFish 2024" },
      dataset: {
        train_start: "2021-01-01",
        train_end: "2022-12-31",
        hidden_test_start: "2023-01-01",
        hidden_test_end: "2025-12-31",
      },
      data_releases: {
        raw_data_root: "./data_releases",
        learning_output_root: "./new_data/learning",
        hidden_output_root: "./new_data/hidden",
        learning_end: "2024-06-01",
        hidden_start: "2024-06-02",
        hidden_end: "2024-12-31",
      },
      backtest: {
        data_start: "2020-01-01",
        scoring_start: "2023-01-01",
        scoring_end: "2024-05-31",
        capital: 100000,
        group_count: 10,
        industry_neutralization: false,
        price_policy: "vwap",
        execution_price: "open",
        mark_price: "close",
        long_only_benchmark: "hs300",
        long_only_risk_free_rate: 0.0175,
        long_only_min_beta_observations: 20,
      },
      scoring: {
        sharpe_weight: 45,
        sharpe_target: 2,
        annual_return_weight: 35,
        annual_return_target: 0.3,
        drawdown_weight: 15,
        drawdown_limit: 0.3,
        turnover_weight: 5,
        turnover_limit: 3,
        short_profit_weight: 50,
        short_profit_target: 0.3,
        minimum_slice_trading_days: 1,
      },
      execution: {
        commission_rate: 0.001,
        slippage_rate: 0.002,
        max_leverage: 1.5,
        top_k: 20,
        long_only_weighting: "rank_equal",
        long_only_target_count: 50,
        max_position_weight: 0.05,
        max_participation_rate: 0.1,
        min_listing_days: 60,
        hidden_test_enabled: true,
        max_concurrent_scoring: 2,
        submission_timeout_seconds: 60,
        submission_timeout_enabled: true,
        long_only: false,
      },
      execution_limits: {
        max_upload_bytes: 10485760,
        scoring_timeout_seconds: 300,
        engine_version: "v1.0.0",
      },
      runtime: {
        runtime_root: "./runtime",
        frontend_dist: "./frontend/dist",
      },
    });
  }),

  http.patch("/api/admin/settings", async () =>
    HttpResponse.json({
      course: { name: "QuantFish 2024" },
      execution_limits: { engine_version: "v1.0.0" },
    })
  ),

  http.get("/api/leaderboard", ({ request }) => {
    const url = new URL(request.url);
    const rows = [
      leaderboardSummarySample(1),
      leaderboardSummarySample(2),
      leaderboardSummarySample(3),
    ];
    if (!url.searchParams.has("limit")) {
      return HttpResponse.json({ rows, count: rows.length });
    }
    const limit = Number(url.searchParams.get("limit") ?? rows.length);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const pageRows = rows.slice(offset, offset + limit);
    return HttpResponse.json({
      rows: pageRows,
      count: rows.length,
      total_count: rows.length,
      limit,
      offset,
      has_next: offset + pageRows.length < rows.length,
    });
  }),

  http.get("/api/submissions", ({ request }) => {
    const url = new URL(request.url);
    const submissions = [submissionSummarySample(1), submissionSummarySample(2)];
    if (!url.searchParams.has("limit")) {
      return HttpResponse.json({ submissions });
    }
    const limit = Number(url.searchParams.get("limit") ?? submissions.length);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const pageRows = submissions.slice(offset, offset + limit);
    return HttpResponse.json({
      submissions: pageRows,
      total_count: submissions.length,
      limit,
      offset,
      has_next: offset + pageRows.length < submissions.length,
    });
  }),

  http.get("/api/submissions/:submissionId/raw-error", ({ params }) =>
    new HttpResponse(`Raw error for ${params.submissionId}`, {
      headers: { "Content-Type": "text/plain" },
    })
  ),

  http.get("/api/submissions/options", () =>
    HttpResponse.json({
      available_data_tracks: [
        "hidden_test",
        "learning",
        "learning_1",
        "learning_2",
        "learning_3",
      ],
    })
  ),

  http.post("/api/submissions", async () => HttpResponse.json(submissionSummarySample(99))),

  http.get("/api/submissions/:submissionId", ({ params }) => {
    const { submissionId } = params;
    if (submissionId === "not-found") {
      return HttpResponse.json({ message: "Submission not found" }, { status: 404 });
    }
    if (submissionId === "server-error") {
      return HttpResponse.text("Internal server error", { status: 500 });
    }
    return HttpResponse.json(submissionDetailSample);
  }),

  http.get("/api/compare", () =>
    HttpResponse.json({
      submissions: [compareSubmissionSample(1), compareSubmissionSample(2)],
    })
  ),

  http.get("/api/admin/teams", () => {
    return HttpResponse.json({
      teams: [teamPublicSample(1), teamPublicSample(2)],
      active_teams: [teamPublicSample(1), teamPublicSample(2)],
      archived_teams: [],
    });
  }),

  http.post("/api/admin/teams", async () => {
    return HttpResponse.json(teamPublicSample(3));
  }),

  http.patch("/api/admin/teams/:teamId", async () => {
    return HttpResponse.json(teamPublicSample(1));
  }),

  http.post("/api/admin/teams/bulk-action", async () => {
    return HttpResponse.json({ updated: 1 });
  }),

  http.get("/api/admin/submissions", ({ request }) => {
    const url = new URL(request.url);
    const submissions = [
      {
        submission_id: "sub-1",
        submission_number: 1,
        submission_label: "#1",
        team_id: "team-1",
        team_name: "Team A",
        type: "python",
        data_track: "hidden_test",
        status: "failed",
        stale: true,
        selectable: true,
        score: null,
        filename: "strategy.py",
        submitted_at: "2024-01-15T09:30:00Z",
        finished_at: "2024-01-15T09:35:00Z",
        raw_error: url.searchParams.has("limit") ? null : "Traceback",
        has_raw_error: true,
        config_snapshot: { course: { name: "QuantFish" } },
        file_paths: { strategy_path: "/tmp/strategy.py" },
      },
    ];
    if (!url.searchParams.has("limit")) {
      return HttpResponse.json({ submissions });
    }
    const limit = Number(url.searchParams.get("limit") ?? submissions.length);
    const offset = Number(url.searchParams.get("offset") ?? 0);
    const pageRows = submissions.slice(offset, offset + limit);
    return HttpResponse.json({
      submissions: pageRows,
      total_count: submissions.length,
      limit,
      offset,
      has_next: offset + pageRows.length < submissions.length,
    });
  }),

  http.get("/api/admin/submissions/:submissionId/source", ({ params }) => {
    const { submissionId } = params;
    return new HttpResponse(`def strategy_${submissionId}():\n    return 1\n`, {
      headers: { "Content-Type": "text/plain" },
    });
  }),

  http.get("/api/admin/submissions/:submissionId/raw-error", ({ params }) =>
    new HttpResponse(`Raw error for ${params.submissionId}`, {
      headers: { "Content-Type": "text/plain" },
    })
  ),

  http.post("/api/admin/submissions/delete", async () =>
    HttpResponse.json({
      deleted: 1,
      skipped: 0,
      deleted_submission_ids: ["sub-1"],
      skipped_submission_ids: [],
      deleted_file_paths: [],
    })
  ),

  http.get("/api/downloads/starter-strategy.py", () =>
    new HttpResponse(
      [
        "# 价格成交额动量",
        "def generate_signals(data, date):",
        "    current = data.current(",
        "        \"stock.daily_returns\",",
        "        columns=[\"stkcd\", \"dretwd\", \"dnvaltrd\"],",
        "        numeric_columns=[\"dretwd\", \"dnvaltrd\"],",
        "    )",
        "    return current.rename(columns={\"stkcd\": \"code\", \"dretwd\": \"score\"})",
        "",
      ].join("\n"),
      {
        headers: { "Content-Type": "text/plain" },
      }
    )
  ),

];
