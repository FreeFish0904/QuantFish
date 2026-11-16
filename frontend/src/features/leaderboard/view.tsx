import { ExternalLink, LoaderCircle, Medal, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useI18n } from "../../shared/i18n";
import { readObjectPreference, writePreference } from "../../shared/preferences/storage";
import { DATA_TRACKS, dataTrackLabelKey, type DataTrack } from "../../shared/submissions/dataTrack";
import type { BadgeStatus } from "../../shared/ui/Badge/Badge";
import { Badge } from "../../shared/ui/Badge/Badge";
import { Button } from "../../shared/ui/Button/Button";
import { DataTable } from "../../shared/ui/DataTable/DataTable";
import type { DataTableColumn } from "../../shared/ui/DataTable/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { formatDateTime, formatPercent, formatScore } from "./formatting";
import {
  sortLeaderboardEntries,
  toLeaderboardEntries,
  useLeaderboard,
  type LeaderboardEntry,
  type SortState
} from "./model";
import type { LeaderboardMetric } from "./api";
import styles from "./view.module.css";

const PAGE_SIZE = 10;
const LEADERBOARD_TRACKS: DataTrack[] = [...DATA_TRACKS];
const LEADERBOARD_METRICS: LeaderboardMetric[] = ["sharpe", "max_drawdown", "calmar"];
const LEADERBOARD_STORAGE_KEY = "quantfish-leaderboard-preferences";

type LeaderboardPreferences = {
  activeTrack: DataTrack;
  activeMetric: LeaderboardMetric;
};

const DEFAULT_LEADERBOARD_PREFERENCES: LeaderboardPreferences = {
  activeTrack: "hidden_test",
  activeMetric: "sharpe"
};
const DEFAULT_LEADERBOARD_SORT: SortState = { key: "rank", direction: "asc" };

function parseLeaderboardTrack(value: unknown): DataTrack | null {
  return LEADERBOARD_TRACKS.includes(value as DataTrack) ? (value as DataTrack) : null;
}

function parseLeaderboardMetric(value: unknown): LeaderboardMetric | null {
  return LEADERBOARD_METRICS.includes(value as LeaderboardMetric)
    ? (value as LeaderboardMetric)
    : null;
}

function readLeaderboardPreferences(): LeaderboardPreferences {
  return readObjectPreference(
    LEADERBOARD_STORAGE_KEY,
    DEFAULT_LEADERBOARD_PREFERENCES,
    {
      activeTrack: parseLeaderboardTrack,
      activeMetric: parseLeaderboardMetric
    }
  );
}

