import { describe, expect, it } from "vitest";

import type { components } from "../../shared/api/generated/api-types";
import {
  toAdminDataReleaseBuildState,
  toAdminSettings,
  toAdminSubmissionRecords,
  toTeamCollections
} from "./model";

type SettingsResponse = components["schemas"]["AdminSettingsResponse"];
type TeamsResponse = components["schemas"]["AdminTeamsResponse"];
type SubmissionsResponse = components["schemas"]["AdminSubmissionsResponse"];
type DataReleaseBuildStateResponse = components["schemas"]["AdminDataReleaseBuildState"];

describe("toAdminDataReleaseBuildState", () => {
  it("maps release readiness and dataset-level job progress", () => {
    const response: DataReleaseBuildStateResponse = {
      source_available: true,
      buildable_release_names: ["learning_1", "learning_2", "learning_3"],
      releases: [
        {
          release_name: "learning_2",
          start: "2015-01-01",
          end: "2020-12-31",
          output_root: "data_releases/learning_2",
          status: "ready",
          last_built_at: "2026-07-24T08:00:00+00:00"
        }
      ],
      job: {
        job_id: "job-1",
        status: "running",
        release_names: ["learning_2"],
        progress_percent: 40,
        tracks: [
          {
            release_name: "learning_2",
            status: "running",
            phase: "building",
            progress_percent: 40,
            completed_datasets: 5,
            total_datasets: 12,
            current_dataset: "stock.daily_returns",
            error_message: null
          }
        ],
        created_at: "2026-07-24T08:00:00+00:00",
        started_at: "2026-07-24T08:00:01+00:00",
        finished_at: null,
        current_release_name: "learning_2",
        error_message: null
      }
    };

    const state = toAdminDataReleaseBuildState(response);

    expect(state.sourceAvailable).toBe(true);
    expect(state.releases[0]).toEqual({
      releaseName: "learning_2",
      start: "2015-01-01",
      end: "2020-12-31",
      outputRoot: "data_releases/learning_2",
      status: "ready",
      lastBuiltAt: "2026-07-24T08:00:00+00:00"
    });
    expect(state.job?.currentReleaseName).toBe("learning_2");
    expect(state.job?.tracks[0]).toEqual({
      releaseName: "learning_2",
      status: "running",
      phase: "building",
      progressPercent: 40,
      completedDatasets: 5,
      totalDatasets: 12,
      currentDataset: "stock.daily_returns",
      errorMessage: null
    });
  });
});

describe("toAdminSettings", () => {
  it("maps editable admin settings from backend contracts", () => {
    const response: SettingsResponse = {
      course: { name: "QuantFish 2026" },
      dataset: {
        train_start: "2021-01-01",
        train_end: "2022-12-31",
        hidden_test_start: "2023-01-01",
        hidden_test_end: "2025-12-31"
      },
      scoring: {
        sharpe_weight: 45,
        sharpe_target: 2,
        annual_return_weight: 35,
        annual_return_target: 0.3,
        drawdown_weight: 15,
        drawdown_limit: 0.3,
        turnover_weight: 5,
        turnover_limit: 3,
        short_profit_weight: 50,
        short_profit_target: 0.3,
        minimum_slice_trading_days: 120
      },
      execution: {
        commission_rate: 0.001,
        slippage_rate: 0.002,
        sell_stamp_duty_rate: 0.0007,
        max_leverage: 1.5,
        top_k: 20,
        long_only_weighting: "score_proportional",
        long_only_target_count: 40,
        max_position_weight: 0.04,
        max_participation_rate: 0.08,
        min_listing_days: 90,
        terminal_stale_position_policy: "carry",
        allowed_market_types: [1, 4],
        submissions_enabled: false,
        hidden_test_enabled: false,
        max_concurrent_scoring: 2,
        submission_timeout_seconds: 60,
        submission_timeout_enabled: true,
        long_only: true
      },
      backtest: {
        data_start: "2021-01-01",
        scoring_start: "2023-01-01",
        scoring_end: "2025-12-31",
        capital: 1_000_000,
        group_count: 5,
        industry_neutralization: true,
        price_policy: "front_adjusted",
        execution_price: "vwap",
        mark_price: "close",
        long_only_benchmark: "hs300",
        long_only_risk_free_rate: 0.02,
        long_only_min_beta_observations: 30
      },
      settings_history: [
        {
          entry_id: "hist-1",
          created_at: "2026-06-24T09:30:00+00:00",
          entry_type: "settings_change",
          config_sha256: "abcdef123456",
          changed_fields: ["execution.max_leverage"],
          settings: { execution: { max_leverage: 1 } },
          stale_marked: false,
          affected_submission_ids: [],
          affected_count: 0,
          reverted_at: null
        },
        {
          entry_id: "stale-1",
          created_at: "2026-06-24T09:45:00+00:00",
          entry_type: "stale_mark",
          config_sha256: null,
          changed_fields: [],
          settings: {},
          stale_marked: true,
          affected_submission_ids: ["sub-1", "sub-2"],
          affected_count: 2,
          reverted_at: null
        }
      ],
      execution_limits: { engine_version: "engine-x" },
      runtime: { runtime_root: "/tmp/runtime", frontend_dist: "frontend/dist" }
    };

    const settings = toAdminSettings(response);

    expect(settings.dataset.trainStart).toBe("2021-01-01");
    expect(settings.dataset.hiddenTestEnd).toBe("2025-12-31");
    expect(settings.scoring.sharpeWeight).toBe(45);
    expect(settings.scoring.annualReturnWeight).toBe(35);
    expect(settings.scoring.shortProfitWeight).toBe(50);
    expect(settings.scoring.shortProfitTarget).toBe(0.3);
    expect(settings.scoring.minimumSliceTradingDays).toBe(120);
    expect(settings.execution.longOnly).toBe(true);
    expect(settings.execution.longOnlyWeighting).toBe("score_proportional");
    expect(settings.execution.longOnlyTargetCount).toBe(40);
    expect(settings.execution.maxPositionWeight).toBe(0.04);
    expect(settings.execution.maxParticipationRate).toBe(0.08);
    expect(settings.execution.minListingDays).toBe(90);
    expect(settings.execution.sellStampDutyRate).toBe(0.0007);
    expect(settings.execution.terminalStalePositionPolicy).toBe("carry");
    expect(settings.execution.allowedMarketTypes).toEqual([1, 4]);
    expect(settings.execution.submissionsEnabled).toBe(false);
    expect(settings.execution.hiddenTestEnabled).toBe(false);
    expect(settings.capital).toBe(1_000_000);
    expect(settings.industryNeutralization).toBe(true);
    expect(settings.longOnlyBenchmark).toBe("hs300");
    expect(settings.longOnlyRiskFreeRate).toBe(0.02);
    expect(settings.longOnlyMinBetaObservations).toBe(30);
    expect(settings.engineVersion).toBe("engine-x");
    expect(settings.settingsHistory).toEqual([
      {
        entryId: "hist-1",
        createdAt: "2026-06-24T09:30:00+00:00",
        entryType: "settings_change",
        configSha256: "abcdef123456",
        changedFields: ["execution.max_leverage"],
        settings: { execution: { max_leverage: 1 } },
        staleMarked: false,
        affectedSubmissionIds: [],
        affectedCount: 0,
        revertedAt: null
      },
      {
        entryId: "stale-1",
        createdAt: "2026-06-24T09:45:00+00:00",
        entryType: "stale_mark",
        configSha256: null,
        changedFields: [],
        settings: {},
        staleMarked: true,
        affectedSubmissionIds: ["sub-1", "sub-2"],
        affectedCount: 2,
        revertedAt: null
      }
    ]);
  });
});

