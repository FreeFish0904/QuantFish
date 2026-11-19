import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Download,
  FileUp,
  LoaderCircle,
  PackageOpen,
  UploadCloud,
  UserRound,
  XCircle
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useParticipantSession } from "../session/model";
import { useI18n } from "../../shared/i18n";
import {
  DATA_TRACKS,
  dataTrackLabelKey,
  isLearningDataTrack,
  normalizeDataTrack,
  type DataTrack
} from "../../shared/submissions/dataTrack";
import { Button } from "../../shared/ui/Button/Button";
import { Card } from "../../shared/ui/Card/Card";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { PasswordInput } from "../../shared/ui/PasswordInput/PasswordInput";
import {
  deriveSubmitState,
  useEnvironmentOptions,
  useSubmissionOptions,
  useSubmitStrategy,
  useSubmissionStatus
} from "./model";
import styles from "./view.module.css";

const SUBMISSION_COOLDOWN_MS = 2000;

export function SubmissionView() {
  const { t } = useI18n();
  const [teamName, setTeamName] = useState("");
  const [password, setPassword] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dataTrack, setDataTrack] = useState<DataTrack>("learning");
  const [submittedId, setSubmittedId] = useState<string | null>(null);
  const [submittedTrack, setSubmittedTrack] = useState<DataTrack>("learning");
  const [acceptedSubmissionLabel, setAcceptedSubmissionLabel] = useState<string | null>(null);
  const [isCooldownActive, setIsCooldownActive] = useState(false);
  const [environmentMenuOpen, setEnvironmentMenuOpen] = useState(false);
  const cooldownTimeoutRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const submit = useSubmitStrategy();
  const statusQuery = useSubmissionStatus(submittedId ?? undefined);
  const submissionOptions = useSubmissionOptions();
  const environmentOptions = useEnvironmentOptions();
  const participantSession = useParticipantSession();
  const activeTeamName = participantSession.data?.authenticated
    ? participantSession.data.team_name
    : null;
  const availableDataTracks = useMemo<DataTrack[]>(() => {
    const rawTracks = submissionOptions.data?.available_data_tracks ?? (["learning"] as DataTrack[]);
    const normalized = rawTracks.map((track) => normalizeDataTrack(track));
    const tracks = DATA_TRACKS.filter((track) => normalized.includes(track));
    return tracks.length > 0 ? tracks : ["learning"];
  }, [submissionOptions.data]);
  const selectedDataTrack: DataTrack = availableDataTracks.includes(dataTrack)
    ? dataTrack
    : availableDataTracks[0] ?? "learning";

  useEffect(() => {
    if (!availableDataTracks.includes(dataTrack)) {
      setDataTrack(availableDataTracks[0] ?? "learning");
    }
  }, [availableDataTracks, dataTrack]);

  useEffect(() => () => {
    if (cooldownTimeoutRef.current !== null) {
      window.clearTimeout(cooldownTimeoutRef.current);
    }
  }, []);

  const hasRequiredSubmitFields = activeTeamName
    ? file !== null
    : teamName.trim().length > 0 && password.length > 0 && file !== null;
  const canSubmit = hasRequiredSubmitFields && !submit.isPending && !isCooldownActive;
  const submitGuidance = isCooldownActive
    ? t("submissions.cooldownHint")
    : !activeTeamName && (teamName.trim().length === 0 || password.length === 0)
      ? t("submissions.credentialsHint")
      : file === null
        ? t("submissions.chooseFileHint")
        : t("submissions.readyHint", { track: t(dataTrackLabelKey(selectedDataTrack)) });

  function clearFileSelection() {
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function startSubmissionCooldown() {
    if (cooldownTimeoutRef.current !== null) {
      window.clearTimeout(cooldownTimeoutRef.current);
    }
    setIsCooldownActive(true);
    cooldownTimeoutRef.current = window.setTimeout(() => {
      setIsCooldownActive(false);
      cooldownTimeoutRef.current = null;
    }, SUBMISSION_COOLDOWN_MS);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit || !file) {
      return;
    }

    const payload = activeTeamName
      ? { file, dataTrack: selectedDataTrack }
      : { teamName: teamName.trim(), password, file, dataTrack: selectedDataTrack };
    submit.mutate(
      payload,
      {
        onSuccess: (data) => {
          setSubmittedId(data.submission_id);
          setSubmittedTrack(normalizeDataTrack(data.data_track));
          setAcceptedSubmissionLabel(data.submission_label);
          clearFileSelection();
          startSubmissionCooldown();
        }
      }
    );
  }

  const state = deriveSubmitState({
    isSubmitting: submit.isPending,
    status: statusQuery.data?.status,
    hasSubmitError: submit.isError,
    hasStatusError: statusQuery.isError,
    isStatusLoading: statusQuery.isLoading,
    hasSubmittedId: submittedId !== null
  });
  const errorMessage = submit.error?.message ?? statusQuery.error?.message;

  return (
    <section aria-labelledby="submission-title" className={styles.view}>
      <header className={styles.header}>
        <div>
          <p className={styles.muted}>{t("submissions.eyebrow")}</p>
          <h1 id="submission-title">{t("submissions.title")}</h1>
          <p>{t("submissions.description")}</p>
        </div>
      </header>

      <div className={styles.grid}>
        <Card header={<h2>{t("submissions.strategyPackageTitle")}</h2>}>
          <form className={styles.form} onSubmit={handleSubmit}>
            {activeTeamName ? (
              <div className={styles.sessionNotice}>
                <UserRound aria-hidden="true" size={18} />
                <strong>{t("submissions.submittingAs", { team: activeTeamName })}</strong>
              </div>
            ) : (
              <>
                <div className={styles.field}>
                  <label htmlFor="team-name">{t("submissions.teamNameLabel")}</label>
                  <input
                    autoComplete="username"
                    className={styles.input}
                    id="team-name"
                    name="teamName"
                    onChange={(event) => setTeamName(event.target.value)}
                    value={teamName}
                  />
                </div>
                <div className={styles.field}>
                  <label htmlFor="team-password">{t("submissions.teamPasswordLabel")}</label>
                  <PasswordInput
                    autoComplete="current-password"
                    id="team-password"
                    inputClassName={styles.input}
                    name="password"
                    onChange={(event) => setPassword(event.target.value)}
                    value={password}
                  />
                </div>
              </>
            )}
            <div className={styles.field}>
              <label htmlFor="strategy-file">{t("submissions.strategyFileLabel")}</label>
              <input
                accept=".py"
                className={styles.fileInput}
                aria-describedby="strategy-file-name"
                id="strategy-file"
                name="strategy"
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                ref={fileInputRef}
                type="file"
              />
              <div className={styles.filePicker}>
                <label className={styles.fileButton} htmlFor="strategy-file">
                  <FileUp aria-hidden="true" size={17} />
                  {t("submissions.chooseFile")}
                </label>
                <span aria-live="polite" className={styles.fileName} id="strategy-file-name">
                  {file?.name ?? t("submissions.noFileSelected")}
                </span>
              </div>
            </div>

            <fieldset className={styles.trackField}>
              <legend>{t("submissions.dataTrackLabel")}</legend>
              <div className={styles.trackOptions}>
                {availableDataTracks.map((track) => (
                  <label
                    className={styles.trackOption}
                    data-selected={dataTrack === track}
                    key={track}
                  >
                    <input
                      checked={dataTrack === track}
                      name="dataTrack"
                      onChange={() => setDataTrack(track)}
                      type="radio"
                      value={track}
                    />
                    <Check aria-hidden="true" className={styles.checkIcon} size={14} />
                    <span>{t(dataTrackLabelKey(track))}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <p aria-live="polite" className={styles.formHint} id="submission-form-hint">
              {submitGuidance}
            </p>
            <div className={styles.actions}>
              <Button aria-describedby="submission-form-hint" disabled={!canSubmit} type="submit">
                <UploadCloud aria-hidden="true" size={17} />
                {t("submissions.submitButton")}
              </Button>
              <a
                className={styles.linkButton}
                download
                href="/api/downloads/learning-data.zip"
              >
                <Download aria-hidden="true" size={17} />
                {t("submissions.downloadLearningData")}
              </a>
              <div className={styles.environmentMenu}>
                <Button
                  aria-expanded={environmentMenuOpen}
                  aria-haspopup="menu"
                  className={styles.environmentButton}
                  onClick={() => setEnvironmentMenuOpen((open) => !open)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") {
                      setEnvironmentMenuOpen(false);
                    }
                  }}
                  type="button"
                  variant="ghost"
                >
                  <PackageOpen aria-hidden="true" size={17} />
                  {t("submissions.downloadEnvironment")}
                  <ChevronDown aria-hidden="true" size={16} />
                </Button>
                {environmentMenuOpen ? (
                  <EnvironmentDownloadMenu
                    isError={environmentOptions.isError}
                    isLoading={environmentOptions.isLoading}
                    options={environmentOptions.data?.platforms ?? []}
                  />
                ) : null}
              </div>
            </div>
          </form>
        </Card>

        <Card header={<h2>{t("submissions.statusTitle")}</h2>}>
          <SubmissionStatePanel
            dataTrack={submittedId === null ? selectedDataTrack : submittedTrack}
            state={state}
          />
          {errorMessage ? (
            <div className={styles.error}>
              <ErrorState message={errorMessage} title={t("submissions.submissionFailedTitle")} />
            </div>
          ) : null}
        </Card>
      </div>

      {acceptedSubmissionLabel ? (
        <SubmissionAcceptedDialog
          label={acceptedSubmissionLabel}
          onClose={() => setAcceptedSubmissionLabel(null)}
        />
      ) : null}
    </section>
  );
}