export function LeaderboardView() {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const [{ activeTrack, activeMetric }, setLeaderboardPreferences] =
    useState<LeaderboardPreferences>(readLeaderboardPreferences);
  const [search, setSearchState] = useState("");
  const [sort, setSort] = useState<SortState>(DEFAULT_LEADERBOARD_SORT);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const leaderboardQueryParams = useMemo(
    () => ({
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
      search,
      sortBy: leaderboardSortKeyToApi(sort.key),
      sortDir: sort.direction,
      dataTrack: activeTrack,
      metric: activeMetric
    }),
    [activeMetric, activeTrack, page, search, sort]
  );
  const { data, error, isLoading, refetch } = useLeaderboard(leaderboardQueryParams);
  const entries = data ? toLeaderboardEntries(data.rows, activeMetric) : [];
  const totalCountFromServer = (data as { total_count?: number } | undefined)?.total_count;
  const serverPaged = typeof totalCountFromServer === "number";
  const filteredRows = useMemo(() => {
    if (serverPaged) {
      return entries;
    }
    const query = search.trim().toLowerCase();
    return sortLeaderboardEntries(
      entries.filter((entry) => (query ? entry.teamName.toLowerCase().includes(query) : true)),
      sort
    );
  }, [entries, search, serverPaged, sort]);
  const totalRows = serverPaged ? totalCountFromServer : filteredRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const visibleRows = serverPaged
    ? entries
    : filteredRows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  function setSearch(nextSearch: string) {
    setSearchState(nextSearch);
    setPage(1);
  }

  function selectTrack(track: DataTrack) {
    if (track === activeTrack) {
      return;
    }
    const nextPreferences = { activeTrack: track, activeMetric };
    setLeaderboardPreferences(nextPreferences);
    writePreference(LEADERBOARD_STORAGE_KEY, nextPreferences);
    setSort(DEFAULT_LEADERBOARD_SORT);
    setPage(1);
    setSelected(new Set());
  }

  function selectMetric(metric: LeaderboardMetric) {
    if (metric === activeMetric) {
      return;
    }
    const nextPreferences = { activeTrack, activeMetric: metric };
    setLeaderboardPreferences(nextPreferences);
    writePreference(LEADERBOARD_STORAGE_KEY, nextPreferences);
    setSort(DEFAULT_LEADERBOARD_SORT);
    setPage(1);
    setSelected(new Set());
  }

  function toggleSort(key: keyof LeaderboardEntry) {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: defaultLeaderboardSortDirection(key, activeMetric) }
    );
    setPage(1);
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

  function compare() {
    if (selected.size < 2) {
      return;
    }
    const params = new URLSearchParams();
    selected.forEach((id) => params.append("submission_id", id));
    navigate(`/compare?${params.toString()}`);
  }

  if (isLoading) {
    return (
      <section className={styles.view} aria-label={t("leaderboard.loadingTitle")}>
        <div className={styles.loadingState} role="status" aria-live="polite">
          <LoaderCircle aria-hidden="true" className={styles.spinner} size={28} />
          <div>
            <h3>{t("leaderboard.loadingTitle")}</h3>
            <p className={styles.muted}>{t("leaderboard.loadingDescription")}</p>
          </div>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className={styles.view} aria-label={t("leaderboard.errorTitle")}>
        <ErrorState
          title={t("leaderboard.errorTitle")}
          message={error.message}
          onRetry={refetch}
        />
      </section>
    );
  }

  const lastUpdated =
    data && data.rows.length > 0
      ? new Date(
          Math.max(...data.rows.map((row) => new Date(row.submitted_at).getTime()))
        ).toISOString()
      : new Date().toISOString();

  const pageStatus = leaderboardPageStatus(data?.rows ?? []);

  const columns: DataTableColumn<LeaderboardEntry>[] = [
    {
      key: "rank",
      header: t("leaderboard.rank"),
      render: (row) => <RankCell badge={row.badge} rank={row.rank} />,
      sortKey: "rank"
    },
    {
      key: "team",
      header: t("leaderboard.team"),
      render: (row) => (
        <Link
          aria-label={t("leaderboard.viewSubmission", { team: row.teamName })}
          className={styles.entryLink}
          to={`/submissions/${row.id}`}
        >
          {row.teamName}
          <ExternalLink aria-hidden="true" size={14} />
        </Link>
      ),
      sortKey: "teamName"
    },
    {
      key: "metric",
      header: t(metricLabelKey(activeMetric)),
      render: (row) => formatMetricValue(row.metricValue, activeMetric, language),
      sortKey: "metricValue",
      align: "right"
    },
    {
      key: "status",
      header: t("leaderboard.status"),
      render: (row) => <Badge status={toBadgeStatus(row.status)} label={t(statusLabelKey(row.status))} />,
      sortKey: "status"
    },
    {
      key: "submitted",
      header: t("leaderboard.submitted"),
      render: (row) => formatDateTime(row.submittedAt, language),
      sortKey: "submittedAt"
    }
  ];

  return (
    <section className={styles.view} aria-labelledby="leaderboard-title">
      <header className={styles.header}>
        <div>
          <p className={styles.muted}>{t("leaderboard.eyebrow")}</p>
          <h2 id="leaderboard-title">{t("leaderboard.title")}</h2>
          <p className={styles.muted}>{t("leaderboard.updatedAt", { time: formatDateTime(lastUpdated, language) })}</p>
        </div>
        <Badge status={pageStatus.status} label={t(pageStatus.labelKey)} />
      </header>

      <div
        aria-label={t("leaderboard.trackSelectLabel")}
        className={styles.trackTabs}
        role="group"
      >
        {LEADERBOARD_TRACKS.map((track) => {
          const selectedTrack = activeTrack === track;
          return (
            <Button
              key={track}
              aria-pressed={selectedTrack}
              className={[
                styles.trackTab,
                selectedTrack ? styles.activeTrackTab : ""
              ].join(" ")}
              onClick={() => selectTrack(track)}
              variant="ghost"
            >
              {t(dataTrackLabelKey(track))}
            </Button>
          );
        })}
      </div>

      <div className={styles.toolbar}>
        <div className={styles.toolbarMain}>
          <nav className={styles.tabs} role="tablist" aria-label={t("leaderboard.metricTabsLabel")}>
            {LEADERBOARD_METRICS.map((metric) => {
              const selectedMetric = activeMetric === metric;
              return (
                <Button
                  key={metric}
                  aria-controls="leaderboard-panel"
                  aria-selected={selectedMetric}
                  className={[styles.tab, selectedMetric ? styles.activeTab : ""].join(" ")}
                  id={`leaderboard-tab-${metric}`}
                  onClick={() => selectMetric(metric)}
                  role="tab"
                  variant="ghost"
                >
                  {t(metricLabelKey(metric))}
                </Button>
              );
            })}
          </nav>

          <label className={styles.search}>
            <Search aria-hidden="true" size={17} />
            <input
              aria-label={t("leaderboard.searchPlaceholder")}
              placeholder={t("leaderboard.searchPlaceholder")}
              role="searchbox"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
        </div>

        <div className={styles.toolbarAction}>
          <Button disabled={selected.size < 2} onClick={compare} variant="primary">
            {t("leaderboard.compareSelected")}
          </Button>
        </div>
      </div>

      <section
        className={styles.panel}
        aria-labelledby={`leaderboard-tab-${activeMetric}`}
        id="leaderboard-panel"
        role="tabpanel"
      >
        <div className={styles.panelHeader}>
          <div>
            <h3 id="leaderboard-table-title">
              {t("leaderboard.rankingTitle", {
                track: t(dataTrackLabelKey(activeTrack)),
                metric: t(metricLabelKey(activeMetric))
              })}
            </h3>
            <p className={styles.muted}>
              {selected.size > 0
                ? t("leaderboard.selectedCount", { count: selected.size })
                : t("leaderboard.submissionsShown", { count: visibleRows.length })}
            </p>
          </div>
        </div>
        <div aria-atomic="true" aria-live="polite" className={styles.visuallyHidden}>
          {t("leaderboard.submissionsShown", { count: visibleRows.length })}.{" "}
          {t("common.sortBy", {
            header:
              sort.key === "rank"
                ? t("leaderboard.rank")
                : sort.key === "teamName"
                  ? t("leaderboard.team")
                  : sort.key === "metricValue"
                    ? t(metricLabelKey(activeMetric))
                    : sort.key === "status"
                      ? t("leaderboard.status")
                      : t("leaderboard.submitted")
          })}
          .
        </div>
        <DataTable
          caption={t("leaderboard.rankingTitle", {
            track: t(dataTrackLabelKey(activeTrack)),
            metric: t(metricLabelKey(activeMetric))
          })}
          columns={columns}
          empty={
            search.trim() ? (
              <EmptyState
                action={
                  <Button
                    aria-label={t("common.close")}
                    onClick={() => setSearch("")}
                    variant="ghost"
                  >
                    <X aria-hidden="true" size={16} />
                  </Button>
                }
                description={t("leaderboard.noRankedDescription")}
                title={t("leaderboard.noRankedTitle")}
              />
            ) : (
              <EmptyState
                description={t("leaderboard.noRankedDescription")}
                title={t("leaderboard.noRankedTitle")}
              />
            )
          }
          getRowId={(row) => row.id}
          getRowLabel={(row) => row.teamName}
          onSelectRow={toggleSelection}
          onSort={(key) => toggleSort(key as keyof LeaderboardEntry)}
          rows={visibleRows}
          selectedRowIds={selected}
          sort={sort}
        />
      </section>

      <footer className={styles.pagination}>
        <Button
          aria-label={t("leaderboard.previousPage")}
          disabled={safePage <= 1}
          variant="ghost"
          onClick={() => setPage(safePage - 1)}
        >
          {t("common.previous")}
        </Button>
        <span className={styles.pageInfo}>
          {t("common.pageInfo", { page: safePage, totalPages })}
        </span>
        <Button
          aria-label={t("leaderboard.nextPage")}
          disabled={safePage >= totalPages}
          variant="ghost"
          onClick={() => setPage(safePage + 1)}
        >
          {t("common.next")}
        </Button>
      </footer>
    </section>
  );
}

