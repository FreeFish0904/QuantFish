import { AlertTriangle, CheckCircle, CircleQuestionMark, History, RotateCcw, Save, X } from "lucide-react";
import { useId, useState, type FormEvent } from "react";

import { useI18n } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/Button/Button";
import {
  useMarkAdminStaleSubmissions,
  useRevertAdminStaleMark,
  useUpdateAdminSettings,
  type AdminSettings,
  type AdminSettingsHistoryEntry
} from "../model";
import styles from "./Panels.module.css";

type ExecutionPayload = {
  commission_rate: number;
  slippage_rate: number;
  sell_stamp_duty_rate: number;
  max_leverage: number;
  top_k: number | null;
  long_only_weighting: string;
  long_only_target_count: number;
  max_position_weight: number;
  max_participation_rate: number;
  min_listing_days: number;
  terminal_stale_position_policy: string;
  allowed_market_types: number[];
  submissions_enabled: boolean;
  hidden_test_enabled: boolean;
  max_concurrent_scoring: number;
  submission_timeout_seconds: number;
  submission_timeout_enabled: boolean;
  long_only: boolean;
};

type BacktestPayload = {
  capital: number;
  industry_neutralization: boolean;
  long_only_benchmark: string;
  long_only_risk_free_rate: number;
  long_only_min_beta_observations: number;
};

type NumericFormValue = number | null | "";
type ExecutionForm = Omit<
  ExecutionPayload,
  | "commission_rate"
  | "slippage_rate"
  | "sell_stamp_duty_rate"
  | "max_leverage"
  | "top_k"
  | "long_only_target_count"
  | "max_position_weight"
  | "max_participation_rate"
  | "min_listing_days"
  | "max_concurrent_scoring"
  | "submission_timeout_seconds"
> & {
  capital: NumericFormValue;
  long_only_benchmark: string;
  long_only_risk_free_rate: NumericFormValue;
  long_only_min_beta_observations: NumericFormValue;
  commission_rate: NumericFormValue;
  slippage_rate: NumericFormValue;
  sell_stamp_duty_rate: NumericFormValue;
  max_leverage: NumericFormValue;
  top_k: NumericFormValue;
  long_only_target_count: NumericFormValue;
  max_position_weight: NumericFormValue;
  max_participation_rate: NumericFormValue;
  min_listing_days: NumericFormValue;
  allowed_market_types: number[];
  max_concurrent_scoring: NumericFormValue;
  submission_timeout_seconds: NumericFormValue;
  industry_neutralization: boolean;
};
type NumericFieldKey =
  | "capital"
  | "commission_rate"
  | "slippage_rate"
  | "sell_stamp_duty_rate"
  | "max_leverage"
  | "top_k"
  | "long_only_target_count"
  | "max_position_weight"
  | "max_participation_rate"
  | "min_listing_days"
  | "long_only_risk_free_rate"
  | "long_only_min_beta_observations"
  | "max_concurrent_scoring"
  | "submission_timeout_seconds";

type ExecutionSettingsPayload = {
  execution: ExecutionPayload;
  backtest: BacktestPayload;
};

type MarkStaleOptions = {
  onSuccess?: () => void;
};

type ExecutionPanelProps = {
  settings: AdminSettings;
  isSaving?: boolean;
  isRestoringHistory?: boolean;
  isMarkingStale?: boolean;
  isRevertingStale?: boolean;
  onSave?: (payload: ExecutionSettingsPayload) => void;
  onRestoreHistory?: (entryId: string) => void;
  onMarkStale?: (options?: MarkStaleOptions) => void;
  onRevertStaleMark?: (entryId: string) => void;
};

