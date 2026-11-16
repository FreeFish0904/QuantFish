import { describe, expect, it } from "vitest";

import {
  buildExecutionParameterRows,
  isLongShortExecutionMode,
  type SubmissionExecutionParameters
} from "./executionParameters";

describe("buildExecutionParameterRows", () => {
  it("includes the industry neutralization setting", () => {
    const rows = buildExecutionParameterRows(
      {
        data_track: "learning",
        long_only: false,
        group_count: 5,
        industry_neutralization: true
      } as SubmissionExecutionParameters,
      (key) => {
        if (key === "executionParameters.yes") {
          return "Yes";
        }
        return key;
      }
    );

    expect(rows).toEqual(
      expect.arrayContaining([
        {
          id: "industry_neutralization",
          label: "executionParameters.industryNeutralization",
          value: "Yes"
        }
      ])
    );
  });

  it("shows the derived backtest mode without alpha type", () => {
    const rows = buildExecutionParameterRows(
      {
        data_track: "hidden_test",
        long_only: true
      } as SubmissionExecutionParameters,
      (key) => {
        if (key === "executionParameters.longOnlyMode") {
          return "Long-only";
        }
        return key;
      }
    );

    expect(rows).toEqual(
      expect.arrayContaining([
        {
          id: "execution_mode",
          label: "executionParameters.backtestMode",
          value: "Long-only"
        }
      ])
    );
    expect(rows.some((row) => row.id === "alpha_type")).toBe(false);
  });

  it("shows the long-only risk-free rate", () => {
    const rows = buildExecutionParameterRows(
      {
        data_track: "hidden_test",
        long_only: true,
        long_only_risk_free_rate: 0.0175
      } as SubmissionExecutionParameters,
      (key) => {
        if (key === "executionParameters.longOnlyRiskFreeRate") {
          return "Long-only risk-free rate";
        }
        return key;
      }
    );

    expect(rows).toEqual(
      expect.arrayContaining([
        {
          id: "long_only_risk_free_rate",
          label: "Long-only risk-free rate",
          value: "1.75%"
        }
      ])
    );
  });

  it("shows sell stamp duty and terminal stale-position policy", () => {
    const rows = buildExecutionParameterRows(
      {
        data_track: "hidden_test",
        long_only: true,
        sell_stamp_duty_rate: 0.0005,
        terminal_stale_position_policy: "reject"
      } as SubmissionExecutionParameters,
      (key) => key
    );

    expect(rows).toEqual(
      expect.arrayContaining([
        {
          id: "sell_stamp_duty_rate",
          label: "executionParameters.sellStampDuty",
          value: "0.05%"
        },
        {
          id: "terminal_stale_position_policy",
          label: "executionParameters.terminalStalePositionPolicy",
          value: "reject"
        }
      ])
    );
  });
});

describe("isLongShortExecutionMode", () => {
  it("treats the long-only toggle as the effective mode", () => {
    expect(
      isLongShortExecutionMode({
        long_only: true
      } as SubmissionExecutionParameters)
    ).toBe(false);
  });

  it("keeps raw long-short mode when the long-only toggle is off", () => {
    expect(
      isLongShortExecutionMode({
        long_only: false
      } as SubmissionExecutionParameters)
    ).toBe(true);
  });
});
