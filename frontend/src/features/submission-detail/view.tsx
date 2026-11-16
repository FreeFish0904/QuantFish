import { CircleQuestionMark, FileDown, TableProperties } from "lucide-react";
import { useEffect, useId, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { useI18n } from "../../shared/i18n";
import { ComposedChart } from "../../shared/charts/ComposedChart/ComposedChart";
import { downloadTextFile, toCsv } from "../../shared/downloads/download";
import { Badge, type BadgeStatus } from "../../shared/ui/Badge/Badge";
import { dataTrackLabelKey } from "../../shared/submissions/dataTrack";
import { ExecutionParametersTable } from "../../shared/submissions/ExecutionParametersTable";
import { isLongShortExecutionMode } from "../../shared/submissions/executionParameters";
import { Button } from "../../shared/ui/Button/Button";
import { Card } from "../../shared/ui/Card/Card";
import { DataTable } from "../../shared/ui/DataTable/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { toSubmissionDetailDisplay, useSubmissionDetail, type MetricRow, type PerformanceRow } from "./model";
import { KpiCard } from "./ui/KpiCard";
import styles from "./view.module.css";

type RangeKey = "1M" | "3M" | "1YR" | "ALL";

const ranges: RangeKey[] = ["1M", "3M", "1YR", "ALL"];

function mapStatusToBadge(status: string): { status: BadgeStatus; labelKey: string } {
  switch (status) {
    case "queued":
      return { status: "queued", labelKey: "common.queued" };
    case "running":
      return { status: "running", labelKey: "common.running" };
    case "completed":
      return { status: "scored", labelKey: "common.scored" };
    case "failed":
      return { status: "failed", labelKey: "common.failed" };
    default:
      return { status: "offline", labelKey: `common.${status}` };
  }
}

const kpiLabelKeys: Record<string, string> = {
  "total-return": "compare.totalReturn",
  "annual-return": "compare.annualReturn",
  sharpe: "leaderboard.sharpe",
  "max-drawdown": "compare.maxDrawdown"
};

const longOnlyKpiLabelKeys: Record<string, string> = {
  "total-return": "submissionDetail.activeTotalReturnKpi",
  "annual-return": "submissionDetail.activeAnnualReturnKpi",
  sharpe: "submissionDetail.activeSharpeKpi",
  "max-drawdown": "submissionDetail.activeMaxDrawdownKpi"
};

const tradeSummaryKeys: Record<string, string> = {
  "Winning trades": "submissionDetail.winningTrades",
  "Average turnover": "submissionDetail.averageTurnover",
  "Trading days": "submissionDetail.tradingDays"
};

const performanceColumns = [
  { key: "period", headerKey: "submissionDetail.period" },
  { key: "long", headerKey: "submissionDetail.long" },
  { key: "short", headerKey: "submissionDetail.short" },
  { key: "longCount", headerKey: "submissionDetail.longNumber" },
  { key: "shortCount", headerKey: "submissionDetail.shortNumber" },
  { key: "sharpe", headerKey: "leaderboard.sharpe" },
  { key: "totalReturn", headerKey: "submissionDetail.totalReturn" },
  { key: "annualizedReturn", headerKey: "submissionDetail.annualizedReturn" },
  { key: "turnover", headerKey: "submissionDetail.turnover" },
  { key: "drawdown", headerKey: "leaderboard.drawdown" },
  { key: "fitness", headerKey: "submissionDetail.fitnessHeader" },
  { key: "calmar", headerKey: "submissionDetail.calmar" }
] as const;

const metricNoteKeys: Record<string, string> = {
  Cumulative: "submissionDetail.cumulative",
  Annualized: "submissionDetail.annualized",
  "Calendar average": "submissionDetail.calendarAverage",
  "Worst calendar year": "submissionDetail.worstCalendarYear",
  "Risk-adjusted": "submissionDetail.riskAdjusted",
  "Worst peak-to-trough": "submissionDetail.worstPeakToTrough",
  "Daily average": "submissionDetail.dailyAverage",
  "Profitable days": "submissionDetail.profitableDays",
  "Long exposure": "submissionDetail.longExposure",
  "Short exposure": "submissionDetail.shortExposure",
  "Long total return": "submissionDetail.longTotalReturn",
  "Short total return": "submissionDetail.shortTotalReturn",
  "Annualized short profit": "submissionDetail.annualizedShortProfit",
  "Long + short": "submissionDetail.longPlusShort",
  "Long - short": "submissionDetail.longMinusShort",
  Observations: "submissionDetail.observations",
  "Daily positions": "submissionDetail.dailyPositions",
  "Return / drawdown": "submissionDetail.returnDrawdown",
  "Sharpe × return / turnover": "submissionDetail.fitness",
  "Raw portfolio": "submissionDetail.rawPortfolio",
  "Benchmark beta": "submissionDetail.benchmarkBeta",
  "Active risk": "submissionDetail.activeRisk",
  "Active Sharpe": "submissionDetail.activeSharpe",
  "Beta-adjusted": "submissionDetail.betaAdjusted",
  "Cumulative active return": "submissionDetail.cumulativeActiveReturn"
};

type Translator = (key: string, values?: Record<string, string | number>) => string;

function MetricHelpButton({
  helpKey,
  label,
  t
}: {
  helpKey: NonNullable<MetricRow["helpKey"]>;
  label: string;
  t: Translator;
}) {
  const tooltipId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const baseKey = `submissionDetail.metricHelp.${helpKey}`;

  return (
    <span
      className={styles.metricHelp}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <button
        aria-describedby={isOpen ? tooltipId : undefined}
        aria-label={t("submissionDetail.metricHelpLabel", { metric: label })}
        className={styles.metricHelpButton}
        onBlur={() => setIsOpen(false)}
        onFocus={() => setIsOpen(true)}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setIsOpen(false);
          }
        }}
        type="button"
      >
        <CircleQuestionMark aria-hidden="true" size={14} />
      </button>
      {isOpen ? (
        <span className={styles.metricHelpTooltip} id={tooltipId} role="tooltip">
          <span>{t(`${baseKey}.description`)}</span>
          <span className={styles.metricHelpFormula}>
            <span>{t("submissionDetail.metricHelpFormulaLabel")}</span>
            <code>{t(`${baseKey}.formula`)}</code>
          </span>
          <span>{t(`${baseKey}.assumptions`)}</span>
        </span>
      ) : null}
    </span>
  );
}