type ExecutionHelpKey =
  | "backtestMode"
  | "startingCapital"
  | "commissionRate"
  | "slippageRate"
  | "sellStampDutyRate"
  | "maxLeverage"
  | "industryNeutralization"
  | "marketTypeScope"
  | "longShortTopBottomK"
  | "longOnlyWeighting"
  | "longOnlyTargetCount"
  | "maxPositionWeight"
  | "maxParticipationRate"
  | "minListingDays"
  | "terminalStalePositionPolicy"
  | "longOnlyBenchmark"
  | "longOnlyRiskFreeRate"
  | "longOnlyMinBetaObservations"
  | "submissionsEnabled"
  | "hiddenTestEnabled"
  | "submissionTimeoutEnabled"
  | "maxConcurrentScoring"
  | "submissionTimeoutSeconds";

type NumericFieldDefinition = {
  key: NumericFieldKey;
  labelKey: string;
  helpKey: ExecutionHelpKey;
  step: string;
  min?: number;
};

type BooleanFieldDefinition = {
  key: keyof ExecutionForm;
  labelKey: string;
  helpKey: ExecutionHelpKey;
};

const sharedNumericFields: NumericFieldDefinition[] = [
  { key: "capital", labelKey: "admin.startingCapital", helpKey: "startingCapital", step: "1", min: 1 },
  { key: "commission_rate", labelKey: "admin.commissionRate", helpKey: "commissionRate", step: "0.0001", min: 0 },
  { key: "slippage_rate", labelKey: "admin.slippageRate", helpKey: "slippageRate", step: "0.0001", min: 0 },
  {
    key: "sell_stamp_duty_rate",
    labelKey: "admin.sellStampDutyRate",
    helpKey: "sellStampDutyRate",
    step: "0.0001",
    min: 0
  },
  { key: "max_leverage", labelKey: "admin.maxLeverage", helpKey: "maxLeverage", step: "0.1", min: 0 }
];

const longShortNumericFields: NumericFieldDefinition[] = [
  { key: "top_k", labelKey: "admin.longShortTopBottomK", helpKey: "longShortTopBottomK", step: "1", min: 1 }
];

const longOnlyNumericFields: NumericFieldDefinition[] = [
  {
    key: "long_only_target_count",
    labelKey: "admin.longOnlyTargetCount",
    helpKey: "longOnlyTargetCount",
    step: "1",
    min: 1
  },
  {
    key: "max_position_weight",
    labelKey: "admin.maxPositionWeight",
    helpKey: "maxPositionWeight",
    step: "0.01",
    min: 0
  },
  {
    key: "max_participation_rate",
    labelKey: "admin.maxParticipationRate",
    helpKey: "maxParticipationRate",
    step: "0.01",
    min: 0
  },
  { key: "min_listing_days", labelKey: "admin.minListingDays", helpKey: "minListingDays", step: "1", min: 0 },
  {
    key: "long_only_risk_free_rate",
    labelKey: "admin.longOnlyRiskFreeRate",
    helpKey: "longOnlyRiskFreeRate",
    step: "0.0001",
    min: -0.9999
  },
  {
    key: "long_only_min_beta_observations",
    labelKey: "admin.longOnlyMinBetaObservations",
    helpKey: "longOnlyMinBetaObservations",
    step: "1",
    min: 1
  }
];

const operationNumericFields: NumericFieldDefinition[] = [
  {
    key: "max_concurrent_scoring",
    labelKey: "admin.maxConcurrentScoring",
    helpKey: "maxConcurrentScoring",
    step: "1",
    min: 1
  },
  {
    key: "submission_timeout_seconds",
    labelKey: "admin.submissionTimeoutSeconds",
    helpKey: "submissionTimeoutSeconds",
    step: "1",
    min: 1
  }
];

const operationBooleanFields: BooleanFieldDefinition[] = [
  { key: "submissions_enabled", labelKey: "admin.submissionsEnabled", helpKey: "submissionsEnabled" },
  { key: "hidden_test_enabled", labelKey: "admin.hiddenTestEnabled", helpKey: "hiddenTestEnabled" },
  {
    key: "submission_timeout_enabled",
    labelKey: "admin.submissionTimeoutEnabled",
    helpKey: "submissionTimeoutEnabled"
  }
];