function RankCell({ badge, rank }: { badge: string | null; rank: number }) {
  const { t } = useI18n();
  const ariaLabel = badge
    ? t("leaderboard.medalRank", { badge, rank })
    : t("leaderboard.rankLabel", { rank });
  const tierClass = badge && badge in styles ? styles[badge] : "";
  return (
    <span aria-label={ariaLabel} className={[styles.rank, tierClass].join(" ")}>
      {badge ? <Medal aria-hidden="true" size={16} /> : null}
      {rank}
    </span>
  );
}

function metricLabelKey(metric: LeaderboardMetric): string {
  switch (metric) {
    case "max_drawdown":
      return "leaderboard.maxdd";
    case "calmar":
      return "leaderboard.calmar";
    default:
      return "leaderboard.sharpe";
  }
}

function formatMetricValue(
  value: number | null,
  metric: LeaderboardMetric,
  language: "en" | "zh"
): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }
  if (metric === "max_drawdown") {
    return formatPercent(Math.abs(value), language);
  }
  return formatScore(value, language);
}

function leaderboardSortKeyToApi(key: keyof LeaderboardEntry): string {
  switch (key) {
    case "teamName":
      return "team_name";
    case "metricValue":
      return "metric_value";
    case "submittedAt":
      return "submitted_at";
    default:
      return key;
  }
}

