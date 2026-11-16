export type PerformancePoint = {
  date: string;
  equity: number;
  strategyEquityCny: number;
  strategyPercentChange: number | null;
  benchmark: number | null;
  benchmarkPercentChange: number | null;
  alpha: number | null;
  alphaPercentChange: number | null;
  drawdown: number;
  dailyPnl: number;
  buyCny: number;
  sellCny: number;
  groupPercentChanges?: Record<string, number | null>;
};

export type PerformanceAvailability = {
  hasAlpha: boolean;
  hasBenchmark: boolean;
};

export type PerformanceGroupSeries = {
  id: string;
  label: string;
  color: string;
  finalCumulativeReturn: number;
  isBest: boolean;
};

export type PerformanceGroupSummary = {
  total_return: number;
  all_return: number;
  annual_return: number;
  average_year_return: number;
  worst_year_return: number;
  sharpe: number;
  max_drawdown: number;
  win_rate: number;
  trading_days: number;
};

type GroupPoint = {
  date: string;
  group: string;
  value: number;
};

type DailyGroupReturn = {
  date: string;
  value: number;
};

const GROUP_COLORS = [
  "#34d399",
  "#fb923c",
  "#60a5fa",
  "#f472b6",
  "#c084fc",
  "#facc15",
  "#2dd4bf",
  "#f87171"
];
const TRADING_DAYS_PER_YEAR = 252;

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  return value as Record<string, unknown>;
}

function asPointSeries(value: unknown): Array<Record<string, unknown>> | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.filter((point): point is Record<string, unknown> => Boolean(asRecord(point)));
}

function datesFromSeries(points: Array<Record<string, unknown>> | undefined): string[] {
  if (!Array.isArray(points)) {
    return [];
  }
  return points.map((point) => String(point.date ?? "")).filter(Boolean);
}

function buildValueMap(points: Array<Record<string, unknown>> | undefined, key: string): Map<string, number> {
  const values = new Map<string, number>();
  if (!Array.isArray(points)) {
    return values;
  }
  for (const point of points) {
    const date = String(point.date ?? "");
    const rawValue = point[key];
    if (rawValue === null || rawValue === undefined || rawValue === "") {
      continue;
    }
    const value = Number(rawValue);
    if (date && Number.isFinite(value)) {
      values.set(date, value);
    }
  }
  return values;
}

function firstNonEmptyMap(...maps: Array<Map<string, number>>): Map<string, number> {
  for (const map of maps) {
    if (map.size > 0) {
      return map;
    }
  }
  return new Map<string, number>();
}

function buildArithmeticValueMap(points: Array<Record<string, unknown>> | undefined, key: string): Map<string, number> {
  const values = new Map<string, number>();
  if (!Array.isArray(points)) {
    return values;
  }

  let cumulative = 1;
  for (const point of points) {
    const date = String(point.date ?? "");
    const rawValue = point[key];
    if (!date || rawValue === null || rawValue === undefined || rawValue === "") {
      continue;
    }
    const value = Number(rawValue);
    if (!Number.isFinite(value)) {
      continue;
    }

    cumulative += value;
    values.set(date, cumulative);
  }
  return values;
}

