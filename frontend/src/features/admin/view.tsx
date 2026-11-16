import { AlertCircle, CheckCircle, LoaderCircle, X } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useI18n } from "../../shared/i18n";
import { Button } from "../../shared/ui/Button/Button";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { PasswordInput } from "../../shared/ui/PasswordInput/PasswordInput";
import {
  type AdminDatasetSettings,
  useAdminDataReleases,
  useAdminLogin,
  useAdminLogout,
  useAdminSession,
  useAdminSettings,
  useAdminSubmissions,
  useAdminTeams,
  useCreateTeam,
  useCreateTeamCohort,
  useDeleteAdminSubmissions,
  useDeleteTeamCohort,
  useMarkAdminStaleSubmissions,
  useRevertAdminStaleMark,
  useRevertAdminSettingsHistory,
  useRerunAdminSubmissions,
  useStartAdminDataReleaseBuild,
  useTeamBulkAction,
  useUpdateAdminSettings,
  useUpdateTeam,
  useUpdateTeamCohort
} from "./model";
import { AdminTabs, type AdminSection } from "./ui/AdminTabs";
import { DatasetPanel } from "./ui/DatasetPanel";
import { ExecutionPanel } from "./ui/ExecutionPanel";
import { OverviewPanel } from "./ui/OverviewPanel";
import { SubmissionsPanel } from "./ui/SubmissionsPanel";
import { TeamsPanel } from "./ui/TeamsPanel";
import styles from "./view.module.css";

const ADMIN_SUBMISSION_PAGE_SIZE = 25;
const DATASET_STATUS_DISMISS_MS = 6000;

type DatasetPayload = {
  train_start: string;
  train_end: string;
  hidden_test_start: string;
  hidden_test_end: string;
};

type DatasetSaveStatus = "idle" | "processing" | "success" | "error";

