import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { components } from "../../shared/api/generated/api-types";
import { fetchLeaderboard, type FetchLeaderboardParams, type LeaderboardMetric } from "./api";

export type LeaderboardEntry = {
  id: string;
  teamName: string;
  status: string;
  metric: LeaderboardMetric;
  metricValue: number | null;
  rank: number;
  sharpe: number;
  drawdown: number;
  calmar: number | null;
  submittedAt: string;
  badge: string | null;
};

export type SortDirection = "asc" | "desc";

export type SortState = {
  key: keyof LeaderboardEntry;
  direction: SortDirection;
};

export function toLeaderboardEntries(
  rows: components["schemas"]["LeaderboardSummary"][],
  requestedMetric?: LeaderboardMetric
): LeaderboardEntry[] {
  return rows.map((row) => {
    const summary = row.summary ?? {};
    const rowMetric = normalizeLeaderboardMetric(row.metric);
    const metric = requestedMetric ?? rowMetric;
    const rowMetricValue = finiteNumber(row.metric_value);
    const metricValue =
      metric === "calmar"
        ? metricValueFromSummary(summary, "calmar")
        : requestedMetric && requestedMetric !== rowMetric
        ? metricValueFromSummary(summary, requestedMetric)
        : rowMetricValue ?? metricValueFromSummary(summary, metric);
    return {
      id: row.id,
      teamName: row.team_name,
      status: row.stale ? "stale" : row.status,
      metric,
      metricValue,
      rank: row.rank,
      sharpe: summary.sharpe ?? 0,
      drawdown: summary.max_drawdown ?? 0,
      calmar: metricValueFromSummary(summary, "calmar"),
      submittedAt: row.submitted_at,
      badge: row.badge
    };
  });
}

export function useLeaderboard(params: FetchLeaderboardParams) {
  return useQuery({
    queryKey: ["leaderboard", params],
    queryFn: () => fetchLeaderboard(params),
    placeholderData: (previousData, previousQuery) => {
      const previousParams = previousQuery?.queryKey[1] as FetchLeaderboardParams | undefined;
      return previousParams?.dataTrack === params.dataTrack && previousParams?.metric === params.metric
        ? previousData
        : undefined;
    }
  });
}

function normalizeLeaderboardMetric(value: string | null | undefined): LeaderboardMetric {
  if (value === "max_drawdown" || value === "calmar") {
    return value;
  }
  return "sharpe";
}

function metricValueFromSummary(
  summary: components["schemas"]["LeaderboardSummary"]["summary"],
  metric: LeaderboardMetric
): number | null {
  if (metric === "max_drawdown") {
    return finiteNumber(summary.max_drawdown) ?? 0;
  }
  if (metric === "calmar") {
    const storedCalmar = summary.calmar;
    if (Object.prototype.hasOwnProperty.call(summary, "calmar")) {
      return finiteNumber(storedCalmar);
    }
    const annualReturn = finiteNumber(summary.annual_return);
    const maxDrawdown = finiteNumber(summary.max_drawdown);
    if (annualReturn !== null && maxDrawdown !== null) {
      const drawdown = Math.abs(maxDrawdown);
      return drawdown > 0 ? annualReturn / drawdown : null;
    }
    return null;
  }
  return finiteNumber(summary[metric]) ?? 0;
}

export type UseLeaderboardFiltersResult = {
  visibleRows: LeaderboardEntry[];
  page: number;
  pageSize: number;
  totalPages: number;
  setPage: (page: number) => void;
  sort: SortState;
  setSort: (sort: SortState) => void;
  toggleSort: (key: keyof LeaderboardEntry) => void;
  selected: Set<string>;
  toggleSelection: (id: string) => void;
  search: string;
  setSearch: (search: string) => void;
  compareUrl: string | null;
  compare: () => void;
};

const DEFAULT_PAGE_SIZE = 10;

export function sortLeaderboardEntries(
  entries: LeaderboardEntry[],
  sort: SortState
): LeaderboardEntry[] {
  return [...entries].sort((first, second) => compareRows(first, second, sort));
}

export function useLeaderboardFilters(entries: LeaderboardEntry[]): UseLeaderboardFiltersResult {
  const navigate = useNavigate();
  const [search, setSearchState] = useState("");
  const [sort, setSort] = useState<SortState>({ key: "rank", direction: "asc" });
  const [page, setPageState] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  function setSearch(nextSearch: string) {
    setSearchState(nextSearch);
    setPageState(1);
  }

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    return sortLeaderboardEntries(
      entries.filter((entry) => (query ? entry.teamName.toLowerCase().includes(query) : true)),
      sort
    );
  }, [entries, search, sort]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / DEFAULT_PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const visibleRows = filteredRows.slice(
    (safePage - 1) * DEFAULT_PAGE_SIZE,
    safePage * DEFAULT_PAGE_SIZE
  );

  const compareUrl = useMemo(() => {
    if (selected.size < 2) return null;
    const params = new URLSearchParams();
    selected.forEach((id) => params.append("submission_id", id));
    return `/compare?${params.toString()}`;
  }, [selected]);

  const compare = () => {
    if (compareUrl) navigate(compareUrl);
  };

  function toggleSort(key: keyof LeaderboardEntry) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" }
    );
    setPageState(1);
  }

  function toggleSelection(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return {
    visibleRows,
    page: safePage,
    pageSize: DEFAULT_PAGE_SIZE,
    totalPages,
    setPage: setPageState,
    sort,
    setSort,
    toggleSort,
    selected,
    toggleSelection,
    search,
    setSearch,
    compareUrl,
    compare
  };
}

function compareRows(first: LeaderboardEntry, second: LeaderboardEntry, sort: SortState): number {
  const firstValue = first[sort.key];
  const secondValue = second[sort.key];
  const direction = sort.direction === "asc" ? 1 : -1;
  const firstNumber = nullableNumber(firstValue);
  const secondNumber = nullableNumber(secondValue);

  if (firstNumber !== null || secondNumber !== null) {
    if (firstNumber === null) return 1;
    if (secondNumber === null) return -1;
    return (firstNumber - secondNumber) * direction;
  }

  return String(firstValue).localeCompare(String(secondValue)) * direction;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nullableNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
