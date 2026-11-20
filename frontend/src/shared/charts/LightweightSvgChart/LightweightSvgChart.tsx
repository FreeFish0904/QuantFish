import { useEffect, useMemo, useRef, useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";

import { lightweightTicks, readSeriesValue } from "./scale";
import styles from "./LightweightSvgChart.module.css";

const DEFAULT_VIEW_BOX_WIDTH = 760;
const DEFAULT_MARGIN = { bottom: 28, left: 44, right: 16, top: 16 };
const AXIS_EPSILON = 1e-10;
const TOOLTIP_EDGE_CLEARANCE = 180;
const TOOLTIP_OFFSET = 12;

export type LightweightSeriesType = "bar" | "line" | "scatter";

export type LightweightSeries = {
  color: string;
  connectNulls?: boolean;
  dataKey: string;
  name: string;
  radius?: number;
  strokeDasharray?: string;
  strokeWidth?: number;
  type: LightweightSeriesType;
};

export type LightweightTooltipPayloadItem<T extends Record<string, unknown>> = {
  color: string;
  dataKey: string;
  name: string;
  payload: T;
  value: number | null;
};

export type LightweightTooltipState<T extends Record<string, unknown>> = {
  index: number;
  label: unknown;
  payload: Array<LightweightTooltipPayloadItem<T>>;
  point: T;
  x: number;
  y: number;
};

type ChartMargin = {
  bottom: number;
  left: number;
  right: number;
  top: number;
};

export type LightweightSvgChartProps<T extends Record<string, unknown>> = {
  data: T[];
  height: number;
  margin?: Partial<ChartMargin>;
  series: LightweightSeries[];
  showXAxis?: boolean;
  showYAxis?: boolean;
  tooltip?: (state: LightweightTooltipState<T>) => ReactNode;
  viewBoxWidth?: number;
  xKey: keyof T | string;
  xTickCount?: number;
  yDomain: [number, number];
  yTickFormatter?: (value: number) => string;
  yTicks?: number[];
};

type PlotArea = {
  bottom: number;
  height: number;
  left: number;
  right: number;
  top: number;
  width: number;
};

type HoverPoint = {
  clientX: number;
  clientY: number;
  index: number;
};

type TooltipSide = "left" | "right";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function plotArea(width: number, height: number, margin: ChartMargin): PlotArea {
  const left = margin.left;
  const right = width - margin.right;
  const top = margin.top;
  const bottom = height - margin.bottom;
  return {
    bottom,
    height: Math.max(1, bottom - top),
    left,
    right,
    top,
    width: Math.max(1, right - left)
  };
}

function xPosition(index: number, total: number, plot: PlotArea): number {
  if (total <= 1) {
    return plot.left + plot.width / 2;
  }
  return plot.left + (index / (total - 1)) * plot.width;
}

function yPosition(value: number, domain: [number, number], plot: PlotArea): number {
  const [min, max] = domain;
  const span = max - min || 1;
  return plot.bottom - ((value - min) / span) * plot.height;
}

function buildLinePath<T extends Record<string, unknown>>(
  data: T[],
  series: LightweightSeries,
  domain: [number, number],
  plot: PlotArea
): string {
  let path = "";
  let started = false;
  data.forEach((point, index) => {
    const value = readSeriesValue(point, series.dataKey);
    if (value === null) {
      if (!series.connectNulls) {
        started = false;
      }
      return;
    }
    const x = xPosition(index, data.length, plot);
    const y = yPosition(value, domain, plot);
    path += `${started ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`;
    started = true;
  });
  return path;
}

function xTickIndexes(total: number, count: number): number[] {
  if (total <= 0) {
    return [];
  }
  if (total <= count) {
    return Array.from({ length: total }, (_, index) => index);
  }
  const last = total - 1;
  const indexes = new Set<number>([0, last]);
  for (let tick = 1; tick < count - 1; tick += 1) {
    indexes.add(Math.round((last * tick) / (count - 1)));
  }
  return [...indexes].sort((a, b) => a - b);
}

function fallbackFormat(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  }
  return String(value ?? "");
}

function tooltipSide(x: number, width: number): TooltipSide {
  const availableLeft = Math.max(0, x);
  const availableRight = Math.max(0, width - x);
  return availableRight < TOOLTIP_EDGE_CLEARANCE && availableLeft > availableRight ? "left" : "right";
}

function tooltipTransform(side: TooltipSide): string {
  return side === "left" ? `translate(calc(-100% - ${TOOLTIP_OFFSET}px), -50%)` : `translate(${TOOLTIP_OFFSET}px, -50%)`;
}

