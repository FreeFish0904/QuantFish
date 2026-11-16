import { AlertTriangle, Play, RefreshCw, Save, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useI18n } from "../../../shared/i18n";
import { dataTrackLabelKey } from "../../../shared/submissions/dataTrack";
import { Button } from "../../../shared/ui/Button/Button";
import {
  useUpdateAdminSettings,
  type AdminDataReleaseBuildState,
  type AdminSettings,
  type HistoricalReleaseName
} from "../model";
import styles from "./Panels.module.css";

const HISTORICAL_RELEASE_NAMES: HistoricalReleaseName[] = [
  "learning_1",
  "learning_2",
  "learning_3"
];

type DatasetPayload = {
  train_start: string;
  train_end: string;
  hidden_test_start: string;
  hidden_test_end: string;
};

type DatasetPanelProps = {
  settings: AdminSettings;
  isSaving?: boolean;
  onSave?: (dataset: DatasetPayload) => void;
  releaseState?: AdminDataReleaseBuildState;
  releaseError?: string;
  isReleaseLoading?: boolean;
  isStartingReleaseBuild?: boolean;
  onRefreshReleases?: () => void;
  onStartReleaseBuild?: (releaseNames: HistoricalReleaseName[]) => void;
};

function toForm(settings: AdminSettings): DatasetPayload {
  return {
    train_start: settings.dataset.trainStart,
    train_end: settings.dataset.trainEnd,
    hidden_test_start: settings.dataset.hiddenTestStart,
    hidden_test_end: settings.dataset.hiddenTestEnd
  };
}