function numericValue(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function groupSortNumber(groupId: string): number | null {
  const match = groupId.match(/(\d+)$/);
  return match ? Number(match[1]) : null;
}

function compareGroupIds(left: string, right: string): number {
  const leftNumber = groupSortNumber(left);
  const rightNumber = groupSortNumber(right);
  if (leftNumber !== null && rightNumber !== null && leftNumber !== rightNumber) {
    return leftNumber - rightNumber;
  }
  return left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" });
}

function groupLabel(groupId: string): string {
  const groupNumber = groupSortNumber(groupId);
  return groupNumber === null ? groupId : `Group ${groupNumber}`;
}

function groupRowsFromGraphData(graphDataSource: unknown): GroupPoint[] {
  const graphData = asRecord(graphDataSource);
  const rows = asPointSeries(graphData?.group_cumulative);
  if (!rows || rows.length === 0) {
    return [];
  }

  return rows
    .map((point) => {
      const date = String(point.date ?? "");
      const group = String(point.group ?? "");
      const value = numericValue(point.cumulative_return);
      return date && group && value !== null ? { date, group, value } : null;
    })
    .filter((point): point is GroupPoint => point !== null)
    .sort((left, right) => {
      const groupOrder = compareGroupIds(left.group, right.group);
      return groupOrder === 0 ? left.date.localeCompare(right.date) : groupOrder;
    });
}

function buildGroupValueMap(rows: GroupPoint[]): Map<string, Record<string, number>> {
  const values = new Map<string, Record<string, number>>();
  for (const row of rows) {
    values.set(row.date, {
      ...(values.get(row.date) ?? {}),
      [row.group]: row.value
    });
  }
  return values;
}

export function buildGroupSeriesFromGraphData(graphDataSource: unknown): PerformanceGroupSeries[] {
  const rows = groupRowsFromGraphData(graphDataSource);
  if (rows.length === 0) {
    return [];
  }

  const finalByGroup = new Map<string, { date: string; value: number }>();
  for (const row of rows) {
    const current = finalByGroup.get(row.group);
    if (!current || row.date >= current.date) {
      finalByGroup.set(row.group, { date: row.date, value: row.value });
    }
  }

  const groupIds = [...finalByGroup.keys()].sort(compareGroupIds);
  const bestGroupId = groupIds.reduce<string | null>((bestId, groupId) => {
    if (bestId === null) {
      return groupId;
    }
    const bestValue = finalByGroup.get(bestId)?.value ?? Number.NEGATIVE_INFINITY;
    const nextValue = finalByGroup.get(groupId)?.value ?? Number.NEGATIVE_INFINITY;
    return nextValue > bestValue ? groupId : bestId;
  }, null);

  return groupIds.map((groupId, index) => ({
    color: GROUP_COLORS[index % GROUP_COLORS.length],
    finalCumulativeReturn: finalByGroup.get(groupId)?.value ?? 0,
    id: groupId,
    isBest: groupId === bestGroupId,
    label: groupLabel(groupId)
  }));
}

function dailyReturnsFromCumulative(rows: GroupPoint[]): DailyGroupReturn[] {
  const returns: DailyGroupReturn[] = [];
  let previousCumulative = 0;

  for (const row of rows.sort((left, right) => left.date.localeCompare(right.date))) {
    const value = row.value - previousCumulative;
    returns.push({ date: row.date, value });
    previousCumulative = row.value;
  }

  return returns;
}

function annualizedReturn(totalReturn: number, count: number): number {
  if (count <= 0) {
    return 0;
  }
  return (totalReturn * TRADING_DAYS_PER_YEAR) / count;
}

function sharpeRatio(returns: number[]): number {
  if (returns.length < 2) {
    return 0;
  }
  const mean = returns.reduce((total, value) => total + value, 0) / returns.length;
  const variance =
    returns.reduce((total, value) => total + (value - mean) ** 2, 0) / (returns.length - 1);
  const standardDeviation = Math.sqrt(variance);
  return standardDeviation > 0 && Number.isFinite(standardDeviation)
    ? (Math.sqrt(TRADING_DAYS_PER_YEAR) * mean) / standardDeviation
    : 0;
}

function maxDrawdownFromReturns(returns: number[]): number {
  let cumulative = 0;
  let peak = 1;
  let maxDrawdown = 0;

  for (const dailyReturn of returns) {
    cumulative += dailyReturn;
    const equity = 1 + cumulative;
    peak = Math.max(peak, equity);
    if (peak > 0) {
      maxDrawdown = Math.min(maxDrawdown, equity / peak - 1);
    }
  }

  return Math.abs(maxDrawdown);
}

function calendarYearReturns(rows: DailyGroupReturn[]): number[] {
  const byYear = new Map<string, number[]>();
  for (const row of rows) {
    const year = row.date.slice(0, 4);
    byYear.set(year, [...(byYear.get(year) ?? []), row.value]);
  }
  return [...byYear.values()].map((values) => values.reduce((total, value) => total + value, 0));
}

export function buildGroupSummariesFromGraphData(
  graphDataSource: unknown
): Record<string, PerformanceGroupSummary> {
  const rows = groupRowsFromGraphData(graphDataSource);
  if (rows.length === 0) {
    return {};
  }

  const summaries: Record<string, PerformanceGroupSummary> = {};
  const groupIds = [...new Set(rows.map((row) => row.group))].sort(compareGroupIds);
  for (const groupId of groupIds) {
    const groupRows = rows.filter((row) => row.group === groupId);
    const dailyRows = dailyReturnsFromCumulative(groupRows);
    const returns = dailyRows.map((row) => row.value);
    const finalReturn = groupRows[groupRows.length - 1]?.value ?? 0;
    const yearReturns = calendarYearReturns(dailyRows);
    summaries[groupId] = {
      all_return: finalReturn,
      annual_return: annualizedReturn(finalReturn, returns.length),
      average_year_return:
        yearReturns.length === 0
          ? 0
          : yearReturns.reduce((total, value) => total + value, 0) / yearReturns.length,
      max_drawdown: maxDrawdownFromReturns(returns),
      sharpe: sharpeRatio(returns),
      total_return: finalReturn,
      trading_days: returns.length,
      win_rate:
        returns.length === 0
          ? 0
          : returns.filter((value) => value > 0).length / returns.length,
      worst_year_return: yearReturns.length === 0 ? 0 : Math.min(...yearReturns)
    };
  }

  return summaries;
}

function buildPercentChangeMap(valueByDate: Map<string, number>, orderedDates: string[]): Map<string, number> {
  const values = new Map<string, number>();
  let baseline: number | null = null;

  for (const date of orderedDates) {
    const value = valueByDate.get(date);
    if (typeof value !== "number" || !Number.isFinite(value)) {
      continue;
    }
    if (baseline === null) {
      if (value === 0) {
        continue;
      }
      baseline = value;
    }
    values.set(date, value / baseline - 1);
  }

  return values;
}

function buildReturnIndexChangeMap(valueByDate: Map<string, number>, orderedDates: string[]): Map<string, number> {
  const values = new Map<string, number>();

  for (const date of orderedDates) {
    const value = valueByDate.get(date);
    if (typeof value === "number" && Number.isFinite(value)) {
      values.set(date, value - 1);
    }
  }

  return values;
}

export function buildPerformancePointsFromGraphData(graphDataSource: unknown): PerformancePoint[] {
  const graphData = asRecord(graphDataSource);
  if (!graphData) {
    return [];
  }

  const equity = asPointSeries(graphData.equity);
  const equityCny = asPointSeries(graphData.equity_cny);
  if ((!equity || equity.length === 0) && (!equityCny || equityCny.length === 0)) {
    return [];
  }

  const equityByDate = buildValueMap(equity, "equity");
  const equityCnyByDate = buildValueMap(equityCny, "equity_cny");
  const drawdownByDate = buildValueMap(asPointSeries(graphData.drawdown), "drawdown");
  const benchmark = asPointSeries(graphData.benchmark);
  const alpha = asPointSeries(graphData.alpha);
  const dailyPnl = asPointSeries(graphData.daily_pnl);
  const tradeVolume = asPointSeries(graphData.trade_volume);
  const benchmarkByDate = buildValueMap(benchmark, "benchmark_cny");
  const alphaByDate = buildValueMap(alpha, "alpha_cny");
  const pnlByDate = buildValueMap(dailyPnl, "pnl_cny");
  const buyByDate = buildValueMap(tradeVolume, "buy_cny");
  const sellByDate = buildValueMap(tradeVolume, "sell_cny");
  const orderedDates = equity && equity.length > 0 ? datesFromSeries(equity) : datesFromSeries(equityCny);
  const groupValuesByDate = buildGroupValueMap(groupRowsFromGraphData(graphData));
  const benchmarkEquityByDate = firstNonEmptyMap(
    buildValueMap(benchmark, "benchmark_equity"),
    buildArithmeticValueMap(benchmark, "benchmark_return")
  );
  const alphaEquityByDate = firstNonEmptyMap(
    buildValueMap(alpha, "alpha_equity"),
    buildArithmeticValueMap(alpha, "alpha_return")
  );
  const strategyPercentByDate =
    equityByDate.size > 0
      ? buildReturnIndexChangeMap(equityByDate, orderedDates)
      : buildPercentChangeMap(equityCnyByDate, orderedDates);
  const benchmarkPercentByDate =
    benchmarkEquityByDate.size > 0
      ? buildReturnIndexChangeMap(benchmarkEquityByDate, orderedDates)
      : buildPercentChangeMap(buildValueMap(benchmark, "benchmark_cny"), orderedDates);
  const alphaPercentByDate =
    alphaEquityByDate.size > 0
      ? buildReturnIndexChangeMap(alphaEquityByDate, orderedDates)
      : buildPercentChangeMap(buildValueMap(alpha, "alpha_cny"), orderedDates);

  return orderedDates.map((date) => {
    const strategyEquityCny = equityCnyByDate.get(date) ?? equityByDate.get(date) ?? 0;
    const groupPercentChanges = groupValuesByDate.get(date);
    return {
      date,
      equity: strategyEquityCny,
      strategyEquityCny,
      strategyPercentChange: strategyPercentByDate.get(date) ?? null,
      benchmark: benchmarkByDate.get(date) ?? null,
      benchmarkPercentChange: benchmarkPercentByDate.get(date) ?? null,
      alpha: alphaByDate.get(date) ?? null,
      alphaPercentChange: alphaPercentByDate.get(date) ?? null,
      drawdown: drawdownByDate.get(date) ?? 0,
      dailyPnl: pnlByDate.get(date) ?? 0,
      buyCny: buyByDate.get(date) ?? 0,
      sellCny: sellByDate.get(date) ?? 0,
      ...(groupPercentChanges ? { groupPercentChanges } : {})
    };
  });
}

export function buildPerformancePointsFromArtifacts(artifacts: Record<string, unknown>): PerformancePoint[] {
  return buildPerformancePointsFromGraphData(artifacts.graph_data);
}

export function buildPerformanceAvailability(points: PerformancePoint[]): PerformanceAvailability {
  return {
    hasAlpha: points.some(
      (point) => typeof point.alphaPercentChange === "number" && Number.isFinite(point.alphaPercentChange)
    ),
    hasBenchmark: points.some(
      (point) => typeof point.benchmarkPercentChange === "number" && Number.isFinite(point.benchmarkPercentChange)
    )
  };
}
