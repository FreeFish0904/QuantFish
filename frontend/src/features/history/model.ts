import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import type { StudentApiError } from "../../shared/api/errors";
import {
  dataTrackSearchText,
  normalizeDataTrack,
  type DataTrack
} from "../../shared/submissions/dataTrack";
import type {
  FetchSubmissionHistoryParams,
  SubmissionHistoryResponse,
  SubmissionHistorySummary
} from "./api";
import { fetchSubmissionHistory, fetchSubmissionRawError, fetchSubmissionSource } from "./api";

export type HistoryEntry = {
  id: string;
  submissionNumber: number;
  submissionLabel: string;
  teamId: string;
  teamName: string;
  status: string;
  dataTrack: DataTrack;
  isStale: boolean;
  submittedAt: string;
  scoredAt: string | null;
  calmar: number | null;
  sharpe: number | null;
  totalReturn: number | null;
  drawdown: number | null;
  errorMessage: string | null;
  rawError: string | null;
  hasRawError: boolean;
  compareSelectable: boolean;
};

export type HistorySortKey =
  | "id"
  | "submissionNumber"
  | "teamName"
  | "status"
  | "dataTrack"
  | "submittedAt"
  | "scoredAt"
  | "calmar"
  | "sharpe"
  | "totalReturn"
  | "drawdown";

export type HistorySortState = {
  key: HistorySortKey;
  direction: "asc" | "desc";
};

export type HistoryFilters = {
  search: string;
  status: string;
  dataTrack: DataTrack | "all";
  currentTeamId?: string | null;
  myAccountOnly?: boolean;
};

export const DEFAULT_HISTORY_SORT: HistorySortState = {
  key: "submittedAt",
  direction: "desc"
};

export function useSubmissionHistory(params: FetchSubmissionHistoryParams) {
  return useQuery<SubmissionHistoryResponse, StudentApiError>({
    queryKey: ["submission-history", params],
    queryFn: () => fetchSubmissionHistory(params),
    placeholderData: keepPreviousData
  });
}

export function useSubmissionRawError() {
  return useMutation<string, StudentApiError, string>({
    mutationFn: fetchSubmissionRawError
  });
}

export function useSubmissionSource() {
  return useMutation<string, StudentApiError, string>({
    mutationFn: fetchSubmissionSource
  });
}

export function toHistoryEntries(rows: SubmissionHistorySummary[]): HistoryEntry[] {
  return rows.map((row) => ({
    id: row.submission_id,
    submissionNumber: row.submission_number,
    submissionLabel: row.submission_label,
    teamId: row.team_id,
    teamName: row.team_name,
    status: row.status,
    dataTrack: normalizeDataTrack(row.data_track),
    isStale: row.stale,
    submittedAt: row.submitted_at,
    scoredAt: row.scored_at ?? null,
    calmar: row.metrics?.calmar ?? null,
    sharpe: row.metrics?.sharpe ?? null,
    totalReturn: row.metrics?.total_return ?? null,
    drawdown: row.metrics?.max_drawdown ?? null,
    errorMessage: row.error_message ?? null,
    rawError: row.raw_error ?? null,
    hasRawError: Boolean(row.has_raw_error || row.raw_error),
    compareSelectable: row.status === "completed" && !row.stale
  }));
}

export function filterHistoryEntries(
  entries: HistoryEntry[],
  filters: HistoryFilters
): HistoryEntry[] {
  const query = filters.search.trim().toLowerCase();
  return entries.filter((entry) => {
    const matchesCurrentTeam =
      !filters.myAccountOnly || !filters.currentTeamId || entry.teamId === filters.currentTeamId;
    const matchesStatus = filters.status === "all" || entry.status === filters.status;
    const matchesTrack = filters.dataTrack === "all" || entry.dataTrack === filters.dataTrack;
    if (!matchesCurrentTeam) {
      return false;
    }
    if (!matchesStatus) {
      return false;
    }
    if (!matchesTrack) {
      return false;
    }
    if (!query) {
      return true;
    }
    return [
      entry.submissionLabel,
      entry.id,
      entry.teamId,
      entry.teamName,
      entry.status,
      dataTrackSearchText(entry.dataTrack)
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
}

export function sortHistoryEntries(
  entries: HistoryEntry[],
  sort: HistorySortState = DEFAULT_HISTORY_SORT
): HistoryEntry[] {
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...entries].sort((first, second) => {
    const firstValue = first[sort.key];
    const secondValue = second[sort.key];

    if (typeof firstValue === "number" || typeof secondValue === "number") {
      return (numericValue(firstValue) - numericValue(secondValue)) * direction;
    }

    if (isDateKey(sort.key)) {
      return (Date.parse(firstValue ?? "") - Date.parse(secondValue ?? "")) * direction;
    }

    return String(firstValue ?? "").localeCompare(String(secondValue ?? "")) * direction;
  });
}

export function formatHistoryMetric(value: number | null | undefined, digits = 2): string {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

export function formatHistoryPercent(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
}

function numericValue(value: string | number | null): number {
  return typeof value === "number" && Number.isFinite(value) ? value : Number.NEGATIVE_INFINITY;
}

function isDateKey(key: HistorySortKey): key is "submittedAt" | "scoredAt" {
  return key === "submittedAt" || key === "scoredAt";
}