export function DatasetPanel({
  settings,
  isSaving,
  onSave,
  releaseState,
  releaseError,
  isReleaseLoading = false,
  isStartingReleaseBuild = false,
  onRefreshReleases,
  onStartReleaseBuild
}: DatasetPanelProps) {
  const { t, language } = useI18n();
  const fallbackUpdate = useUpdateAdminSettings();
  const [form, setForm] = useState<DatasetPayload>(() => toForm(settings));
  const [selectedReleases, setSelectedReleases] = useState<HistoricalReleaseName[]>([]);
  const [confirmingReleaseBuild, setConfirmingReleaseBuild] = useState(false);
  const releaseSelectionInitialized = useRef(false);

  useEffect(() => {
    setForm(toForm(settings));
  }, [settings]);

  useEffect(() => {
    if (!releaseState || releaseSelectionInitialized.current) {
      return;
    }
    setSelectedReleases(
      releaseState.releases
        .filter((release) => release.status === "missing")
        .map((release) => release.releaseName)
    );
    releaseSelectionInitialized.current = true;
  }, [releaseState]);

  const updateField = (field: keyof DatasetPayload, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (onSave) {
      onSave(form);
    } else {
      fallbackUpdate.mutate({ dataset: form });
    }
  };

  const activeJob =
    releaseState?.job?.status === "queued" || releaseState?.job?.status === "running";
  const buildableReleases = releaseState?.buildableReleaseNames ?? HISTORICAL_RELEASE_NAMES;
  const selectedBuildReleases = buildableReleases.filter((name) =>
    selectedReleases.includes(name)
  );
  const selectedReleaseDetails = (releaseState?.releases ?? []).filter((release) =>
    selectedBuildReleases.includes(release.releaseName)
  );
  const jobError = releaseState?.job?.errorMessage ?? releaseError;

  const toggleRelease = (releaseName: HistoricalReleaseName) => {
    setSelectedReleases((current) =>
      current.includes(releaseName)
        ? current.filter((name) => name !== releaseName)
        : HISTORICAL_RELEASE_NAMES.filter(
            (name) => current.includes(name) || name === releaseName
          )
    );
  };

  return (
    <div className={styles.stack}>
      <form className={styles.datasetSettingsForm} onSubmit={handleSubmit}>
        <div className={styles.formGrid}>
          <label className={styles.field} htmlFor="admin-train-start">
            <span>{t("admin.trainStartDate")}</span>
            <input
              id="admin-train-start"
              onChange={(event) => updateField("train_start", event.target.value)}
              required
              type="date"
              value={form.train_start}
            />
          </label>
          <label className={styles.field} htmlFor="admin-train-end">
            <span>{t("admin.trainEndDate")}</span>
            <input
              id="admin-train-end"
              onChange={(event) => updateField("train_end", event.target.value)}
              required
              type="date"
              value={form.train_end}
            />
          </label>
          <label className={styles.field} htmlFor="admin-hidden-start">
            <span>{t("admin.hiddenTestStartDate")}</span>
            <input
              id="admin-hidden-start"
              onChange={(event) => updateField("hidden_test_start", event.target.value)}
              required
              type="date"
              value={form.hidden_test_start}
            />
          </label>
          <label className={styles.field} htmlFor="admin-hidden-end">
            <span>{t("admin.hiddenTestEndDate")}</span>
            <input
              id="admin-hidden-end"
              onChange={(event) => updateField("hidden_test_end", event.target.value)}
              required
              type="date"
              value={form.hidden_test_end}
            />
          </label>
        </div>
        <div className={styles.previewRow} aria-live="polite">
          <span>{t("admin.trainingPreview", { start: form.train_start, end: form.train_end })}</span>
          <span>
            {t("admin.hiddenTestingPreview", {
              start: form.hidden_test_start,
              end: form.hidden_test_end
            })}
          </span>
        </div>
        <Button
          className={styles.saveButton}
          disabled={isSaving ?? fallbackUpdate.isPending}
          type="submit"
        >
          <Save aria-hidden="true" size={16} />
          {t("admin.saveDataset")}
        </Button>
      </form>

      <section className={styles.releaseBuilder} aria-labelledby="release-builder-title">
        <div className={styles.sectionHeader}>
          <div>
            <h2 id="release-builder-title">{t("admin.releaseBuilderTitle")}</h2>
            <p className={styles.sectionDescription}>{t("admin.releaseBuilderDescription")}</p>
          </div>
          {onRefreshReleases ? (
            <Button onClick={onRefreshReleases} type="button" variant="ghost">
              <RefreshCw aria-hidden="true" size={15} />
              {t("admin.refreshReleaseStatus")}
            </Button>
          ) : null}
        </div>

        {isReleaseLoading && !releaseState ? (
          <p className={styles.releaseNotice} role="status">
            {t("admin.loadingReleaseStatus")}
          </p>
        ) : null}

        {!isReleaseLoading && releaseState && !releaseState.sourceAvailable ? (
          <p className={styles.releaseWarning} role="alert">
            {t("admin.releaseSourceMissing")}
          </p>
        ) : null}

        {jobError ? (
          <p className={styles.releaseError} role="alert">
            {t("admin.releaseBuildError", { error: jobError })}
          </p>
        ) : null}

        {releaseState?.job ? (
          <div className={styles.overallProgress} aria-live="polite">
            <div className={styles.progressLabel}>
              <strong>{t("admin.releaseOverallProgress")}</strong>
              <span>{Math.round(releaseState.job.progressPercent)}%</span>
            </div>
            <progress
              aria-label={t("admin.releaseOverallProgress")}
              max={100}
              value={releaseState.job.progressPercent}
            />
            <small>
              {releaseStatusLabel(releaseState.job.status, t)}
              {releaseState.job.currentReleaseName
                ? ` · ${t(dataTrackLabelKey(releaseState.job.currentReleaseName))}`
                : ""}
            </small>
          </div>
        ) : null}

        <div className={styles.releaseGrid}>
          {(releaseState?.releases ?? []).map((release) => {
            const trackProgress = releaseState?.job?.tracks.find(
              (track) => track.releaseName === release.releaseName
            );
            const checked = selectedReleases.includes(release.releaseName);
            return (
              <article className={styles.releaseCard} key={release.releaseName}>
                <label className={styles.releaseChoice}>
                  <input
                    checked={checked}
                    disabled={activeJob}
                    onChange={() => toggleRelease(release.releaseName)}
                    type="checkbox"
                  />
                  <span>
                    <strong>{t(dataTrackLabelKey(release.releaseName))}</strong>
                    <small>{release.releaseName}</small>
                  </span>
                </label>
                <p>{t("admin.releaseDateRange", { start: release.start, end: release.end })}</p>
                <p className={styles.releasePath}>{release.outputRoot}</p>
                <div className={styles.releaseCardStatus}>
                  <span>{releaseStatusLabel(trackProgress?.status ?? release.status, t)}</span>
                  {release.lastBuiltAt ? (
                    <span>
                      {t("admin.releaseBuiltAt", {
                        time: formatReleaseTime(release.lastBuiltAt, language)
                      })}
                    </span>
                  ) : null}
                </div>
                {trackProgress ? (
                  <div className={styles.trackProgress}>
                    <div className={styles.progressLabel}>
                      <span>{releasePhaseLabel(trackProgress.phase, t)}</span>
                      <span>{Math.round(trackProgress.progressPercent)}%</span>
                    </div>
                    <progress
                      aria-label={t("admin.releaseTrackProgress", {
                        track: t(dataTrackLabelKey(release.releaseName))
                      })}
                      max={100}
                      value={trackProgress.progressPercent}
                    />
                    {trackProgress.currentDataset ? (
                      <small>
                        {t("admin.releaseCurrentDataset", {
                          dataset: trackProgress.currentDataset,
                          completed: trackProgress.completedDatasets,
                          total: trackProgress.totalDatasets
                        })}
                      </small>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>

        <div className={styles.releaseActions}>
          <Button
            disabled={
              isReleaseLoading ||
              isStartingReleaseBuild ||
              activeJob ||
              !releaseState?.sourceAvailable ||
              selectedReleases.length === 0
            }
            onClick={() => setConfirmingReleaseBuild(true)}
            type="button"
          >
            <Play aria-hidden="true" size={16} />
            {activeJob
              ? t("admin.releaseBuildRunning")
              : isStartingReleaseBuild
                ? t("admin.releaseBuildStarting")
                : t("admin.generateSelectedReleases")}
          </Button>
          <span>{t("admin.releaseBuildAsyncHint")}</span>
        </div>

        {confirmingReleaseBuild ? (
          <div className={styles.dialogBackdrop}>
            <div
              aria-labelledby="admin-confirm-release-build-title"
              aria-modal="true"
              className={styles.dialog}
              role="dialog"
            >
              <div className={styles.modalHeader}>
                <h2 id="admin-confirm-release-build-title">
                  {t("admin.confirmReleaseBuildTitle")}
                </h2>
                <Button
                  aria-label={t("common.close")}
                  onClick={() => setConfirmingReleaseBuild(false)}
                  type="button"
                  variant="ghost"
                >
                  <X aria-hidden="true" size={16} />
                </Button>
              </div>
              <p className={styles.dialogBody}>{t("admin.confirmReleaseBuildBody")}</p>
              <ul className={styles.releaseConfirmList}>
                {selectedReleaseDetails.map((release) => (
                  <li key={release.releaseName}>
                    <strong>{t(dataTrackLabelKey(release.releaseName))}</strong>
                    <span>{t("admin.releaseDateRange", { start: release.start, end: release.end })}</span>
                  </li>
                ))}
              </ul>
              <div className={styles.dialogActions}>
                <Button
                  disabled={isStartingReleaseBuild}
                  onClick={() => setConfirmingReleaseBuild(false)}
                  type="button"
                  variant="ghost"
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  disabled={isStartingReleaseBuild || activeJob}
                  onClick={() => {
                    onStartReleaseBuild?.(selectedBuildReleases);
                    setConfirmingReleaseBuild(false);
                  }}
                  type="button"
                >
                  <AlertTriangle aria-hidden="true" size={15} />
                  {t("admin.confirmReleaseBuildAction")}
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function formatReleaseTime(value: string, language: "en" | "zh") {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-US", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parsed);
}

function releaseStatusLabel(
  status: string,
  t: (key: string, variables?: Record<string, string | number>) => string
) {
  const keyByStatus: Record<string, string> = {
    missing: "admin.releaseStatusMissing",
    ready: "admin.releaseStatusReady",
    queued: "admin.releaseStatusQueued",
    running: "admin.releaseStatusRunning",
    completed: "admin.releaseStatusCompleted",
    failed: "admin.releaseStatusFailed",
    cancelled: "admin.releaseStatusCancelled"
  };
  return t(keyByStatus[status] ?? "admin.releaseStatusUnknown");
}

function releasePhaseLabel(
  phase: string,
  t: (key: string, variables?: Record<string, string | number>) => string
) {
  const keyByPhase: Record<string, string> = {
    queued: "admin.releasePhaseQueued",
    waiting_for_scoring: "admin.releasePhaseWaitingForScoring",
    scanning: "admin.releasePhaseScanning",
    validating: "admin.releasePhaseValidating",
    preparing: "admin.releasePhasePreparing",
    building: "admin.releasePhaseBuilding",
    cataloging: "admin.releasePhaseCataloging",
    publishing: "admin.releasePhasePublishing",
    completed: "admin.releasePhaseCompleted",
    failed: "admin.releasePhaseFailed",
    cancelled: "admin.releasePhaseCancelled"
  };
  return t(keyByPhase[phase] ?? "admin.releasePhaseWorking");
}