function renderMetricName(row: MetricRow, t: Translator) {
  return (
    <span className={styles.metricName}>
      <span>{row.metric}</span>
      {row.helpKey ? <MetricHelpButton helpKey={row.helpKey} label={row.metric} t={t} /> : null}
    </span>
  );
}

function renderMetricNote(note: string, t: (key: string) => string): string {
  const normalizedNote = note.trim();
  if (!normalizedNote) {
    return "—";
  }
  const translationKey = metricNoteKeys[normalizedNote];
  return translationKey ? t(translationKey) : normalizedNote;
}

function groupDisplayLabel(
  group: { isBest: boolean; label: string },
  t: (key: string, values?: Record<string, string | number>) => string
): string {
  return group.isBest ? t("submissionDetail.bestGroupLabel", { group: group.label }) : group.label;
}

export function SubmissionDetailView() {
  const { t } = useI18n();
  const { submissionId } = useParams<{ submissionId: string }>();
  const { data, isLoading, error, refetch } = useSubmissionDetail(submissionId ?? "");
  const [range, setRange] = useState<RangeKey>("ALL");
  const [showBenchmark, setShowBenchmark] = useState(false);
  const [showAlpha, setShowAlpha] = useState(false);
  const display = useMemo(() => (data ? toSubmissionDetailDisplay(data) : null), [data]);
  const groupChartSeries = useMemo(
    () =>
      (data?.groupSeries ?? [])
        .map((group) => ({
          color: group.color,
          id: group.id,
          name: groupDisplayLabel(group, t)
        })),
    [data?.groupSeries, t]
  );

  useEffect(() => {
    if (!data) {
      return;
    }
    if (!data.performanceAvailability.hasBenchmark) {
      setShowBenchmark(false);
    }
    if (!data.performanceAvailability.hasAlpha || isLongShortExecutionMode(data.executionParameters)) {
      setShowAlpha(false);
    }
  }, [data]);

  if (error) {
    return (
      <section className={styles.view} aria-label={t("submissionDetail.errorTitle")}>
        <ErrorState title={t("submissionDetail.errorTitle")} message={error.message} onRetry={refetch} />
      </section>
    );
  }

  if (isLoading || !data || !display) {
    return (
      <section className={styles.view} aria-label={t("submissionDetail.loadingTitle")}>
        <EmptyState title={t("submissionDetail.loadingTitle")} description={t("submissionDetail.loadingDescription")} />
      </section>
    );
  }

  const badge = mapStatusToBadge(data.status);
  const alphaApplicable = !isLongShortExecutionMode(data.executionParameters);
  const hasMissingPerformanceSeries =
    !data.performanceAvailability.hasBenchmark || (alphaApplicable && !data.performanceAvailability.hasAlpha);
  const benchmarkEnabled = data.performanceAvailability.hasBenchmark;
  const alphaEnabled = alphaApplicable && data.performanceAvailability.hasAlpha;

  const downloadCurveCsv = () => {
    const columns = [
      "date",
      "strategy_equity",
      "strategy_pct_change",
      "benchmark",
      "alpha",
      "drawdown",
      "daily_pnl"
    ];
    const rows = data.equityCurve.map((point) => ({
      date: point.date,
      strategy_equity: point.strategyEquityCny,
      strategy_pct_change: point.strategyPercentChange,
      benchmark: point.benchmark,
      alpha: point.alpha,
      drawdown: point.drawdown,
      daily_pnl: point.dailyPnl
    }));
    downloadTextFile(
      `${data.submissionId}-equity-curve.csv`,
      toCsv(rows, columns),
      "text/csv;charset=utf-8"
    );
  };

  const downloadMetricsJson = () => {
    const payload = {
      submission_id: data.submissionId,
      submission_label: data.submissionLabel,
      team: data.teamName,
      status: data.status,
      stale: data.isStale,
      submitted_at: data.submittedAt,
      scored_at: data.scoredAt ?? null,
      kpis: Object.fromEntries(display.kpis.map((kpi) => [kpi.id, kpi.value])),
      metrics: Object.fromEntries(display.metricRows.map((row) => [row.metric, row.value])),
      trade_summary: Object.fromEntries(
        display.tradeSummaryRows.map((row) => [row.label, row.value])
      )
    };
    downloadTextFile(
      `${data.submissionId}-metrics.json`,
      JSON.stringify(payload, null, 2),
      "application/json"
    );
  };

  return (
    <section className={styles.view} aria-labelledby="submission-detail-title">
      <header className={styles.header}>
        <div>
          <h2 className={styles.title} id="submission-detail-title">
            {data.submissionLabel}
          </h2>
          <p className={styles.meta}>
            {t("submissionDetail.teamLabel", { team: data.teamName })}
            {" · "}
            {t("submissionDetail.fileLabel", { filename: data.originalFilename })}
            {" · "}
            {t("submissionDetail.trackLabel", { track: t(dataTrackLabelKey(data.dataTrack)) })}
            {" · "}
            {t("submissionDetail.submittedAt", { time: new Date(data.submittedAt).toLocaleString() })}
          </p>
        </div>
        <div className={styles.headerAside}>
          <Badge status={badge.status} label={t(badge.labelKey)} />
          <div className={styles.downloads}>
            {data.status === "completed" && data.pdfReportAvailable ? (
              <a
                className={styles.downloadLink}
                href={`/api/submissions/${encodeURIComponent(data.submissionId)}/report`}
              >
                <FileDown aria-hidden="true" size={15} />
                {t("submissionDetail.downloadPdf")}
              </a>
            ) : null}
            <button
              className={styles.downloadLink}
              disabled={data.equityCurve.length === 0}
              onClick={downloadCurveCsv}
              type="button"
            >
              <TableProperties aria-hidden="true" size={15} />
              {t("submissionDetail.downloadCurve")}
            </button>
            <button
              className={styles.downloadLink}
              disabled={display.metricRows.length === 0}
              onClick={downloadMetricsJson}
              type="button"
            >
              <FileDown aria-hidden="true" size={15} />
              {t("submissionDetail.downloadMetrics")}
            </button>
          </div>
        </div>
      </header>

      {data.isStale ? (
        <p className={[styles.panelNotice, styles.panelNoticeWarning].join(" ")}>
          {t("submissionDetail.staleResultNotice")}
        </p>
      ) : null}

      <div className={styles.kpiGrid}>
        {display.kpis.map((kpi) => (
          <KpiCard
            key={kpi.id}
            label={t((alphaApplicable ? longOnlyKpiLabelKeys : kpiLabelKeys)[kpi.id] ?? kpi.label)}
            tone={kpi.tone}
            value={kpi.value}
          />
        ))}
      </div>

      {alphaApplicable ? (
        <p className={styles.panelNotice}>{t("submissionDetail.longOnlyReturnSurfaceNotice")}</p>
      ) : null}

      <section className={styles.panel} aria-labelledby="run-chart-title">
        <Card
          header={
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.panelTitle} id="run-chart-title">
                  {t("submissionDetail.equityDrawdownTitle")}
                </h3>
                <p className={styles.panelMeta}>{t("submissionDetail.rangeLabel", { range })}</p>
              </div>
              <div className={styles.segmented} role="group" aria-label={t("submissionDetail.chartRange")}>
                {ranges.map((item) => (
                  <Button
                    aria-pressed={range === item}
                    key={item}
                    variant={range === item ? "primary" : "ghost"}
                    onClick={() => setRange(item)}
                  >
                    {item}
                  </Button>
                ))}
              </div>
              <label className={styles.toggle}>
                <input
                  checked={benchmarkEnabled && showBenchmark}
                  disabled={!benchmarkEnabled}
                  onChange={(event) => setShowBenchmark(event.target.checked)}
                  type="checkbox"
                />
                {t("submissionDetail.benchmarkToggle")}
              </label>
              {alphaApplicable ? (
                <label className={styles.toggle}>
                  <input
                    checked={alphaEnabled && showAlpha}
                    disabled={!alphaEnabled}
                    onChange={(event) => setShowAlpha(event.target.checked)}
                    type="checkbox"
                  />
                  {t("submissionDetail.alphaToggle")}
                </label>
              ) : null}
            </div>
          }
        >
          {hasMissingPerformanceSeries ? (
            <p className={[styles.panelNotice, styles.panelNoticeWarning].join(" ")}>
              {t("submissionDetail.performanceSeriesUnavailable")}
            </p>
          ) : null}
          <div className={styles.chartStack}>
            <ComposedChart
              hasAlpha={data.performanceAvailability.hasAlpha}
              hasBenchmark={data.performanceAvailability.hasBenchmark}
              height={320}
              points={data.equityCurve}
              range={range}
              showAlpha={alphaEnabled && showAlpha}
              showBenchmark={benchmarkEnabled && showBenchmark}
              title={t("submissionDetail.equityDrawdownTitle")}
            />
            {groupChartSeries.length > 0 ? (
              <ComposedChart
                chartMode="groups"
                groupSeries={groupChartSeries}
                height={220}
                points={data.equityCurve}
                range={range}
                title={t("submissionDetail.resultGroupPerformanceTitle")}
              />
            ) : null}
          </div>
        </Card>
      </section>

      <section className={styles.panel} aria-labelledby="execution-parameters-title">
        <Card
          header={
            <div>
              <h3 className={styles.panelTitle} id="execution-parameters-title">
                {t("executionParameters.title")}
              </h3>
              <p className={styles.panelMeta}>{t("executionParameters.description")}</p>
            </div>
          }
        >
          <ExecutionParametersTable parameters={data.executionParameters} />
        </Card>
      </section>

      <section className={styles.panel} aria-labelledby="yearly-performance-title">
        <Card
          header={
            <div>
              <h3 className={styles.panelTitle} id="yearly-performance-title">
                {t("submissionDetail.yearlyPerformanceTitle")}
              </h3>
              <p className={styles.panelMeta}>{t("submissionDetail.yearlyPerformanceDescription")}</p>
            </div>
          }
        >
          <DataTable<PerformanceRow>
            caption={t("submissionDetail.yearlyPerformanceTitle")}
            columns={performanceColumns.map((column) => ({
              key: column.key,
              header: t(column.headerKey),
              render: (row: PerformanceRow) => row[column.key],
              align: column.key === "period" ? "left" : "right"
            }))}
            empty={
              <EmptyState
                title={t("submissionDetail.yearlyPerformanceEmptyTitle")}
                description={t("submissionDetail.yearlyPerformanceUnavailable")}
              />
            }
            getRowId={(row) => row.period}
            rows={data.performanceRows}
          />
        </Card>
      </section>

      <section className={styles.panel} aria-labelledby="trade-summary-title">
        <Card
          header={
            <div>
              <h3 className={styles.panelTitle} id="trade-summary-title">
                {t("submissionDetail.tradeSummaryTitle")}
              </h3>
              <p className={styles.panelMeta}>{t("submissionDetail.tradeSummaryDescription")}</p>
            </div>
          }
        >
          <DataTable
            caption={t("submissionDetail.tradeSummaryTitle")}
            columns={[
              { key: "label", header: t("submissionDetail.metric"), render: (row) => row.label },
              { key: "value", header: t("submissionDetail.value"), render: (row) => row.value, align: "right" }
            ]}
            getRowId={(row) => row.label}
            rows={display.tradeSummaryRows.map((row) => ({
              ...row,
              label: t(tradeSummaryKeys[row.label] ?? row.label)
            }))}
          />
        </Card>
      </section>

      <section className={styles.panel} aria-labelledby="metrics-title">
        <Card
          header={
            <div>
              <h3 className={styles.panelTitle} id="metrics-title">
                {t("submissionDetail.metricTableTitle")}
              </h3>
              <p className={styles.panelMeta}>{t("submissionDetail.metricTableDescription")}</p>
            </div>
          }
        >
          <DataTable
            caption={t("submissionDetail.metricTableTitle")}
            columns={[
              { key: "metric", header: t("submissionDetail.metric"), render: (row) => renderMetricName(row, t) },
              { key: "value", header: t("submissionDetail.value"), render: (row) => row.value, align: "right" },
              { key: "note", header: t("submissionDetail.note"), render: (row) => renderMetricNote(row.note, t) }
            ]}
            getRowId={(row) => row.metric}
            rows={display.metricRows}
          />
        </Card>
      </section>
    </section>
  );
}
