import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { ReactNode } from "react";

import { I18nProvider } from "../../i18n";
import { ComposedChart, PerformanceTooltip } from "./ComposedChart";
import { visibleAxisTicks } from "./axisTicks";

const chartStylesText = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "ComposedChart.module.css"),
  "utf8"
);

function Wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider defaultLanguage="en">{children}</I18nProvider>;
}

const points = [
  {
    date: "2026-01-01",
    equity: 1_000_000,
    strategyEquityCny: 1_000_000,
    strategyPercentChange: 0,
    benchmark: 1_010_000,
    benchmarkPercentChange: 0,
    alpha: 1_020_000,
    alphaPercentChange: 0,
    drawdown: 0,
    dailyPnl: 20_000,
    buyCny: 300_000,
    sellCny: 100_000
  },
  {
    date: "2026-02-01",
    equity: 1_042_000,
    strategyEquityCny: 1_042_000,
    strategyPercentChange: 0.042,
    benchmark: 990_000,
    benchmarkPercentChange: -0.02,
    alpha: 1_070_000,
    alphaPercentChange: 0.062,
    drawdown: -0.018,
    dailyPnl: -8_000,
    buyCny: 50_000,
    sellCny: 150_000
  }
];

function makeLongPoints(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const day = String((index % 28) + 1).padStart(2, "0");
    const month = String((Math.floor(index / 28) % 12) + 1).padStart(2, "0");
    return {
      date: `2024-${month}-${day}`,
      equity: 1_000_000 + index * 1_000,
      strategyEquityCny: 1_000_000 + index * 1_000,
      strategyPercentChange: index / 1_000,
      benchmark: 1_000_000 + index * 600,
      benchmarkPercentChange: index / 1_500,
      alpha: 1_000_000 + index * 300,
      alphaPercentChange: index / 2_000,
      drawdown: index % 7 === 0 ? -index / 10_000 : 0,
      dailyPnl: index % 2 === 0 ? 1_000 : -800,
      buyCny: 20_000,
      sellCny: 15_000
    };
  });
}