describe("toTeamCollections", () => {
  it("keeps active and archived teams separate with password nulls", () => {
    const response = {
      teams: [
        {
          team_id: "team-a",
          team_name: "Alpha",
          display_name: "Alpha",
          submission_count: 2,
          created_at: "2026-06-19T10:00:00Z",
          status: "active",
          password: null,
          cohort_id: "cohort-hidden",
          cohort_name: "Hidden cohort",
          history_visible: false,
          submissions_enabled: true
        }
      ],
      active_teams: [
        {
          team_id: "team-a",
          team_name: "Alpha",
          display_name: "Alpha",
          submission_count: 2,
          created_at: "2026-06-19T10:00:00Z",
          status: "active",
          password: null,
          cohort_id: "cohort-hidden",
          cohort_name: "Hidden cohort",
          history_visible: false,
          submissions_enabled: true
        }
      ],
      archived_teams: [
        {
          team_id: "team-b",
          team_name: "Beta",
          display_name: "Beta",
          submission_count: 0,
          created_at: "2026-06-18T10:00:00Z",
          status: "archived",
          password: null,
          cohort_id: null,
          cohort_name: null,
          history_visible: true,
          submissions_enabled: true
        }
      ],
      cohorts: [
        {
          cohort_id: "cohort-hidden",
          name: "Hidden cohort",
          team_ids: ["team-a"],
          history_visible: false,
          submissions_enabled: true,
          created_at: "2026-06-18T09:00:00Z",
          updated_at: "2026-06-18T09:00:00Z"
        }
      ]
    } as unknown as TeamsResponse;

    const teams = toTeamCollections(response);

    expect(teams.activeTeams[0].password).toBeNull();
    expect(teams.activeTeams[0].cohortId).toBe("cohort-hidden");
    expect(teams.activeTeams[0].historyVisible).toBe(false);
    expect(teams.activeTeams[0].submissionsEnabled).toBe(true);
    expect(teams.archivedTeams[0].status).toBe("archived");
    expect(teams.cohorts[0]).toEqual({
      cohortId: "cohort-hidden",
      name: "Hidden cohort",
      teamIds: ["team-a"],
      historyVisible: false,
      submissionsEnabled: true,
      createdAt: "2026-06-18T09:00:00Z",
      updatedAt: "2026-06-18T09:00:00Z"
    });
  });
});

describe("toAdminSubmissionRecords", () => {
  it("maps raw admin submission records", () => {
    const response: SubmissionsResponse = {
      submissions: [
        {
          submission_id: "sub-1",
          submission_number: 1,
          submission_label: "#1",
          team_id: "team-a",
          team_name: "Alpha",
          type: "python",
          data_track: "learning",
          status: "failed",
          stale: true,
          selectable: true,
          score: null,
          filename: "strategy.py",
          submitted_at: "2026-06-19T10:00:00Z",
          finished_at: "2026-06-19T10:01:00Z",
          raw_error: "Traceback",
          config_snapshot: { course: { name: "QuantFish" } },
          file_paths: { strategy_path: "/tmp/strategy.py" }
        }
      ]
    };

    const records = toAdminSubmissionRecords(response);

    expect(records[0].id).toBe("sub-1");
    expect(records[0].submissionNumber).toBe(1);
    expect(records[0].submissionLabel).toBe("#1");
    expect(records[0].dataTrack).toBe("learning");
    expect(records[0].rawError).toBe("Traceback");
    expect(records[0].filePaths.strategy_path).toBe("/tmp/strategy.py");
  });
});
