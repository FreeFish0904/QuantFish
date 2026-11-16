import { describe, expect, it } from "vitest";

import type { CompareResponse } from "./api";
import { COMPARE_COLORS, toCompareModel } from "./model";

describe("toCompareModel", () => {
  it("maps submissions with stable colors and builds aligned equity and drawdown rows", () => {
    const response: CompareResponse = {
      submissions: [
        {
          submission_id: "sub-1",
          submission_number: 1,
          submission_label: "#1",
          team_id: "team-a",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "hidden_test",
          metrics: {
            total_return: 0.184,
            annual_return: 0.21,
            sharpe: 1.82,
            max_drawdown: -0.04
          },
          equity: [
            { date: "2026-01-01", equity: 100000 },
            { date: "2026-06-01", equity: 118400 }
          ],
          drawdown: [
            { date: "2026-01-01", drawdown: 0 },
            { date: "2026-06-01", drawdown: -0.04 }
          ],
          execution_parameters: {
            data_track: "hidden_test",
            data_start: "2015-01-01",
            scoring_start: "2023-01-01",
            scoring_end: "2025-12-31",
            capital: 1_000_000,
            group_count: 5,
            price_policy: "front_adjusted",
            execution_price: "vwap",
            mark_price: "close",
            commission_rate: 0.001,
            slippage_rate: 0.0005,
            max_leverage: 1,
            top_k: null,
            long_only: false,
            submission_timeout_enabled: false,
            submission_timeout_seconds: 120
          }
        },
        {
          submission_id: "sub-2",
          submission_number: 2,
          submission_label: "#2",
          team_id: "team-b",
          team_name: "Beta Fund",
          status: "completed",
          data_track: "learning",
          metrics: {
            total_return: 0.122,
            annual_return: 0.14,
            sharpe: 1.43,
            max_drawdown: -0.08
          },
          equity: [
            { date: "2026-01-01", equity: 100000 },
            { date: "2026-06-01", equity: 112200 }
          ],
          drawdown: [
            { date: "2026-01-01", drawdown: 0 },
            { date: "2026-06-01", drawdown: -0.08 }
          ],
          execution_parameters: null
        }
      ]
    };

    const model = toCompareModel(response);

    expect(model.submissions).toHaveLength(2);
    expect(model.submissions[0]).toMatchObject({
      id: "sub-1",
      submissionNumber: 1,
      submissionLabel: "#1",
      teamId: "team-a",
      teamName: "Alpha Desk",
      displayName: "#1 · Alpha Desk",
      status: "completed",
      dataTrack: "hidden_test",
      color: COMPARE_COLORS[0],
      totalReturn: 0.184,
      sharpe: 1.82,
      maxDrawdown: -0.04
    });
    expect(model.submissions[1].color).toBe(COMPARE_COLORS[1]);

    expect(model.series).toEqual([
      { id: "sub-1", name: "#1 · Alpha Desk", color: COMPARE_COLORS[0] },
      { id: "sub-2", name: "#2 · Beta Fund", color: COMPARE_COLORS[1] }
    ]);

    expect(model.points).toEqual([
      {
        date: "2026-01-01",
        values: {
          "sub-1": { equity: 100000, drawdown: 0 },
          "sub-2": { equity: 100000, drawdown: 0 }
        }
      },
      {
        date: "2026-06-01",
        values: {
          "sub-1": { equity: 118400, drawdown: -0.04 },
          "sub-2": { equity: 112200, drawdown: -0.08 }
        }
      }
    ]);

    expect(model.equityData).toEqual([
      { date: "2026-01-01", "sub-1": 100000, "sub-2": 100000 },
      { date: "2026-06-01", "sub-1": 118400, "sub-2": 112200 }
    ]);

    expect(model.drawdownData).toEqual([
      { date: "2026-01-01", "sub-1": 0, "sub-2": 0 },
      { date: "2026-06-01", "sub-1": -0.04, "sub-2": -0.08 }
    ]);
  });

  it("handles partial dates where equity and drawdown arrays differ", () => {
    const response: CompareResponse = {
      submissions: [
        {
          submission_id: "sub-1",
          submission_number: 1,
          submission_label: "#1",
          team_id: "team-a",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "hidden_test",
          metrics: null,
          equity: [{ date: "2026-01-01", equity: 100000 }],
          drawdown: [],
          execution_parameters: null
        }
      ]
    };

    const model = toCompareModel(response);

    expect(model.points).toEqual([
      {
        date: "2026-01-01",
        values: {
          "sub-1": { equity: 100000, drawdown: null }
        }
      }
    ]);
  });

  it("maps optional rich graph data for detailed compare mode", () => {
    const response: CompareResponse = {
      submissions: [
        {
          submission_id: "sub-1",
          submission_number: 1,
          submission_label: "#1",
          team_id: "team-a",
          team_name: "Alpha Desk",
          status: "completed",
          data_track: "learning",
          metrics: {
            total_return: 0.184,
            annual_return: 0.21,
            sharpe: 1.82,
            max_drawdown: -0.04
          },
          equity: [{ date: "2026-01-01", equity: 1.02 }],
          drawdown: [{ date: "2026-01-01", drawdown: -0.01 }],
          execution_parameters: {
            data_track: "learning",
            data_start: "2015-01-01",
            scoring_start: "2023-01-01",
            scoring_end: "2025-12-31",
            capital: 1_000_000,
            group_count: 5,
            price_policy: "front_adjusted",
            execution_price: "vwap",
            mark_price: "close",
            commission_rate: 0.001,
            slippage_rate: 0.0005,
            max_leverage: 1,
            top_k: null,
            long_only: false,
            submission_timeout_enabled: false,
            submission_timeout_seconds: 120
          },
          graph_data: {
            equity: [{ date: "2026-01-01", equity: 1.02 }],
            equity_cny: [{ date: "2026-01-01", equity_cny: 1_020_000 }],
            drawdown: [{ date: "2026-01-01", drawdown: -0.01 }],
            benchmark: [{ date: "2026-01-01", benchmark_return: 0.01, benchmark_cny: 1_010_000 }],
            alpha: [{ date: "2026-01-01", alpha_return: 0.02, alpha_cny: 1_030_000 }],
            daily_pnl: [{ date: "2026-01-01", pnl_cny: 20_000, daily_return: 0.02 }],
            trade_volume: [{ date: "2026-01-01", buy_cny: 300_000, sell_cny: 100_000 }],
            group_cumulative: [
              { date: "2026-01-01", group: "group_1", cumulative_return: 0.03 },
              { date: "2026-01-01", group: "group_2", cumulative_return: -0.01 }
            ]
          }
        }
      ]
    };

    const model = toCompareModel(response);

    expect(model.detailedSubmissions).toEqual([
      {
        id: "sub-1",
        displayName: "#1 · Alpha Desk",
        dataTrack: "learning",
        points: [
          {
            date: "2026-01-01",
            equity: 1_020_000,
            strategyEquityCny: 1_020_000,
            strategyPercentChange: expect.closeTo(0.02),
            benchmark: 1_010_000,
            benchmarkPercentChange: expect.closeTo(0.01),
            alpha: 1_030_000,
            alphaPercentChange: expect.closeTo(0.02),
            drawdown: -0.01,
            dailyPnl: 20_000,
            buyCny: 300_000,
            sellCny: 100_000,
            groupPercentChanges: {
              group_1: 0.03,
              group_2: -0.01
            }
          }
        ],
        groupSeries: [
          {
            color: "#34d399",
            finalCumulativeReturn: 0.03,
            id: "group_1",
            isBest: true,
            label: "Group 1"
          },
          {
            color: "#fb923c",
            finalCumulativeReturn: -0.01,
            id: "group_2",
            isBest: false,
            label: "Group 2"
          }
        ],
        availability: {
          hasAlpha: true,
          hasBenchmark: true
        },
        executionParameters: {
          data_track: "learning",
          data_start: "2015-01-01",
          scoring_start: "2023-01-01",
          scoring_end: "2025-12-31",
          capital: 1_000_000,
          group_count: 5,
          price_policy: "front_adjusted",
          execution_price: "vwap",
          mark_price: "close",
          commission_rate: 0.001,
          slippage_rate: 0.0005,
          max_leverage: 1,
          top_k: null,
          long_only: false,
          submission_timeout_enabled: false,
          submission_timeout_seconds: 120
        },
        hasGraphData: true
      }
    ]);
  });
});