const sharedBooleanFields: BooleanFieldDefinition[] = [
  { key: "industry_neutralization", labelKey: "admin.industryNeutralization", helpKey: "industryNeutralization" }
];

const marketTypeOrder = [
  { value: 1, key: "marketTypes.shanghaiA" },
  { value: 2, key: "marketTypes.shanghaiB" },
  { value: 4, key: "marketTypes.shenzhenA" },
  { value: 8, key: "marketTypes.shenzhenB" },
  { value: 16, key: "marketTypes.chiNext" },
  { value: 32, key: "marketTypes.starMarket" },
  { value: 64, key: "marketTypes.beijingA" }
];

const defaultNumericValues: Record<NumericFieldKey, number> = {
  capital: 1_000_000,
  commission_rate: 0.0003,
  slippage_rate: 0.0005,
  sell_stamp_duty_rate: 0.0005,
  max_leverage: 1,
  top_k: 0,
  long_only_target_count: 50,
  max_position_weight: 0.05,
  max_participation_rate: 0.1,
  min_listing_days: 60,
  long_only_risk_free_rate: 0.0175,
  long_only_min_beta_observations: 20,
  max_concurrent_scoring: 1,
  submission_timeout_seconds: 120
};

function toForm(settings: AdminSettings): ExecutionForm {
  return {
    capital: settings.capital ?? 1_000_000,
    long_only_benchmark: settings.longOnlyBenchmark ?? "hs300",
    long_only_risk_free_rate: settings.longOnlyRiskFreeRate,
    long_only_min_beta_observations: settings.longOnlyMinBetaObservations,
    commission_rate: settings.execution.commissionRate,
    slippage_rate: settings.execution.slippageRate,
    sell_stamp_duty_rate: settings.execution.sellStampDutyRate,
    max_leverage: settings.execution.maxLeverage,
    top_k: settings.execution.topK,
    long_only_weighting: settings.execution.longOnlyWeighting,
    long_only_target_count: settings.execution.longOnlyTargetCount,
    max_position_weight: settings.execution.maxPositionWeight,
    max_participation_rate: settings.execution.maxParticipationRate,
    min_listing_days: settings.execution.minListingDays,
    terminal_stale_position_policy: settings.execution.terminalStalePositionPolicy,
    allowed_market_types: settings.execution.allowedMarketTypes,
    submissions_enabled: settings.execution.submissionsEnabled,
    hidden_test_enabled: settings.execution.hiddenTestEnabled,
    max_concurrent_scoring: settings.execution.maxConcurrentScoring,
    submission_timeout_seconds: settings.execution.submissionTimeoutSeconds,
    submission_timeout_enabled: settings.execution.submissionTimeoutEnabled,
    long_only: settings.execution.longOnly,
    industry_neutralization: settings.industryNeutralization
  };
}