function defaultLeaderboardSortDirection(
  key: keyof LeaderboardEntry,
  activeMetric: LeaderboardMetric
): SortState["direction"] {
  if (key === "metricValue") {
    return activeMetric === "max_drawdown" ? "asc" : "desc";
  }
  if (key === "submittedAt") {
    return "desc";
  }
  return "asc";
}

function statusLabelKey(status: string): string {
  switch (status) {
    case "completed":
      return "common.scored";
    case "queued":
      return "common.queued";
    default:
      return `common.${status}`;
  }
}

function toBadgeStatus(status: string): BadgeStatus {
  if (status === "completed") return "scored";
  if (status === "queued") return "queued";
  if (
    status === "online" ||
    status === "degraded" ||
    status === "offline" ||
    status === "queued" ||
    status === "running" ||
    status === "scored" ||
    status === "failed" ||
    status === "stale"
  ) {
    return status;
  }
  return "running";
}

function leaderboardPageStatus(
  rows: { status: string; stale: boolean; eligible: boolean }[]
): { status: BadgeStatus; labelKey: string } {
  if (rows.some((row) => row.status === "running")) {
    return { status: "online", labelKey: "common.liveScoring" };
  }
  if (rows.some((row) => row.stale) && !rows.some((row) => row.eligible)) {
    return { status: "stale", labelKey: "common.stale" };
  }
  return { status: "scored", labelKey: "common.standby" };
}
