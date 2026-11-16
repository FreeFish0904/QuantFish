import { describe, expect, it } from "vitest";

import type { components } from "../../shared/api/generated/api-types";
import {
  filterHistoryEntries,
  formatHistoryMetric,
  sortHistoryEntries,
  toHistoryEntries
} from "./model";

type SubmissionSummary = components["schemas"]["SubmissionSummary"];

const submissions: SubmissionSummary[] = [
  {
    submission_id: "sub-old",
    submission_number: 1,
    submission_label: "#1",
    team_id: "team-alpha",
    team_name: "Alpha Desk",
    status: "completed",
    data_track: "hidden_test",
    stale: false,
    submitted_at: "2026-06-18T08:00:00Z",
    scored_at: "2026-06-18T08:05:00Z",
    metrics: {
      sharpe: 1.2,
      total_return: 0.08,
      annual_return: 0.08,
      max_drawdown: -0.05,
      average_turnover: 0.2,
      average_short_exposure: 0,
      calmar: 1.6
    },
    score: 33.5,
    error_message: null
  },
  {
    submission_id: "sub-new",
    submission_number: 2,
    submission_label: "#2",
    team_id: "team-alpha",
    team_name: "Alpha Desk",
    status: "failed",
    data_track: "learning",
    stale: false,
    submitted_at: "2026-06-18T10:00:00Z",
    scored_at: "2026-06-18T10:02:00Z",
    metrics: null,
    score: null,
    error_message: "Strategy raised",
    raw_error: "Traceback\nRuntimeError: Strategy raised"
  },
  {
    submission_id: "sub-beta",
    submission_number: 3,
    submission_label: "#3",
    team_id: "team-beta",
    team_name: "Beta Fund",
    status: "completed",
    data_track: "hidden_test",
    stale: false,
    submitted_at: "2026-06-18T09:00:00Z",
    scored_at: "2026-06-18T09:05:00Z",
    metrics: {
      sharpe: 1.8,
      total_return: 0.12,
      annual_return: 0.12,
      max_drawdown: -0.04,
      average_turnover: 0.25,
      average_short_exposure: 0,
      calmar: 3.25
    },
    score: 52.083333333333336,
    error_message: null
  }
];

describe("toHistoryEntries", () => {
  it("maps submission summaries and keeps duplicate team uploads", () => {
    const entries = toHistoryEntries(submissions);

    expect(entries).toHaveLength(3);
    expect(entries.map((entry) => entry.teamName).filter((name) => name === "Alpha Desk")).toHaveLength(2);
    expect(entries[0]).toMatchObject({
      id: "sub-old",
      submissionNumber: 1,
      submissionLabel: "#1",
      teamId: "team-alpha",
      teamName: "Alpha Desk",
      status: "completed",
      dataTrack: "hidden_test",
      isStale: false,
      calmar: 1.6,
      sharpe: 1.2,
      totalReturn: 0.08,
      drawdown: -0.05,
      errorMessage: null,
      rawError: null
    });
    expect(entries[1].sharpe).toBeNull();
    expect(entries[1].calmar).toBeNull();
    expect(entries[1].rawError).toBe("Traceback\nRuntimeError: Strategy raised");
  });

  it("marks stale completed runs as not comparable", () => {
    const entries = toHistoryEntries([
      {
        ...submissions[0],
        stale: true
      }
    ]);

    expect(entries[0].isStale).toBe(true);
    expect(entries[0].compareSelectable).toBe(false);
  });
});

describe("history filtering and sorting", () => {
  it("filters by team query and status", () => {
    const entries = toHistoryEntries(submissions);

    expect(filterHistoryEntries(entries, { search: "alpha", status: "all", dataTrack: "all" })).toHaveLength(2);
    expect(filterHistoryEntries(entries, { search: "alpha", status: "failed", dataTrack: "all" })).toEqual([
      expect.objectContaining({ id: "sub-new" })
    ]);
    expect(filterHistoryEntries(entries, { search: "#3", status: "all", dataTrack: "all" })).toEqual([
      expect.objectContaining({ id: "sub-beta" })
    ]);
  });

  it("filters and searches by data track", () => {
    const entries = toHistoryEntries(submissions);
    const windowEntries = toHistoryEntries([
      ...submissions,
      {
        ...submissions[1],
        submission_id: "sub-window-2",
        submission_number: 4,
        submission_label: "#4",
        data_track: "learning_2"
      }
    ]);

    expect(filterHistoryEntries(entries, { search: "", status: "all", dataTrack: "learning" })).toEqual([
      expect.objectContaining({ id: "sub-new" })
    ]);
    expect(filterHistoryEntries(entries, { search: "learning", status: "all", dataTrack: "all" })).toEqual([
      expect.objectContaining({ id: "sub-new" })
    ]);
    expect(filterHistoryEntries(entries, { search: "", status: "all", dataTrack: "hidden_test" })).toHaveLength(2);
    expect(
      filterHistoryEntries(windowEntries, {
        search: "2020",
        status: "all",
        dataTrack: "learning_2"
      })
    ).toEqual([expect.objectContaining({ id: "sub-window-2" })]);
  });

  it("filters to the logged-in team when my account only is enabled", () => {
    const entries = toHistoryEntries(submissions);

    expect(
      filterHistoryEntries(entries, {
        search: "",
        status: "all",
        dataTrack: "all",
        currentTeamId: "team-alpha",
        myAccountOnly: true
      }).map((entry) => entry.id)
    ).toEqual(["sub-old", "sub-new"]);
    expect(
      filterHistoryEntries(entries, {
        search: "",
        status: "all",
        dataTrack: "all",
        currentTeamId: null,
        myAccountOnly: true
      })
    ).toHaveLength(3);
  });

  it("sorts newest submissions first by default", () => {
    const entries = toHistoryEntries(submissions);

    expect(sortHistoryEntries(entries, { key: "submittedAt", direction: "desc" }).map((entry) => entry.id)).toEqual([
      "sub-new",
      "sub-beta",
      "sub-old"
    ]);
  });

  it("sorts by calmar score", () => {
    const entries = toHistoryEntries(submissions);

    expect(sortHistoryEntries(entries, { key: "calmar", direction: "desc" }).map((entry) => entry.id)).toEqual([
      "sub-beta",
      "sub-old",
      "sub-new"
    ]);
  });
});

describe("formatHistoryMetric", () => {
  it("formats missing metrics safely", () => {
    expect(formatHistoryMetric(null)).toBe("—");
    expect(formatHistoryMetric(undefined)).toBe("—");
    expect(formatHistoryMetric(1.234)).toBe("1.23");
  });
});
