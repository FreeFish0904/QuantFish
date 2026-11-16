import { AlertTriangle, FileCode, RotateCcw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { useI18n } from "../../../shared/i18n";
import {
  dataTrackLabelKey,
  dataTrackSearchText
} from "../../../shared/submissions/dataTrack";
import { Button } from "../../../shared/ui/Button/Button";
import { SubmissionSourceDialog } from "../../../shared/ui/SubmissionSourceDialog";
import {
  useAdminSubmissionRawError,
  useAdminSubmissionSource,
  useDeleteAdminSubmissions,
  type AdminSubmissionRecord
} from "../model";
import styles from "./Panels.module.css";

type DeletePayload = {
  submission_ids: string[];
  force: boolean;
};

type RerunPayload = {
  scope: "all" | "selected";
  submission_ids?: string[];
};

type RerunResult = {
  queued: number;
  skipped: number;
  queued_submission_ids: string[];
  skipped_submission_ids: string[];
};

type TextLookup = {
  mutate: (
    submissionId: string,
    options?: {
      onSuccess?: (value: string) => void;
      onError?: (error: unknown) => void;
    }
  ) => void;
  isPending: boolean;
  reset?: () => void;
};

type SubmissionsPanelProps = {
  submissions?: AdminSubmissionRecord[];
  isDeleting?: boolean;
  isRerunning?: boolean;
  onDelete?: (payload: DeletePayload) => void;
  onRerun?: (
    payload: RerunPayload,
    options?: {
      onSuccess?: (value: RerunResult) => void;
      onError?: (error: unknown) => void;
    }
  ) => void;
  search?: string;
  statusFilter?: string;
  onSearchChange?: (search: string) => void;
  onStatusFilterChange?: (status: string) => void;
  page?: number;
  pageSize?: number;
  totalCount?: number;
  hasNext?: boolean;
  onPageChange?: (page: number) => void;
  sourceLookup?: TextLookup;
  rawErrorLookup?: TextLookup;
};

const activeStatuses = new Set(["queued", "running"]);

function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

function matchesSearch(row: AdminSubmissionRecord, search: string): boolean {
  if (search.length === 0) return true;
  const trackText = dataTrackSearchText(row.dataTrack);
  const haystack = `${row.submissionLabel} ${row.teamName} ${row.id} ${row.filename} ${trackText}`.toLowerCase();
  return haystack.includes(search.toLowerCase());
}

export function SubmissionsPanel({
  submissions = [],
  isDeleting,
  isRerunning,
  onDelete,
  onRerun,
  search,
  statusFilter,
  onSearchChange,
  onStatusFilterChange,
  page = 1,
  pageSize = 25,
  totalCount,
  hasNext = false,
  onPageChange,
  sourceLookup: sourceLookupOverride,
  rawErrorLookup: rawErrorLookupOverride
}: SubmissionsPanelProps) {
  const { t } = useI18n();
  const fallbackDelete = useDeleteAdminSubmissions();
  const defaultSourceLookup = useAdminSubmissionSource();
  const defaultRawErrorLookup = useAdminSubmissionRawError();
  const sourceLookup = sourceLookupOverride ?? defaultSourceLookup;
  const rawErrorLookup = rawErrorLookupOverride ?? defaultRawErrorLookup;
  const [localSearch, setLocalSearch] = useState("");
  const [localStatusFilter, setLocalStatusFilter] = useState("all");
  const [allowActiveDeletion, setAllowActiveDeletion] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [rawErrorModal, setRawErrorModal] = useState<{
    row: AdminSubmissionRecord;
    rawError?: string;
    error?: string;
  } | null>(null);
  const [sourceModal, setSourceModal] = useState<{
    row: AdminSubmissionRecord;
    source?: string;
    error?: string;
  } | null>(null);
  const [confirmingRerunAll, setConfirmingRerunAll] = useState(false);
  const [rerunResult, setRerunResult] = useState<RerunResult | null>(null);
  const [rerunError, setRerunError] = useState<string | null>(null);

  const currentSearch = search ?? localSearch;
  const currentStatusFilter = statusFilter ?? localStatusFilter;
  const serverControlled =
    Boolean(onSearchChange || onStatusFilterChange || onPageChange) ||
    typeof totalCount === "number";
  const activeCount = submissions.filter((submission) => activeStatuses.has(submission.status)).length;
  const visibleRows = useMemo(
    () => {
      if (serverControlled) {
        return submissions;
      }
      return submissions.filter((submission) => {
        const statusMatches = currentStatusFilter === "all" || submission.status === currentStatusFilter;
        return statusMatches && matchesSearch(submission, currentSearch.trim());
      });
    },
    [currentSearch, currentStatusFilter, serverControlled, submissions]
  );

  const selectableVisibleRows = visibleRows.filter((row) => row.selectable || (allowActiveDeletion && activeStatuses.has(row.status)));
  const totalRows = totalCount ?? visibleRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
  const safePage = Math.min(page, totalPages);

  const isSelectable = (row: AdminSubmissionRecord): boolean =>
    row.selectable || (allowActiveDeletion && activeStatuses.has(row.status));

  const openSource = (row: AdminSubmissionRecord) => {
    setRawErrorModal(null);
    setSourceModal({ row });
    sourceLookup.mutate(row.id, {
      onSuccess: (source) => setSourceModal({ row, source }),
      onError: (error) =>
        setSourceModal({
          row,
          error: error instanceof Error ? error.message : t("admin.sourceCodeUnavailable")
        })
    });
  };

  const openRawError = (row: AdminSubmissionRecord) => {
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
      onError: (error) =>
        setRawErrorModal((current) =>
          current?.row.id === row.id
            ? {
                row,
                error: error instanceof Error ? error.message : t("admin.noError")
              }
            : current
        )
    });
  };

  const closeRawError = () => {
    setRawErrorModal(null);
    rawErrorLookup.reset?.();
  };

  const updateSearch = (value: string) => {
    if (onSearchChange) {
      onSearchChange(value);
    } else {
      setLocalSearch(value);
    }
  };

  const updateStatusFilter = (value: string) => {
    if (onStatusFilterChange) {
      onStatusFilterChange(value);
    } else {
      setLocalStatusFilter(value);
    }
  };

  const toggleSelected = (id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllVisible = () => {
    setSelectedIds((current) => {
      const next = new Set(current);
      const allSelected = selectableVisibleRows.every((row) => next.has(row.id));
      for (const row of selectableVisibleRows) {
        if (allSelected) next.delete(row.id);
        else next.add(row.id);
      }
      return next;
    });
  };

  const deleteSelected = () => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    const payload = { submission_ids: ids, force: allowActiveDeletion };
    if (onDelete) onDelete(payload);
    else fallbackDelete.mutate(payload);
    setSelectedIds(new Set());
  };
  const deleting = isDeleting ?? fallbackDelete.isPending;
  const rerunning = Boolean(isRerunning);

  const rerunOptions = {
    onSuccess: (value: RerunResult) => {
      setRerunResult(value);
      setRerunError(null);
    },
    onError: (error: unknown) => {
      setRerunResult(null);
      setRerunError(error instanceof Error ? error.message : t("admin.rerunFailed"));
    }
  };

  const rerunSelected = () => {
    if (!onRerun) return;
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    onRerun({ scope: "selected", submission_ids: ids }, rerunOptions);
    setSelectedIds(new Set());
  };

  const rerunAll = () => {
    if (!onRerun) return;
    onRerun({ scope: "all" }, rerunOptions);
    setConfirmingRerunAll(false);
  };

  return (
    <div className={styles.stack}>
      <div className={styles.submissionToolbar}>
        <label className={styles.inlineField} htmlFor="admin-submission-search">
          <span>{t("admin.searchSubmissions")}</span>
          <input
            id="admin-submission-search"
            onChange={(event) => updateSearch(event.target.value)}
            role="searchbox"
            type="search"
            value={currentSearch}
          />
        </label>
        <label className={styles.inlineField} htmlFor="admin-submission-status">
          <span>{t("admin.filterStatus")}</span>
          <select
            id="admin-submission-status"
            onChange={(event) => updateStatusFilter(event.target.value)}
            value={currentStatusFilter}
          >
            <option value="all">{t("admin.allStatuses")}</option>
            <option value="queued">{t("common.queued")}</option>
            <option value="running">{t("common.running")}</option>
            <option value="completed">{t("common.scored")}</option>
            <option value="failed">{t("common.failed")}</option>
          </select>
        </label>
        {activeCount > 0 ? (
          <label className={styles.toggle} htmlFor="admin-allow-active-deletion">
            <input
              checked={allowActiveDeletion}
              id="admin-allow-active-deletion"
              onChange={(event) => {
                setAllowActiveDeletion(event.target.checked);
                if (!event.target.checked) {
                  setSelectedIds((current) => {
                    const next = new Set(current);
                    for (const row of submissions) {
                      if (activeStatuses.has(row.status)) next.delete(row.id);
                    }
                    return next;
                  });
                }
              }}
              type="checkbox"
            />
            <span>{t("admin.allowActiveDeletion")}</span>
            <strong>{t("admin.activeCount", { count: activeCount })}</strong>
          </label>
        ) : null}
      </div>

      <div className={styles.bulkBar}>
        <Button disabled={selectableVisibleRows.length === 0} onClick={selectAllVisible} type="button" variant="ghost">
          {t("admin.selectAllVisible")}
        </Button>
        <Button disabled={selectedIds.size === 0 || deleting} onClick={deleteSelected} type="button" variant="ghost">
          <Trash2 aria-hidden="true" size={15} />
          {t("admin.deleteSelected")}
        </Button>
        {onRerun ? (
          <>
            <Button
              disabled={selectedIds.size === 0 || rerunning}
              onClick={rerunSelected}
              type="button"
              variant="ghost"
            >
              <RotateCcw aria-hidden="true" size={15} />
              {t("admin.rerunSelected")}
            </Button>
            <Button
              disabled={rerunning}
              onClick={() => setConfirmingRerunAll(true)}
              type="button"
              variant="ghost"
            >
              <RotateCcw aria-hidden="true" size={15} />
              {t("admin.rerunAll")}
            </Button>
          </>
        ) : null}
      </div>

      {rerunResult ? (
        <p className={styles.muted} role="status">
          {t("admin.rerunResult", { queued: rerunResult.queued, skipped: rerunResult.skipped })}
        </p>
      ) : null}
      {rerunError ? (
        <p className={styles.muted} role="alert">
          {rerunError}
        </p>
      ) : null}

      <div
        aria-label={`${t("admin.submissions")}. ${t("common.tableScrollHint")}`}
        className={styles.tableWrap}
        data-scroll-hint={t("common.tableScrollHint")}
        role="region"
        tabIndex={0}
      >
        <table aria-label={t("admin.submissions")} className={styles.table}>
          <caption>{t("admin.submissions")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("common.select")}</th>
              <th scope="col">{t("admin.id")}</th>
              <th scope="col">{t("admin.team")}</th>
              <th scope="col">{t("admin.type")}</th>
              <th scope="col">{t("admin.track")}</th>
              <th scope="col">{t("admin.status")}</th>
              <th scope="col">{t("admin.filename")}</th>
              <th scope="col">{t("admin.submittedTime")}</th>
              <th scope="col">{t("admin.finishedTime")}</th>
              <th scope="col">{t("admin.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const selectable = isSelectable(row);
              return (
                <tr key={row.id}>
                  <td>
                    <input
                      aria-label={t("admin.selectSubmission", { id: row.submissionLabel })}
                      checked={selectedIds.has(row.id)}
                      disabled={!selectable}
                      onChange={() => toggleSelected(row.id)}
                      type="checkbox"
                    />
                  </td>
                  <td title={row.id}>
                    <span className={styles.nowrap}>{row.submissionLabel}</span>
                  </td>
                  <td>{row.teamName}</td>
                  <td>{row.type}</td>
                  <td>{t(dataTrackLabelKey(row.dataTrack))}</td>
                  <td>
                    <span className={styles.statusCell}>
                      {row.status === "queued"
                        ? t("common.queued")
                        : row.status === "running"
                          ? t("common.running")
                          : row.status === "completed"
                            ? t("common.scored")
                            : row.status === "failed"
                              ? t("common.failed")
                              : statusLabel(row.status)}
                    </span>
                    {row.stale ? <span className={styles.staleBadge}>{t("common.stale")}</span> : null}
                  </td>
                  <td>{row.filename}</td>
                  <td>{row.submittedAt}</td>
                  <td>{row.finishedAt ?? "-"}</td>
                  <td>
                    <div className={styles.submissionActions}>
                      <Button
                        aria-label={t("admin.viewCodeFor", { id: row.submissionLabel })}
                        onClick={() => openSource(row)}
                        type="button"
                        variant="ghost"
                      >
                        <FileCode aria-hidden="true" size={15} />
                        {t("admin.viewCode")}
                      </Button>
                      {row.rawError || row.hasRawError ? (
                        <Button
                          aria-label={t("admin.viewRawErrorFor", { id: row.submissionLabel })}
                          onClick={() => openRawError(row)}
                          type="button"
                          variant="ghost"
                        >
                          <AlertTriangle aria-hidden="true" size={15} />
                          {t("admin.viewRawError")}
                        </Button>
                      ) : (
                        <span className={styles.muted}>{t("admin.noError")}</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <footer className={styles.pagination}>
        <Button
          aria-label={t("history.previousPage")}
          disabled={!onPageChange || safePage <= 1}
          onClick={() => onPageChange?.(safePage - 1)}
          type="button"
          variant="ghost"
        >
          {t("common.previous")}
        </Button>
        <span className={styles.muted}>
          {t("common.pageInfo", { page: safePage, totalPages })}
        </span>
        <Button
          aria-label={t("history.nextPage")}
          disabled={!onPageChange || (!hasNext && safePage >= totalPages)}
          onClick={() => onPageChange?.(safePage + 1)}
          type="button"
          variant="ghost"
        >
          {t("common.next")}
        </Button>
      </footer>

      {rawErrorModal ? (
        <div className={styles.dialogBackdrop}>
          <div
            aria-labelledby="admin-raw-error-title"
            aria-modal="true"
            className={styles.dialog}
            role="dialog"
          >
            <div className={styles.modalHeader}>
              <h2 id="admin-raw-error-title">
                {t("admin.rawErrorTitle", { id: rawErrorModal.row.submissionLabel })}
              </h2>
              <Button onClick={closeRawError} type="button" variant="ghost">
                {t("common.cancel")}
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
          closeLabel={t("common.cancel")}
          error={sourceModal.error}
          isLoading={sourceLookup.isPending}
          loadingLabel={t("admin.loadingSourceCode")}
          onClose={() => setSourceModal(null)}
          pythonLabel={t("admin.pythonSourceCode")}
          source={sourceModal.source}
          title={t("admin.sourceCodeTitle", { id: sourceModal.row.submissionLabel })}
          unavailableLabel={t("admin.sourceCodeUnavailable")}
        />
      ) : null}

      {confirmingRerunAll ? (
        <div className={styles.dialogBackdrop}>
          <div
            aria-labelledby="admin-rerun-all-title"
            aria-modal="true"
            className={styles.dialog}
            role="dialog"
          >
            <div className={styles.modalHeader}>
              <h2 id="admin-rerun-all-title">{t("admin.rerunAllTitle")}</h2>
              <Button onClick={() => setConfirmingRerunAll(false)} type="button" variant="ghost">
                {t("common.cancel")}
              </Button>
            </div>
            <p className={styles.muted}>{t("admin.rerunAllDescription")}</p>
            <div className={styles.bulkBar}>
              <Button onClick={() => setConfirmingRerunAll(false)} type="button" variant="ghost">
                {t("common.cancel")}
              </Button>
              <Button disabled={rerunning} onClick={rerunAll} type="button" variant="ghost">
                <RotateCcw aria-hidden="true" size={15} />
                {t("admin.confirmRerunAll")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
