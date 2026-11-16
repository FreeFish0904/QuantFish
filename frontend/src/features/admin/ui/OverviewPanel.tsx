import type { ReactNode } from "react";

import { useI18n } from "../../../shared/i18n";
import { Card } from "../../../shared/ui/Card/Card";
import type { AdminSettings } from "../model";
import styles from "./Panels.module.css";

type OverviewPanelProps = {
  settings: AdminSettings;
};

function formatWindow(start: string | null, end: string | null, fallback: string): ReactNode {
  if (!start && !end) {
    return fallback;
  }
  if (!start || !end) {
    return <span className={styles.nowrap}>{start ?? end}</span>;
  }
  return (
    <>
      <span className={styles.nowrap}>{start}</span>
      <span className={styles.rangeSeparator}>-</span>
      <span className={styles.nowrap}>{end}</span>
    </>
  );
}

export function OverviewPanel({ settings }: OverviewPanelProps) {
  const { t } = useI18n();
  const scoringWindow = formatWindow(settings.scoringStart, settings.scoringEnd, t("admin.notConfigured"));
  const hiddenWindow = formatWindow(settings.hiddenStart, settings.hiddenEnd, t("admin.notConfigured"));
  const executionMode = settings.execution.longOnly ? t("admin.longOnlyMode") : t("admin.longShortMode");

  return (
    <div className={styles.metricGrid}>
      <Card header={t("admin.courseHealth")}>
        <div className={styles.metricValue}>{settings.courseName}</div>
        <p className={styles.metricHint}>{t("admin.activeCourse")}</p>
      </Card>
      <Card header={t("admin.scoringReadiness")}>
        <div className={styles.metricValue}>{scoringWindow}</div>
        <p className={styles.metricHint}>{executionMode}</p>
      </Card>
      <Card header={t("admin.releaseState")}>
        <div className={styles.metricValue}>{settings.hiddenOutputRoot ?? t("admin.notReleased")}</div>
        <p className={styles.metricHint}>{hiddenWindow}</p>
      </Card>
      <Card header={t("admin.queueState")}>
        <div className={styles.metricValue}>{t("admin.seconds", { count: settings.scoringTimeoutSeconds ?? "—" })}</div>
        <p className={styles.metricHint}>{settings.engineVersion ?? t("admin.engineUnknown")}</p>
      </Card>
    </div>
  );
}
