import { Save } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { useI18n } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/Button/Button";
import { useUpdateAdminSettings, type AdminSettings } from "../model";
import styles from "./Panels.module.css";

type ScoringPayload = {
  sharpe_weight: number;
  sharpe_target: number;
  annual_return_weight: number;
  annual_return_target: number;
  drawdown_weight: number;
  drawdown_limit: number;
  turnover_weight: number;
  turnover_limit: number;
  short_profit_weight: number;
  short_profit_target: number;
  minimum_slice_trading_days: number;
};

type ScoringPanelProps = {
  settings: AdminSettings;
  isSaving?: boolean;
  onSave?: (scoring: ScoringPayload) => void;
};

const fields: Array<{ key: keyof ScoringPayload; labelKey: string; step: string; min?: number }> = [
  { key: "sharpe_weight", labelKey: "admin.sharpeWeight", step: "0.01", min: 0 },
  { key: "sharpe_target", labelKey: "admin.sharpeTarget", step: "0.01", min: 0.01 },
  { key: "annual_return_weight", labelKey: "admin.annualReturnWeight", step: "0.01", min: 0 },
  { key: "annual_return_target", labelKey: "admin.annualReturnTarget", step: "0.01", min: 0.01 },
  { key: "drawdown_weight", labelKey: "admin.drawdownWeight", step: "0.01", min: 0 },
  { key: "drawdown_limit", labelKey: "admin.drawdownLimit", step: "0.01", min: 0.01 },
  { key: "turnover_weight", labelKey: "admin.turnoverWeight", step: "0.01", min: 0 },
  { key: "turnover_limit", labelKey: "admin.turnoverLimit", step: "0.01", min: 0.01 },
  { key: "short_profit_weight", labelKey: "admin.shortProfitWeight", step: "0.01", min: 0 },
  { key: "short_profit_target", labelKey: "admin.shortProfitTarget", step: "0.01", min: 0.01 },
  { key: "minimum_slice_trading_days", labelKey: "admin.minimumSliceTradingDays", step: "1", min: 1 }
];

function toForm(settings: AdminSettings): ScoringPayload {
  return {
    sharpe_weight: settings.scoring.sharpeWeight,
    sharpe_target: settings.scoring.sharpeTarget,
    annual_return_weight: settings.scoring.annualReturnWeight,
    annual_return_target: settings.scoring.annualReturnTarget,
    drawdown_weight: settings.scoring.drawdownWeight,
    drawdown_limit: settings.scoring.drawdownLimit,
    turnover_weight: settings.scoring.turnoverWeight,
    turnover_limit: settings.scoring.turnoverLimit,
    short_profit_weight: settings.scoring.shortProfitWeight,
    short_profit_target: settings.scoring.shortProfitTarget,
    minimum_slice_trading_days: settings.scoring.minimumSliceTradingDays
  };
}

export function ScoringPanel({ settings, isSaving, onSave }: ScoringPanelProps) {
  const { t } = useI18n();
  const fallbackUpdate = useUpdateAdminSettings();
  const [form, setForm] = useState<ScoringPayload>(() => toForm(settings));

  useEffect(() => {
    setForm(toForm(settings));
  }, [settings]);

  const updateField = (field: keyof ScoringPayload, value: string) => {
    setForm((current) => ({
      ...current,
      [field]: value === "" ? 0 : Number(value)
    }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (onSave) {
      onSave(form);
    } else {
      fallbackUpdate.mutate({ scoring: form });
    }
  };

  return (
    <form className={styles.stack} onSubmit={handleSubmit}>
      <div className={styles.formGrid}>
        {fields.map((field) => (
          <label className={styles.field} htmlFor={`admin-${field.key}`} key={field.key}>
            <span>{t(field.labelKey)}</span>
            <input
              id={`admin-${field.key}`}
              min={field.min}
              onChange={(event) => updateField(field.key, event.target.value)}
              step={field.step}
              type="number"
              value={form[field.key]}
            />
          </label>
        ))}
      </div>
      <p className={styles.readout}>
        {t("admin.scoringFormulaPreview")}
      </p>
      <Button className={styles.saveButton} disabled={isSaving ?? fallbackUpdate.isPending} type="submit">
        <Save aria-hidden="true" size={16} />
        {t("admin.saveScoring")}
      </Button>
    </form>
  );
}