function formatCompactNumber(value: number): string {
  const normalized = Math.abs(value) < AXIS_EPSILON ? 0 : value;
  const abs = Math.abs(normalized);
  if (abs >= 1_000_000_000) {
    return `${(normalized / 1_000_000_000).toFixed(1)}B`;
  }
  if (abs >= 1_000_000) {
    return `${(normalized / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${(normalized / 1_000).toFixed(0)}K`;
  }
  return normalized.toFixed(abs > 0 && abs < 1 ? 2 : 0);
}

function tooltipPayload<T extends Record<string, unknown>>(
  point: T,
  series: LightweightSeries[]
): Array<LightweightTooltipPayloadItem<T>> {
  return series.map((item) => ({
    color: item.color,
    dataKey: item.dataKey,
    name: item.name,
    payload: point,
    value: readSeriesValue(point, item.dataKey)
  }));
}

function DefaultTooltip<T extends Record<string, unknown>>({ state }: { state: LightweightTooltipState<T> }) {
  const rows = state.payload.filter((item) => item.value !== null);
  if (rows.length === 0) {
    return null;
  }
  return (
    <div className={styles.tooltip} role="tooltip">
      <div className={styles.tooltipDate}>{fallbackFormat(state.label)}</div>
      {rows.map((item) => (
        <div className={styles.tooltipRow} key={item.dataKey}>
          <span className={styles.tooltipSeries}>
            <span className={styles.tooltipSwatch} style={{ background: item.color }} />
            {item.name}
          </span>
          <span className={styles.tooltipValue}>{formatCompactNumber(item.value ?? 0)}</span>
        </div>
      ))}
    </div>
  );
}

