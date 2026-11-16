import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import {
  buildPerformanceAvailability,
  buildGroupSeriesFromGraphData,
  buildPerformancePointsFromGraphData,
  type PerformanceAvailability,
  type PerformanceGroupSeries,
  type PerformancePoint
} from "../../shared/charts/performanceGraphData";
import { normalizeDataTrack, type DataTrack } from "../../shared/submissions/dataTrack";
import type { SubmissionExecutionParameters } from "../../shared/submissions/executionParameters";
import type { CompareResponse } from "./api";
import { fetchCompareSubmissions } from "./api";

export const COMPARE_COLORS = [
  "var(--sf-cyan)",
  "var(--sf-amber)",
  "var(--sf-emerald)",
  "var(--sf-violet)"
];

export type CompareSubmission = {
  id: string;
  submissionNumber: number;
  submissionLabel: string;
  teamId: string;
  teamName: string;
  displayName: string;
  status: string;
  dataTrack: DataTrack;
  color: string;
  totalReturn: number | null;
  annualReturn: number | null;
  sharpe: number | null;
  maxDrawdown: number | null;
};

export type CompareSeries = {
  id: string;
  name: string;
  color: string;
};

export type ComparePoint = {
  date: string;
  values: Record<string, { equity: number | null; drawdown: number | null }>;
};

export type CompareChartRow = {
  date: string;
  [key: string]: number | null | string;
};

export type CompareDetailedSubmission = {
  id: string;
  displayName: string;
  dataTrack: DataTrack;
  points: PerformancePoint[];
  groupSeries: PerformanceGroupSeries[];
  availability: PerformanceAvailability;
  executionParameters: SubmissionExecutionParameters | null;
  hasGraphData: boolean;
};

export type CompareModel = {
  submissions: CompareSubmission[];
  series: CompareSeries[];
  points: ComparePoint[];
  equityData: CompareChartRow[];
  drawdownData: CompareChartRow[];
  detailedSubmissions: CompareDetailedSubmission[];
};

function pickColor(index: number): string {
  return COMPARE_COLORS[index % COMPARE_COLORS.length];
}

export function toCompareModel(backendResponse: CompareResponse): CompareModel {
  const submissions: CompareSubmission[] = backendResponse.submissions.map(
    (submission, index) => ({
      id: submission.submission_id,
      submissionNumber: submission.submission_number,
      submissionLabel: submission.submission_label,
      teamId: submission.team_id,
      teamName: submission.team_name,
      displayName: `${submission.submission_label} · ${submission.team_name}`,
      status: submission.status,
      dataTrack: normalizeDataTrack(submission.data_track),
      color: pickColor(index),
      totalReturn: submission.metrics?.total_return ?? null,
      annualReturn: submission.metrics?.annual_return ?? null,
      sharpe: submission.metrics?.sharpe ?? null,
      maxDrawdown: submission.metrics?.max_drawdown ?? null
    })
  );

  const series: CompareSeries[] = submissions.map((submission) => ({
    id: submission.id,
    name: submission.displayName,
    color: submission.color
  }));

  const byDate = new Map<
    string,
    Record<string, { equity: number | null; drawdown: number | null }>
  >();

  backendResponse.submissions.forEach((submission) => {
    const id = submission.submission_id;

    for (const point of submission.equity) {
      const record = point as Record<string, unknown>;
      const date = typeof record.date === "string" ? record.date : "";
      const equity = typeof record.equity === "number" ? record.equity : null;
      if (!date) continue;
      const row = byDate.get(date) ?? {};
      row[id] = { ...(row[id] ?? { equity: null, drawdown: null }), equity };
      byDate.set(date, row);
    }

    for (const point of submission.drawdown) {
      const record = point as Record<string, unknown>;
      const date = typeof record.date === "string" ? record.date : "";
      const drawdown = typeof record.drawdown === "number" ? record.drawdown : null;
      if (!date) continue;
      const row = byDate.get(date) ?? {};
      row[id] = { ...(row[id] ?? { equity: null, drawdown: null }), drawdown };
      byDate.set(date, row);
    }
  });

  const sortedDates = Array.from(byDate.keys()).sort();

  const points: ComparePoint[] = sortedDates.map((date) => ({
    date,
    values: byDate.get(date) ?? {}
  }));

  const equityData: CompareChartRow[] = points.map((point) => ({
    date: point.date,
    ...Object.fromEntries(
      Object.entries(point.values).map(([id, value]) => [id, value.equity])
    )
  }));

  const drawdownData: CompareChartRow[] = points.map((point) => ({
    date: point.date,
    ...Object.fromEntries(
      Object.entries(point.values).map(([id, value]) => [id, value.drawdown])
    )
  }));

  const detailedSubmissions: CompareDetailedSubmission[] = backendResponse.submissions.map((submission) => {
    const displayName = `${submission.submission_label} · ${submission.team_name}`;
    const detailedPoints = buildPerformancePointsFromGraphData(submission.graph_data);
    const groupSeries = buildGroupSeriesFromGraphData(submission.graph_data);
    return {
      id: submission.submission_id,
      displayName,
      dataTrack: normalizeDataTrack(submission.data_track),
      points: detailedPoints,
      groupSeries,
      availability: buildPerformanceAvailability(detailedPoints),
      executionParameters: submission.execution_parameters ?? null,
      hasGraphData: detailedPoints.length > 0
    };
  });

  return {
    submissions,
    series,
    points,
    equityData,
    drawdownData,
    detailedSubmissions
  };
}

export function useCompareSubmissions(includeGraphData = false) {
  const [searchParams] = useSearchParams();
  const submissionIds = useMemo(
    () => searchParams.getAll("submission_id").filter(Boolean),
    [searchParams]
  );

  const query = useQuery({
    queryKey: ["compare", submissionIds, includeGraphData],
    queryFn: () => fetchCompareSubmissions(submissionIds, { includeGraphData }),
    enabled: submissionIds.length >= 2,
    placeholderData: (previousData) => previousData
  });

  const model = query.data ? toCompareModel(query.data) : undefined;

  return {
    submissionIds,
    model,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch
  };
}
