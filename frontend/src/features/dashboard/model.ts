import { useQuery } from "@tanstack/react-query";

import type { StudentApiError } from "../../shared/api/errors";
import type { components } from "../../shared/api/generated/api-types";
import { fetchDashboard } from "./api";

type DashboardResponse = components["schemas"]["DashboardResponse"];
type LeaderboardSummary = components["schemas"]["LeaderboardSummary"];

export type RunnerStatus = {
  status: "online" | "offline";
  queued: number;
  running: number;
  lastUpdated: string;
  scoringTimeoutSeconds: number | null;
  submissionsEnabled: boolean;
};

export type DashboardKpi = {
  id: string;
  label: string;
  value: number;
  format: "number";
  tone: "neutral" | "positive" | "warning" | "danger";
};

export type LatestSubmission = {
  id: string;
  teamName: string;
  status: string;
  stale: boolean;
  sharpe?: number;
  drawdown?: number;
  submittedAt: string;
};

export type DashboardModel = {
  className: string;
  runnerStatus: RunnerStatus;
  scoringTimeoutSeconds: number | null;
  kpis: DashboardKpi[];
  latestSubmissions: LatestSubmission[];
};

export function toDashboardModel(dashboard: DashboardResponse): DashboardModel {
  const statusCounts = dashboard.status_counts;
  const completed = statusCounts.completed ?? 0;
  const staleResults = dashboard.latest.filter((row) => row.stale).length;
  const runnerStatus = toRunnerStatus(dashboard.runner_status);
  const queued = runnerStatus.queued;

  const kpis: DashboardKpi[] = [
    {
      id: "active-teams",
      label: "Active teams",
      value: dashboard.team_count,
      format: "number",
      tone: "neutral"
    },
    {
      id: "scored-runs",
      label: "Scored runs",
      value: completed,
      format: "number",
      tone: "positive"
    },
    {
      id: "queued-jobs",
      label: "Queued jobs",
      value: queued,
      format: "number",
      tone: "warning"
    },
    {
      id: "stale-results",
      label: "Stale results",
      value: staleResults,
      format: "number",
      tone: "neutral"
    }
  ];

  return {
    className: dashboard.course_name ?? "QuantFish Classroom",
    runnerStatus,
    scoringTimeoutSeconds: runnerStatus.scoringTimeoutSeconds,
    kpis,
    latestSubmissions: dashboard.latest.map(toLatestSubmission)
  };
}

function toRunnerStatus(status: DashboardResponse["runner_status"]): RunnerStatus {
  return {
    status: status.status,
    queued: status.queued,
    running: status.running,
    lastUpdated: status.updated_at,
    scoringTimeoutSeconds: status.scoring_timeout_seconds ?? null,
    submissionsEnabled: status.submissions_enabled
  };
}

function toLatestSubmission(row: LeaderboardSummary): LatestSubmission {
  const summary = row.summary ?? {};
  return {
    id: row.id,
    teamName: row.team_name,
    status: row.status,
    stale: row.stale,
    sharpe: optionalNumber(summary.sharpe),
    drawdown: optionalNumber(summary.max_drawdown),
    submittedAt: row.submitted_at
  };
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function useDashboard() {
  return useQuery<DashboardResponse, StudentApiError>({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard
  });
}
