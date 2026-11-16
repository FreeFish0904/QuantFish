import { useEffect, useMemo, useRef, useState } from "react";

import { LightweightSvgChart, type LightweightSeries } from "../LightweightSvgChart/LightweightSvgChart";
import { useI18n } from "../../i18n";
import { EmptyState } from "../../ui/EmptyState/EmptyState";
import styles from "./ComposedChart.module.css";

const STRATEGY_COLOR = "var(--qf-cyan)";
const BENCHMARK_COLOR = "var(--qf-amber)";
const ALPHA_COLOR = "var(--qf-violet)";
const DRAWDOWN_COLOR = "var(--qf-red)";
const PROFIT_COLOR = "var(--qf-profit)";
const LOSS_COLOR = "var(--qf-loss)";
const AXIS_COLOR = "var(--qf-text-muted)";
const GROUP_DATA_KEY_PREFIX = "groupPercentChange_";
const SECONDARY_CHART_HEIGHT = 150;
const CHART_GAP = 4;
const STACK_VERTICAL_PADDING = 2;
const VIRTUAL_SCROLL_FALLBACK_WIDTH = 760;
const FINITE_RANGE_BUFFER_POINTS = 8;
const VISIBLE_POINTS_BY_RANGE: Record<string, number> = {
  "1M": 22,
  "3M": 66,
  "1YR": 252
};

export type ComposedChartPoint = {
  date: string;
  equity: number;
  strategyEquityCny?: number;
  strategyPercentChange?: number | null;
  benchmark: number | null;
  benchmarkPercentChange?: number | null;
  alpha: number | null;
  alphaPercentChange?: number | null;
  drawdown: number;
  dailyPnl: number;
  buyCny: number;
  sellCny: number;
  groupPercentChanges?: Record<string, number | null>;
};

export type ComposedChartGroupSeries = {
  id: string;
  name: string;
  color: string;
  emphasis?: boolean;
};

export type ComposedChartProps = {
  points: ComposedChartPoint[];
  title: string;
  chartMode?: "performance" | "groups";
  height?: number;
  range?: "1M" | "3M" | "1YR" | "ALL";
  showAlpha?: boolean;
  showBenchmark?: boolean;
  hasAlpha?: boolean;
  hasBenchmark?: boolean;
  groupSeries?: ComposedChartGroupSeries[];
};

type DecoratedPoint = ComposedChartPoint & {
  drawdownMarker: number | null;
  profitPnl: number | null;
  lossPnl: number | null;
  [key: string]: unknown;
};

type PointWindow = {
  start: number;
  end: number;
};

type TooltipPayloadItem = {
  color?: string;
  dataKey?: unknown;
  name?: unknown;
  payload?: Record<string, unknown>;
  value?: unknown;
};

type TooltipRow = {
  color?: string;
  label: string;
  format: "cny" | "percent";
  value: number;
};

type AxisTick = {
  label: string;
  top: number;
  value: number;
};

type AxisKind = "currency" | "percent";

type AxisScale = {
  domain: [number, number];
  ticks: number[];
};

const AXIS_EPSILON = 1e-10;

function chartTitleId(title: string): string {
  return `sf-chart-title-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")}`;
}

function formatCny(value: number): string {
  return new Intl.NumberFormat("en-US", {
    currency: "CNY",
    currencyDisplay: "code",
    maximumFractionDigits: 0,
    style: "currency"
  }).format(value);
}

