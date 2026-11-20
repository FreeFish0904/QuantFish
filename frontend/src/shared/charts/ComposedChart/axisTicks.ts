// Axis scaling and label thinning for `ComposedChart`.
//
// These helpers are exported so the chart module only exports components
// (`react-refresh/only-export-components`), and so the tick tests can exercise
// the maths without rendering.

export type AxisTick = {
  label: string;
  top: number;
  value: number;
};

export type AxisKind = "currency" | "percent";

export type AxisScale = {
  domain: [number, number];
  ticks: number[];
};

const AXIS_EPSILON = 1e-10;

function normalizeAxisZero(value: number): number {
  return Math.abs(value) < AXIS_EPSILON ? 0 : value;
}

export function formatAxisCny(value: number): string {
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

export function formatAxisPercent(value: number): string {
  const percent = normalizeAxisZero(value) * 100;
  const abs = Math.abs(percent);
  const digits = abs > 0 && abs < 1 ? 1 : 0;
  return `${percent.toFixed(digits)}%`;
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

export function buildAxisScale(domain: [number, number], height: number, kind: AxisKind): AxisScale {
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
  const lowerTicks = axisSideTicks(
    Math.abs(lowerBound),
    axisTickStep(Math.abs(lowerBound), height, kind),
    -1
  );
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
  const candidates = [...scale.ticks].sort((a, b) => {
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
