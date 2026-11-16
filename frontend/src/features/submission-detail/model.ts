import { useQuery, type QueryClient } from "@tanstack/react-query";

import { StudentApiError } from "../../shared/api/errors";
import {
  buildPerformanceAvailability,
  buildGroupSeriesFromGraphData,
  buildPerformancePointsFromArtifacts,
  type PerformanceAvailability,
  type PerformanceGroupSeries,
  type PerformancePoint
} from "../../shared/charts/performanceGraphData";
import { normalizeDataTrack, type DataTrack } from "../../shared/submissions/dataTrack";
import type { SubmissionExecutionParameters } from "../../shared/submissions/executionParameters";
import type { BackendSubmissionDetail } from "./api";
import { fetchSubmissionDetail } from "./api";

export type KpiCard = {
  id: string;
  label: string;
  value: string;
  tone: "positive" | "warning" | "danger" | "neutral";
};

export type MetricRow = {
  helpKey?: "alpha" | "beta";
  metric: string;
  value: string;
  note: string;
};

export type TradeSummaryRow = {
  label: string;
  value: string;
};

export type PerformanceRow = {
  period: string;
  long: string;
  short: string;
  longCount: string;
  shortCount: string;
  sharpe: string;
  totalReturn: string;
  annualizedReturn: string;
  turnover: string;
  drawdown: string;
  fitness: string;
  calmar: string;
};

export type SubmissionDetailModel = {
  submissionId: string;
  submissionNumber: number;
  submissionLabel: string;
  teamId: string;
  teamName: string;
  originalFilename: string;
  status: string;
  dataTrack: DataTrack;
  isStale: boolean;
  rank?: number;
  submittedAt: string;
  scoredAt?: string | null;
  executionParameters: SubmissionExecutionParameters | null;
  kpis: KpiCard[];
  equityCurve: PerformancePoint[];
  performanceAvailability: PerformanceAvailability;
  groupSeries: PerformanceGroupSeries[];
  bestGroupId: string | null;
  metricRows: MetricRow[];
  performanceRows: PerformanceRow[];
  tradeSummaryRows: TradeSummaryRow[];
};

export type SubmissionDetailDisplay = {
  kpis: KpiCard[];
  metricRows: MetricRow[];
  tradeSummaryRows: TradeSummaryRow[];
};