function formatAxisCny(value: number): string {
  const normalizedValue = normalizeAxisZero(value);
  const abs = Math.abs(normalizedValue);
  if (abs >= 1_000_000_000) {
    return `CNY ${(normalizedValue / 1_000_000_000).toFixed(1)}B`;
  }
  if (abs >= 1_000_000) {
    return `CNY ${(normalizedValue / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `CNY ${(normalizedValue / 1_000).toFixed(0)}K`;
  }
  return `CNY ${normalizedValue.toFixed(0)}`;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function formatAxisPercent(value: number): string {
  const percent = normalizeAxisZero(value) * 100;
  const abs = Math.abs(percent);
  const digits = abs > 0 && abs < 1 ? 1 : 0;
  return `${percent.toFixed(digits)}%`;
}

function visiblePointCount(range: ComposedChartProps["range"], total: number): number {
  if (!range || range === "ALL") {
    return total;
  }
  return Math.min(total, VISIBLE_POINTS_BY_RANGE[range] ?? total);
}

function topDrawdownDates(points: ComposedChartPoint[], start: number, end: number): Set<string> {
  return new Set(
    points
      .slice(start, end + 1)
      .filter((point) => point.drawdown < 0)
      .sort((a, b) => a.drawdown - b.drawdown)
      .slice(0, 3)
      .map((point) => point.date)
  );
}

function tooltipNumber(value: unknown): number | null {
  if (Array.isArray(value)) {
    if (value[0] === null || value[0] === undefined || value[0] === "") {
      return null;
    }
    const number = Number(value[0]);
    return Number.isFinite(number) ? number : null;
  }
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function isDateLikeLabel(value: unknown): value is string {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}(?:[T\s].*)?$/.test(value.trim());
}

function tooltipDate(label: unknown, payload: TooltipPayloadItem[]): string {
  for (const entry of payload) {
    const date = entry.payload?.date;
    if (isDateLikeLabel(date)) {
      return date;
    }
  }
  if (isDateLikeLabel(label)) {
    return label;
  }
  return "";
}

function tooltipRow(entry: TooltipPayloadItem): TooltipRow | null {
  const label = String(entry.name ?? entry.dataKey ?? "");
  if (!label) {
    return null;
  }

  if (entry.dataKey === "drawdownMarker") {
    const value = tooltipNumber(entry.payload?.drawdown);
    return value === null
      ? null
      : {
          color: entry.color,
          format: "percent",
          label,
          value
        };
  }

  const value = tooltipNumber(entry.value);
  const dataKey = String(entry.dataKey ?? "");
  const percentKeys = new Set(["strategyPercentChange", "benchmarkPercentChange", "alphaPercentChange"]);
  return value === null
    ? null
    : {
        color: entry.color,
        format: percentKeys.has(dataKey) || dataKey.startsWith(GROUP_DATA_KEY_PREFIX) ? "percent" : "cny",
        label,
        value
      };
}

function strategyEquityTooltipRow(entry: TooltipPayloadItem, label: string): TooltipRow | null {
  if (entry.dataKey !== "strategyPercentChange") {
    return null;
  }
  const value = tooltipNumber(entry.payload?.strategyEquityCny ?? entry.payload?.equity);
  return value === null
    ? null
    : {
        color: STRATEGY_COLOR,
        format: "cny",
        label,
        value
      };
}

export function PerformanceTooltip({
  active,
  label,
  payload,
  strategyEquityLabel = "Cumulative Return Value"
}: {
  active?: boolean;
  label?: unknown;
  payload?: TooltipPayloadItem[];
  strategyEquityLabel?: string;
}) {
  if (!active || !Array.isArray(payload) || payload.length === 0) {
    return null;
  }
  const rows: TooltipRow[] = [];
  for (const entry of payload) {
    const row = tooltipRow(entry);
    if (row !== null) {
      rows.push(row);
    }
    const strategyEquityRow = strategyEquityTooltipRow(entry, strategyEquityLabel);
    if (strategyEquityRow !== null) {
      rows.push(strategyEquityRow);
    }
  }

  if (rows.length === 0) {
    return null;
  }

  const date = tooltipDate(label, payload);

  return (
    <div className={styles.tooltip} role="tooltip">
      {date ? <div className={styles.tooltipDate}>{date}</div> : null}
      {rows.map((entry) => (
        <div className={styles.tooltipRow} key={`${entry.label}-${entry.value}`}>
          <span className={styles.tooltipSeries}>
            <span className={styles.tooltipSwatch} style={{ background: entry.color ?? AXIS_COLOR }} />
            {entry.label}
          </span>
          <span className={styles.tooltipValue}>
            {entry.format === "percent" ? formatPercent(entry.value) : formatCny(entry.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

function hasSeriesValue(points: ComposedChartPoint[], key: keyof ComposedChartPoint): boolean {
  return points.some((point) => typeof point[key] === "number" && Number.isFinite(point[key]));
}

function recordNumber(point: Record<string, unknown>, field: string): number | null {
  const value = point[field];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function domainFor(
  points: DecoratedPoint[],
  fields: string[],
  includeZero = false,
  minimumPadding = 1
): [number, number] {
  const values: number[] = includeZero ? [0] : [];
  for (const point of points) {
    for (const field of fields) {
      const value = recordNumber(point, field);
      if (value !== null) {
        values.push(value);
      }
    }
  }
  if (values.length === 0) {
    return includeZero ? [0, 1] : [0, 1];
  }
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (min === max) {
    const padding = Math.max(Math.abs(min) * 0.04, minimumPadding);
    min -= padding;
    max += padding;
  }
  if (includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  return [min, max];
}

function normalizeAxisZero(value: number): number {
  return Math.abs(value) < AXIS_EPSILON ? 0 : value;
}

function niceStep(value: number): number {
  if (!Number.isFinite(value) || value <= 0) {
    return 1;
  }
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  if (normalized <= 1) {
    return magnitude;
  }
  if (normalized <= 2) {
    return 2 * magnitude;
  }
  if (normalized <= 5) {
    return 5 * magnitude;
  }
  return 10 * magnitude;
}

function niceAxisBoundary(value: number, kind: AxisKind): number {
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  const minimumBound = kind === "percent" ? 0.1 : 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const normalized = value / magnitude;
  const niceNormalized = [1, 2, 3, 5, 10].find((step) => normalized <= step + AXIS_EPSILON) ?? 10;
  return Math.max(Number((niceNormalized * magnitude).toPrecision(12)), minimumBound);
}

function axisTickStep(bound: number, height: number, kind: AxisKind): number {
  if (!Number.isFinite(bound) || bound <= 0) {
    return kind === "percent" ? 0.1 : 1;
  }
  const targetIntervals = height <= 170 ? 1 : 3;
  const minimumStep = kind === "percent" ? 0.1 : 1;
  return Math.min(bound, Math.max(niceStep(bound / targetIntervals), minimumStep));
}

function axisSideTicks(bound: number, step: number, sign: 1 | -1): number[] {
  if (!Number.isFinite(bound) || bound <= 0 || !Number.isFinite(step) || step <= 0) {
    return [];
  }
  const values: number[] = [];
  for (let value = step; value < bound - AXIS_EPSILON; value += step) {
    values.push(normalizeAxisZero(Number((sign * value).toPrecision(12))));
  }
  values.push(normalizeAxisZero(Number((sign * bound).toPrecision(12))));
  return values;
}

function buildAxisScale(domain: [number, number], height: number, kind: AxisKind): AxisScale {
  const [min, max] = domain;
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    const fallbackStep = kind === "percent" ? 0.01 : 1;
    return {
      domain: [0, fallbackStep],
      ticks: [0, fallbackStep]
    };
  }
  const minWithZero = Math.min(min, 0);
  const maxWithZero = Math.max(max, 0);
  const lowerBound = -niceAxisBoundary(Math.abs(minWithZero), kind);
  const upperBound = niceAxisBoundary(maxWithZero, kind);
  const lowerTicks = axisSideTicks(Math.abs(lowerBound), axisTickStep(Math.abs(lowerBound), height, kind), -1);
  const upperTicks = axisSideTicks(upperBound, axisTickStep(upperBound, height, kind), 1);
  const ticks = [...new Set([...lowerTicks, 0, ...upperTicks])].sort((a, b) => a - b);
  return {
    domain: [lowerBound, upperBound],
    ticks
  };
}

function isAxisScale(value: [number, number] | AxisScale): value is AxisScale {
  return !Array.isArray(value);
}

export function visibleAxisTicks(
  axis: [number, number] | AxisScale,
  height: number,
  formatter: (value: number) => string = formatAxisCny,
  kind: AxisKind = formatter === formatAxisCny ? "currency" : "percent"
): AxisTick[] {
  const scale = isAxisScale(axis) ? axis : buildAxisScale(axis, height, kind);
  const [min, max] = scale.domain;
  const span = max - min || 1;
  const edgePadding = Math.min(24, Math.max(18, height * 0.08));
  const minGap = 40;
  const seenLabels = new Set<string>();
  const visible: AxisTick[] = [];
  const candidates = [...scale.ticks]
    .sort((a, b) => {
      if (a === 0) return -1;
      if (b === 0) return 1;
      const aExtreme = a === min || a === max ? 0 : 1;
      const bExtreme = b === min || b === max ? 0 : 1;
      if (aExtreme !== bExtreme) {
        return aExtreme - bExtreme;
      }
      return Math.abs(b) - Math.abs(a);
    });

  for (const value of candidates) {
    const normalizedValue = normalizeAxisZero(value);
    const label = formatter(normalizedValue);
    if (seenLabels.has(label)) {
      continue;
    }
    const ratio = 1 - (normalizedValue - min) / span;
    const top = Math.min(height - edgePadding, Math.max(edgePadding, ratio * height));
    if (visible.some((tick) => Math.abs(tick.top - top) < minGap)) {
      continue;
    }
    seenLabels.add(label);
    visible.push({ label, top, value: normalizedValue });
  }
  return visible.sort((a, b) => b.value - a.value);
}

function addExtremaIndices(points: ComposedChartPoint[], keep: Set<number>) {
  const keys: Array<keyof ComposedChartPoint> = [
    "equity",
    "strategyEquityCny",
    "strategyPercentChange",
    "benchmarkPercentChange",
    "alphaPercentChange",
    "dailyPnl",
    "buyCny",
    "sellCny"
  ];
  const scan = (value: unknown, index: number, extrema: { minIndex: number; maxIndex: number; minValue: number; maxValue: number }) => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return;
    }
    if (value < extrema.minValue) {
      extrema.minValue = value;
      extrema.minIndex = index;
    }
    if (value > extrema.maxValue) {
      extrema.maxValue = value;
      extrema.maxIndex = index;
    }
  };
  for (const key of keys) {
    const extrema = {
      maxIndex: -1,
      maxValue: Number.NEGATIVE_INFINITY,
      minIndex: -1,
      minValue: Number.POSITIVE_INFINITY
    };
    points.forEach((point, index) => {
      scan(point[key], index, extrema);
    });
    if (extrema.minIndex >= 0) keep.add(extrema.minIndex);
    if (extrema.maxIndex >= 0) keep.add(extrema.maxIndex);
  }

  const groupExtrema = {
    maxIndex: -1,
    maxValue: Number.NEGATIVE_INFINITY,
    minIndex: -1,
    minValue: Number.POSITIVE_INFINITY
  };
  points.forEach((point, index) => {
    Object.values(point.groupPercentChanges ?? {}).forEach((value) => scan(value, index, groupExtrema));
  });
  if (groupExtrema.minIndex >= 0) {
    keep.add(groupExtrema.minIndex);
  }
  if (groupExtrema.maxIndex >= 0) {
    keep.add(groupExtrema.maxIndex);
  }
}

function downsampleAllPoints(points: ComposedChartPoint[], maxPoints: number): ComposedChartPoint[] {
  if (points.length <= maxPoints) {
    return points;
  }

  const keep = new Set<number>([0, points.length - 1]);
  addExtremaIndices(points, keep);
  points
    .map((point, index) => ({ drawdown: point.drawdown, index }))
    .filter((point) => point.drawdown < 0)
    .sort((a, b) => a.drawdown - b.drawdown)
    .slice(0, 3)
    .forEach((point) => keep.add(point.index));

  const remaining = Math.max(0, maxPoints - keep.size);
  if (remaining > 0) {
    for (let sample = 0; sample < remaining; sample += 1) {
      const ratio = remaining === 1 ? 0 : sample / (remaining - 1);
      keep.add(Math.round(ratio * (points.length - 1)));
    }
  }

  const sorted = [...keep].sort((a, b) => a - b);
  const trimmed =
    sorted.length <= maxPoints
      ? sorted
      : [0, ...sorted.filter((index) => index !== 0 && index !== points.length - 1).slice(0, maxPoints - 2), points.length - 1].sort(
          (a, b) => a - b
        );

  return trimmed.map((index) => points[index]);
}

function LegendItem({
  color,
  dot = false,
  label,
  unavailable = false
}: {
  color: string;
  dot?: boolean;
  label: string;
  unavailable?: boolean;
}) {
  return (
    <span className={`${styles.legendItem} ${unavailable ? styles.legendUnavailable : ""}`}>
      <span className={dot ? styles.dotSwatch : styles.swatch} style={{ background: color }} />
      {label}
    </span>
  );
}

function AxisRail({
  height,
  label,
  ticks,
  side = "left"
}: {
  height: number;
  label: string;
  ticks: AxisTick[];
  side?: "left" | "right";
}) {
  return (
    <div
      className={`${styles.axisRail} ${side === "right" ? styles.axisRailRight : ""}`}
      data-testid="fixed-y-axis-rail"
      style={{ height }}
      aria-hidden="true"
    >
      <span className={styles.axisRailTitle}>{label}</span>
      {ticks.map((tick) => (
        <span
          className={styles.axisTick}
          key={`${tick.label}-${tick.top}`}
          style={{ top: tick.top }}
        >
          <span className={styles.axisTickLabel}>{tick.label}</span>
          <span className={styles.axisTickRule} />
        </span>
      ))}
    </div>
  );
}

function requestFrame(callback: () => void): number {
  if (typeof window !== "undefined" && typeof window.requestAnimationFrame === "function") {
    return window.requestAnimationFrame(callback);
  }
  return window.setTimeout(callback, 16);
}

function cancelFrame(handle: number) {
  if (typeof window !== "undefined" && typeof window.cancelAnimationFrame === "function") {
    window.cancelAnimationFrame(handle);
    return;
  }
  window.clearTimeout(handle);
}

export function ComposedChart({
  points,
  title,
  chartMode = "performance",
  height = 280,
  range = "ALL",
  showAlpha = false,
  showBenchmark = false,
  hasAlpha,
  hasBenchmark,
  groupSeries = []
}: ComposedChartProps) {
  const { t } = useI18n();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const [viewportWidth, setViewportWidth] = useState(VIRTUAL_SCROLL_FALLBACK_WIDTH);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [visibleRange, setVisibleRange] = useState<PointWindow>({
    start: 0,
    end: Math.max(0, points.length - 1)
  });
  const visibleCount = visiblePointCount(range, points.length);
  const isScrollable = range !== "ALL" && points.length > visibleCount;
  const plotWidth = isScrollable
    ? Math.max(viewportWidth, Math.ceil((points.length / Math.max(visibleCount, 1)) * viewportWidth))
    : viewportWidth;
  const isGroupChart = chartMode === "groups";
  const stackHeight = isGroupChart
    ? height + STACK_VERTICAL_PADDING * 2
    : height + SECONDARY_CHART_HEIGHT * 2 + CHART_GAP * 2 + STACK_VERTICAL_PADDING * 2;
  const benchmarkAvailable = hasBenchmark ?? hasSeriesValue(points, "benchmarkPercentChange");
  const alphaAvailable = hasAlpha ?? hasSeriesValue(points, "alphaPercentChange");
  const renderBenchmark = !isGroupChart && showBenchmark && benchmarkAvailable;
  const renderAlpha = !isGroupChart && showAlpha && alphaAvailable;
  const visibleGroupSeries = useMemo(
    () =>
      groupSeries.map((series, index) => ({
        ...series,
        dataKey: `${GROUP_DATA_KEY_PREFIX}${index}`
      })),
    [groupSeries]
  );

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) {
      return;
    }
    const updateWidth = () => {
      setViewportWidth(Math.max(320, node.clientWidth || VIRTUAL_SCROLL_FALLBACK_WIDTH));
    };
    updateWidth();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(updateWidth);
      observer.observe(node);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  useEffect(() => {
    return () => {
      if (frameRef.current !== null) {
        cancelFrame(frameRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const total = points.length;
    const windowSize = visiblePointCount(range, total);
    const start = range === "ALL" ? 0 : Math.max(0, total - windowSize);
    const end = range === "ALL" ? Math.max(0, total - 1) : Math.max(0, total - 1);
    setVisibleRange({ start, end });
    if (!isScrollable) {
      setScrollLeft(0);
      return;
    }
    const maxScroll = Math.max(0, plotWidth - viewportWidth);
    setScrollLeft(maxScroll);
    if (scrollRef.current) {
      scrollRef.current.scrollLeft = maxScroll;
    }
  }, [isScrollable, plotWidth, points.length, range, viewportWidth]);

  function updateVisibleRange() {
    const node = scrollRef.current;
    const total = points.length;
    const windowSize = visiblePointCount(range, total);
    if (!node || range === "ALL" || total <= windowSize) {
      setScrollLeft(0);
      setVisibleRange({ start: 0, end: Math.max(0, total - 1) });
      return;
    }
    const maxScroll = Math.max(1, plotWidth - viewportWidth);
    const nextScrollLeft = Math.min(maxScroll, Math.max(0, node.scrollLeft));
    const ratio = nextScrollLeft / maxScroll;
    const start = Math.round((total - windowSize) * ratio);
    const end = Math.min(total - 1, start + windowSize - 1);
    setScrollLeft(nextScrollLeft);
    setVisibleRange((current) => (current.start === start && current.end === end ? current : { start, end }));
  }

  function scheduleVisibleRangeUpdate() {
    if (frameRef.current !== null) {
      return;
    }
    frameRef.current = requestFrame(() => {
      frameRef.current = null;
      updateVisibleRange();
    });
  }

  const renderWindow = useMemo<PointWindow>(() => {
    if (!isScrollable) {
      return { start: 0, end: Math.max(0, points.length - 1) };
    }
    return {
      start: Math.max(0, visibleRange.start - FINITE_RANGE_BUFFER_POINTS),
      end: Math.min(points.length - 1, visibleRange.end + FINITE_RANGE_BUFFER_POINTS)
    };
  }, [isScrollable, points.length, visibleRange]);

  const renderedSourcePoints = useMemo(() => {
    if (range === "ALL") {
      const maxAllPoints = Math.max(180, Math.floor(viewportWidth * 0.55));
      return downsampleAllPoints(points, maxAllPoints);
    }
    return points.slice(renderWindow.start, renderWindow.end + 1);
  }, [points, range, renderWindow, viewportWidth]);

  const visibleDrawdownDates = useMemo(
    () => topDrawdownDates(points, visibleRange.start, visibleRange.end),
    [points, visibleRange]
  );

  const decoratedPoints = useMemo<DecoratedPoint[]>(
    () =>
      renderedSourcePoints.map((point) => {
        const groupFields = Object.fromEntries(
          visibleGroupSeries.map((series) => [series.dataKey, point.groupPercentChanges?.[series.id] ?? null])
        );
        return {
          ...point,
          ...groupFields,
          strategyEquityCny: point.strategyEquityCny ?? point.equity,
          drawdownMarker: visibleDrawdownDates.has(point.date) ? point.strategyPercentChange ?? null : null,
          profitPnl: point.dailyPnl > 0 ? point.dailyPnl : null,
          lossPnl: point.dailyPnl < 0 ? point.dailyPnl : null
        };
      }),
    [renderedSourcePoints, visibleDrawdownDates, visibleGroupSeries]
  );

  const groupChangeFields = visibleGroupSeries.map((series) => series.dataKey);
  const changeFields = isGroupChart ? groupChangeFields : ["strategyPercentChange", "drawdownMarker", ...groupChangeFields];
  if (renderBenchmark) {
    changeFields.push("benchmarkPercentChange");
  }
  if (renderAlpha) {
    changeFields.push("alphaPercentChange");
  }
  const changeDomain = domainFor(decoratedPoints, changeFields, true, 0.01);
  const pnlDomain = domainFor(decoratedPoints, ["dailyPnl", "profitPnl", "lossPnl"], true);
  const volumeDomain = domainFor(decoratedPoints, ["buyCny", "sellCny"], true);
  const changeAxis = buildAxisScale(changeDomain, height, "percent");
  const pnlAxis = buildAxisScale(pnlDomain, SECONDARY_CHART_HEIGHT, "currency");
  const volumeAxis = buildAxisScale(volumeDomain, SECONDARY_CHART_HEIGHT, "currency");
  const changeAxisTicks = visibleAxisTicks(changeAxis, height, formatAxisPercent);
  const pnlAxisTicks = visibleAxisTicks(pnlAxis, SECONDARY_CHART_HEIGHT);
  const volumeAxisTicks = visibleAxisTicks(volumeAxis, SECONDARY_CHART_HEIGHT);

  if (points.length === 0) {
    return <EmptyState title={t("charts.noDataTitle")} description={t("charts.noDataDescription")} />;
  }

  const frameClassName = isScrollable ? styles.frameScrollable : styles.frame;
  const groupChangeSeries: LightweightSeries[] = visibleGroupSeries.map(
    (series): LightweightSeries => ({
      color: series.color,
      connectNulls: true,
      dataKey: series.dataKey,
      name: series.name,
      strokeDasharray: series.emphasis ? undefined : "5 4",
      strokeWidth: series.emphasis ? 2.3 : 1.8,
      type: "line"
    })
  );
  const changeSeries: LightweightSeries[] = [
    ...(isGroupChart
      ? []
      : [
          {
            color: STRATEGY_COLOR,
            connectNulls: true,
            dataKey: "strategyPercentChange",
            name: t("charts.strategyChange"),
            strokeWidth: 2.4,
            type: "line" as const
          }
        ]),
    ...groupChangeSeries,
    ...(renderBenchmark
      ? [
          {
            color: BENCHMARK_COLOR,
            connectNulls: true,
            dataKey: "benchmarkPercentChange",
            name: t("charts.benchmarkChange"),
            strokeWidth: 1.9,
            type: "line" as const
          }
        ]
      : []),
    ...(renderAlpha
      ? [
          {
            color: ALPHA_COLOR,
            connectNulls: true,
            dataKey: "alphaPercentChange",
            name: t("charts.alphaChange"),
            strokeWidth: 1.9,
            type: "line" as const
          }
        ]
      : []),
    ...(isGroupChart
      ? []
      : [
          {
            color: DRAWDOWN_COLOR,
            dataKey: "drawdownMarker",
            name: t("charts.topDrawdowns"),
            radius: 4,
            type: "scatter" as const
          }
        ])
  ];
  const pnlSeries: LightweightSeries[] = [
    { color: PROFIT_COLOR, dataKey: "profitPnl", name: t("charts.dailyPnl"), type: "bar" },
    { color: LOSS_COLOR, dataKey: "lossPnl", name: t("charts.dailyPnl"), type: "bar" }
  ];
  const volumeSeries: LightweightSeries[] = [
    { color: PROFIT_COLOR, dataKey: "buyCny", name: t("common.buy"), type: "bar" },
    { color: LOSS_COLOR, dataKey: "sellCny", name: t("common.sell"), type: "bar" }
  ];
  const plotStack = (
    <div
      className={`${styles.plotStack} ${isScrollable ? styles.plotStackFloating : ""}`}
      style={isScrollable ? { transform: `translateX(${scrollLeft}px)`, width: viewportWidth } : { width: "100%" }}
    >
      <LightweightSvgChart
        data={decoratedPoints}
        height={height}
        margin={{ bottom: 28, left: 0, right: 18, top: 16 }}
        series={changeSeries}
        showYAxis={false}
        tooltip={(state) => (
          <PerformanceTooltip
            active
            label={state.label}
            payload={state.payload}
            strategyEquityLabel={t("charts.strategyEquity")}
          />
        )}
        xKey="date"
        yDomain={changeAxis.domain}
        yTickFormatter={formatAxisPercent}
        yTicks={changeAxis.ticks}
      />

      {isGroupChart ? null : (
        <LightweightSvgChart
          data={decoratedPoints}
          height={SECONDARY_CHART_HEIGHT}
          margin={{ bottom: 28, left: 0, right: 18, top: 12 }}
          series={pnlSeries}
          showYAxis={false}
          tooltip={(state) => <PerformanceTooltip active label={state.label} payload={state.payload} />}
          xKey="date"
          yDomain={pnlAxis.domain}
          yTicks={pnlAxis.ticks}
        />
      )}

      {isGroupChart ? null : (
        <LightweightSvgChart
          data={decoratedPoints}
          height={SECONDARY_CHART_HEIGHT}
          margin={{ bottom: 28, left: 0, right: 18, top: 12 }}
          series={volumeSeries}
          showYAxis={false}
          tooltip={(state) => <PerformanceTooltip active label={state.label} payload={state.payload} />}
          xKey="date"
          yDomain={volumeAxis.domain}
          yTicks={volumeAxis.ticks}
        />
      )}
    </div>
  );

  const titleId = chartTitleId(title);

  return (
    <div aria-label={title} aria-labelledby={titleId} className={styles.chart} role="img">
      <span className={styles.chartTitle} id={titleId}>{title}</span>
      <div className={styles.legend}>
        {isGroupChart ? null : <LegendItem color={STRATEGY_COLOR} label={t("charts.strategy")} />}
        {visibleGroupSeries.map((series) => (
          <LegendItem color={series.color} key={series.id} label={series.name} />
        ))}
        {showBenchmark ? (
          <LegendItem
            color={BENCHMARK_COLOR}
            label={
              benchmarkAvailable
                ? t("charts.benchmark")
                : t("charts.unavailable", { name: t("charts.benchmark") })
            }
            unavailable={!benchmarkAvailable}
          />
        ) : null}
        {showAlpha ? (
          <LegendItem
            color={ALPHA_COLOR}
            label={
              alphaAvailable
                ? t("charts.alpha")
                : t("charts.unavailable", { name: t("charts.alpha") })
            }
            unavailable={!alphaAvailable}
          />
        ) : null}
        {isGroupChart ? null : <LegendItem color={DRAWDOWN_COLOR} dot label={t("charts.topDrawdowns")} />}
        {isGroupChart ? null : <LegendItem color={PROFIT_COLOR} label={t("charts.dailyPnl")} />}
        {isGroupChart ? null : <LegendItem color={PROFIT_COLOR} label={t("common.buy")} />}
        {isGroupChart ? null : <LegendItem color={LOSS_COLOR} label={t("common.sell")} />}
        <span className={styles.unitLabel}>{t("charts.percentUnit")}</span>
      </div>
      <div className={styles.chartBody}>
        <div className={styles.axisStack}>
          <AxisRail height={height} label={t("charts.changeFromStartPercent")} ticks={changeAxisTicks} />
          {isGroupChart ? null : (
            <AxisRail height={SECONDARY_CHART_HEIGHT} label={`${t("charts.pnl")} ${t("charts.currencyUnit")}`} ticks={pnlAxisTicks} />
          )}
          {isGroupChart ? null : (
            <AxisRail
              height={SECONDARY_CHART_HEIGHT}
              label={`${t("charts.volume")} ${t("charts.currencyUnit")}`}
              ticks={volumeAxisTicks}
            />
          )}
        </div>
        <div
          className={frameClassName}
          data-drawdown-dates={[...visibleDrawdownDates].join(",")}
          data-rendered-points={decoratedPoints.length}
          data-scroll-throttled="true"
          data-testid="chart-scroll-frame"
          data-visible-points={visibleCount}
          onScroll={scheduleVisibleRangeUpdate}
          ref={scrollRef}
        >
          {isScrollable ? (
            <div className={styles.scrollSpacer} style={{ minHeight: stackHeight, width: plotWidth }}>
              {plotStack}
            </div>
          ) : (
            plotStack
          )}
        </div>
      </div>
    </div>
  );
}