export function LightweightSvgChart<T extends Record<string, unknown>>({
  data,
  height,
  margin,
  series,
  showXAxis = true,
  showYAxis = true,
  tooltip,
  viewBoxWidth = DEFAULT_VIEW_BOX_WIDTH,
  xKey,
  xTickCount = 6,
  yDomain,
  yTickFormatter = formatCompactNumber,
  yTicks
}: LightweightSvgChartProps<T>) {
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  const [measuredWidth, setMeasuredWidth] = useState(viewBoxWidth);
  const resolvedMargin = {
    ...DEFAULT_MARGIN,
    ...margin
  };
  const chartWidth = measuredWidth;
  const chartPlot = plotArea(chartWidth, height, resolvedMargin);
  const ticks = yTicks ?? lightweightTicks(yDomain);
  const [hover, setHover] = useState<HoverPoint | null>(null);
  const xTicks = useMemo(() => xTickIndexes(data.length, xTickCount), [data.length, xTickCount]);
  const barSeries = series.filter((item) => item.type === "bar");
  const lineSeries = series.filter((item) => item.type === "line");
  const scatterSeries = series.filter((item) => item.type === "scatter");
  const hoverState = useMemo<LightweightTooltipState<T> | null>(() => {
    if (hover === null || data.length === 0) {
      return null;
    }
    const point = data[hover.index];
    return {
      index: hover.index,
      label: point?.[String(xKey)],
      payload: tooltipPayload(point, series),
      point,
      x: hover.clientX,
      y: hover.clientY
    };
  }, [data, hover, series, xKey]);
  const renderedTooltip = hoverState ? (tooltip ? tooltip(hoverState) : <DefaultTooltip state={hoverState} />) : null;
  const tooltipPlacement = hoverState ? tooltipSide(hoverState.x, chartWidth) : "right";

  useEffect(() => {
    const node = surfaceRef.current;
    if (!node) {
      return;
    }
    const updateWidth = () => {
      const nextWidth = Math.max(320, Math.round(node.clientWidth || viewBoxWidth));
      setMeasuredWidth((current) => (current === nextWidth ? current : nextWidth));
    };
    updateWidth();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(updateWidth);
      observer.observe(node);
      return () => observer.disconnect();
    }
    if (typeof window !== "undefined") {
      window.addEventListener("resize", updateWidth);
      return () => window.removeEventListener("resize", updateWidth);
    }
  }, [viewBoxWidth]);

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (data.length === 0) {
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const rectWidth = rect.width || chartWidth;
    const rectHeight = rect.height || height;
    const viewX = ((event.clientX - rect.left) / rectWidth) * chartWidth;
    const ratio = clamp((viewX - chartPlot.left) / chartPlot.width, 0, 1);
    const index = data.length <= 1 ? 0 : Math.round(ratio * (data.length - 1));
    setHover({
      clientX: clamp(event.clientX - rect.left, 0, rectWidth),
      clientY: clamp(event.clientY - rect.top, 0, rectHeight),
      index
    });
  }

  const style = { "--chart-height": `${height}px` } as CSSProperties;
  const baselineY = yPosition(0, yDomain, chartPlot);
  const pointSlot = data.length <= 1 ? chartPlot.width : chartPlot.width / Math.max(1, data.length - 1);
  const barClusterWidth = Math.min(28, Math.max(4, pointSlot * 0.62));
  const barWidth = Math.max(2, barClusterWidth / Math.max(1, barSeries.length));

  return (
    <div
      className={styles.surface}
      data-animation="none"
      data-chart-engine="lightweight-svg"
      data-testid="lightweight-chart-surface"
      ref={surfaceRef}
      style={style}
    >
      <svg
        aria-hidden="true"
        className={styles.svg}
        data-animation="none"
        focusable="false"
        onPointerLeave={() => setHover(null)}
        onPointerMove={handlePointerMove}
        viewBox={`0 0 ${chartWidth} ${height}`}
      >
        {ticks.map((tick) => {
          const y = yPosition(tick, yDomain, chartPlot);
          return <line className={styles.gridLine} key={`grid-${tick}`} x1={chartPlot.left} x2={chartPlot.right} y1={y} y2={y} />;
        })}
        {showYAxis ? (
          <>
            <line className={styles.axisLine} x1={chartPlot.left} x2={chartPlot.left} y1={chartPlot.top} y2={chartPlot.bottom} />
            {ticks.map((tick) => {
              const y = yPosition(tick, yDomain, chartPlot);
              return (
                <text
                  className={styles.axisLabel}
                  dominantBaseline="middle"
                  key={`y-${tick}`}
                  textAnchor="end"
                  x={chartPlot.left - 8}
                  y={y}
                >
                  {yTickFormatter(tick)}
                </text>
              );
            })}
          </>
        ) : null}
        {showXAxis ? (
          <>
            <line className={styles.axisLine} x1={chartPlot.left} x2={chartPlot.right} y1={chartPlot.bottom} y2={chartPlot.bottom} />
            {xTicks.map((index) => {
              const x = xPosition(index, data.length, chartPlot);
              return (
                <text className={styles.axisLabel} key={`x-${index}`} textAnchor="middle" x={x} y={height - 8}>
                  {fallbackFormat(data[index]?.[String(xKey)])}
                </text>
              );
            })}
          </>
        ) : null}
        {barSeries.map((item, barIndex) => (
          <g data-testid={`lightweight-bar-${item.dataKey}`} key={item.dataKey}>
            {data.map((point, pointIndex) => {
              const value = readSeriesValue(point, item.dataKey);
              if (value === null) {
                return null;
              }
              const centerX = xPosition(pointIndex, data.length, chartPlot);
              const x = centerX - barClusterWidth / 2 + barIndex * barWidth + 0.5;
              const y = yPosition(value, yDomain, chartPlot);
              const top = Math.min(y, baselineY);
              const barHeight = Math.max(1, Math.abs(baselineY - y));
              return (
                <rect
                  data-animation="none"
                  fill={item.color}
                  height={barHeight}
                  key={`${item.dataKey}-${pointIndex}`}
                  rx="1.5"
                  width={Math.max(1, barWidth - 1)}
                  x={x}
                  y={top}
                />
              );
            })}
          </g>
        ))}
        {lineSeries.map((item) => (
          <path
            d={buildLinePath(data, item, yDomain, chartPlot)}
            data-animation="none"
            data-testid={`lightweight-line-${item.dataKey}`}
            fill="none"
            key={item.dataKey}
            stroke={item.color}
            strokeDasharray={item.strokeDasharray}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={item.strokeWidth ?? 2}
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {scatterSeries.map((item) => (
          <g data-testid={`lightweight-scatter-${item.dataKey}`} key={item.dataKey}>
            {data.map((point, index) => {
              const value = readSeriesValue(point, item.dataKey);
              if (value === null) {
                return null;
              }
              return (
                <circle
                  cx={xPosition(index, data.length, chartPlot)}
                  cy={yPosition(value, yDomain, chartPlot)}
                  data-animation="none"
                  fill={item.color}
                  key={`${item.dataKey}-${index}`}
                  r={item.radius ?? 4}
                />
              );
            })}
          </g>
        ))}
        {hoverState ? (
          <line
            className={styles.hoverRule}
            data-animation="none"
            x1={xPosition(hoverState.index, data.length, chartPlot)}
            x2={xPosition(hoverState.index, data.length, chartPlot)}
            y1={chartPlot.top}
            y2={chartPlot.bottom}
          />
        ) : null}
      </svg>
      {renderedTooltip ? (
        <div
          className={styles.tooltipOverlay}
          data-tooltip-side={tooltipPlacement}
          style={{
            left: hoverState?.x ?? 0,
            top: hoverState?.y ?? 0,
            transform: tooltipTransform(tooltipPlacement)
          }}
        >
          {renderedTooltip}
        </div>
      ) : null}
    </div>
  );
}