function toPayload(form: ExecutionForm): ExecutionSettingsPayload {
  return {
    backtest: {
      capital: numberForPayload(form.capital, "capital"),
      industry_neutralization: form.industry_neutralization,
      long_only_benchmark: form.long_only_benchmark || "hs300",
      long_only_risk_free_rate: numberForPayload(form.long_only_risk_free_rate, "long_only_risk_free_rate"),
      long_only_min_beta_observations: numberForPayload(
        form.long_only_min_beta_observations,
        "long_only_min_beta_observations"
      )
    },
    execution: {
      commission_rate: numberForPayload(form.commission_rate, "commission_rate"),
      slippage_rate: numberForPayload(form.slippage_rate, "slippage_rate"),
      sell_stamp_duty_rate: numberForPayload(form.sell_stamp_duty_rate, "sell_stamp_duty_rate"),
      max_leverage: numberForPayload(form.max_leverage, "max_leverage"),
      top_k: form.long_only || form.top_k === "" ? null : form.top_k,
      long_only_weighting: form.long_only_weighting,
      long_only_target_count: numberForPayload(form.long_only_target_count, "long_only_target_count"),
      max_position_weight: numberForPayload(form.max_position_weight, "max_position_weight"),
      max_participation_rate: numberForPayload(form.max_participation_rate, "max_participation_rate"),
      min_listing_days: numberForPayload(form.min_listing_days, "min_listing_days"),
      terminal_stale_position_policy: form.terminal_stale_position_policy,
      allowed_market_types: form.allowed_market_types,
      submissions_enabled: form.submissions_enabled,
      hidden_test_enabled: form.hidden_test_enabled,
      max_concurrent_scoring: numberForPayload(form.max_concurrent_scoring, "max_concurrent_scoring"),
      submission_timeout_seconds: numberForPayload(form.submission_timeout_seconds, "submission_timeout_seconds"),
      submission_timeout_enabled: form.submission_timeout_enabled,
      long_only: form.long_only
    }
  };
}

type Translator = (key: string, values?: Record<string, string | number>) => string;

function ExecutionHelpButton({
  helpKey,
  label,
  t
}: {
  helpKey: ExecutionHelpKey;
  label: string;
  t: Translator;
}) {
  const tooltipId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const baseKey = `admin.executionHelp.${helpKey}`;

  return (
    <span className={styles.settingHelp}>
      <button
        aria-describedby={isOpen ? tooltipId : undefined}
        aria-label={t("admin.settingHelpLabel", { setting: label })}
        className={styles.settingHelpButton}
        onBlur={() => setIsOpen(false)}
        onFocus={() => setIsOpen(true)}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        type="button"
      >
        <CircleQuestionMark aria-hidden="true" size={15} />
      </button>
      {isOpen ? (
        <span className={styles.settingHelpTooltip} id={tooltipId} role="tooltip">
          <span className={styles.settingHelpDescription}>{t(`${baseKey}.description`)}</span>
          <span className={styles.settingHelpDetail}>
            <span>{t("admin.settingHelpUnitLabel")}</span>
            {t(`${baseKey}.unit`)}
          </span>
          <span className={styles.settingHelpCode}>
            <span>{t("admin.settingHelpPseudoCodeLabel")}</span>
            <code>{t(`${baseKey}.pseudoCode`)}</code>
          </span>
        </span>
      ) : null}
    </span>
  );
}

function SettingLabel({
  helpKey,
  htmlFor,
  label,
  t
}: {
  helpKey: ExecutionHelpKey;
  htmlFor?: string;
  label: string;
  t: Translator;
}) {
  return (
    <span className={styles.settingLabelRow}>
      {htmlFor ? (
        <label className={styles.fieldLabelText} htmlFor={htmlFor}>
          {label}
        </label>
      ) : (
        <span className={styles.fieldLabelText}>{label}</span>
      )}
      <ExecutionHelpButton helpKey={helpKey} label={label} t={t} />
    </span>
  );
}

