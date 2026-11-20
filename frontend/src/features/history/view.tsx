import { AlertTriangle, ExternalLink, FileCode, FileText, Filter, GitCompare, Search } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useI18n } from "../../shared/i18n";
import { readObjectPreference, writePreference } from "../../shared/preferences/storage";
import {
  DATA_TRACKS,
  dataTrackLabelKey,
  isDataTrack,
  type DataTrack
} from "../../shared/submissions/dataTrack";
import { useParticipantSession } from "../session/model";
import { prefetchSubmissionDetail } from "../submission-detail/model";
import { Badge, type BadgeStatus } from "../../shared/ui/Badge/Badge";
import { Button } from "../../shared/ui/Button/Button";
import { DataTable, type DataTableColumn } from "../../shared/ui/DataTable/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { SubmissionSourceDialog } from "../../shared/ui/SubmissionSourceDialog";
import {
  DEFAULT_HISTORY_SORT,
  filterHistoryEntries,
  formatHistoryMetric,
  formatHistoryPercent,
  sortHistoryEntries,
  toHistoryEntries,
  useSubmissionHistory,
  useSubmissionRawError,
  useSubmissionSource,
  type HistoryEntry,
  type HistorySortKey,
  type HistorySortState
} from "./model";
import styles from "./view.module.css";

const PAGE_SIZE = 10;
const STATUS_OPTIONS = ["all", "completed", "running", "queued", "failed"];
const TRACK_OPTIONS: Array<DataTrack | "all"> = ["all", ...DATA_TRACKS];
const HISTORY_STORAGE_KEY = "quantfish-history-preferences";
const HISTORY_SORT_KEYS: HistorySortKey[] = [
  "id",
  "submissionNumber",
  "teamName",
  "status",
  "dataTrack",
  "submittedAt",
  "scoredAt",
  "calmar",
  "sharpe",
  "totalReturn",
  "drawdown"
];

type HistoryPreferences = {
  status: string;
  dataTrack: DataTrack | "all";
  myAccountOnly: boolean;
  sort: HistorySortState;
};

const DEFAULT_HISTORY_PREFERENCES: HistoryPreferences = {
  status: "all",
  dataTrack: "all",
  myAccountOnly: false,
  sort: DEFAULT_HISTORY_SORT
};

function parseHistoryStatus(value: unknown): string | null {
  return STATUS_OPTIONS.includes(String(value)) ? String(value) : null;
}

function parseHistoryDataTrack(value: unknown): DataTrack | "all" | null {
  if (value === "all" || isDataTrack(value)) {
    return value;
  }
  return null;
}

function parseHistorySort(value: unknown): HistorySortState | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const sort = value as Record<string, unknown>;
  if (
    HISTORY_SORT_KEYS.includes(sort.key as HistorySortKey) &&
    (sort.direction === "asc" || sort.direction === "desc")
  ) {
    return {
      key: sort.key as HistorySortKey,
      direction: sort.direction
    };
  }
  return null;
}

function readHistoryPreferences(): HistoryPreferences {
  return readObjectPreference(
    HISTORY_STORAGE_KEY,
    DEFAULT_HISTORY_PREFERENCES,
    {
      status: parseHistoryStatus,
      dataTrack: parseHistoryDataTrack,
      myAccountOnly: (value) => (typeof value === "boolean" ? value : null),
      sort: parseHistorySort
    }
  );
}

