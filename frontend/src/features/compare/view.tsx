import { Activity, ArrowLeft, LoaderCircle, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ComposedChart } from "../../shared/charts/ComposedChart/ComposedChart";
import { useI18n } from "../../shared/i18n";
import { dataTrackLabelKey } from "../../shared/submissions/dataTrack";
import { ExecutionParametersTable } from "../../shared/submissions/ExecutionParametersTable";
import { isLongShortExecutionMode } from "../../shared/submissions/executionParameters";
import { Badge, type BadgeStatus } from "../../shared/ui/Badge/Badge";
import { Button } from "../../shared/ui/Button/Button";
import { Card } from "../../shared/ui/Card/Card";
import { DataTable } from "../../shared/ui/DataTable/DataTable";
import { EmptyState } from "../../shared/ui/EmptyState/EmptyState";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { MultiLineChart } from "../../shared/charts/MultiLineChart/MultiLineChart";
import type { CompareDetailedSubmission, CompareSubmission, CompareModel } from "./model";
import { useCompareSubmissions } from "./model";
import { useSeriesVisibility } from "../../shared/charts/useSeriesVisibility";
import styles from "./view.module.css";

type RangeKey = "1M" | "3M" | "1YR" | "ALL";

const ranges: RangeKey[] = ["1M", "3M", "1YR", "ALL"];