export function ExecutionPanel({
  settings,
  isSaving,
  isRestoringHistory,
  isMarkingStale,
  isRevertingStale,
  onSave,
  onRestoreHistory,
  onMarkStale,
  onRevertStaleMark
}: ExecutionPanelProps) {
  const { t } = useI18n();
  const fallbackUpdate = useUpdateAdminSettings();
  const fallbackMarkStale = useMarkAdminStaleSubmissions();
  const fallbackRevertStale = useRevertAdminStaleMark();
  const [form, setForm] = useState<ExecutionForm>(() => toForm(settings));
  const [formSource, setFormSource] = useState(settings);
  const marketScopeEmpty = form.allowed_market_types.length === 0;
  const marketTypeOptions = marketTypeOrder.map((option) => ({
    value: option.value,
    label: `${option.value} ${t(option.key)}`
  }));

  // Re-seed the draft while rendering when the server settings change, so the
  // form never paints a stale value and no effect has to copy props into state.
  if (settings !== formSource) {
    setFormSource(settings);
    setForm(toForm(settings));
  }

  const updateNumber = (field: NumericFieldKey, value: string) => {
    setForm((current) => ({
      ...current,
      [field]: parseNumberField(field, value)
    }));
  };

  const updateBoolean = (field: keyof ExecutionForm, value: boolean) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const updateMarketType = (marketType: number, checked: boolean) => {
    setForm((current) => {
      const selected = new Set(current.allowed_market_types);
      if (checked) {
        selected.add(marketType);
      } else {
        selected.delete(marketType);
      }
      return {
        ...current,
        allowed_market_types: marketTypeOrder
          .map((option) => option.value)
          .filter((value) => selected.has(value))
      };
    });
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = toPayload(form);
    if (onSave) {
      onSave(payload);
    } else {
      fallbackUpdate.mutate(payload);
    }
  };

  const handleMarkStale = (options?: MarkStaleOptions) => {
    if (onMarkStale) {
      onMarkStale(options);
    } else {
      fallbackMarkStale.mutate(undefined, options);
    }
  };

  const handleRevertStaleMark = (entryId: string) => {
    if (onRevertStaleMark) {
      onRevertStaleMark(entryId);
    } else {
      fallbackRevertStale.mutate(entryId);
    }
  };

  const renderNumberField = (field: NumericFieldDefinition) => (
    <div className={styles.field} key={field.key}>
      <SettingLabel helpKey={field.helpKey} htmlFor={`admin-${field.key}`} label={t(field.labelKey)} t={t} />
      <input
        id={`admin-${field.key}`}
        min={field.min}
        onChange={(event) => updateNumber(field.key, event.target.value)}
        step={field.step}
        type="number"
        value={numberInputValue(form[field.key])}
      />
    </div>
  );

  const renderToggleField = (field: BooleanFieldDefinition) => (
    <div className={styles.toggleWithHelp} key={field.key}>
      <label className={styles.toggle} htmlFor={`admin-${field.key}`}>
        <input
          checked={Boolean(form[field.key])}
          id={`admin-${field.key}`}
          onChange={(event) => updateBoolean(field.key, event.target.checked)}
          type="checkbox"
        />
        <span>{t(field.labelKey)}</span>
      </label>
      <ExecutionHelpButton helpKey={field.helpKey} label={t(field.labelKey)} t={t} />
    </div>
  );

  return (
    <form className={styles.stack} onSubmit={handleSubmit}>
      <section className={styles.executionSection} aria-labelledby="admin-execution-mode-title">
        <div className={styles.sectionHeader}>
          <div className={styles.sectionTitleWithHelp}>
            <h2 id="admin-execution-mode-title">{t("admin.backtestMode")}</h2>
            <ExecutionHelpButton helpKey="backtestMode" label={t("admin.backtestMode")} t={t} />
          </div>
        </div>
        <div className={styles.segmentedControl} role="group" aria-label={t("admin.backtestMode")}>
          <Button
            aria-pressed={!form.long_only}
            onClick={() => updateBoolean("long_only", false)}
            type="button"
            variant={!form.long_only ? "primary" : "ghost"}
          >
            {t("admin.longShortMode")}
          </Button>
          <Button
            aria-pressed={form.long_only}
            onClick={() => updateBoolean("long_only", true)}
            type="button"
            variant={form.long_only ? "primary" : "ghost"}
          >
            {t("admin.longOnlyMode")}
          </Button>
        </div>
      </section>

      <section className={styles.executionSection} aria-labelledby="admin-shared-execution-title">
        <div className={styles.sectionHeader}>
          <h2 id="admin-shared-execution-title">{t("admin.sharedExecution")}</h2>
        </div>
        <div className={styles.formGrid}>{sharedNumericFields.map(renderNumberField)}</div>
        <div className={styles.formGrid}>
          <div className={styles.field}>
            <SettingLabel
              helpKey="terminalStalePositionPolicy"
              htmlFor="admin-terminal-stale-position-policy"
              label={t("admin.terminalStalePositionPolicy")}
              t={t}
            />
            <select
              id="admin-terminal-stale-position-policy"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  terminal_stale_position_policy: event.target.value
                }))
              }
              value={form.terminal_stale_position_policy}
            >
              <option value="reject">reject</option>
              <option value="carry">carry</option>
            </select>
          </div>
        </div>
        <div className={styles.toggleGrid}>{sharedBooleanFields.map(renderToggleField)}</div>
        <fieldset className={styles.marketGroup}>
          <legend>
            <SettingLabel helpKey="marketTypeScope" label={t("admin.marketTypeScope")} t={t} />
          </legend>
          <div className={styles.toggleGrid}>
            {marketTypeOptions.map((option) => (
              <label className={styles.toggle} htmlFor={`admin-market-type-${option.value}`} key={option.value}>
                <input
                  checked={form.allowed_market_types.includes(option.value)}
                  id={`admin-market-type-${option.value}`}
                  onChange={(event) => updateMarketType(option.value, event.target.checked)}
                  type="checkbox"
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <section className={styles.executionSection} aria-labelledby="admin-long-short-settings-title">
        <div className={styles.sectionHeader}>
          <h2 id="admin-long-short-settings-title">{t("admin.longShortSettings")}</h2>
          <span className={form.long_only ? styles.inactiveChip : styles.activeChip}>
            {form.long_only ? t("admin.inactiveMode") : t("admin.activeMode")}
          </span>
        </div>
        <div className={styles.formGrid}>{longShortNumericFields.map(renderNumberField)}</div>
      </section>

      <section className={styles.executionSection} aria-labelledby="admin-long-only-settings-title">
        <div className={styles.sectionHeader}>
          <h2 id="admin-long-only-settings-title">{t("admin.longOnlySettings")}</h2>
          <span className={form.long_only ? styles.activeChip : styles.inactiveChip}>
            {form.long_only ? t("admin.activeMode") : t("admin.inactiveMode")}
          </span>
        </div>
        <div className={styles.formGrid}>
          <div className={styles.field}>
            <SettingLabel
              helpKey="longOnlyWeighting"
              htmlFor="admin-long-only-weighting"
              label={t("admin.longOnlyWeighting")}
              t={t}
            />
            <select
              id="admin-long-only-weighting"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  long_only_weighting: event.target.value
                }))
              }
              value={form.long_only_weighting}
            >
              <option value="rank_equal">rank_equal</option>
              <option value="score_proportional">score_proportional</option>
            </select>
          </div>
          {longOnlyNumericFields.slice(0, 4).map(renderNumberField)}
          <div className={styles.field}>
            <SettingLabel
              helpKey="longOnlyBenchmark"
              htmlFor="admin-long-only-benchmark"
              label={t("admin.longOnlyBenchmark")}
              t={t}
            />
            <input
              id="admin-long-only-benchmark"
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  long_only_benchmark: event.target.value
                }))
              }
              type="text"
              value={form.long_only_benchmark}
            />
          </div>
          {longOnlyNumericFields.slice(4).map(renderNumberField)}
        </div>
      </section>

      <section className={styles.executionSection} aria-labelledby="admin-platform-operations-title">
        <div className={styles.sectionHeader}>
          <h2 id="admin-platform-operations-title">{t("admin.platformOperations")}</h2>
        </div>
        <div className={styles.toggleGrid}>{operationBooleanFields.map(renderToggleField)}</div>
        <div className={styles.formGrid}>{operationNumericFields.map(renderNumberField)}</div>
        <p className={styles.readout}>
          {t("admin.executionPreview", {
            seconds: form.submission_timeout_enabled
              ? numberForPayload(form.submission_timeout_seconds, "submission_timeout_seconds")
              : t("admin.timeoutOff"),
            concurrency: numberForPayload(form.max_concurrent_scoring, "max_concurrent_scoring")
          })}
        </p>
      </section>

      <SettingsHistoryList
        entries={settings.settingsHistory}
        isMarkingStale={Boolean(isMarkingStale ?? fallbackMarkStale.isPending)}
        isRestoring={Boolean(isRestoringHistory)}
        isRevertingStale={Boolean(isRevertingStale ?? fallbackRevertStale.isPending)}
        onMarkStale={handleMarkStale}
        onRestore={onRestoreHistory}
        onRevertStaleMark={handleRevertStaleMark}
      />
      <Button
        className={styles.saveButton}
        disabled={marketScopeEmpty || (isSaving ?? fallbackUpdate.isPending)}
        type="submit"
      >
        <Save aria-hidden="true" size={16} />
        {t("admin.saveExecution")}
      </Button>
    </form>
  );
}