export function HistoryView() {
  const { t, language } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const participantSession = useParticipantSession();
  const [search, setSearch] = useState("");
  const [{ status, dataTrack, myAccountOnly, sort }, setHistoryPreferences] =
    useState<HistoryPreferences>(readHistoryPreferences);
  const [page, setPage] = useState(1);
  const [selectedRowsById, setSelectedRowsById] = useState<Map<string, HistoryEntry>>(
    () => new Map()
  );
  const [downloadingPdfs, setDownloadingPdfs] = useState<Set<string>>(new Set());
  const [rawErrorModal, setRawErrorModal] = useState<{
    row: HistoryEntry;
    rawError?: string;
    error?: string;
  } | null>(null);
  const [sourceModal, setSourceModal] = useState<{
    row: HistoryEntry;
    source?: string;
    error?: string;
  } | null>(null);
  const currentTeamId = participantSession.data?.authenticated
    ? participantSession.data.team_id ?? null
    : null;
  const effectiveMyAccountOnly = Boolean(currentTeamId) && myAccountOnly;
  const historyQueryParams = useMemo(
    () => ({
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
      search,
      status,
      dataTrack,
      teamId: effectiveMyAccountOnly ? currentTeamId : null,
      sortBy: historySortKeyToApi(sort.key),
      sortDir: sort.direction
    }),
    [currentTeamId, dataTrack, effectiveMyAccountOnly, page, search, sort, status]
  );
  const { data, error, isLoading, refetch } = useSubmissionHistory(historyQueryParams);
  const rawErrorLookup = useSubmissionRawError();
  const sourceLookup = useSubmissionSource();

  const entries = useMemo(() => toHistoryEntries(data?.submissions ?? []), [data]);
  const totalCountFromServer = (data as { total_count?: number } | undefined)?.total_count;
  const serverPaged = typeof totalCountFromServer === "number";
  const filteredRows = useMemo(
    () => {
      if (serverPaged) {
        return entries;
      }
      return sortHistoryEntries(
        filterHistoryEntries(entries, {
          search,
          status,
          dataTrack,
          currentTeamId,
          myAccountOnly: effectiveMyAccountOnly
        }),
        sort
      );
    },
    [currentTeamId, dataTrack, effectiveMyAccountOnly, entries, search, serverPaged, sort, status]
  );
  const totalRows = serverPaged ? totalCountFromServer : filteredRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const visibleRows = serverPaged
    ? entries
    : filteredRows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const selectedIds = useMemo(() => new Set(selectedRowsById.keys()), [selectedRowsById]);
  const selectedComparableRows = useMemo(
    () =>
      Array.from(selectedRowsById.values()).filter((entry) => entry.compareSelectable),
    [selectedRowsById]
  );

  // The result set can shrink under the current page (another team's submission
  // disappears, a filter now matches less). Clamp during render rather than in an
  // effect so the table never commits an out-of-range page; `totalPages` only
  // becomes known after the query answers, which is why it cannot be derived.
  if (page !== safePage) {
    setPage(safePage);
  }

  function updateSearch(value: string) {
    setSearch(value);
    setPage(1);
  }

  function saveHistoryPreferences(next: HistoryPreferences) {
    setHistoryPreferences(next);
    writePreference(HISTORY_STORAGE_KEY, next);
  }

  function updateStatus(value: string) {
    saveHistoryPreferences({ status: value, dataTrack, myAccountOnly, sort });
    setPage(1);
  }

  function updateDataTrack(value: string) {
    const nextTrack = isDataTrack(value) ? value : "all";
    saveHistoryPreferences({ status, dataTrack: nextTrack, myAccountOnly, sort });
    setPage(1);
  }

  function updateMyAccountOnly(checked: boolean) {
    saveHistoryPreferences({ status, dataTrack, myAccountOnly: checked, sort });
    setPage(1);
    setSelectedRowsById(new Map());
  }

  function toggleSort(key: HistorySortKey) {
    const nextSort: HistorySortState =
      sort.key === key
        ? { key, direction: sort.direction === "asc" ? "desc" : "asc" }
        : { key, direction: key === "submittedAt" ? "desc" : "asc" };
    saveHistoryPreferences({ status, dataTrack, myAccountOnly, sort: nextSort });
    setPage(1);
  }

  function toggleSelected(rowId: string) {
    const row = visibleRows.find((entry) => entry.id === rowId);
    setSelectedRowsById((current) => {
      const next = new Map(current);
      if (next.has(rowId)) {
        next.delete(rowId);
      } else if (row) {
        next.set(rowId, row);
      }
      return next;
    });
  }

  function compareSelected() {
    if (selectedComparableRows.length < 2) {
      return;
    }
    const params = new URLSearchParams();
    for (const row of selectedComparableRows) {
      params.append("submission_id", row.id);
    }
    navigate(`/compare?${params.toString()}`);
  }

  function prefetchCompletedSubmission(row: HistoryEntry) {
    if (row.status !== "completed") {
      return;
    }
    void prefetchSubmissionDetail(queryClient, row.id);
  }

  function openRawError(row: HistoryEntry) {
    setSourceModal(null);
    setRawErrorModal({ row, rawError: row.rawError ?? undefined });
    if (row.rawError) {
      return;
    }
    rawErrorLookup.mutate(row.id, {
      onSuccess: (rawError) =>
        setRawErrorModal((current) =>
          current?.row.id === row.id ? { row, rawError } : current
        ),
      onError: (lookupError) =>
        setRawErrorModal((current) =>
          current?.row.id === row.id
            ? {
                row,
                error:
                  lookupError instanceof Error
                    ? lookupError.message
                    : t("history.errorTitle")
              }
            : current
        )
    });
  }

  function closeRawError() {
    setRawErrorModal(null);
    rawErrorLookup.reset();
  }

  function canViewSource(row: HistoryEntry): boolean {
    return Boolean(
      participantSession.data?.authenticated &&
        currentTeamId &&
        row.teamId === currentTeamId
    );
  }

  function openSource(row: HistoryEntry) {
    if (!canViewSource(row)) {
      return;
    }
    setRawErrorModal(null);
    setSourceModal({ row });
    sourceLookup.mutate(row.id, {
      onSuccess: (source) =>
        setSourceModal((current) =>
          current?.row.id === row.id ? { row, source } : current
        ),
      onError: (lookupError) =>
        setSourceModal((current) =>
          current?.row.id === row.id
            ? {
                row,
                error:
                  lookupError instanceof Error
                    ? lookupError.message
                    : t("history.sourceCodeUnavailable")
              }
            : current
        )
    });
  }

  function closeSource() {
    setSourceModal(null);
    sourceLookup.reset();
  }

  async function downloadPdf(row: HistoryEntry) {
    const submissionId = row.id;
    setDownloadingPdfs((prev) => new Set(prev).add(submissionId));
    try {
      const response = await fetch(
        `${window.location.origin}/api/submissions/${encodeURIComponent(submissionId)}/report`
      );
      if (!response.ok) {
        throw new Error(response.status === 404 ? t("history.reportUnavailable") : t("history.reportFailed"));
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `report_${row.submissionLabel.replace("#", "")}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : t("history.reportFailed"));
    } finally {
      setDownloadingPdfs((prev) => {
        const next = new Set(prev);
        next.delete(submissionId);
        return next;
      });
    }
  }

  if (isLoading) {
    return (
      <section aria-label={t("history.loadingTitle")} className={styles.view}>
        <EmptyState
          description={t("history.loadingDescription")}
          title={t("history.loadingTitle")}
        />
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label={t("history.errorTitle")} className={styles.view}>
        <ErrorState
          message={error.message}
          onRetry={refetch}
          title={t("history.errorTitle")}
        />
      </section>
    );
  }

  const columns: DataTableColumn<HistoryEntry>[] = [
    {
      key: "submission",
      header: t("history.submission"),
      render: (row) => (
        <Link
          aria-label={t("history.viewSubmission", { label: row.submissionLabel })}
          className={styles.labelLink}
          onFocus={() => prefetchCompletedSubmission(row)}
          onMouseEnter={() => prefetchCompletedSubmission(row)}
          to={`/submissions/${row.id}`}
        >
          {row.submissionLabel}
          <ExternalLink aria-hidden="true" size={14} />
        </Link>
      ),
      sortKey: "submissionNumber"
    },
    {
      key: "team",
      header: t("history.team"),
      render: (row) => row.teamName,
      sortKey: "teamName"
    },
    {
      key: "status",
      header: t("history.status"),
      render: (row) => (
        <Badge
          label={t(statusLabelKey(row.status, row.isStale))}
          status={badgeStatus(row.status, row.isStale)}
        />
      ),
      sortKey: "status"
    },
    {
      key: "track",
      header: t("history.track"),
      render: (row) => t(dataTrackLabelKey(row.dataTrack)),
      sortKey: "dataTrack"
    },
    {
      key: "calmar",
      header: t("history.calmarScore"),
      render: (row) => formatHistoryMetric(row.calmar, 3),
      sortKey: "calmar",
      align: "right"
    },
    {
      key: "sharpe",
      header: t("history.sharpe"),
      render: (row) => formatHistoryMetric(row.sharpe),
      sortKey: "sharpe",
      align: "right"
    },
    {
      key: "return",
      header: t("history.totalReturn"),
      render: (row) => formatHistoryPercent(row.totalReturn),
      sortKey: "totalReturn",
      align: "right"
    },
    {
      key: "drawdown",
      header: t("history.drawdown"),
      render: (row) => formatHistoryPercent(row.drawdown),
      sortKey: "drawdown",
      align: "right"
    },
    {
      key: "submitted",
      header: t("history.submitted"),
      render: (row) => formatDateTime(row.submittedAt, language),
      sortKey: "submittedAt"
    },
    {
      key: "scored",
      header: t("history.scored"),
      render: (row) => row.scoredAt ? formatDateTime(row.scoredAt, language) : "—",
      sortKey: "scoredAt"
    },
    {
      key: "error",
      header: t("history.error"),
      render: (row) =>
        row.errorMessage || row.rawError || row.hasRawError ? (
          <div className={styles.errorCell}>
            {row.errorMessage ? <span className={styles.errorText}>{row.errorMessage}</span> : null}
            {row.rawError || row.hasRawError ? (
              <Button
                aria-label={t("history.viewRawErrorFor", { label: row.submissionLabel })}
                onClick={() => openRawError(row)}
                variant="ghost"
              >
                <AlertTriangle aria-hidden="true" size={15} />
                {t("history.viewRawError")}
              </Button>
            ) : null}
          </div>
        ) : (
          "—"
        )
    },
    {
      key: "action",
      header: t("history.action"),
      render: (row) => {
        const isCompleted = row.status === "completed";
        const isDownloading = downloadingPdfs.has(row.id);
        return (
          <div className={styles.actionCell}>
            <Button
              aria-label={isCompleted ? t("history.downloadPdfFor", { label: row.submissionLabel }) : t("history.reportUnavailable")}
              disabled={!isCompleted || isDownloading}
              onClick={() => downloadPdf(row)}
              title={isCompleted ? t("history.downloadPdf") : t("history.reportUnavailable")}
              variant="ghost"
            >
              <FileText aria-hidden="true" size={15} />
              {isDownloading ? t("history.generatingReport") : t("history.downloadPdf")}
            </Button>
            {canViewSource(row) ? (
              <Button
                aria-label={t("history.viewCodeFor", { label: row.submissionLabel })}
                onClick={() => openSource(row)}
                variant="ghost"
              >
                <FileCode aria-hidden="true" size={15} />
                {t("history.viewCode")}
              </Button>
            ) : null}
          </div>
        );
      }
    },
  ];

  return (
    <section aria-labelledby="history-title" className={styles.view}>
      <header className={styles.header}>
        <div>
          <p className={styles.muted}>{t("history.eyebrow")}</p>
          <h1 id="history-title">{t("history.title")}</h1>
          <p className={styles.muted}>{t("history.description")}</p>
        </div>
      </header>

      <div className={styles.toolbar}>
        <label className={styles.search}>
          <Search aria-hidden="true" size={17} />
          <input
            aria-label={t("history.searchPlaceholder")}
            placeholder={t("history.searchPlaceholder")}
            role="searchbox"
            value={search}
            onChange={(event) => updateSearch(event.target.value)}
          />
        </label>

        <label className={styles.statusFilter}>
          <Filter aria-hidden="true" size={17} />
          <select
            aria-label={t("history.statusFilter")}
            value={status}
            onChange={(event) => updateStatus(event.target.value)}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(option === "all" ? "history.allStatuses" : statusLabelKey(option))}
              </option>
            ))}
          </select>
        </label>

        <label className={styles.statusFilter}>
          <Filter aria-hidden="true" size={17} />
          <select
            aria-label={t("history.trackFilter")}
            value={dataTrack}
            onChange={(event) => updateDataTrack(event.target.value)}
          >
            {TRACK_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {t(option === "all" ? "history.allTracks" : dataTrackLabelKey(option))}
              </option>
            ))}
          </select>
        </label>

        <div className={styles.accountToggleWrap}>
          <label className={styles.accountToggle}>
            <input
              aria-describedby={currentTeamId ? undefined : "history-my-submissions-hint"}
              checked={effectiveMyAccountOnly}
              disabled={!currentTeamId}
              onChange={(event) => updateMyAccountOnly(event.target.checked)}
              type="checkbox"
            />
            <span>{t("history.mySubmissionsOnly")}</span>
          </label>
          {!currentTeamId ? (
            <p className={styles.helper} id="history-my-submissions-hint">
              {t("history.mySubmissionsLoginHint")}
            </p>
          ) : null}
        </div>
      </div>

      <section aria-labelledby="history-table-title" className={styles.panel}>
        <div className={styles.panelHeader}>
          <div>
            <h3 id="history-table-title">{t("history.tableTitle")}</h3>
            <p className={styles.muted}>
              {t("history.uploadsShown", { count: totalRows })}
            </p>
          </div>
          <Button
            className={styles.compareButton}
            disabled={selectedComparableRows.length < 2}
            onClick={compareSelected}
            variant="ghost"
          >
            <GitCompare aria-hidden="true" size={15} />
            {t("history.compareSelected")}
          </Button>
        </div>

        <DataTable
          caption={t("history.title")}
          columns={columns}
          empty={
            <EmptyState
              description={t("history.emptyDescription")}
              title={t("history.emptyTitle")}
            />
          }
          getRowId={(row) => row.id}
          getRowLabel={(row) => row.submissionLabel}
          isRowSelectable={(row) => row.compareSelectable}
          onSelectRow={toggleSelected}
          onSort={(key) => toggleSort(key as HistorySortKey)}
          rows={visibleRows}
          selectedRowIds={selectedIds}
          sort={sort}
        />
      </section>

      <footer className={styles.pagination}>
        <Button
          aria-label={t("history.previousPage")}
          disabled={safePage <= 1}
          onClick={() => setPage(safePage - 1)}
          variant="ghost"
        >
          {t("common.previous")}
        </Button>
        <span className={styles.pageInfo}>
          {t("common.pageInfo", { page: safePage, totalPages })}
        </span>
        <Button
          aria-label={t("history.nextPage")}
          disabled={safePage >= totalPages}
          onClick={() => setPage(safePage + 1)}
          variant="ghost"
        >
          {t("common.next")}
        </Button>
      </footer>

      {rawErrorModal ? (
        <div className={styles.dialogBackdrop}>
          <div
            aria-label={t("history.rawErrorTitle", { label: rawErrorModal.row.submissionLabel })}
            aria-modal="true"
            className={styles.dialog}
            role="dialog"
          >
            <div className={styles.modalHeader}>
              <h2>{t("history.rawErrorTitle", { label: rawErrorModal.row.submissionLabel })}</h2>
              <Button
                aria-label={t("history.closeRawError")}
                onClick={closeRawError}
                type="button"
                variant="ghost"
              >
                {t("history.closeRawError")}
              </Button>
            </div>
            {rawErrorModal.rawError ? <pre>{rawErrorModal.rawError}</pre> : null}
            {!rawErrorModal.rawError && rawErrorModal.error ? (
              <p className={styles.muted}>{rawErrorModal.error}</p>
            ) : null}
            {!rawErrorModal.rawError && !rawErrorModal.error ? (
              <p className={styles.muted}>{t("common.loading")}</p>
            ) : null}
          </div>
        </div>
      ) : null}

      {sourceModal ? (
        <SubmissionSourceDialog
          closeLabel={t("history.closeSourceCode")}
          error={sourceModal.error}
          isLoading={sourceLookup.isPending}
          loadingLabel={t("history.loadingSourceCode")}
          onClose={closeSource}
          pythonLabel={t("history.pythonSourceCode")}
          source={sourceModal.source}
          title={t("history.sourceCodeTitle", { label: sourceModal.row.submissionLabel })}
          unavailableLabel={t("history.sourceCodeUnavailable")}
        />
      ) : null}
    </section>
  );
}

function historySortKeyToApi(key: HistorySortKey): string {
  switch (key) {
    case "submissionNumber":
      return "submission_number";
    case "teamName":
      return "team_name";
    case "dataTrack":
      return "data_track";
    case "submittedAt":
      return "submitted_at";
    case "scoredAt":
      return "scored_at";
    case "totalReturn":
      return "total_return";
    case "drawdown":
      return "max_drawdown";
    default:
      return key;
  }
}

function formatDateTime(value: string, language: "en" | "zh"): string {
  return new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short"
  }).format(new Date(value));
}

function statusLabelKey(status: string, stale = false): string {
  if (stale) {
    return "common.stale";
  }
  switch (status) {
    case "completed":
      return "common.scored";
    case "queued":
      return "common.queued";
    case "running":
      return "common.running";
    case "failed":
      return "common.failed";
    default:
      return `common.${status}`;
  }
}

function badgeStatus(status: string, stale = false): BadgeStatus {
  if (stale) return "stale";
  if (status === "completed") return "scored";
  if (status === "queued" || status === "running" || status === "failed") {
    return status;
  }
  return "offline";
}
