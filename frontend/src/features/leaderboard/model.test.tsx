import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";

import type { components } from "../../shared/api/generated/api-types";
import { toLeaderboardEntries, useLeaderboardFilters } from "./model";

const sampleRows: components["schemas"]["LeaderboardSummary"][] = [
  {
    rank: 1,
    id: "sub-1",
    team_name: "Alpha Desk",
    status: "completed",
    stale: false,
    eligible: true,
    submitted_at: "2026-06-18T08:00:00Z",
    summary: { sharpe: 1.8, max_drawdown: -0.04, total_return: 0.12, calmar: 3 },
    score: 1.8,
    metric: "sharpe",
    metric_value: 1.8,
    badge: "gold"
  },
  {
    rank: 2,
    id: "sub-2",
    team_name: "Beta Fund",
    status: "completed",
    stale: false,
    eligible: true,
    submitted_at: "2026-06-18T07:00:00Z",
    summary: { sharpe: 1.4, max_drawdown: -0.08, total_return: 0.09, calmar: 2 },
    score: 1.4,
    metric: "sharpe",
    metric_value: 1.4,
    badge: "silver"
  },
  {
    rank: 3,
    id: "sub-3",
    team_name: "Gamma Lab",
    status: "running",
    stale: false,
    eligible: false,
    submitted_at: "2026-06-18T06:00:00Z",
    summary: { sharpe: 1.1, max_drawdown: -0.12, total_return: 0.06, calmar: 1 },
    score: 1.1,
    metric: "sharpe",
    metric_value: 1.1,
    badge: null
  }
];

describe("toLeaderboardEntries", () => {
  it("maps backend rows to camelCase domain model", () => {
    const entries = toLeaderboardEntries(sampleRows);

    expect(entries).toHaveLength(3);
    expect(entries[0]).toMatchObject({
      id: "sub-1",
      teamName: "Alpha Desk",
      status: "completed",
      metric: "sharpe",
      metricValue: 1.8,
      rank: 1,
      sharpe: 1.8,
      drawdown: -0.04,
      calmar: 3,
      badge: "gold"
    });
    expect("score" in entries[0]).toBe(false);
    expect("track" in entries[0]).toBe(false);
    expect(entries[1].badge).toBe("silver");
    expect(entries[2].badge).toBeNull();
  });

  it("defaults missing numeric summaries to zero and keeps Calmar missing", () => {
    const entries = toLeaderboardEntries([
      {
        rank: 4,
        id: "sub-4",
        team_name: "Delta One",
        status: "completed",
        stale: false,
        eligible: true,
        submitted_at: "2026-06-18T05:00:00Z",
        summary: {},
        score: 50,
        metric: "calmar",
        metric_value: 0,
        badge: null
      }
    ]);

    expect(entries[0].sharpe).toBe(0);
    expect(entries[0].drawdown).toBe(0);
    expect(entries[0].calmar).toBeNull();
    expect(entries[0].metric).toBe("calmar");
    expect(entries[0].metricValue).toBeNull();
  });

  it("does not recompute Calmar when the backend marks it missing", () => {
    const entries = toLeaderboardEntries(
      [
        {
          rank: 4,
          id: "sub-smooth",
          team_name: "Smooth Return",
          status: "completed",
          stale: false,
          eligible: false,
          submitted_at: "2026-06-18T05:00:00Z",
          summary: { annual_return: 0.2, max_drawdown: 0, calmar: null },
          score: 0,
          metric: "calmar",
          metric_value: 0,
          badge: null
        }
      ],
      "calmar"
    );

    expect(entries[0].calmar).toBeNull();
    expect(entries[0].metricValue).toBeNull();
  });

  it("uses requested Calmar instead of stale row metric metadata", () => {
    const entries = toLeaderboardEntries(
      [
        {
          rank: 1,
          id: "sub-calmar",
          team_name: "Calmar Desk",
          status: "completed",
          stale: false,
          eligible: true,
          submitted_at: "2026-06-18T08:00:00Z",
          summary: { sharpe: 1.8, annual_return: 0.12, max_drawdown: -0.04 },
          score: 1.8,
          metric: "sharpe",
          metric_value: 1.8,
          badge: "gold"
        }
      ],
      "calmar"
    );

    expect(entries[0].metric).toBe("calmar");
    expect(entries[0].metricValue).toBeCloseTo(3);
    expect(entries[0].calmar).toBeCloseTo(3);
  });
});

describe("useLeaderboardFilters", () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <MemoryRouter>{children}</MemoryRouter>;
  }

  it("filters by search query", async () => {
    const entries = toLeaderboardEntries(sampleRows);
    const { result } = renderHook(() => useLeaderboardFilters(entries), { wrapper });

    expect(result.current.visibleRows).toHaveLength(3);

    act(() => result.current.setSearch("beta"));
    await waitFor(() => {
      expect(result.current.visibleRows).toHaveLength(1);
      expect(result.current.visibleRows[0].teamName).toBe("Beta Fund");
    });
  });

  it("sorts rows by selected metric column and direction", async () => {
    const entries = toLeaderboardEntries(sampleRows);
    const { result } = renderHook(() => useLeaderboardFilters(entries), { wrapper });

    act(() => result.current.toggleSort("metricValue"));
    await waitFor(() => {
      expect(result.current.visibleRows[0].teamName).toBe("Gamma Lab");
      expect(result.current.visibleRows[2].teamName).toBe("Alpha Desk");
    });

    act(() => result.current.toggleSort("metricValue"));
    await waitFor(() => {
      expect(result.current.visibleRows[0].teamName).toBe("Alpha Desk");
    });
  });

  it("paginates rows", async () => {
    const entries = toLeaderboardEntries(sampleRows);
    const { result } = renderHook(() => useLeaderboardFilters(entries), { wrapper });

    act(() => result.current.setPage(2));
    await waitFor(() => {
      expect(result.current.page).toBe(1);
    });

    // pageSize is 10, so with 3 entries page 2 gets clamped to 1.
  });

  it("toggles selection and builds compare url", async () => {
    const entries = toLeaderboardEntries(sampleRows);
    const { result } = renderHook(() => useLeaderboardFilters(entries), { wrapper });

    expect(result.current.compareUrl).toBeNull();

    act(() => result.current.toggleSelection("sub-1"));
    expect(result.current.compareUrl).toBeNull();

    act(() => result.current.toggleSelection("sub-2"));
    await waitFor(() => {
      expect(result.current.compareUrl).toContain("submission_id=sub-1");
      expect(result.current.compareUrl).toContain("submission_id=sub-2");
    });

    act(() => result.current.toggleSelection("sub-1"));
    await waitFor(() => {
      expect(result.current.compareUrl).toBeNull();
    });
  });
});