const SUBMISSION_DETAIL_QUERY_KEY = "submission-detail" as const;
const SUBMISSION_DETAIL_STALE_MS = 5 * 60 * 1000;

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(2)}%`;
}

function formatDrawdownPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return formatPercent(Math.abs(value));
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return String(Math.trunc(value));
}

function toTone(value: number | null | undefined, mode: "higher-better" | "lower-better"): KpiCard["tone"] {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "neutral";
  }
  if (mode === "higher-better") {
    return value > 0 ? "positive" : value < 0 ? "danger" : "neutral";
  }
  return value < 0 ? "positive" : value > 0 ? "danger" : "neutral";
}

function buildKpiCards(metrics: Record<string, number>): KpiCard[] {
  const totalReturn = metrics.total_return ?? metrics.all_return ?? 0;
  const annualReturn = metrics.annual_return ?? 0;
  const sharpe = metrics.sharpe ?? 0;
  const maxDrawdown = metrics.max_drawdown ?? 0;
  const maxDrawdownMagnitude = Number.isFinite(maxDrawdown) ? Math.abs(maxDrawdown) : maxDrawdown;

  return [
    {
      id: "total-return",
      label: "Total return",
      value: formatPercent(totalReturn),
      tone: toTone(totalReturn, "higher-better")
    },
    {
      id: "annual-return",
      label: "Annual return",
      value: formatPercent(annualReturn),
      tone: toTone(annualReturn, "higher-better")
    },
    {
      id: "sharpe",
      label: "Sharpe",
      value: formatNumber(sharpe),
      tone: toTone(sharpe, "higher-better")
    },
    {
      id: "max-drawdown",
      label: "Max drawdown",
      value: formatDrawdownPercent(maxDrawdown),
      tone: toTone(maxDrawdownMagnitude, "lower-better")
    }
  ];
}

function formatMetricRowValue(metric: string, value: number | null | undefined): string {
  if (metric === "max_drawdown") {
    return formatDrawdownPercent(value);
  }
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(4) : String(value ?? "—");
}

function formatMetricRowName(metric: string): string {
  const displayNames: Record<string, string> = {
    active_total_return: "Alpha",
    beta: "Beta"
  };
  return displayNames[metric] ?? metric.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function metricHelpKey(metric: string): MetricRow["helpKey"] {
  if (metric === "active_total_return") {
    return "alpha";
  }
  if (metric === "beta") {
    return "beta";
  }
  return undefined;
}

function buildMetricRows(metrics: Record<string, number>, summary: Record<string, number>): MetricRow[] {
  const source = Object.keys(summary).length > 0 ? summary : metrics;
  const noteMap: Record<string, string> = {
    total_return: "Cumulative",
    all_return: "Cumulative",
    annual_return: "Annualized",
    average_year_return: "Calendar average",
    worst_year_return: "Worst calendar year",
    sharpe: "Risk-adjusted",
    max_drawdown: "Worst peak-to-trough",
    average_turnover: "Daily average",
    win_rate: "Profitable days",
    average_long_exposure: "Long exposure",
    average_short_exposure: "Short exposure",
    long_total_return: "Long total return",
    short_total_return: "Short total return",
    annualized_short_profit: "Annualized short profit",
    average_gross_exposure: "Long + short",
    average_net_exposure: "Long - short",
    trading_days: "Observations",
    average_position_count: "Daily positions",
    calmar: "Return / drawdown",
    fitness: "Sharpe × return / turnover",
    raw_total_return: "Raw portfolio",
    raw_sharpe: "Raw portfolio",
    raw_max_drawdown: "Raw portfolio",
    raw_calmar: "Raw portfolio",
    risk_free_rate: "Annual risk-free rate",
    risk_free_daily_return: "Daily risk-free rate",
    beta: "Benchmark beta",
    tracking_error: "Active risk",
    information_ratio: "Active Sharpe",
    active_total_return: "Cumulative active return",
    active_annual_return: "Beta-adjusted",
    active_max_drawdown: "Beta-adjusted",
    active_calmar: "Beta-adjusted"
  };

  return Object.entries(source).map(([metric, value]) => ({
    helpKey: metricHelpKey(metric),
    metric: formatMetricRowName(metric),
    value: formatMetricRowValue(metric, value),
    note: noteMap[metric] ?? ""
  }));
}

function buildTradeSummaryRows(summary: Record<string, number>): TradeSummaryRow[] {
  const keys = ["win_rate", "average_turnover", "trading_days", "average_position_count"];
  const rows: TradeSummaryRow[] = [];

  for (const key of keys) {
    const value = summary[key];
    if (value !== undefined && Number.isFinite(value)) {
      const display = key === "win_rate" || key === "average_turnover" ? formatPercent(value) : String(value);
      rows.push({
        label: key.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()),
        value: display
      });
    }
  }

  if (rows.length === 0) {
    rows.push(
      { label: "Winning trades", value: "—" },
      { label: "Average turnover", value: "—" },
      { label: "Trading days", value: "—" }
    );
  }

  return rows;
}

function buildPerformanceRows(rows: BackendSubmissionDetail["performance_table"] = []): PerformanceRow[] {
  return rows.map((row) => ({
    period: String(row.period),
    long: formatNumber(row.long, 3),
    short: formatNumber(row.short, 3),
    longCount: formatCount(row.long_count),
    shortCount: formatCount(row.short_count),
    sharpe: formatNumber(row.sharpe, 6),
    totalReturn: formatNumber(row.total_return, 6),
    annualizedReturn: formatNumber(row.annualized_return, 6),
    turnover: formatNumber(row.turnover, 3),
    drawdown: formatNumber(row.drawdown, 3),
    fitness: formatNumber(row.fitness, 6),
    calmar: formatNumber(row.calmar, 6)
  }));
}

export function toSubmissionDetailModel(backendDetail: BackendSubmissionDetail): SubmissionDetailModel {
  const metrics = (backendDetail.metrics ?? {}) as Record<string, number>;
  const artifacts = (backendDetail.artifacts ?? {}) as Record<string, unknown>;
  const summary = (artifacts.summary as Record<string, number>) ?? {};
  const equityCurve = buildPerformancePointsFromArtifacts(artifacts);
  const groupSeries = buildGroupSeriesFromGraphData(artifacts.graph_data);
  const bestGroupId = groupSeries.find((group) => group.isBest)?.id ?? null;

  return {
    submissionId: backendDetail.submission_id,
    submissionNumber: backendDetail.submission_number,
    submissionLabel: backendDetail.submission_label,
    teamId: backendDetail.team_id,
    teamName: backendDetail.team_name,
    originalFilename: backendDetail.original_filename,
    status: backendDetail.status,
    dataTrack: normalizeDataTrack(backendDetail.data_track),
    isStale: backendDetail.stale,
    submittedAt: backendDetail.submitted_at,
    scoredAt: backendDetail.scored_at,
    executionParameters: backendDetail.execution_parameters ?? null,
    kpis: buildKpiCards(metrics),
    equityCurve,
    performanceAvailability: buildPerformanceAvailability(equityCurve),
    groupSeries,
    bestGroupId,
    metricRows: buildMetricRows(metrics, summary),
    performanceRows: buildPerformanceRows(backendDetail.performance_table),
    tradeSummaryRows: buildTradeSummaryRows(summary)
  };
}

export function toSubmissionDetailDisplay(model: SubmissionDetailModel): SubmissionDetailDisplay {
  return {
    kpis: model.kpis,
    metricRows: model.metricRows,
    tradeSummaryRows: model.tradeSummaryRows
  };
}

async function fetchSubmissionDetailModel(submissionId: string): Promise<SubmissionDetailModel> {
  const backendDetail = await fetchSubmissionDetail(submissionId);
  return toSubmissionDetailModel(backendDetail);
}

export function prefetchSubmissionDetail(queryClient: QueryClient, submissionId: string): Promise<void> {
  if (!submissionId) {
    return Promise.resolve();
  }
  return queryClient.prefetchQuery<SubmissionDetailModel, StudentApiError>({
    queryKey: [SUBMISSION_DETAIL_QUERY_KEY, submissionId],
    queryFn: () => fetchSubmissionDetailModel(submissionId),
    staleTime: SUBMISSION_DETAIL_STALE_MS
  });
}

export function useSubmissionDetail(submissionId: string) {
  return useQuery<SubmissionDetailModel, StudentApiError>({
    queryKey: [SUBMISSION_DETAIL_QUERY_KEY, submissionId],
    queryFn: () => fetchSubmissionDetailModel(submissionId),
    enabled: Boolean(submissionId),
    retry: false,
    staleTime: SUBMISSION_DETAIL_STALE_MS
  });
}