export function AdminConsoleView() {
  const { t } = useI18n();
  const [password, setPassword] = useState("");
  const [activeSection, setActiveSection] = useState<AdminSection>("overview");
  const [submissionSearch, setSubmissionSearch] = useState("");
  const [submissionStatus, setSubmissionStatus] = useState("all");
  const [submissionPage, setSubmissionPage] = useState(1);
  const [datasetSaveStatus, setDatasetSaveStatus] = useState<DatasetSaveStatus>("idle");
  const sessionQuery = useAdminSession();
  const login = useAdminLogin();
  const logout = useAdminLogout();
  const authenticated = Boolean(sessionQuery.data?.authenticated);
  const submissionsEnabled = authenticated && activeSection === "submissions";
  const dataReleasesEnabled = authenticated && activeSection === "dataset";
  const submissionQueryParams = useMemo(
    () => ({
      limit: ADMIN_SUBMISSION_PAGE_SIZE,
      offset: (submissionPage - 1) * ADMIN_SUBMISSION_PAGE_SIZE,
      search: submissionSearch,
      status: submissionStatus,
      sortBy: "submitted_at",
      sortDir: "desc" as const
    }),
    [submissionPage, submissionSearch, submissionStatus]
  );
  const settingsQuery = useAdminSettings(authenticated);
  const teamsQuery = useAdminTeams(authenticated);
  const submissionsQuery = useAdminSubmissions(submissionsEnabled, submissionQueryParams);
  const dataReleasesQuery = useAdminDataReleases(dataReleasesEnabled);
  const updateSettings = useUpdateAdminSettings();
  const revertSettingsHistory = useRevertAdminSettingsHistory();
  const markStaleSubmissions = useMarkAdminStaleSubmissions();
  const revertStaleMark = useRevertAdminStaleMark();
  const createTeam = useCreateTeam();
  const updateTeam = useUpdateTeam();
  const teamBulkAction = useTeamBulkAction();
  const createTeamCohort = useCreateTeamCohort();
  const updateTeamCohort = useUpdateTeamCohort();
  const deleteTeamCohort = useDeleteTeamCohort();
  const deleteSubmissions = useDeleteAdminSubmissions();
  const rerunSubmissions = useRerunAdminSubmissions();
  const startDataReleaseBuild = useStartAdminDataReleaseBuild();

  const isLoading =
    sessionQuery.isLoading ||
    (authenticated &&
      (settingsQuery.isLoading ||
        teamsQuery.isLoading ||
        (submissionsEnabled && submissionsQuery.isLoading)));
  const isError =
    sessionQuery.isError ||
    settingsQuery.isError ||
    teamsQuery.isError ||
    (submissionsEnabled && submissionsQuery.isError);
  const error =
    sessionQuery.error ??
    settingsQuery.error ??
    teamsQuery.error ??
    (submissionsEnabled ? submissionsQuery.error : null);

  const retry = () => {
    sessionQuery.refetch();
    settingsQuery.refetch();
    teamsQuery.refetch();
    submissionsQuery.refetch();
    dataReleasesQuery.refetch();
  };

  function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    login.mutate({ password });
  }

  useEffect(() => {
    if (datasetSaveStatus !== "success") {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      setDatasetSaveStatus("idle");
    }, DATASET_STATUS_DISMISS_MS);

    return () => window.clearTimeout(timeoutId);
  }, [datasetSaveStatus]);

  if (isLoading) {
    return (
      <div className={styles.loading} role="status" aria-live="polite">
        <LoaderCircle aria-hidden="true" className={styles.loadingIcon} size={32} />
        <span>{t("admin.loading")}</span>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <section className={styles.loginShell} aria-labelledby="admin-login-title">
        <form className={styles.loginForm} onSubmit={handleLoginSubmit}>
          <div>
            <p className={styles.kicker}>{t("admin.eyebrow")}</p>
            <h1 className={styles.loginTitle} id="admin-login-title">
              {t("admin.loginTitle")}
            </h1>
          </div>
          <label className={styles.loginField}>
            <span>{t("admin.adminPassword")}</span>
            <PasswordInput
              aria-label={t("admin.adminPassword")}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              required
              value={password}
            />
          </label>
          <p className={styles.loginHint} id="admin-login-hint">
            {t("admin.loginHint")}
          </p>
          <Button
            aria-describedby="admin-login-hint"
            disabled={login.isPending || password.length === 0}
            type="submit"
          >
            {login.isPending ? t("admin.loggingIn") : t("admin.login")}
          </Button>
          {login.error ? (
            <ErrorState
              message={login.error instanceof Error ? login.error.message : undefined}
              title={t("admin.loginErrorTitle")}
            />
          ) : null}
        </form>
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

  const settings = settingsQuery.data;
  const teams = teamsQuery.data;
  const submissionsPage = submissionsQuery.data;
  const submissions = submissionsPage?.records ?? [];
  const teamCount = (teams?.activeTeams.length ?? 0) + (teams?.archivedTeams.length ?? 0);

  if (!settings || !teams) {
    return <EmptyState title={t("admin.emptyTitle")} description={t("admin.emptyDescription")} />;
  }

  const saveDataset = (dataset: DatasetPayload) => {
    if (!datasetDatesChanged(settings.dataset, dataset)) {
      updateSettings.mutate({ dataset });
      return;
    }

    setDatasetSaveStatus("processing");
    updateSettings.mutate(
      { dataset },
      {
        onError: () => setDatasetSaveStatus("error"),
        onSuccess: () => setDatasetSaveStatus("success")
      }
    );
  };

  return (
    <section className={styles.admin} aria-labelledby="admin-title">
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{t("admin.eyebrow")}</p>
          <h1 id="admin-title" className={styles.title}>
            {t("admin.title")}
          </h1>
        </div>
        <div className={styles.statusGroup}>
          <div className={styles.status} role="group" aria-label={t("admin.statusLabel")}>
            <span>{t("admin.teamsCount", { count: teamCount })}</span>
            <span>{settings.engineVersion ?? t("admin.unknownEngine")}</span>
            <span>{t("admin.timeout", { seconds: settings.scoringTimeoutSeconds ?? "—" })}</span>
          </div>
          <Button onClick={() => logout.mutate()} type="button" variant="ghost">
            {t("admin.logout")}
          </Button>
        </div>
      </header>

      <AdminTabs activeSection={activeSection} onSelect={setActiveSection} />

      <div
        aria-labelledby={`admin-tab-${activeSection}`}
        className={styles.panel}
        id={`admin-panel-${activeSection}`}
        role="tabpanel"
      >
        {activeSection === "overview" && <OverviewPanel settings={settings} />}
        {activeSection === "dataset" && (
          <DatasetPanel
            isSaving={updateSettings.isPending}
            isReleaseLoading={dataReleasesQuery.isLoading}
            isStartingReleaseBuild={startDataReleaseBuild.isPending}
            onSave={saveDataset}
            onRefreshReleases={() => dataReleasesQuery.refetch()}
            onStartReleaseBuild={(releaseNames) =>
              startDataReleaseBuild.mutate({ release_names: releaseNames })
            }
            releaseError={mutationOrQueryError(
              startDataReleaseBuild.error ?? dataReleasesQuery.error
            )}
            releaseState={dataReleasesQuery.data}
            settings={settings}
          />
        )}
        {activeSection === "execution" && (
          <ExecutionPanel
            isSaving={updateSettings.isPending}
            isMarkingStale={markStaleSubmissions.isPending}
            isRevertingStale={revertStaleMark.isPending}
            isRestoringHistory={revertSettingsHistory.isPending}
            onMarkStale={(options) => markStaleSubmissions.mutate(undefined, options)}
            onSave={(payload) => updateSettings.mutate(payload)}
            onRevertStaleMark={(entryId) => revertStaleMark.mutate(entryId)}
            onRestoreHistory={(entryId) => revertSettingsHistory.mutate(entryId)}
            settings={settings}
          />
        )}
        {activeSection === "teams" && (
          <TeamsPanel
            isWorking={createTeam.isPending || updateTeam.isPending || teamBulkAction.isPending}
            isCohortWorking={createTeamCohort.isPending || updateTeamCohort.isPending || deleteTeamCohort.isPending}
            onBulkAction={(payload) => teamBulkAction.mutate(payload)}
            onCreate={(team) => createTeam.mutate(team)}
            onCreateCohort={(cohort) => createTeamCohort.mutate(cohort)}
            onDeleteCohort={(cohortId) => deleteTeamCohort.mutate(cohortId)}
            onUpdate={(teamId, team) => updateTeam.mutate({ teamId, team })}
            onUpdateCohort={(cohortId, cohort) => updateTeamCohort.mutate({ cohortId, cohort })}
            teams={teams}
          />
        )}
        {activeSection === "submissions" && (
          <SubmissionsPanel
            hasNext={submissionsPage?.hasNext ?? false}
            isDeleting={deleteSubmissions.isPending}
            isRerunning={rerunSubmissions.isPending}
            onDelete={(payload) => deleteSubmissions.mutate(payload)}
            onPageChange={setSubmissionPage}
            onRerun={(payload, options) => rerunSubmissions.mutate(payload, options)}
            onSearchChange={(value) => {
              setSubmissionSearch(value);
              setSubmissionPage(1);
            }}
            onStatusFilterChange={(value) => {
              setSubmissionStatus(value);
              setSubmissionPage(1);
            }}
            page={submissionPage}
            pageSize={submissionsPage?.limit ?? ADMIN_SUBMISSION_PAGE_SIZE}
            search={submissionSearch}
            statusFilter={submissionStatus}
            submissions={submissions}
            totalCount={submissionsPage?.totalCount ?? submissions.length}
          />
        )}
      </div>
      <DatasetProcessingToast
        onDismiss={() => setDatasetSaveStatus("idle")}
        status={datasetSaveStatus}
      />
    </section>
  );
}

function mutationOrQueryError(error: unknown): string | undefined {
  return error instanceof Error ? error.message : undefined;
}

function datasetDatesChanged(settings: AdminDatasetSettings, dataset: DatasetPayload) {
  return (
    settings.trainStart !== dataset.train_start ||
    settings.trainEnd !== dataset.train_end ||
    settings.hiddenTestStart !== dataset.hidden_test_start ||
    settings.hiddenTestEnd !== dataset.hidden_test_end
  );
}

function DatasetProcessingToast({
  onDismiss,
  status
}: {
  onDismiss: () => void;
  status: DatasetSaveStatus;
}) {
  const { t } = useI18n();

  if (status === "idle") {
    return null;
  }

  const copy = {
    processing: {
      icon: <LoaderCircle aria-hidden="true" className={styles.datasetToastSpinner} size={18} />,
      label: t("admin.datasetUpdateProcessingLabel"),
      title: t("admin.datasetUpdateProcessing")
    },
    success: {
      icon: <CheckCircle aria-hidden="true" size={18} />,
      label: t("admin.datasetUpdateDoneLabel"),
      title: t("admin.datasetUpdateDone")
    },
    error: {
      icon: <AlertCircle aria-hidden="true" size={18} />,
      label: t("admin.datasetUpdateFailedLabel"),
      title: t("admin.datasetUpdateFailed")
    }
  }[status];

  return (
    <div
      aria-label={copy.label}
      aria-live="polite"
      className={[
        styles.datasetToast,
        status === "success" ? styles.datasetToastSuccess : "",
        status === "error" ? styles.datasetToastError : ""
      ].join(" ")}
      role="status"
    >
      <span className={styles.datasetToastIcon}>{copy.icon}</span>
      <span className={styles.datasetToastText}>
        <strong>{copy.title}</strong>
        {status === "processing" ? <small>{t("admin.datasetUpdateProcessingDetail")}</small> : null}
      </span>
      {status === "error" ? (
        <Button
          aria-label={t("common.close")}
          className={styles.datasetToastDismiss}
          onClick={onDismiss}
          type="button"
          variant="ghost"
        >
          <X aria-hidden="true" size={14} />
        </Button>
      ) : null}
    </div>
  );
}

export { AdminSection };