function SubmissionAcceptedDialog({
  label,
  onClose
}: {
  label: string;
  onClose: () => void;
}) {
  const { t } = useI18n();

  return (
    <div className={styles.dialogBackdrop}>
      <div
        aria-label={t("submissions.acceptedDialogTitle")}
        aria-modal="true"
        className={styles.dialog}
        role="dialog"
      >
        <div className={styles.modalHeader}>
          <h2>{t("submissions.acceptedDialogTitle")}</h2>
          <Button onClick={onClose} type="button" variant="ghost">
            {t("submissions.acceptedDialogClose")}
          </Button>
        </div>
        <p className={styles.dialogBody}>{t("submissions.acceptedDialogBody", { label })}</p>
      </div>
    </div>
  );
}

function EnvironmentDownloadMenu({
  isError,
  isLoading,
  options
}: {
  isError: boolean;
  isLoading: boolean;
  options: Array<{
    platform: string;
    label: string;
    architecture: string;
    status: "available" | "stale" | "missing";
    size_bytes: number | null;
    updated_at: string | null;
    download_url: string | null;
  }>;
}) {
  const { t } = useI18n();

  return (
    <div aria-label={t("submissions.environmentMenuTitle")} className={styles.menu} role="menu">
      <strong className={styles.menuTitle}>{t("submissions.environmentMenuTitle")}</strong>
      {isLoading ? (
        <span className={styles.menuHint}>
          <LoaderCircle aria-hidden="true" className={styles.spinIcon} size={16} />
          {t("submissions.environmentLoading")}
        </span>
      ) : null}
      {isError ? (
        <span className={styles.menuHint}>
          <AlertTriangle aria-hidden="true" size={16} />
          {t("submissions.environmentLoadError")}
        </span>
      ) : null}
      {!isLoading && !isError && options.length === 0 ? (
        <span className={styles.menuHint}>
          <PackageOpen aria-hidden="true" size={16} />
          {t("submissions.environmentEmpty")}
        </span>
      ) : null}
      {options.map((option) => {
        const statusKey = `submissions.environmentStatus.${option.status}`;
        const localizedPlatform = translatedPlatformLabel(t, option.platform, option.label);
        const detail = [
          t(statusKey),
          option.size_bytes !== null
            ? t("submissions.environmentSize", { size: formatBytes(option.size_bytes) })
            : null,
          option.updated_at
            ? t("submissions.environmentUpdated", { date: formatDate(option.updated_at) })
            : null
        ].filter(Boolean).join(" · ");
        const content = (
          <>
            <span className={styles.menuItemLabel}>{localizedPlatform}</span>
            <span className={styles.menuItemMeta}>{detail}</span>
          </>
        );
        if (option.status === "available" && option.download_url) {
          return (
            <a className={styles.menuItem} download href={option.download_url} key={option.platform} role="menuitem">
              {content}
            </a>
          );
        }
        return (
          <button className={styles.menuItem} disabled key={option.platform} role="menuitem" type="button">
            {content}
          </button>
        );
      })}
    </div>
  );
}