type SettingsHistoryListProps = {
  entries: AdminSettingsHistoryEntry[];
  isMarkingStale: boolean;
  isRestoring: boolean;
  isRevertingStale: boolean;
  onMarkStale: (options?: MarkStaleOptions) => void;
  onRestore?: (entryId: string) => void;
  onRevertStaleMark: (entryId: string) => void;
};

function SettingsHistoryList({
  entries,
  isMarkingStale,
  isRestoring,
  isRevertingStale,
  onMarkStale,
  onRestore,
  onRevertStaleMark
}: SettingsHistoryListProps) {
  const { t } = useI18n();
  const [confirmingStaleMark, setConfirmingStaleMark] = useState(false);
  const [staleMarkSuccessVisible, setStaleMarkSuccessVisible] = useState(false);

  const confirmStaleMark = () => {
    onMarkStale({
      onSuccess: () => {
        setConfirmingStaleMark(false);
        setStaleMarkSuccessVisible(true);
      }
    });
  };

  return (
    <section className={styles.historySection} aria-labelledby="admin-settings-history-title">
      <div className={styles.historyHeader}>
        <h2 id="admin-settings-history-title">{t("admin.settingsHistory")}</h2>
        <Button
          aria-label={t("admin.markStaleSubmissions")}
          disabled={isMarkingStale}
          onClick={() => setConfirmingStaleMark(true)}
          type="button"
          variant="ghost"
        >
          <AlertTriangle aria-hidden="true" size={15} />
          {t("admin.markStaleSubmissions")}
        </Button>
      </div>
      {entries.length === 0 ? (
        <p className={styles.muted}>{t("admin.settingsHistoryEmpty")}</p>
      ) : (
        <div
          aria-label={`${t("admin.settingsHistory")}. ${t("common.tableScrollHint")}`}
          className={`${styles.tableWrap} ${styles.historyScroll}`}
          data-scroll-hint={t("common.tableScrollHint")}
          role="region"
          tabIndex={0}
        >
          <table className={styles.table} aria-label={t("admin.settingsHistory")}>
            <caption>{t("admin.settingsHistory")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("admin.createdAt")}</th>
                <th scope="col">{t("admin.historyType")}</th>
                <th scope="col">{t("admin.changedFields")}</th>
                <th scope="col">{t("admin.staleMarkStatus")}</th>
                <th scope="col">{t("admin.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.entryId}>
                  <td>{formatHistoryDate(entry.createdAt)}</td>
                  <td>{t(historyTypeLabelKey(entry))}</td>
                  <td>{historyChangeSummary(entry, t)}</td>
                  <td>{historyStaleStatus(entry, t)}</td>
                  <td>
                    {entry.entryType === "settings_change" ? (
                      <Button
                        aria-label={t("admin.restoreSettingsHistory", { id: entry.entryId })}
                        disabled={isRestoring || !onRestore}
                        onClick={() => onRestore?.(entry.entryId)}
                        type="button"
                        variant="ghost"
                      >
                        <RotateCcw aria-hidden="true" size={15} />
                        {t("admin.restoreSettings")}
                      </Button>
                    ) : entry.revertedAt === null ? (
                      <Button
                        aria-label={t("admin.revertStaleMarkHistory", { id: entry.entryId })}
                        disabled={isRevertingStale}
                        onClick={() => onRevertStaleMark(entry.entryId)}
                        type="button"
                        variant="ghost"
                      >
                        <History aria-hidden="true" size={15} />
                        {t("admin.revertStaleMark")}
                      </Button>
                    ) : (
                      <span className={styles.muted}>{t("admin.staleMarkReverted")}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {confirmingStaleMark ? (
        <div className={styles.dialogBackdrop}>
          <div
            aria-labelledby="admin-confirm-stale-mark-title"
            aria-modal="true"
            className={styles.dialog}
            role="dialog"
          >
            <div className={styles.modalHeader}>
              <h2 id="admin-confirm-stale-mark-title">{t("admin.confirmStaleMarkTitle")}</h2>
              <Button
                aria-label={t("common.close")}
                onClick={() => setConfirmingStaleMark(false)}
                type="button"
                variant="ghost"
              >
                <X aria-hidden="true" size={16} />
              </Button>
            </div>
            <p className={styles.dialogBody}>{t("admin.confirmStaleMarkBody")}</p>
            <div className={styles.dialogActions}>
              <Button
                disabled={isMarkingStale}
                onClick={() => setConfirmingStaleMark(false)}
                type="button"
                variant="ghost"
              >
                {t("common.cancel")}
              </Button>
              <Button disabled={isMarkingStale} onClick={confirmStaleMark} type="button">
                <AlertTriangle aria-hidden="true" size={15} />
                {t("admin.confirmStaleMarkAction")}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      {staleMarkSuccessVisible ? (
        <div className={styles.toast} role="status" aria-live="polite" aria-atomic="true">
          <CheckCircle aria-hidden="true" size={16} />
          <span>{t("admin.staleMarkSuccess")}</span>
          <Button
            aria-label={t("common.close")}
            onClick={() => setStaleMarkSuccessVisible(false)}
            type="button"
            variant="ghost"
          >
            <X aria-hidden="true" size={15} />
          </Button>
        </div>
      ) : null}
    </section>
  );
}

function historyTypeLabelKey(entry: AdminSettingsHistoryEntry): string {
  return entry.entryType === "stale_mark" ? "admin.historyTypeStaleMark" : "admin.historyTypeSettings";
}

function historyChangeSummary(
  entry: AdminSettingsHistoryEntry,
  t: (key: string, values?: Record<string, string | number>) => string
): string {
  if (entry.entryType === "stale_mark") {
    return t("admin.affectedSubmissions", { count: entry.affectedCount });
  }
  return entry.changedFields.length > 0 ? entry.changedFields.join(", ") : "-";
}

function historyStaleStatus(
  entry: AdminSettingsHistoryEntry,
  t: (key: string, values?: Record<string, string | number>) => string
): string {
  if (entry.entryType === "stale_mark") {
    return entry.revertedAt === null ? t("admin.staleMarkActive") : t("admin.staleMarkReverted");
  }
  return entry.staleMarked ? t("admin.staleMarkedWithChange") : t("admin.noStaleMark");
}

function formatHistoryDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function parseNumberField(_field: NumericFieldKey, value: string): NumericFormValue {
  if (value === "") {
    return "";
  }
  return Number(value);
}

function numberForPayload(value: NumericFormValue, field: NumericFieldKey): number {
  return value === "" || value === null ? defaultNumericValues[field] : value;
}

function numberInputValue(value: NumericFormValue): string {
  return value === "" || value === null ? "" : String(value);
}
