import { Activity } from "lucide-react";

import { useI18n } from "../../shared/i18n";
import { Badge, type BadgeStatus } from "../../shared/ui/Badge/Badge";
import { Card } from "../../shared/ui/Card/Card";
import { DataTable } from "../../shared/ui/DataTable/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { toDashboardModel, useDashboard } from "./model";
import type { DashboardKpi, LatestSubmission } from "./model";
import styles from "./view.module.css";

function formatNumber(value: number): string {
  return value.toLocaleString();
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString();
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
    case "scored":
      return "common.scored";
    default:
      return `common.${status}`;
  }
}

function badgeStatus(status: string, stale = false): BadgeStatus {
  if (stale) {
    return "stale";
  }
  if (status === "completed") return "scored";
  if (status === "queued" || status === "running" || status === "failed" || status === "scored") {
    return status;
  }
  return "offline";
}

const kpiLabelKeys: Record<string, string> = {
  "active-teams": "dashboard.activeTeams",
  "scored-runs": "dashboard.scoredRuns",
  "queued-jobs": "dashboard.queuedJobs",
  "stale-results": "dashboard.staleResults"
};

function kpiToneClass(tone: DashboardKpi["tone"]): string {
  switch (tone) {
    case "positive":
      return styles.tonePositive;
    case "warning":
      return styles.toneWarning;
    case "danger":
      return styles.toneDanger;
    default:
      return styles.toneNeutral;
  }
}

export function DashboardView() {
  const { t } = useI18n();
  const dashboardQuery = useDashboard();

  const submissionColumns = [
    { key: "team", header: t("dashboard.team"), render: (row: LatestSubmission) => row.teamName },
    {
      key: "status",
      header: t("dashboard.status"),
      render: (row: LatestSubmission) => (
        <Badge label={t(statusLabelKey(row.status, row.stale))} status={badgeStatus(row.status, row.stale)} />
      )
    },
    {
      key: "submitted",
      header: t("dashboard.submitted"),
      render: (row: LatestSubmission) => formatDateTime(row.submittedAt)
    }
  ];

  if (dashboardQuery.isLoading) {
    return (
      <section aria-label={t("dashboard.loadingTitle")} className={styles.view}>
        <EmptyState
          description={t("dashboard.loadingDescription")}
          title={t("dashboard.loadingTitle")}
        />
      </section>
    );
  }

  if (dashboardQuery.error) {
    return (
      <section aria-label={t("dashboard.errorTitle")} className={styles.view}>
        <ErrorState
          message={dashboardQuery.error.message}
          onRetry={() => dashboardQuery.refetch()}
          title={t("dashboard.errorTitle")}
        />
      </section>
    );
  }

  if (!dashboardQuery.data) {
    return (
      <section aria-label={t("dashboard.emptyTitle")} className={styles.view}>
        <EmptyState
          description={t("dashboard.emptyDescription")}
          title={t("dashboard.emptyTitle")}
        />
      </section>
    );
  }

  const model = toDashboardModel(dashboardQuery.data);

  return (
    <section aria-labelledby="dashboard-title" className={styles.view}>
      <header className={styles.header}>
        <div>
          <p className={styles.muted}>{t("dashboard.eyebrow")}</p>
          <h2 id="dashboard-title">{t("dashboard.title")}</h2>
          <p className={styles.subtitle}>
            {model.className}
          </p>
        </div>
        <Badge
          label={model.runnerStatus.status === "online" ? t("dashboard.scoringOnline") : t("dashboard.runnerOffline")}
          status={model.runnerStatus.status}
        />
      </header>

      <div aria-label={t("dashboard.metricsLabel")} className={styles.kpiGrid}>
        {model.kpis.map((kpi) => (
          <Card header={t(kpiLabelKeys[kpi.id] ?? `[${kpi.label}]`)} key={kpi.id}>
            <span className={[styles.kpiValue, kpiToneClass(kpi.tone)].join(" ")}>
              {formatNumber(kpi.value)}
            </span>
          </Card>
        ))}
      </div>

      <div className={styles.twoColumn}>
        <section className={styles.panel}>
          <div className={styles.panelIntro}>
            <h3 id="latest-submissions-title">{t("dashboard.latestSubmissionsTitle")}</h3>
            <p className={styles.panelDescription}>{t("dashboard.latestSubmissionsDescription")}</p>
          </div>
          <div data-testid="latest-submissions-box">
            <DataTable
              caption={t("dashboard.latestSubmissionsTitle")}
              columns={submissionColumns}
              empty={
                <EmptyState
                  description={t("dashboard.latestSubmissionsEmptyDescription")}
                  title={t("dashboard.latestSubmissionsEmptyTitle")}
                />
              }
              getRowId={(row) => row.id}
              getRowLabel={(row) => row.teamName}
              rows={model.latestSubmissions}
            />
          </div>
        </section>

        <aside aria-labelledby="live-status-title" className={styles.panel}>
          <div className={styles.panelIntro}>
            <div className={styles.liveHeader}>
              <h3 id="live-status-title">{t("dashboard.liveStatusTitle")}</h3>
              <Activity aria-hidden="true" className={styles.liveIcon} size={20} />
            </div>
          </div>
          <div className={styles.panelSurface} data-testid="live-status-box">
            <dl className={styles.definitionList}>
              <div>
                <dt>{t("dashboard.queue")}</dt>
                <dd>{t("dashboard.queued", { count: model.runnerStatus.queued })}</dd>
              </div>
              <div>
                <dt>{t("common.running")}</dt>
                <dd>{t("dashboard.running", { count: model.runnerStatus.running })}</dd>
              </div>
              <div>
                <dt>{t("dashboard.updated")}</dt>
                <dd>{formatDateTime(model.runnerStatus.lastUpdated)}</dd>
              </div>
              {model.scoringTimeoutSeconds ? (
                <div>
                  <dt>{t("dashboard.scoringTimeout")}</dt>
                  <dd>{t("dashboard.seconds", { count: model.scoringTimeoutSeconds })}</dd>
                </div>
              ) : null}
            </dl>
          </div>
        </aside>
      </div>
    </section>
  );
}