function translatedPlatformLabel(
  t: (key: string, variables?: Record<string, string | number>) => string,
  platform: string,
  fallback: string
): string {
  const keyByPlatform: Record<string, string> = {
    "macos-arm64": "submissions.environmentPlatform.macosArm64",
    "macos-x86_64": "submissions.environmentPlatform.macosX8664",
    "windows-x86_64": "submissions.environmentPlatform.windowsX8664"
  };
  const key = keyByPlatform[platform];
  if (!key) {
    return fallback;
  }
  const translated = t(key);
  return translated.startsWith("[") ? fallback : translated;
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function formatDate(value: string): string {
  return value.slice(0, 10);
}

const STATE_CONTENT: Record<
  ReturnType<typeof deriveSubmitState>,
  { Icon: typeof Clock3; titleKey: string; bodyKey: string }
> = {
  idle: {
    Icon: Clock3,
    titleKey: "submissions.stateIdleTitle",
    bodyKey: "submissions.stateIdleBody"
  },
  queued: {
    Icon: Clock3,
    titleKey: "submissions.stateQueuedTitle",
    bodyKey: "submissions.stateQueuedBody"
  },
  running: {
    Icon: LoaderCircle,
    titleKey: "submissions.stateRunningTitle",
    bodyKey: "submissions.stateRunningBody"
  },
  success: {
    Icon: CheckCircle2,
    titleKey: "submissions.stateSuccessTitle",
    bodyKey: "submissions.stateSuccessBody"
  },
  error: {
    Icon: XCircle,
    titleKey: "submissions.stateErrorTitle",
    bodyKey: "submissions.stateErrorBody"
  }
};

const TRACK_STATE_BODY_KEYS: Partial<
  Record<ReturnType<typeof deriveSubmitState>, Record<"hidden_test" | "learning", string>>
> = {
  queued: {
    hidden_test: "submissions.stateQueuedBodyHidden",
    learning: "submissions.stateQueuedBodyLearning"
  },
  running: {
    hidden_test: "submissions.stateRunningBodyHidden",
    learning: "submissions.stateRunningBodyLearning"
  },
  success: {
    hidden_test: "submissions.stateSuccessBodyHidden",
    learning: "submissions.stateSuccessBodyLearning"
  }
};

function SubmissionStatePanel({
  dataTrack,
  state
}: {
  dataTrack: DataTrack;
  state: ReturnType<typeof deriveSubmitState>;
}) {
  const { t } = useI18n();
  const { Icon, titleKey, bodyKey } = STATE_CONTENT[state];
  const trackFamily = isLearningDataTrack(dataTrack) ? "learning" : "hidden_test";
  const effectiveBodyKey = TRACK_STATE_BODY_KEYS[state]?.[trackFamily] ?? bodyKey;

  return (
    <section aria-live="polite" className={styles.statePanel}>
      <strong className={styles.stateTitle}>
        <Icon aria-hidden="true" className={state === "running" ? styles.spinIcon : undefined} size={18} />
        {t(titleKey)}
      </strong>
      <span className={styles.muted}>{t(effectiveBodyKey)}</span>
    </section>
  );
}
