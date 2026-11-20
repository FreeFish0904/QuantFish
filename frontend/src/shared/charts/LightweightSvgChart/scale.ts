// Domain and tick maths for `LightweightSvgChart`.
//
// Kept out of the component module so it only exports components
// (`react-refresh/only-export-components`); `LineChart` and `MultiLineChart`
// reuse these helpers directly.

export function readSeriesValue<T extends Record<string, unknown>>(
  point: T,
  dataKey: string
): number | null {
  const value = point[dataKey];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return null;
  }
  return Math.abs(value) < 1e-10 ? 0 : value;
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

export function lightweightDomainForSeries<T extends Record<string, unknown>>(
  data: T[],
  dataKeys: string[],
  includeZero = false
): [number, number] {
  const values: number[] = includeZero ? [0] : [];
  for (const point of data) {
    for (const key of dataKeys) {
      const value = readSeriesValue(point, key);
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
    const padding = Math.max(Math.abs(min) * 0.08, 1);
    min -= padding;
    max += padding;
  } else {
    const padding = (max - min) * 0.08;
    min -= padding;
    max += padding;
  }
  if (includeZero) {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }
  return [min, max];
}

export function lightweightTicks(domain: [number, number], targetIntervals = 4): number[] {
  const [min, max] = domain;
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) {
    return [0, 1];
  }
  const step = niceStep((max - min) / Math.max(1, targetIntervals));
  const start = Math.floor(min / step) * step;
  const end = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  const count = Math.max(1, Math.round((end - start) / step));
  for (let index = 0; index <= count; index += 1) {
    ticks.push(Number((start + step * index).toPrecision(12)));
  }
  return ticks;
}
