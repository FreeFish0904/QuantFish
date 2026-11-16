import { describe, expect, it } from "vitest";

import type { components } from "../../shared/api/generated/api-types";
import { toDashboardModel } from "./model";

type DashboardResponse = components["schemas"]["DashboardResponse"];

const dashboard: DashboardResponse = {
  course_name: "QClass 2026",
  scoring_timeout_seconds: 300,
  submission_count: 10,
  team_count: 5,
  status_counts: { queued: 1, running: 2, completed: 7 },
  runner_status: {
    status: "online",
    queued: 1,
    running: 2,
    updated_at: "2026-06-18T08:35:00+00:00",
    scoring_timeout_seconds: 300,
    submissions_enabled: true
  },
  latest: [
    {
      badge: null,
      score: 94.25,
      metric: "score",
      metric_value: 94.25,
      eligible: true,
      id: "sub-1",
      rank: 1,
      stale: true,
      status: "completed",
      submitted_at: "2026-06-18T08:30:00Z",
      summary: { max_drawdown: -0.05, sharpe: 1.42 },
      team_name: "Alpha Desk"
    }
  ]
};

describe("toDashboardModel", () => {
  it("maps runner status from the backend snapshot", () => {
    const model = toDashboardModel(dashboard);
    expect(model.runnerStatus.status).toBe("online");
    expect(model.runnerStatus.running).toBe(2);
    expect(model.runnerStatus.queued).toBe(1);
    expect(model.runnerStatus.lastUpdated).toBe("2026-06-18T08:35:00+00:00");
    expect(model.runnerStatus.submissionsEnabled).toBe(true);
    expect(model.scoringTimeoutSeconds).toBe(300);
  });

  it("maps KPIs from status counts and team count", () => {
    const model = toDashboardModel(dashboard);
    expect(model.kpis.find((kpi) => kpi.id === "active-teams")?.value).toBe(5);
    expect(model.kpis.find((kpi) => kpi.id === "scored-runs")?.value).toBe(7);
    expect(model.kpis.find((kpi) => kpi.id === "queued-jobs")?.value).toBe(1);
    expect(model.kpis.find((kpi) => kpi.id === "stale-results")?.value).toBe(1);
  });

  it("maps latest submissions with summary metrics", () => {
    const model = toDashboardModel(dashboard);
    expect(model.latestSubmissions).toHaveLength(1);

    const row = model.latestSubmissions[0];
    expect(row.id).toBe("sub-1");
    expect(row.teamName).toBe("Alpha Desk");
    expect("track" in row).toBe(false);
    expect(row.status).toBe("completed");
    expect(row.stale).toBe(true);
    expect("score" in row).toBe(false);
    expect("rank" in row).toBe(false);
    expect(row.sharpe).toBe(1.42);
    expect(row.drawdown).toBe(-0.05);
    expect(row.submittedAt).toBe("2026-06-18T08:30:00Z");
  });

  it("maps class settings from course name", () => {
    const model = toDashboardModel(dashboard);
    expect(model.className).toBe("QClass 2026");
    expect(model.scoringTimeoutSeconds).toBe(300);
  });

  it("uses backend offline runner status when submissions are disabled", () => {
    const offline: DashboardResponse = {
      ...dashboard,
      runner_status: {
        status: "offline",
        queued: 0,
        running: 0,
        updated_at: "2026-06-18T08:40:00+00:00",
        scoring_timeout_seconds: null,
        submissions_enabled: false
      }
    };
    const model = toDashboardModel(offline);
    expect(model.runnerStatus.status).toBe("offline");
    expect(model.runnerStatus.submissionsEnabled).toBe(false);
    expect(model.scoringTimeoutSeconds).toBeNull();
  });
});
