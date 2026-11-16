import { LoaderCircle } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { useI18n } from "../../shared/i18n";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import {
  useAdminCohortSubmissionRawError,
  useAdminCohortSubmissions,
  useAdminCohortSubmissionSource,
  useAdminSession,
  useAdminTeams,
  useRerunAdminCohortSubmissions
} from "./model";
import { SubmissionsPanel } from "./ui/SubmissionsPanel";
import styles from "./view.module.css";

const COHORT_SUBMISSION_PAGE_SIZE = 25;

function cohortTeamCountText(
  teamIds: string[],
  t: (key: string, variables?: Record<string, string | number>) => string
): string {
  if (teamIds.length === 0) return t("admin.cohortNoTeamsSelected");
  if (teamIds.length === 1) return t("admin.cohortTeamCount", { count: teamIds.length });
  return t("admin.cohortTeamCountPlural", { count: teamIds.length });
}

export function AdminCohortSubmissionsView() {
  const { t } = useI18n();
  const { cohortId = "" } = useParams<{ cohortId: string }>();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const sessionQuery = useAdminSession();
  const authenticated = Boolean(sessionQuery.data?.authenticated);
  const teamsQuery = useAdminTeams(authenticated);
  const queryParams = useMemo(
    () => ({
      limit: COHORT_SUBMISSION_PAGE_SIZE,
      offset: (page - 1) * COHORT_SUBMISSION_PAGE_SIZE,
      search,
      status: statusFilter,
      sortBy: "submitted_at",
      sortDir: "desc" as const
    }),
    [page, search, statusFilter]
  );
  const submissionsQuery = useAdminCohortSubmissions(
    authenticated && Boolean(cohortId),
    cohortId,
    queryParams
  );
  const rerunSubmissions = useRerunAdminCohortSubmissions(cohortId);
  const sourceLookup = useAdminCohortSubmissionSource(cohortId);
  const rawErrorLookup = useAdminCohortSubmissionRawError(cohortId);

  const isLoading =
    sessionQuery.isLoading ||
    (authenticated && (teamsQuery.isLoading || submissionsQuery.isLoading));
  const isError =
    sessionQuery.isError ||
    teamsQuery.isError ||
    (authenticated && submissionsQuery.isError);
  const error =
    sessionQuery.error ??
    teamsQuery.error ??
    (authenticated ? submissionsQuery.error : null);

  const retry = () => {
    sessionQuery.refetch();
    teamsQuery.refetch();
    submissionsQuery.refetch();
  };

  if (isLoading) {
    return (
      <section className={styles.admin}>
        <div className={styles.loading} role="status" aria-live="polite">
          <LoaderCircle aria-hidden="true" className={styles.loadingIcon} size={32} />
          {t("admin.loading")}
        </div>
      </section>
    );
  }

  if (!authenticated) {
    return (
      <section className={styles.admin}>
        <EmptyState
          description={t("admin.cohortHistoryLoginDescription")}
          title={t("admin.loginTitle")}
        />
      </section>
    );
  }

  if (isError) {
    return (
      <section className={styles.admin}>
        <ErrorState
          message={error instanceof Error ? error.message : undefined}
          onRetry={retry}
          title={t("admin.errorTitle")}
        />
      </section>
    );
  }

  const teams = teamsQuery.data;
  const cohort = teams?.cohorts.find((entry) => entry.cohortId === cohortId);

  if (!teams || !cohort) {
    return (
      <section className={styles.admin}>
        <EmptyState
          description={t("admin.cohortNotFoundDescription")}
          title={t("admin.cohortNotFound")}
        />
      </section>
    );
  }

  const submissionsPage = submissionsQuery.data;
  const submissions = submissionsPage?.records ?? [];

  return (
    <section className={styles.admin} aria-labelledby="admin-cohort-submissions-title">
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{t("admin.teamCohortHistoryEyebrow")}</p>
          <h1 id="admin-cohort-submissions-title" className={styles.title}>
            {t("admin.cohortSubmissionsTitle", { name: cohort.name })}
          </h1>
        </div>
        <div className={styles.statusGroup}>
          <div className={styles.status} role="group" aria-label={t("admin.statusLabel")}>
            <span>
              {cohort.historyVisible
                ? t("admin.cohortHistoryVisible")
                : t("admin.cohortHistoryHidden")}
            </span>
            <span>
              {cohort.submissionsEnabled
                ? t("admin.cohortSubmissionsOpen")
                : t("admin.cohortSubmissionsClosed")}
            </span>
            <span>{cohortTeamCountText(cohort.teamIds, t)}</span>
          </div>
          <Link className={styles.buttonLink} to="/admin">
            {t("admin.cohortHistoryBackToTeams")}
          </Link>
        </div>
      </header>

      <div className={styles.panel}>
        <SubmissionsPanel
          hasNext={submissionsPage?.hasNext ?? false}
          isRerunning={rerunSubmissions.isPending}
          onPageChange={setPage}
          onRerun={(payload, options) => rerunSubmissions.mutate(payload, options)}
          onSearchChange={(value) => {
            setSearch(value);
            setPage(1);
          }}
          onStatusFilterChange={(value) => {
            setStatusFilter(value);
            setPage(1);
          }}
          page={page}
          pageSize={submissionsPage?.limit ?? COHORT_SUBMISSION_PAGE_SIZE}
          rawErrorLookup={rawErrorLookup}
          search={search}
          sourceLookup={sourceLookup}
          statusFilter={statusFilter}
          submissions={submissions}
          totalCount={submissionsPage?.totalCount ?? submissions.length}
        />
      </div>
    </section>
  );
}
