import type { components } from "../api/generated/api-types";
import { dataTrackLabelKey, normalizeDataTrack } from "./dataTrack";

export type SubmissionExecutionParameters = components["schemas"]["SubmissionExecutionParameters"];

export type ExecutionParameterRow = {
  id: string;
  label: string;
  value: string;
};

type Translator = (key: string, variables?: Record<string, string | number>) => string;

const marketTypeKeys: Record<number, string> = {
  1: "marketTypes.shanghaiA",
  2: "marketTypes.shanghaiB",
  4: "marketTypes.shenzhenA",
  8: "marketTypes.shenzhenB",
  16: "marketTypes.chiNext",
  32: "marketTypes.starMarket",
  64: "marketTypes.beijingA"
};

function blank(value: unknown): boolean {
  return value === null || value === undefined || value === "";
}

function trimNumber(value: number, maximumFractionDigits = 4): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
    minimumFractionDigits: 0
  }).format(value);
}

function formatRaw(value: unknown): string {
  return blank(value) ? "—" : String(value);
}

function formatCny(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  return new Intl.NumberFormat("en-US", {
    currency: "CNY",
    currencyDisplay: "code",
    maximumFractionDigits: 0,
    style: "currency"
  }).format(number);
}

function formatRate(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  return `${trimNumber(number * 100)}%`;
}

function formatLeverage(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  return `${trimNumber(number, 2)}x`;
}

function formatBoolean(value: unknown, t: Translator): string {
  if (typeof value !== "boolean") {
    return "—";
  }
  return value ? t("executionParameters.yes") : t("executionParameters.no");
}

function formatMarketTypes(value: unknown, t: Translator): string {
  if (!Array.isArray(value) || value.length === 0) {
    return "—";
  }
  return value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
    .map((item) => {
      const key = marketTypeKeys[item];
      const label = key ? t(key) : undefined;
      return label ? `${item} ${label}` : String(item);
    })
    .join(", ");
}

function formatScoringWindow(parameters: SubmissionExecutionParameters, t: Translator): string {
  if (blank(parameters.scoring_start) && blank(parameters.scoring_end)) {
    return "—";
  }
  return t("executionParameters.dateRange", {
    end: formatRaw(parameters.scoring_end),
    start: formatRaw(parameters.scoring_start)
  });
}

function formatTimeout(parameters: SubmissionExecutionParameters, t: Translator): string {
  if (parameters.submission_timeout_enabled === false) {
    return t("executionParameters.disabled");
  }
  if (parameters.submission_timeout_enabled === true && !blank(parameters.submission_timeout_seconds)) {
    return t("executionParameters.seconds", {
      seconds: Number(parameters.submission_timeout_seconds)
    });
  }
  return "—";
}

export function isLongShortExecutionMode(parameters: SubmissionExecutionParameters | null | undefined): boolean {
  return parameters?.long_only !== true;
}

function formatBacktestMode(parameters: SubmissionExecutionParameters, t: Translator): string {
  return parameters.long_only === true
    ? t("executionParameters.longOnlyMode")
    : t("executionParameters.longShortMode");
}

export function buildExecutionParameterRows(
  parameters: SubmissionExecutionParameters | null | undefined,
  t: Translator
): ExecutionParameterRow[] {
  if (!parameters) {
    return [];
  }

  return [
    {
      id: "data_track",
      label: t("executionParameters.dataTrack"),
      value: t(dataTrackLabelKey(normalizeDataTrack(parameters.data_track)))
    },
    {
      id: "data_start",
      label: t("executionParameters.dataStart"),
      value: formatRaw(parameters.data_start)
    },
    {
      id: "scoring_window",
      label: t("executionParameters.scoringWindow"),
      value: formatScoringWindow(parameters, t)
    },
    {
      id: "capital",
      label: t("executionParameters.capital"),
      value: formatCny(parameters.capital)
    },
    {
      id: "execution_mode",
      label: t("executionParameters.backtestMode"),
      value: formatBacktestMode(parameters, t)
    },
    {
      id: "group_count",
      label: t("executionParameters.groupCount"),
      value: formatRaw(parameters.group_count)
    },
    {
      id: "industry_neutralization",
      label: t("executionParameters.industryNeutralization"),
      value: formatBoolean(parameters.industry_neutralization, t)
    },
    {
      id: "price_policy",
      label: t("executionParameters.pricePolicy"),
      value: formatRaw(parameters.price_policy)
    },
    {
      id: "execution_price",
      label: t("executionParameters.executionPrice"),
      value: formatRaw(parameters.execution_price)
    },
    {
      id: "mark_price",
      label: t("executionParameters.markPrice"),
      value: formatRaw(parameters.mark_price)
    },
    {
      id: "long_only_benchmark",
      label: t("executionParameters.longOnlyBenchmark"),
      value: formatRaw(parameters.long_only_benchmark)
    },
    {
      id: "long_only_risk_free_rate",
      label: t("executionParameters.longOnlyRiskFreeRate"),
      value: formatRate(parameters.long_only_risk_free_rate)
    },
    {
      id: "long_only_min_beta_observations",
      label: t("executionParameters.longOnlyMinBetaObservations"),
      value: formatRaw(parameters.long_only_min_beta_observations)
    },
    {
      id: "commission_rate",
      label: t("executionParameters.commission"),
      value: formatRate(parameters.commission_rate)
    },
    {
      id: "slippage_rate",
      label: t("executionParameters.slippage"),
      value: formatRate(parameters.slippage_rate)
    },
    {
      id: "sell_stamp_duty_rate",
      label: t("executionParameters.sellStampDuty"),
      value: formatRate(parameters.sell_stamp_duty_rate)
    },
    {
      id: "max_leverage",
      label: t("executionParameters.maxLeverage"),
      value: formatLeverage(parameters.max_leverage)
    },
    {
      id: "top_k",
      label: t("executionParameters.longShortTopBottomK"),
      value: blank(parameters.top_k) ? t("executionParameters.all") : formatRaw(parameters.top_k)
    },
    {
      id: "allowed_market_types",
      label: t("executionParameters.marketSelection"),
      value: formatMarketTypes(parameters.allowed_market_types, t)
    },
    {
      id: "long_only",
      label: t("executionParameters.longOnly"),
      value: formatBoolean(parameters.long_only, t)
    },
    {
      id: "long_only_weighting",
      label: t("executionParameters.longOnlyWeighting"),
      value: formatRaw(parameters.long_only_weighting)
    },
    {
      id: "long_only_target_count",
      label: t("executionParameters.longOnlyTargetCount"),
      value: formatRaw(parameters.long_only_target_count)
    },
    {
      id: "max_position_weight",
      label: t("executionParameters.maxPositionWeight"),
      value: formatRate(parameters.max_position_weight)
    },
    {
      id: "max_participation_rate",
      label: t("executionParameters.maxParticipationRate"),
      value: formatRate(parameters.max_participation_rate)
    },
    {
      id: "min_listing_days",
      label: t("executionParameters.minListingDays"),
      value: formatRaw(parameters.min_listing_days)
    },
    {
      id: "terminal_stale_position_policy",
      label: t("executionParameters.terminalStalePositionPolicy"),
      value: formatRaw(parameters.terminal_stale_position_policy)
    },
    {
      id: "timeout",
      label: t("executionParameters.timeout"),
      value: formatTimeout(parameters, t)
    }
  ];
}