function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null, digits = 2): string {
  if (value === null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function formatSignedPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(2)}%`;
}

function CompareLoadingState({
  description,
  title
}: {
  description: string;
  title: string;
}) {
  return (
    <div aria-busy="true" aria-live="polite" className={styles.loadingState} role="status">
      <LoaderCircle aria-hidden="true" className={styles.spinner} size={28} />
      <div>
        <p className={styles.loadingTitle}>{title}</p>
        <p className={styles.loadingDescription}>{description}</p>
      </div>
    </div>
  );
}

function statusBadge(status: string): BadgeStatus {
  switch (status) {
    case "completed":
      return "scored";
    case "failed":
      return "failed";
    case "running":
      return "running";
    case "queued":
      return "queued";
    default:
      return "running";
  }
}

function statusLabelKey(status: string): string {
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

function groupDisplayLabel(
  group: { isBest: boolean; label: string },
  t: (key: string, values?: Record<string, string | number>) => string
): string {
  return group.isBest ? t("submissionDetail.bestGroupLabel", { group: group.label }) : group.label;
}

function SubmissionCard({ submission }: { submission: CompareSubmission }) {
  const { t } = useI18n();

  return (
    <Card
      className={styles.card}
      header={
        <div className={styles.cardHeader}>
          <div>
            <h3 className={styles.cardTitle}>{submission.displayName}</h3>
            <p className={styles.cardMeta}>
              {t("compare.submittedBy", { team: submission.teamName })}
              {" · "}
              {t("compare.trackLabel", { track: t(dataTrackLabelKey(submission.dataTrack)) })}
            </p>
          </div>
          <Badge label={t(statusLabelKey(submission.status))} status={statusBadge(submission.status)} />
        </div>
      }
    >
      <div
        className={styles.cardAccent}
        style={{ backgroundColor: submission.color }}
      />
      <div className={styles.kpiGrid}>
        <div className={styles.kpi}>
          <span className={styles.kpiLabel}>{t("compare.totalReturn")}</span>
          <span className={styles.kpiValue}>{formatPercent(submission.totalReturn)}</span>
        </div>
        <div className={styles.kpi}>
          <span className={styles.kpiLabel}>{t("compare.sharpe")}</span>
          <span className={styles.kpiValue}>{formatNumber(submission.sharpe)}</span>
        </div>
        <div className={styles.kpi}>
          <span className={styles.kpiLabel}>{t("compare.maxDrawdown")}</span>
          <span className={styles.kpiValue}>{formatPercent(submission.maxDrawdown)}</span>
        </div>
      </div>
    </Card>
  );
}

function BackToLeaderboardLink() {
  const { t } = useI18n();

  return (
    <Link className={styles.backLink} to="/leaderboard">
      <ArrowLeft aria-hidden="true" size={16} />
      {t("compare.backToLeaderboard")}
    </Link>
  );
}

function DetailedGraphsToggle({
  checked,
  onChange
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const { t } = useI18n();
  return (
    <label className={styles.toggle}>
      <input checked={checked} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span>{t("compare.detailedGraphsToggle")}</span>
    </label>
  );
}

function DetailedCompareChart({
  detailedSubmissions,
  isLoading
}: {
  detailedSubmissions: CompareDetailedSubmission[];
  isLoading: boolean;
}) {
  const { t } = useI18n();
  const [range, setRange] = useState<RangeKey>("ALL");
  const [selectedId, setSelectedId] = useState("");
  const graphOptions = useMemo(
    () => detailedSubmissions.filter((submission) => submission.hasGraphData),
    [detailedSubmissions]
  );
  // No effect needed to keep `selectedId` valid: an id that no longer exists (or
  // an empty one) simply falls back to the first option that has graph data.
  const selected =
    graphOptions.find((submission) => submission.id === selectedId) ?? graphOptions[0];
  const seriesKey = selected
    ? [
        selected.id,
        selected.availability.hasBenchmark,
        selected.availability.hasAlpha,
        isLongShortExecutionMode(selected.executionParameters)
      ].join(":")
    : "none";
  const { setAlpha, setBenchmark, visibility } = useSeriesVisibility(seriesKey);
  const showAlpha = visibility.alpha;
  const showBenchmark = visibility.benchmark;

  if (isLoading && graphOptions.length === 0) {
    return (
      <CompareLoadingState
        description={t("compare.detailedLoadingDescription")}
        title={t("compare.detailedLoadingTitle")}
      />
    );
  }

  if (!selected) {
    return (
      <EmptyState
        title={t("compare.noDetailedGraphTitle")}
        description={t("compare.noDetailedGraphDescription")}
      />
    );
  }

  const benchmarkEnabled = selected.availability.hasBenchmark;
  const alphaApplicable = !isLongShortExecutionMode(selected.executionParameters);
  const alphaEnabled = alphaApplicable && selected.availability.hasAlpha;
  const hasMissingPerformanceSeries =
    !selected.availability.hasBenchmark || (alphaApplicable && !selected.availability.hasAlpha);
  const groupChartSeries = selected.groupSeries.map((group) => ({
    color: group.color,
    id: group.id,
    name: groupDisplayLabel(group, t)
  }));

  return (
    <div className={styles.detailedGraph}>
      <div className={styles.detailToolbar}>
        <label className={styles.detailSelector}>
          <span>{t("compare.detailedGraphSubmission")}</span>
          <select
            aria-label={t("compare.detailedGraphSubmission")}
            onChange={(event) => setSelectedId(event.target.value)}
            value={selected.id}
          >
            {graphOptions.map((submission) => (
              <option key={submission.id} value={submission.id}>
                {submission.displayName} · {t(dataTrackLabelKey(submission.dataTrack))}
              </option>
            ))}
          </select>
        </label>
        <div className={styles.segmented} role="group" aria-label={t("submissionDetail.chartRange")}>
          {ranges.map((item) => (
            <Button
              aria-pressed={range === item}
              key={item}
              onClick={() => setRange(item)}
              variant={range === item ? "primary" : "ghost"}
            >
              {item}
            </Button>
          ))}
        </div>
        <label className={styles.toggle}>
          <input
            checked={benchmarkEnabled && showBenchmark}
            disabled={!benchmarkEnabled}
            onChange={(event) => setBenchmark(event.target.checked)}
            type="checkbox"
          />
          <span>{t("submissionDetail.benchmarkToggle")}</span>
        </label>
        {alphaApplicable ? (
          <label className={styles.toggle}>
            <input
              checked={alphaEnabled && showAlpha}
              disabled={!alphaEnabled}
              onChange={(event) => setAlpha(event.target.checked)}
              type="checkbox"
            />
            <span>{t("submissionDetail.alphaToggle")}</span>
          </label>
        ) : null}
      </div>
      {hasMissingPerformanceSeries ? (
        <p className={styles.panelNotice}>{t("submissionDetail.performanceSeriesUnavailable")}</p>
      ) : null}
      <ComposedChart
        hasAlpha={selected.availability.hasAlpha}
        hasBenchmark={selected.availability.hasBenchmark}
        height={320}
        points={selected.points}
        range={range}
        showAlpha={alphaEnabled && showAlpha}
        showBenchmark={benchmarkEnabled && showBenchmark}
        title={t("compare.detailedPerformanceTitle")}
      />
      {groupChartSeries.length > 0 ? (
        <ComposedChart
          chartMode="groups"
          groupSeries={groupChartSeries}
          height={220}
          points={selected.points}
          range={range}
          title={t("submissionDetail.resultGroupPerformanceTitle")}
        />
      ) : null}
      <section className={styles.executionParametersPanel} aria-labelledby="compare-execution-parameters-title">
        <div>
          <h4 className={styles.executionParametersTitle} id="compare-execution-parameters-title">
            {t("executionParameters.title")}
          </h4>
          <p className={styles.panelDescription}>{t("executionParameters.description")}</p>
        </div>
        <ExecutionParametersTable parameters={selected.executionParameters} />
      </section>
    </div>
  );
}

export function CompareView() {
  const { t } = useI18n();
  const [detailedGraphs, setDetailedGraphs] = useState(false);
  const { submissionIds, model, isLoading, isFetching, isError, error, refetch } =
    useCompareSubmissions(detailedGraphs);

  if (submissionIds.length < 2) {
    return (
      <section className={styles.view} aria-label={t("compare.emptyTitle")}>
        <EmptyState
          action={<BackToLeaderboardLink />}
          title={t("compare.emptyTitle")}
          description={t("compare.emptyDescription")}
        />
      </section>
    );
  }

  if (isError) {
    return (
      <section className={styles.view} aria-label={t("compare.errorTitle")}>
        <ErrorState
          title={t("compare.errorTitle")}
          message={error instanceof Error ? error.message : undefined}
          onRetry={refetch}
        />
      </section>
    );
  }

  if (isLoading || !model) {
    return (
      <section className={styles.view} aria-label={t("compare.loadingTitle")}>
        <CompareLoadingState
          description={t("compare.loadingDescription")}
          title={t("compare.loadingTitle")}
        />
      </section>
    );
  }

  return (
    <CompareDataView
      detailedGraphs={detailedGraphs}
      isDetailedLoading={detailedGraphs && isFetching}
      model={model}
      onDetailedGraphsChange={setDetailedGraphs}
    />
  );
}

function CompareDataView({
  detailedGraphs,
  isDetailedLoading,
  model,
  onDetailedGraphsChange
}: {
  detailedGraphs: boolean;
  isDetailedLoading: boolean;
  model: CompareModel;
  onDetailedGraphsChange: (checked: boolean) => void;
}) {
  const { t } = useI18n();

  if (model.submissions.length < 2) {
    return (
      <section className={styles.view} aria-label={t("compare.emptyTitle")}>
        <EmptyState
          action={<BackToLeaderboardLink />}
          title={t("compare.emptyTitle")}
          description={t("compare.emptyDescription")}
        />
      </section>
    );
  }

  const [primary, secondary] = model.submissions;

  const differenceRows = [
    {
      metric: t("compare.totalReturn"),
      primary: formatPercent(primary.totalReturn),
      secondary: formatPercent(secondary.totalReturn),
      diff: formatSignedPercent(
        (primary.totalReturn ?? 0) - (secondary.totalReturn ?? 0)
      ),
      diffValue: (primary.totalReturn ?? 0) - (secondary.totalReturn ?? 0)
    },
    {
      metric: t("compare.annualReturn"),
      primary: formatPercent(primary.annualReturn),
      secondary: formatPercent(secondary.annualReturn),
      diff: formatSignedPercent(
        (primary.annualReturn ?? 0) - (secondary.annualReturn ?? 0)
      ),
      diffValue: (primary.annualReturn ?? 0) - (secondary.annualReturn ?? 0)
    },
    {
      metric: t("compare.sharpe"),
      primary: formatNumber(primary.sharpe),
      secondary: formatNumber(secondary.sharpe),
      diff: formatNumber((primary.sharpe ?? 0) - (secondary.sharpe ?? 0)),
      diffValue: (primary.sharpe ?? 0) - (secondary.sharpe ?? 0)
    },
    {
      metric: t("compare.maxDrawdown"),
      primary: formatPercent(primary.maxDrawdown),
      secondary: formatPercent(secondary.maxDrawdown),
      diff: formatSignedPercent(
        (primary.maxDrawdown ?? 0) - (secondary.maxDrawdown ?? 0)
      ),
      diffValue: (primary.maxDrawdown ?? 0) - (secondary.maxDrawdown ?? 0)
    }
  ];

  return (
    <section className={styles.view} aria-labelledby="compare-title">
      <header className={styles.header}>
        <div>
          <p className={styles.overline}>{t("compare.eyebrow")}</p>
          <h2 id="compare-title" className={styles.title}>
            {t("compare.title")}
          </h2>
          <p className={styles.subtitle}>
            {t("compare.subtitle", { count: model.submissions.length })}
          </p>
        </div>
        <BackToLeaderboardLink />
      </header>

      <div className={styles.cardGrid}>
        {model.submissions.slice(0, 4).map((submission) => (
          <SubmissionCard key={submission.id} submission={submission} />
        ))}
      </div>

      <section className={styles.panel} aria-labelledby="difference-title">
        <div className={styles.panelHeader}>
          <TrendingUp aria-hidden="true" className={styles.panelHeaderIcon} size={18} />
          <div>
            <h3 id="difference-title" className={styles.panelTitle}>
              {t("compare.kpiDifferencesTitle")}
            </h3>
            <p className={styles.panelDescription}>
              {t("compare.kpiDifferencesDescription", { primary: primary.displayName, secondary: secondary.displayName })}
            </p>
          </div>
        </div>
        <DataTable
          caption={t("compare.kpiDifferencesTitle")}
          columns={[
            { key: "metric", header: t("submissionDetail.metric"), render: (row) => row.metric },
            {
              key: "primary",
              header: primary.displayName,
              render: (row) => row.primary,
              align: "right"
            },
            {
              key: "secondary",
              header: secondary.displayName,
              render: (row) => row.secondary,
              align: "right"
            },
            {
              key: "diff",
              header: t("compare.difference"),
              align: "right",
              render: (row) => {
                const className =
                  row.diffValue > 0
                    ? styles.diffPositive
                    : row.diffValue < 0
                      ? styles.diffNegative
                      : styles.diffZero;
                return <span className={className}>{row.diff}</span>;
              }
            }
          ]}
          getRowId={(row) => row.metric}
          rows={differenceRows}
        />
      </section>

      {detailedGraphs ? (
        <section className={styles.panel} aria-labelledby="detailed-performance-title">
          <div className={styles.panelHeader}>
            <Activity aria-hidden="true" className={styles.panelHeaderIcon} size={18} />
            <div>
              <h3 id="detailed-performance-title" className={styles.panelTitle}>
                {t("compare.detailedPerformanceTitle")}
              </h3>
              <p className={styles.panelDescription}>
                {t("compare.detailedPerformanceDescription")}
              </p>
            </div>
            <DetailedGraphsToggle checked={detailedGraphs} onChange={onDetailedGraphsChange} />
          </div>
          <DetailedCompareChart
            detailedSubmissions={model.detailedSubmissions}
            isLoading={isDetailedLoading}
          />
        </section>
      ) : (
        <>
          <section className={styles.panel} aria-labelledby="aligned-equity-title">
            <div className={styles.panelHeader}>
              <Activity aria-hidden="true" className={styles.panelHeaderIcon} size={18} />
              <div>
                <h3 id="aligned-equity-title" className={styles.panelTitle}>
                  {t("compare.alignedEquityTitle")}
                </h3>
                <p className={styles.panelDescription}>
                  {t("compare.alignedEquityDescription")}
                </p>
              </div>
              <DetailedGraphsToggle checked={detailedGraphs} onChange={onDetailedGraphsChange} />
            </div>
            <MultiLineChart
              data={model.equityData}
              height={320}
              series={model.series}
              title={t("compare.alignedEquityTitle")}
              xKey="date"
            />
          </section>

          <section className={styles.panel} aria-labelledby="aligned-drawdown-title">
            <div className={styles.panelHeader}>
              <Activity aria-hidden="true" className={styles.panelHeaderIcon} size={18} />
              <div>
                <h3 id="aligned-drawdown-title" className={styles.panelTitle}>
                  {t("compare.alignedDrawdownTitle")}
                </h3>
                <p className={styles.panelDescription}>
                  {t("compare.alignedDrawdownDescription")}
                </p>
              </div>
            </div>
            <MultiLineChart
              data={model.drawdownData}
              height={320}
              series={model.series}
              title={t("compare.alignedDrawdownTitle")}
              xKey="date"
            />
          </section>
        </>
      )}
    </section>
  );
}
