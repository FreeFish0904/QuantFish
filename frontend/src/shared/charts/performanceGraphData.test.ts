import { describe, expect, it } from "vitest";

import {
  buildGroupSeriesFromGraphData,
  buildGroupSummariesFromGraphData,
  buildPerformanceAvailability,
  buildPerformancePointsFromGraphData
} from "./performanceGraphData";

describe("performanceGraphData", () => {
  it("calculates arithmetic cumulative return from normalized net values", () => {
    const points = buildPerformancePointsFromGraphData({
      equity: [
        { date: "2026-01-01", equity: 1.01 },
        { date: "2026-01-02", equity: 1.04 },
        { date: "2026-01-03", equity: 0.99 }
      ],
      equity_cny: [
        { date: "2026-01-01", equity_cny: 1_010_000 },
        { date: "2026-01-02", equity_cny: 1_040_000 },
        { date: "2026-01-03", equity_cny: 990_000 }
      ],
      daily_returns: [
        { date: "2026-01-01", portfolio_return: 0.01 },
        { date: "2026-01-02", portfolio_return: 0.03 },
        { date: "2026-01-03", portfolio_return: -0.05 }
      ],
      daily_pnl: [
        { date: "2026-01-01", pnl_cny: 10_000, daily_return: 0.01 },
        { date: "2026-01-02", pnl_cny: 30_000, daily_return: 0.03 },
        { date: "2026-01-03", pnl_cny: -50_000, daily_return: -0.05 }
      ],
      drawdown: [
        { date: "2026-01-01", drawdown: 0 },
        { date: "2026-01-02", drawdown: -0.01 },
        { date: "2026-01-03", drawdown: -0.05 }
      ],
      benchmark: [
        { date: "2026-01-01", benchmark_return: 0.004, benchmark_equity: 1.004, benchmark_cny: 1_004_000 },
        { date: "2026-01-02", benchmark_return: -0.012, benchmark_equity: 0.992, benchmark_cny: 992_000 },
        { date: "2026-01-03", benchmark_return: 0.02, benchmark_equity: 1.012, benchmark_cny: 1_012_000 }
      ],
      alpha: [
        { date: "2026-01-01", alpha_return: 0.006, alpha_equity: 1.006, alpha_cny: 1_006_000 },
        { date: "2026-01-02", alpha_return: 0.042, alpha_equity: 1.048, alpha_cny: 1_048_000 },
        { date: "2026-01-03", alpha_return: -0.07, alpha_equity: 0.978, alpha_cny: 978_000 }
      ],
      trade_volume: [
        { date: "2026-01-01", buy_cny: 100_000, sell_cny: 50_000 },
        { date: "2026-01-02", buy_cny: 80_000, sell_cny: 40_000 },
        { date: "2026-01-03", buy_cny: 30_000, sell_cny: 90_000 }
      ]
    });

    expect(points[0]).toMatchObject({
      date: "2026-01-01",
      strategyPercentChange: expect.closeTo(0.01),
      benchmarkPercentChange: expect.closeTo(0.004),
      alphaPercentChange: expect.closeTo(0.006)
    });
    expect(points[1]).toMatchObject({
      date: "2026-01-02",
      equity: 1_040_000,
      strategyEquityCny: 1_040_000,
      strategyPercentChange: expect.closeTo(0.04),
      benchmarkPercentChange: expect.closeTo(-0.008),
      alphaPercentChange: expect.closeTo(0.048),
      benchmark: 992_000,
      alpha: 1_048_000,
      dailyPnl: 30_000,
      buyCny: 80_000,
      sellCny: 40_000
    });
    expect(points[2]).toMatchObject({
      date: "2026-01-03",
      strategyPercentChange: expect.closeTo(-0.01),
      benchmarkPercentChange: expect.closeTo(0.012),
      alphaPercentChange: expect.closeTo(-0.022)
    });
    expect(buildPerformanceAvailability(points)).toEqual({
      hasAlpha: true,
      hasBenchmark: true
    });
  });

  it("preserves the full-series percent baseline across finite visible windows", () => {
    const points = buildPerformancePointsFromGraphData({
      equity: [
        { date: "2026-01-01", equity: 1 },
        { date: "2026-01-02", equity: 1.1 },
        { date: "2026-01-03", equity: 1.05 }
      ],
      drawdown: [{ date: "2026-01-03", drawdown: -0.05 }],
      benchmark: [
        { date: "2026-01-01", benchmark_equity: 1.01 },
        { date: "2026-01-02", benchmark_equity: 0.99 }
      ],
      alpha: [
        { date: "2026-01-01", alpha_equity: 1.02 },
        { date: "2026-01-02", alpha_equity: 1.0506 }
      ]
    });

    expect(points.map((point) => point.strategyPercentChange)).toEqual([
      0,
      expect.closeTo(0.1),
      expect.closeTo(0.05)
    ]);
    const visibleWindow = points.slice(1);

    expect(visibleWindow[0].strategyPercentChange).toBeCloseTo(0.1);
    expect(visibleWindow[1].strategyPercentChange).toBeCloseTo(0.05);
    expect(points[0].benchmarkPercentChange).toBeCloseTo(0.01);
    expect(points[1].benchmarkPercentChange).toBeCloseTo(-0.01);
    expect(points[0].alphaPercentChange).toBeCloseTo(0.02);
    expect(points[1].alphaPercentChange).toBeCloseTo(0.0506);
  });

  it("clips and rebases benchmark and alpha to the strategy date domain", () => {
    const points = buildPerformancePointsFromGraphData({
      equity: [
        { date: "2026-01-02", equity: 1 },
        { date: "2026-01-03", equity: 1.1 }
      ],
      benchmark: [
        { date: "2026-01-01", benchmark_equity: 1, benchmark_cny: 1_000_000 },
        { date: "2026-01-02", benchmark_equity: 1.2, benchmark_cny: 1_200_000 },
        { date: "2026-01-03", benchmark_equity: 1.5, benchmark_cny: 1_500_000 },
        { date: "2026-01-04", benchmark_equity: 2, benchmark_cny: 2_000_000 }
      ],
      alpha: [
        { date: "2026-01-01", alpha_equity: 0.9, alpha_cny: 900_000 },
        { date: "2026-01-02", alpha_equity: 1.1, alpha_cny: 1_100_000 },
        { date: "2026-01-03", alpha_equity: 0.88, alpha_cny: 880_000 },
        { date: "2026-01-04", alpha_equity: 1.3, alpha_cny: 1_300_000 }
      ]
    });

    expect(points.map((point) => point.date)).toEqual(["2026-01-02", "2026-01-03"]);
    expect(points[0].benchmarkPercentChange).toBeCloseTo(0.2);
    expect(points[1].benchmarkPercentChange).toBeCloseTo(0.5);
    expect(points[0].alphaPercentChange).toBeCloseTo(0.1);
    expect(points[1].alphaPercentChange).toBeCloseTo(-0.12);
  });

  it("starts benchmark and alpha from their first overlapping strategy date", () => {
    const points = buildPerformancePointsFromGraphData({
      equity: [
        { date: "2026-01-02", equity: 1 },
        { date: "2026-01-03", equity: 1.1 },
        { date: "2026-01-04", equity: 1.2 }
      ],
      benchmark: [
        { date: "2026-01-03", benchmark_equity: 1.5 },
        { date: "2026-01-04", benchmark_equity: 1.65 }
      ],
      alpha: [{ date: "2026-01-04", alpha_equity: 0.8 }]
    });

    expect(points[0].benchmarkPercentChange).toBeNull();
    expect(points[1].benchmarkPercentChange).toBeCloseTo(0.5);
    expect(points[2].benchmarkPercentChange).toBeCloseTo(0.65);
    expect(points[0].alphaPercentChange).toBeNull();
    expect(points[1].alphaPercentChange).toBeNull();
    expect(points[2].alphaPercentChange).toBeCloseTo(-0.2);
  });

  it("falls back to CNY series and then arithmetic return fields when net values are missing", () => {
    const cnyPoints = buildPerformancePointsFromGraphData({
      equity_cny: [
        { date: "2026-01-01", equity_cny: 1_000_000 },
        { date: "2026-01-02", equity_cny: 1_050_000 }
      ],
      benchmark: [
        { date: "2026-01-01", benchmark_cny: 2_000 },
        { date: "2026-01-02", benchmark_cny: 2_100 }
      ],
      alpha: [
        { date: "2026-01-01", alpha_cny: 1_000 },
        { date: "2026-01-02", alpha_cny: 950 }
      ]
    });

    expect(cnyPoints[0].strategyPercentChange).toBeCloseTo(0);
    expect(cnyPoints[1].strategyPercentChange).toBeCloseTo(0.05);
    expect(cnyPoints[1].benchmarkPercentChange).toBeCloseTo(0.05);
    expect(cnyPoints[1].alphaPercentChange).toBeCloseTo(-0.05);

    const returnPoints = buildPerformancePointsFromGraphData({
      equity: [
        { date: "2026-01-01", equity: 1 },
        { date: "2026-01-02", equity: 1.05 }
      ],
      benchmark: [
        { date: "2026-01-01", benchmark_return: 0.01 },
        { date: "2026-01-02", benchmark_return: -0.02 }
      ],
      alpha: [
        { date: "2026-01-01", alpha_return: 0.02 },
        { date: "2026-01-02", alpha_return: 0.03 }
      ]
    });

    expect(returnPoints[0].benchmarkPercentChange).toBeCloseTo(0.01);
    expect(returnPoints[1].benchmarkPercentChange).toBeCloseTo(-0.01);
    expect(returnPoints[0].alphaPercentChange).toBeCloseTo(0.02);
    expect(returnPoints[1].alphaPercentChange).toBeCloseTo(0.05);
  });

  it("maps grouped cumulative returns and marks the highest final group as best", () => {
    const graphData = {
      equity: [
        { date: "2026-01-01", equity: 1 },
        { date: "2026-01-02", equity: 1.03 }
      ],
      group_cumulative: [
        { date: "2026-01-01", group: "group_1", cumulative_return: 0.01 },
        { date: "2026-01-02", group: "group_1", cumulative_return: 0.03 },
        { date: "2026-01-01", group: "group_2", cumulative_return: 0.04 },
        { date: "2026-01-02", group: "group_2", cumulative_return: 0.02 }
      ]
    };

    const points = buildPerformancePointsFromGraphData(graphData);
    const groups = buildGroupSeriesFromGraphData(graphData);

    expect(points[0].groupPercentChanges).toEqual({
      group_1: 0.01,
      group_2: 0.04
    });
    expect(points[1].groupPercentChanges).toEqual({
      group_1: 0.03,
      group_2: 0.02
    });
    expect(groups).toEqual([
      {
        color: expect.any(String),
        finalCumulativeReturn: 0.03,
        id: "group_1",
        isBest: true,
        label: "Group 1"
      },
      {
        color: expect.any(String),
        finalCumulativeReturn: 0.02,
        id: "group_2",
        isBest: false,
        label: "Group 2"
      }
    ]);
  });

  it("derives group-level performance summaries from cumulative group returns", () => {
    const summaries = buildGroupSummariesFromGraphData({
      equity: [{ date: "2026-01-01", equity: 1 }],
      group_cumulative: [
        { date: "2026-01-01", group: "group_1", cumulative_return: 0.01 },
        { date: "2026-01-02", group: "group_1", cumulative_return: 0.03 },
        { date: "2026-01-01", group: "group_2", cumulative_return: 0.04 },
        { date: "2026-01-02", group: "group_2", cumulative_return: 0.02 }
      ]
    });

    expect(summaries.group_1).toMatchObject({
      total_return: expect.closeTo(0.03),
      all_return: expect.closeTo(0.03),
      annual_return: expect.closeTo((0.03 / 2) * 252),
      average_year_return: expect.closeTo(0.03),
      max_drawdown: 0,
      trading_days: 2,
      win_rate: 1
    });
    expect(summaries.group_1.sharpe).toBeGreaterThan(0);
    expect(summaries.group_2).toMatchObject({
      total_return: expect.closeTo(0.02),
      all_return: expect.closeTo(0.02),
      annual_return: expect.closeTo((0.02 / 2) * 252),
      average_year_return: expect.closeTo(0.02),
      max_drawdown: expect.closeTo(1 - 1.02 / 1.04),
      trading_days: 2,
      win_rate: 0.5
    });
    expect(summaries.group_2.sharpe).toBeLessThan(summaries.group_1.sharpe);
  });
});