describe("ComposedChart", () => {
  it("renders the performance chart stack with market-style percent labels and benchmark/alpha hidden by default", () => {
    render(<ComposedChart points={points} title="Cumulative return and drawdown" range="3M" showAlpha={false} />, {
      wrapper: Wrapper,
    });

    expect(screen.getByRole("img", { name: /cumulative return and drawdown/i })).toBeInTheDocument();
    expect(screen.getAllByText("Strategy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Top drawdowns").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Daily P&L").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Buy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Sell").length).toBeGreaterThan(0);
    expect(screen.getAllByText("%").length).toBeGreaterThan(0);
    expect(screen.queryByText("CSI 300")).not.toBeInTheDocument();
    expect(screen.queryByText("Alpha")).not.toBeInTheDocument();
  });

  it("uses the lightweight svg engine for every stacked graph panel without recharts output", () => {
    render(<ComposedChart points={points} title="Cumulative return and drawdown" range="ALL" />, { wrapper: Wrapper });

    const chartSurfaces = screen.getAllByTestId("lightweight-chart-surface");

    expect(chartSurfaces).toHaveLength(3);
    for (const surface of chartSurfaces) {
      expect(surface).toHaveAttribute("data-chart-engine", "lightweight-svg");
      expect(surface).toHaveAttribute("data-animation", "none");
    }
    expect(screen.getByTestId("lightweight-line-strategyPercentChange")).toBeInTheDocument();
    expect(screen.getByTestId("lightweight-bar-profitPnl")).toBeInTheDocument();
    expect(screen.getByTestId("lightweight-bar-buyCny")).toBeInTheDocument();
    expect(document.querySelector(".recharts-surface")).not.toBeInTheDocument();
  });

  it("shows the HS300 benchmark only when requested", () => {
    render(<ComposedChart points={points} showBenchmark title="Cumulative return and drawdown" />, { wrapper: Wrapper });

    expect(screen.getByText("CSI 300")).toBeInTheDocument();
  });

  it("keeps y axis labels in fixed rails outside the scroll frame", () => {
    render(<ComposedChart points={makeLongPoints(80)} title="Cumulative return and drawdown" range="1M" />, {
      wrapper: Wrapper,
    });

    const scrollFrame = screen.getByTestId("chart-scroll-frame");
    const axisRails = screen.getAllByTestId("fixed-y-axis-rail");

    expect(axisRails).toHaveLength(3);
    for (const rail of axisRails) {
      expect(scrollFrame).not.toContainElement(rail);
    }
  });

  it("renders a buffered finite range instead of every point while scrolling", () => {
    render(<ComposedChart points={makeLongPoints(120)} title="Cumulative return and drawdown" range="1M" />, {
      wrapper: Wrapper,
    });

    const scrollFrame = screen.getByTestId("chart-scroll-frame");

    expect(scrollFrame).toHaveAttribute("data-visible-points", "22");
    expect(Number(scrollFrame.getAttribute("data-rendered-points"))).toBeLessThan(120);
  });

  it("opens a finite range at the latest points and follows the scroll position", async () => {
    render(<ComposedChart points={makeLongPoints(120)} title="Cumulative return and drawdown" range="1M" />, {
      wrapper: Wrapper,
    });

    const scrollFrame = screen.getByTestId("chart-scroll-frame");
    // The window is derived, not stored: the initial render already points at
    // the newest bars instead of painting the first window and correcting itself.
    expect(scrollFrame).toHaveAttribute("data-visible-start", "98");
    expect(scrollFrame).toHaveAttribute("data-visible-end", "119");

    Object.defineProperty(scrollFrame, "scrollLeft", { configurable: true, value: 0, writable: true });
    fireEvent.scroll(scrollFrame);

    await waitFor(() => expect(scrollFrame).toHaveAttribute("data-visible-start", "0"));
    expect(scrollFrame).toHaveAttribute("data-visible-end", "21");
  });

  it("downsamples dense ALL ranges for cheaper initial rendering", () => {
    render(<ComposedChart points={makeLongPoints(1_000)} title="Cumulative return and drawdown" range="ALL" />, {
      wrapper: Wrapper,
    });

    expect(Number(screen.getByTestId("chart-scroll-frame").getAttribute("data-rendered-points"))).toBeLessThan(1_000);
  });

  it("shows alpha when requested", () => {
    render(<ComposedChart points={points} title="Cumulative return and drawdown" range="1YR" showAlpha />, {
      wrapper: Wrapper,
    });

    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });

  it("renders selected result groups as extra percentage lines", () => {
    render(
      <ComposedChart
        groupSeries={[{ color: "#34d399", id: "group_1", name: "Group 1 (best)" }]}
        points={points.map((point, index) => ({
          ...point,
          groupPercentChanges: { group_1: index === 0 ? 0.01 : 0.03 }
        }))}
        title="Cumulative return and drawdown"
      />,
      { wrapper: Wrapper }
    );

    expect(screen.getByText("Group 1 (best)")).toBeInTheDocument();
  });

  it("renders result groups as their own one-panel chart without the equity stack", () => {
    render(
      <ComposedChart
        chartMode="groups"
        groupSeries={[
          { color: "#34d399", id: "group_1", name: "Group 1" },
          { color: "#fb923c", id: "group_2", name: "Group 2" }
        ]}
        points={points.map((point, index) => ({
          ...point,
          groupPercentChanges: {
            group_1: index === 0 ? 0.01 : 0.03,
            group_2: index === 0 ? 0.02 : -0.01
          }
        }))}
        title="Result group cumulative returns"
      />,
      { wrapper: Wrapper }
    );

    expect(screen.getByRole("img", { name: /result group cumulative returns/i })).toBeInTheDocument();
    expect(screen.getAllByTestId("lightweight-chart-surface")).toHaveLength(1);
    expect(screen.getAllByTestId("fixed-y-axis-rail")).toHaveLength(1);
    expect(screen.getByTestId("lightweight-line-groupPercentChange_0")).toBeInTheDocument();
    expect(screen.getByTestId("lightweight-line-groupPercentChange_1")).toBeInTheDocument();
    expect(screen.queryByText("Strategy")).not.toBeInTheDocument();
    expect(screen.queryByText("Top drawdowns")).not.toBeInTheDocument();
    expect(screen.queryByText("Daily P&L")).not.toBeInTheDocument();
    expect(screen.queryByText("Buy")).not.toBeInTheDocument();
    expect(screen.queryByText("Sell")).not.toBeInTheDocument();
  });

  it("formats result group tooltip values as percentages", () => {
    render(
      <PerformanceTooltip
        active
        label="2026-02-01"
        payload={[
          {
            color: "#34d399",
            dataKey: "groupPercentChange_0",
            name: "Group 1 (best)",
            payload: { date: "2026-02-01" },
            value: 0.03
          }
        ]}
      />
    );

    const tooltip = screen.getByRole("tooltip");

    expect(tooltip).toHaveTextContent("3.00%");
    expect(tooltip).not.toHaveTextContent("CNY");
  });

  it("marks benchmark and alpha unavailable when old artifacts do not include those series", () => {
    render(
      <ComposedChart
        hasAlpha={false}
        hasBenchmark={false}
        points={points.map((point) => ({ ...point, alpha: null, benchmark: null }))}
        showBenchmark
        showAlpha
        title="Cumulative return and drawdown"
      />,
      { wrapper: Wrapper }
    );

    expect(screen.getByText("CSI 300 unavailable")).toBeInTheDocument();
    expect(screen.getByText("Alpha unavailable")).toBeInTheDocument();
  });

  it("renders tooltip dates as dates and never formats them as CNYNaN", () => {
    render(
      <PerformanceTooltip
        active
        label="2026-01-01"
        payload={[
          {
            color: "#22d3ee",
            dataKey: "strategyPercentChange",
            name: "Strategy Cumulative Return",
            payload: { strategyEquityCny: 1_000_000 },
            value: 0
          },
          { color: "#91a4bb", dataKey: "date", name: "date", value: "2026-01-01" },
          { color: "#fbbf24", dataKey: "benchmarkPercentChange", name: "CSI 300 Change", value: null },
          { color: "#a78bfa", dataKey: "alphaPercentChange", name: "Alpha Change", value: Number.NaN }
        ]}
      />
    );

    const tooltip = screen.getByRole("tooltip");

    expect(within(tooltip).getByText("2026-01-01")).toBeInTheDocument();
    expect(within(tooltip).getByText("Strategy Cumulative Return")).toBeInTheDocument();
    expect(within(tooltip).getByText("Cumulative Return Value")).toBeInTheDocument();
    expect(within(tooltip).getByText(/CNY/)).toBeInTheDocument();
    expect(tooltip).not.toHaveTextContent("CNYNaN");
    expect(within(tooltip).queryByText("date")).not.toBeInTheDocument();
    expect(within(tooltip).queryByText("CSI 300 Change")).not.toBeInTheDocument();
    expect(within(tooltip).queryByText("Alpha Change")).not.toBeInTheDocument();
  });

  it("keeps tooltip date text using the theme text token", () => {
    expect(chartStylesText).toContain(".tooltipDate");
    expect(chartStylesText).toContain("color: var(--qf-text)");
  });

  it("uses a string tooltip label as the date when payload dates are missing", () => {
    render(
      <PerformanceTooltip
        active
        label="2026-03-01"
        payload={[
          {
            color: "#22d3ee",
            dataKey: "strategyPercentChange",
            name: "Strategy Cumulative Return",
            payload: { strategyEquityCny: 1_000_000 },
            value: 0.01
          }
        ]}
      />
    );

    expect(screen.getByRole("tooltip")).toHaveTextContent("2026-03-01");
  });

  it("does not render numeric sync labels as dates when no payload date exists", () => {
    render(
      <PerformanceTooltip
        active
        label={1}
        payload={[
          {
            color: "#22d3ee",
            dataKey: "strategyPercentChange",
            name: "Strategy Cumulative Return",
            payload: { strategyEquityCny: 1_000_000 },
            value: 0.01
          }
        ]}
      />
    );

    const tooltip = screen.getByRole("tooltip");

    expect(within(tooltip).queryByText("1")).not.toBeInTheDocument();
    expect(tooltip).not.toHaveTextContent("CNYNaN");
  });

  it("formats strategy, HS300, and alpha cumulative returns as percentages in the tooltip", () => {
    render(
      <PerformanceTooltip
        active
        label="2026-02-01"
        payload={[
          {
            color: "#22d3ee",
            dataKey: "strategyPercentChange",
            name: "Strategy Cumulative Return",
            payload: { strategyEquityCny: 1_042_000 },
            value: 0.042
          },
          { color: "#fbbf24", dataKey: "benchmarkPercentChange", name: "CSI 300 Change", value: -0.02 },
          { color: "#a78bfa", dataKey: "alphaPercentChange", name: "Alpha Change", value: 0.062 }
        ]}
      />
    );

    const tooltip = screen.getByRole("tooltip");

    expect(tooltip).toHaveTextContent("CNY 1,042,000");
    expect(tooltip).toHaveTextContent("4.20%");
    expect(tooltip).toHaveTextContent("-2.00%");
    expect(tooltip).toHaveTextContent("6.20%");
    expect(within(tooltip).getByText("CSI 300 Change").nextSibling).not.toHaveTextContent("CNY");
    expect(within(tooltip).getByText("Alpha Change").nextSibling).not.toHaveTextContent("CNY");
  });

  it("falls back to the hovered point date when recharts does not provide a tooltip label", () => {
    render(
      <PerformanceTooltip
        active
        payload={[
          {
            color: "#22d3ee",
            name: "Strategy",
            dataKey: "strategyPercentChange",
            payload: { date: "2026-02-01" },
            value: 0.042
          }
        ]}
      />
    );

    expect(screen.getByRole("tooltip")).toHaveTextContent("2026-02-01");
  });

  it("prefers payload dates over numeric recharts sync labels", () => {
    render(
      <PerformanceTooltip
        active
        label={1}
        payload={[
          {
            color: "#22d3ee",
            name: "Strategy",
            dataKey: "strategyPercentChange",
            payload: { date: "2026-02-01" },
            value: 0.042
          }
        ]}
      />
    );

    const tooltip = screen.getByRole("tooltip");

    expect(within(tooltip).getByText("2026-02-01")).toBeInTheDocument();
    expect(within(tooltip).queryByText("1")).not.toBeInTheDocument();
  });

  it("formats top drawdown tooltip values as percentages", () => {
    render(
      <PerformanceTooltip
        active
        label="2026-02-01"
        payload={[
          {
            color: "#fb7185",
            dataKey: "drawdownMarker",
            name: "Top drawdowns",
            payload: { date: "2026-02-01", drawdown: -0.018 },
            value: 0.042
          }
        ]}
      />
    );

    const tooltip = screen.getByRole("tooltip");

    expect(tooltip).toHaveTextContent("-1.80%");
    expect(tooltip).not.toHaveTextContent("1,042,000");
  });

  it("keeps short y axis rails sparse and deduped", () => {
    const ticks = visibleAxisTicks([0, 1_000], 150).map((tick) => tick.label);

    expect(ticks.length).toBeLessThanOrEqual(3);
    expect(new Set(ticks).size).toBe(ticks.length);
  });

  it("uses rounded zero-origin percentage labels for small ranges", () => {
    const ticks = visibleAxisTicks([-0.018, 0.064], 320, (value) => `${(value * 100).toFixed(0)}%`);
    const labels = ticks.map((tick) => tick.label);

    expect(labels).toContain("0%");
    expect(labels).toEqual(["10%", "0%", "-10%"]);
  });

  it("keeps large percentage axes proportional for 200% and 3000% moves", () => {
    const twoHundredPercentLabels = visibleAxisTicks([0, 2], 280, (value) => `${(value * 100).toFixed(0)}%`).map(
      (tick) => tick.label
    );
    const threeThousandPercentLabels = visibleAxisTicks([0, 30], 280, (value) => `${(value * 100).toFixed(0)}%`).map(
      (tick) => tick.label
    );

    expect(twoHundredPercentLabels).toEqual(["200%", "100%", "0%"]);
    expect(threeThousandPercentLabels).toEqual(["3000%", "2000%", "1000%", "0%"]);
  });

  it("keeps uneven percentage axes close to their positive and negative extrema", () => {
    const labels = visibleAxisTicks([-1.6, 4.54], 320, (value) => `${(value * 100).toFixed(0)}%`).map(
      (tick) => tick.label
    );

    expect(labels).toContain("500%");
    expect(labels).toContain("0%");
    expect(labels).toContain("-200%");
    expect(labels).not.toContain("-500%");
  });

  it("keeps high-return chart labels close to the actual maximum", () => {
    render(
      <ComposedChart
        points={[
          {
            date: "2010-01-04",
            equity: 1_000_000,
            strategyEquityCny: 1_000_000,
            strategyPercentChange: 0,
            benchmark: null,
            benchmarkPercentChange: null,
            alpha: null,
            alphaPercentChange: null,
            drawdown: 0,
            dailyPnl: 0,
            buyCny: 0,
            sellCny: 0
          },
          {
            date: "2022-12-30",
            equity: 5_769_119,
            strategyEquityCny: 5_769_119,
            strategyPercentChange: 4.769119126488158,
            benchmark: null,
            benchmarkPercentChange: null,
            alpha: null,
            alphaPercentChange: null,
            drawdown: -0.008713154249712307,
            dailyPnl: 0,
            buyCny: 0,
            sellCny: 0
          }
        ]}
        range="ALL"
        showAlpha={false}
        showBenchmark={false}
        title="High return result"
      />,
      { wrapper: Wrapper }
    );

    const [changeAxisRail] = screen.getAllByTestId("fixed-y-axis-rail");

    expect(changeAxisRail).toHaveTextContent("500%");
    expect(changeAxisRail).not.toHaveTextContent("1000%");
  });

  it("uses rounded zero-origin cny labels for large ranges", () => {
    const labels = visibleAxisTicks([-8_000, 184_000], 150).map((tick) => tick.label);

    expect(labels).toContain("CNY 0");
    expect(labels).toEqual(["CNY 200K", "CNY 0"]);
  });

  it("labels fixed y axis rails by panel", () => {
    render(<ComposedChart points={points} title="Cumulative return and drawdown" range="ALL" />, {
      wrapper: Wrapper
    });

    const axisRails = screen.getAllByTestId("fixed-y-axis-rail");

    expect(axisRails[0]).toHaveTextContent("Cumulative return %");
    expect(axisRails[1]).toHaveTextContent("P&L CNY");
    expect(axisRails[2]).toHaveTextContent("Volume CNY");
  });

  it("always renders a zero-origin label for each stacked y axis rail", () => {
    render(<ComposedChart points={points} title="Cumulative return and drawdown" range="ALL" />, {
      wrapper: Wrapper
    });

    const axisRails = screen.getAllByTestId("fixed-y-axis-rail");

    expect(axisRails[0]).toHaveTextContent("0%");
    expect(axisRails[1]).toHaveTextContent("CNY 0");
    expect(axisRails[2]).toHaveTextContent("CNY 0");
  });

  it("renders empty state when data is missing", () => {
    render(<ComposedChart points={[]} title="No data" />, { wrapper: Wrapper });

    expect(screen.getByText(/no chart data/i)).toBeInTheDocument();
  });
});
