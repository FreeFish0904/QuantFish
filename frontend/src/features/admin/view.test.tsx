import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, type Mock, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";

import { I18nProvider } from "../../shared/i18n";
import { AdminConsoleView } from "./view";

const loginMock = vi.fn();
const logoutMock = vi.fn();
const updateSettingsMock = vi.fn();
const startDataReleaseBuildMock = vi.fn();
const revertSettingsHistoryMock = vi.fn();
const markStaleSubmissionsMock = vi.fn();
const revertStaleMarkMock = vi.fn();
const createTeamMock = vi.fn();
const updateTeamMock = vi.fn();
const teamBulkActionMock = vi.fn();
const createTeamCohortMock = vi.fn();
const updateTeamCohortMock = vi.fn();
const deleteTeamCohortMock = vi.fn();
const deleteSubmissionsMock = vi.fn();
const rerunSubmissionsMock = vi.fn();
const viewSourceMock = vi.fn();
const viewRawErrorMock = vi.fn();

Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn()
  }
});

vi.mock("./model", () => ({
  useAdminSession: vi.fn(),
  useAdminLogin: vi.fn(),
  useAdminLogout: vi.fn(),
  useAdminSettings: vi.fn(),
  useAdminDataReleases: vi.fn(),
  useStartAdminDataReleaseBuild: vi.fn(),
  useUpdateAdminSettings: vi.fn(),
  useRevertAdminSettingsHistory: vi.fn(),
  useMarkAdminStaleSubmissions: vi.fn(),
  useRevertAdminStaleMark: vi.fn(),
  useAdminTeams: vi.fn(),
  useCreateTeam: vi.fn(),
  useUpdateTeam: vi.fn(),
  useTeamBulkAction: vi.fn(),
  useCreateTeamCohort: vi.fn(),
  useUpdateTeamCohort: vi.fn(),
  useDeleteTeamCohort: vi.fn(),
  useAdminSubmissions: vi.fn(),
  useAdminSubmissionSource: vi.fn(),
  useAdminSubmissionRawError: vi.fn(),
  useDeleteAdminSubmissions: vi.fn(),
  useRerunAdminSubmissions: vi.fn()
}));

import {
  useAdminLogin,
  useAdminLogout,
  useAdminSession,
  useAdminSettings,
  useAdminDataReleases,
  useAdminSubmissions,
  useAdminSubmissionRawError,
  useAdminSubmissionSource,
  useAdminTeams,
  useCreateTeam,
  useCreateTeamCohort,
  useDeleteAdminSubmissions,
  useDeleteTeamCohort,
  useRerunAdminSubmissions,
  useStartAdminDataReleaseBuild,
  useTeamBulkAction,
  useRevertAdminSettingsHistory,
  useMarkAdminStaleSubmissions,
  useRevertAdminStaleMark,
  useUpdateAdminSettings,
  useUpdateTeam,
  useUpdateTeamCohort
} from "./model";

beforeEach(() => {
  vi.clearAllMocks();
});

function Wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  return (
    <I18nProvider defaultLanguage="en">
      <MemoryRouter>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    </I18nProvider>
  );
}

function ChineseWrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  return (
    <I18nProvider defaultLanguage="zh">
      <MemoryRouter>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    </I18nProvider>
  );
}

const settings = {
  courseName: "QuantFish 2026",
  dataset: {
    trainStart: "2021-01-01",
    trainEnd: "2022-12-31",
    hiddenTestStart: "2023-01-01",
    hiddenTestEnd: "2025-12-31"
  },
  scoring: {
    sharpeWeight: 45,
    sharpeTarget: 2,
    annualReturnWeight: 35,
    annualReturnTarget: 0.3,
    drawdownWeight: 15,
    drawdownLimit: 0.3,
    turnoverWeight: 5,
    turnoverLimit: 3,
    shortProfitWeight: 50,
    shortProfitTarget: 0.3,
    minimumSliceTradingDays: 1
  },
  execution: {
    commissionRate: 0.001,
    slippageRate: 0.002,
    sellStampDutyRate: 0.0005,
    maxLeverage: 1.5,
    topK: 20,
    longOnlyWeighting: "rank_equal",
    longOnlyTargetCount: 50,
    maxPositionWeight: 0.05,
    maxParticipationRate: 0.1,
    minListingDays: 60,
    terminalStalePositionPolicy: "reject",
    allowedMarketTypes: [1, 4],
    submissionsEnabled: true,
    hiddenTestEnabled: true,
    maxConcurrentScoring: 2,
    submissionTimeoutSeconds: 60,
    submissionTimeoutEnabled: true,
    longOnly: false
  },
  dataStart: "2021-01-01",
  scoringStart: "2023-01-01",
  scoringEnd: "2025-12-31",
  capital: 1_000_000,
  groupCount: 5,
  industryNeutralization: false,
  longOnlyBenchmark: "hs300",
  longOnlyRiskFreeRate: 0.0175,
  longOnlyMinBetaObservations: 20,
  pricePolicy: "front_adjusted",
  executionPrice: "vwap",
  markPrice: "close",
  rawDataRoot: "new_data",
  learningOutputRoot: "data_releases/learning",
  hiddenOutputRoot: "data_releases/hidden_test",
  learningEnd: "2022-12-31",
  hiddenStart: "2023-01-01",
  hiddenEnd: "2025-12-31",
  engineVersion: "engine-x",
  runtimeRoot: "/tmp/runtime",
  frontendDist: "frontend/dist",
  maxUploadBytes: 10485760,
  scoringTimeoutSeconds: 60,
  settingsHistory: [
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
  ]
};

const dataReleaseState = {
  sourceAvailable: true,
  buildableReleaseNames: ["learning_1", "learning_2", "learning_3"],
  releases: [
    {
      releaseName: "learning_1",
      start: "2010-01-02",
      end: "2015-12-31",
      outputRoot: "data_releases/learning_1",
      status: "ready",
      lastBuiltAt: "2026-07-24T08:00:00+00:00"
    },
    {
      releaseName: "learning_2",
      start: "2015-01-01",
      end: "2020-12-31",
      outputRoot: "data_releases/learning_2",
      status: "missing",
      lastBuiltAt: null
    },
    {
      releaseName: "learning_3",
      start: "2020-01-01",
      end: "2022-12-31",
      outputRoot: "data_releases/learning_3",
      status: "ready",
      lastBuiltAt: "2026-07-24T08:01:00+00:00"
    }
  ],
  job: null
};

const teams = {
  activeTeams: [
    {
      teamId: "team-a",
      teamName: "Alpha",
      displayName: "Alpha",
      submissionCount: 2,
      createdAt: "2026-06-19T10:00:00Z",
      status: "active",
      password: null,
      cohortId: "cohort-hidden",
      cohortName: "Hidden cohort",
      historyVisible: false,
      submissionsEnabled: false
    },
    {
      teamId: "team-c",
      teamName: "Gamma",
      displayName: "Gamma",
      submissionCount: 1,
      createdAt: "2026-06-20T10:00:00Z",
      status: "active",
      password: null,
      cohortId: null,
      cohortName: null,
      historyVisible: true,
      submissionsEnabled: true
    }
  ],
  archivedTeams: [
    {
      teamId: "team-b",
      teamName: "Beta",
      displayName: "Beta",
      submissionCount: 0,
      createdAt: "2026-06-18T10:00:00Z",
      status: "archived",
      password: "temporary",
      cohortId: null,
      cohortName: null,
      historyVisible: true,
      submissionsEnabled: true
    }
  ],
  teams: [],
  cohorts: [
    {
      cohortId: "cohort-hidden",
      name: "Hidden cohort",
      teamIds: ["team-a"],
      historyVisible: false,
      submissionsEnabled: false,
      createdAt: "2026-06-18T09:00:00Z",
      updatedAt: "2026-06-18T09:00:00Z"
    }
  ]
};

const submissions = [
  {
    id: "sub-1",
    submissionNumber: 1,
    submissionLabel: "#1",
    teamId: "team-a",
    teamName: "Alpha",
    type: "python",
    dataTrack: "hidden_test",
    status: "failed",
    stale: true,
    selectable: true,
    score: null,
    filename: "alpha.py",
    submittedAt: "2026-06-19T10:00:00Z",
    finishedAt: "2026-06-19T10:01:00Z",
    rawError: null,
    hasRawError: true,
    configSnapshot: { course: { name: "QuantFish" } },
    filePaths: { strategy_path: "/tmp/alpha.py" }
  },
  {
    id: "sub-2",
    submissionNumber: 2,
    submissionLabel: "#2",
    teamId: "team-b",
    teamName: "Beta",
    type: "python",
    dataTrack: "hidden_test",
    status: "running",
    stale: false,
    selectable: false,
    score: 0.7,
    filename: "beta.py",
    submittedAt: "2026-06-19T10:05:00Z",
    finishedAt: null,
    rawError: null,
    hasRawError: false,
    configSnapshot: null,
    filePaths: { strategy_path: "/tmp/beta.py" }
  }
];

function setupMocks(authenticated = true) {
  (useAdminSession as Mock).mockReturnValue({
    data: { authenticated },
    isLoading: false,
    isError: false,
    refetch: vi.fn()
  });
  (useAdminLogin as Mock).mockReturnValue({ mutate: loginMock, isPending: false });
  (useAdminLogout as Mock).mockReturnValue({ mutate: logoutMock, isPending: false });
  (useAdminSettings as Mock).mockReturnValue({
    data: settings,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  });
  (useAdminDataReleases as Mock).mockReturnValue({
    data: dataReleaseState,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  });
  (useStartAdminDataReleaseBuild as Mock).mockReturnValue({
    mutate: startDataReleaseBuildMock,
    isPending: false,
    error: null
  });
  (useUpdateAdminSettings as Mock).mockReturnValue({
    mutate: updateSettingsMock,
    isPending: false
  });
  (useRevertAdminSettingsHistory as Mock).mockReturnValue({
    mutate: revertSettingsHistoryMock,
    isPending: false
  });
  (useMarkAdminStaleSubmissions as Mock).mockReturnValue({
    mutate: markStaleSubmissionsMock,
    isPending: false
  });
  (useRevertAdminStaleMark as Mock).mockReturnValue({
    mutate: revertStaleMarkMock,
    isPending: false
  });
  (useAdminTeams as Mock).mockReturnValue({
    data: teams,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  });
  (useCreateTeam as Mock).mockReturnValue({ mutate: createTeamMock, isPending: false });
  (useUpdateTeam as Mock).mockReturnValue({ mutate: updateTeamMock, isPending: false });
  (useTeamBulkAction as Mock).mockReturnValue({
    mutate: teamBulkActionMock,
    isPending: false
  });
  (useCreateTeamCohort as Mock).mockReturnValue({
    mutate: createTeamCohortMock,
    isPending: false
  });
  (useUpdateTeamCohort as Mock).mockReturnValue({
    mutate: updateTeamCohortMock,
    isPending: false
  });
  (useDeleteTeamCohort as Mock).mockReturnValue({
    mutate: deleteTeamCohortMock,
    isPending: false
  });
  (useAdminSubmissions as Mock).mockReturnValue({
    data: {
      records: submissions,
      totalCount: 2,
      limit: 25,
      offset: 0,
      hasNext: false
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  });
  (useDeleteAdminSubmissions as Mock).mockReturnValue({
    mutate: deleteSubmissionsMock,
    isPending: false
  });
  (useRerunAdminSubmissions as Mock).mockReturnValue({
    mutate: rerunSubmissionsMock,
    isPending: false
  });
  rerunSubmissionsMock.mockImplementation((_payload, options) => {
    options?.onSuccess?.({
      queued: 1,
      skipped: 0,
      queued_submission_ids: ["sub-1"],
      skipped_submission_ids: []
    });
  });
  viewSourceMock.mockImplementation((_submissionId, options) => {
    options?.onSuccess?.("def alpha_strategy():\n    return 1\n");
  });
  (useAdminSubmissionSource as Mock).mockReturnValue({
    mutate: viewSourceMock,
    isPending: false,
    error: null
  });
  viewRawErrorMock.mockImplementation((_submissionId, options) => {
    options?.onSuccess?.("Traceback raw error");
  });
  (useAdminSubmissionRawError as Mock).mockReturnValue({
    mutate: viewRawErrorMock,
    isPending: false,
    error: null
  });
}

describe("AdminConsoleView", () => {
  it("shows a password login before console access", async () => {
    setupMocks(false);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.type(screen.getByLabelText(/admin password/i), "quantfish-admin");
    await userEvent.click(screen.getByRole("button", { name: /log in/i }));

    expect(loginMock).toHaveBeenCalledWith({ password: "quantfish-admin" });
    expect(screen.queryByRole("heading", { name: /instructor admin/i })).not.toBeInTheDocument();
  });

  it("saves editable dataset and execution settings", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    expect(screen.queryByRole("tab", { name: /^scoring$/i })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));
    await userEvent.clear(screen.getByLabelText(/train start date/i));
    await userEvent.type(screen.getByLabelText(/train start date/i), "2020-01-01");
    expect(screen.getByText(/Training: 2020-01-01 to 2022-12-31/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /save dataset/i }));

    await waitFor(() => {
      expect(updateSettingsMock).toHaveBeenCalledWith(
        {
          dataset: {
            train_start: "2020-01-01",
            train_end: "2022-12-31",
            hidden_test_start: "2023-01-01",
            hidden_test_end: "2025-12-31"
          }
        },
        expect.objectContaining({
          onError: expect.any(Function),
          onSuccess: expect.any(Function)
        })
      );
    });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));
    await userEvent.clear(screen.getByRole("spinbutton", { name: /starting capital/i }));
    await userEvent.type(screen.getByRole("spinbutton", { name: /starting capital/i }), "1500000");
    await userEvent.clear(screen.getByRole("spinbutton", { name: /max leverage/i }));
    await userEvent.type(screen.getByRole("spinbutton", { name: /max leverage/i }), "2.5");
    await userEvent.clear(screen.getByRole("spinbutton", { name: /long-short top\/bottom k/i }));
    await userEvent.type(screen.getByRole("spinbutton", { name: /long-short top\/bottom k/i }), "12");
    await userEvent.click(screen.getByRole("checkbox", { name: /16 ChiNext/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /submissions enabled/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /hidden test track/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /industry neutralization/i }));
    await userEvent.click(screen.getByRole("button", { name: /^long-only$/i }));
    await userEvent.click(screen.getByRole("button", { name: /save execution/i }));
    await waitFor(() => {
      expect(updateSettingsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          backtest: expect.objectContaining({
            capital: 1_500_000,
            industry_neutralization: true,
            long_only_benchmark: "hs300",
            long_only_risk_free_rate: 0.0175,
            long_only_min_beta_observations: 20
          }),
          execution: expect.objectContaining({
            sell_stamp_duty_rate: 0.0005,
            max_leverage: 2.5,
            top_k: null,
            long_only_weighting: "rank_equal",
            long_only_target_count: 50,
            max_position_weight: 0.05,
            max_participation_rate: 0.1,
            min_listing_days: 60,
            terminal_stale_position_policy: "reject",
            allowed_market_types: [1, 4, 16],
            submissions_enabled: false,
            hidden_test_enabled: false,
            long_only: true
          })
        })
      );
    });
  });

  it("confirms selected historical track generation and explains leaderboard impact", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));

    expect(screen.getByRole("heading", { name: /historical track data generation/i })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /learning window 1/i })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: /learning window 2/i })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /learning window 3/i })).not.toBeChecked();
    expect(screen.getByText("data_releases/learning_2")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("checkbox", { name: /learning window 1/i }));
    await userEvent.click(screen.getByRole("button", { name: /generate selected tracks/i }));

    const confirmation = screen.getByRole("dialog", {
      name: /generate these historical tracks/i
    });
    expect(confirmation).toHaveTextContent(/existing completed scores.*become stale/i);
    expect(confirmation).toHaveTextContent(/learning window 1.*2010-01-02 to 2015-12-31/i);
    expect(confirmation).toHaveTextContent(/learning window 2.*2015-01-01 to 2020-12-31/i);
    expect(startDataReleaseBuildMock).not.toHaveBeenCalled();

    await userEvent.click(within(confirmation).getByRole("button", { name: /^cancel$/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(startDataReleaseBuildMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /generate selected tracks/i }));
    await userEvent.click(
      within(screen.getByRole("dialog")).getByRole("button", { name: /start generation/i })
    );
    expect(startDataReleaseBuildMock).toHaveBeenCalledWith({
      release_names: ["learning_1", "learning_2"]
    });
  });

  it("shows overall and per-track progress while generation runs", async () => {
    setupMocks(true);
    (useAdminDataReleases as Mock).mockReturnValue({
      data: {
        ...dataReleaseState,
        job: {
          jobId: "job-1",
          status: "running",
          releaseNames: ["learning_1", "learning_2", "learning_3"],
          progressPercent: 46.7,
          tracks: [
            {
              releaseName: "learning_1",
              status: "completed",
              phase: "completed",
              progressPercent: 100,
              completedDatasets: 12,
              totalDatasets: 12,
              currentDataset: null,
              errorMessage: null
            },
            {
              releaseName: "learning_2",
              status: "running",
              phase: "building",
              progressPercent: 40,
              completedDatasets: 5,
              totalDatasets: 12,
              currentDataset: "stock.daily_returns",
              errorMessage: null
            },
            {
              releaseName: "learning_3",
              status: "queued",
              phase: "queued",
              progressPercent: 0,
              completedDatasets: 0,
              totalDatasets: 0,
              currentDataset: null,
              errorMessage: null
            }
          ],
          createdAt: "2026-07-24T08:00:00+00:00",
          startedAt: "2026-07-24T08:00:01+00:00",
          finishedAt: null,
          currentReleaseName: "learning_2",
          errorMessage: null
        }
      },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn()
    });
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));

    expect(screen.getByRole("progressbar", { name: /overall generation progress/i })).toHaveValue(46.7);
    expect(screen.getByRole("progressbar", { name: /learning window 1.*generation progress/i })).toHaveValue(100);
    expect(screen.getByRole("progressbar", { name: /learning window 2.*generation progress/i })).toHaveValue(40);
    expect(screen.getByRole("progressbar", { name: /learning window 3.*generation progress/i })).toHaveValue(0);
    expect(screen.getByText(/stock\.daily_returns.*5\/12 datasets/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /generation running/i })).toBeDisabled();
  });

  it("lays out execution settings by mode and subsystem", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));

    const headings = [
      "Backtest mode",
      "Shared execution",
      "Long-short settings",
      "Long-only settings",
      "Platform operations"
    ];
    const headingNodes = headings.map((name) => screen.getByRole("heading", { name }));
    expect(headingNodes.map((node) => node.textContent)).toEqual(headings);
    for (let index = 1; index < headingNodes.length; index += 1) {
      expect(
        headingNodes[index - 1].compareDocumentPosition(headingNodes[index]) &
          Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
    }

    expect(screen.getByRole("button", { name: /^long-short$/i })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^long-only$/i })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getAllByText("Active").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Inactive").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/alpha type/i)).not.toBeInTheDocument();
  });

  it("renders execution setting help buttons in setting order", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));

    const helpButtons = screen.getAllByRole("button", { name: /^show help for /i });
    expect(helpButtons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Show help for Backtest mode",
      "Show help for Starting capital",
      "Show help for Commission rate",
      "Show help for Slippage rate",
      "Show help for Sell stamp-duty rate",
      "Show help for Max leverage",
      "Show help for Terminal unpriced-position policy",
      "Show help for Industry neutralization",
      "Show help for MarketType scope",
      "Show help for Long-short top/bottom K",
      "Show help for Long-only weighting",
      "Show help for Long-only target count",
      "Show help for Max position weight",
      "Show help for Max participation rate",
      "Show help for Min listing days",
      "Show help for Long-only benchmark",
      "Show help for Long-only risk-free rate",
      "Show help for Min beta observations",
      "Show help for Submissions enabled",
      "Show help for Hidden test track",
      "Show help for Submission timeout enabled",
      "Show help for Max concurrent scoring",
      "Show help for Submission timeout seconds"
    ]);
  });

  it("shows execution help content on hover and keyboard focus", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));
    await userEvent.hover(screen.getByRole("button", { name: /show help for max participation rate/i }));

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent(/Limits each day's executed trade size against traded value/i);
    expect(tooltip).toHaveTextContent(/Unit: fraction of daily traded value/i);
    expect(tooltip).toHaveTextContent(/cap = rate \* dnvaltrd \/ capital/i);

    await userEvent.unhover(screen.getByRole("button", { name: /show help for max participation rate/i }));
    fireEvent.focus(screen.getByRole("button", { name: /show help for backtest mode/i }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(/mode = long_only \? "longonly" : "longshort"/i);
    fireEvent.blur(screen.getByRole("button", { name: /show help for backtest mode/i }));
    fireEvent.focus(screen.getByRole("button", { name: /show help for long-only risk-free rate/i }));
    expect(screen.getByRole("tooltip")).toHaveTextContent(/annual risk-free rate/i);
    expect(screen.getByRole("tooltip")).toHaveTextContent(/rf_daily = risk_free_rate \/ 252/i);
  });

  it("renders translated execution help content", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: ChineseWrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^执行$/i }));
    await userEvent.hover(screen.getByRole("button", { name: /显示最大成交参与率的说明/i }));

    const tooltip = screen.getByRole("tooltip");
    expect(tooltip).toHaveTextContent(/限制每天实际成交的仓位变化/i);
    expect(tooltip).toHaveTextContent(/单位：每日成交额比例/i);
    expect(tooltip).toHaveTextContent(/cap = rate \* dnvaltrd \/ capital/i);
  });

  it("shows dataset processing while changed split saves are pending", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));
    await userEvent.clear(screen.getByLabelText(/train start date/i));
    await userEvent.type(screen.getByLabelText(/train start date/i), "2020-01-01");
    await userEvent.click(screen.getByRole("button", { name: /save dataset/i }));

    const status = screen.getByRole("status", { name: /dataset split processing/i });
    expect(status).toHaveTextContent(/dataset split update in progress/i);
    expect(status).toHaveTextContent(/large data refresh is still running/i);
  });

  it("shows dataset completion after the changed split save succeeds", async () => {
    setupMocks(true);
    updateSettingsMock.mockImplementationOnce((_payload, options) => {
      options?.onSuccess?.();
    });
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));
    await userEvent.clear(screen.getByLabelText(/train start date/i));
    await userEvent.type(screen.getByLabelText(/train start date/i), "2020-01-01");
    await userEvent.click(screen.getByRole("button", { name: /save dataset/i }));

    expect(screen.getByRole("status", { name: /dataset split saved/i })).toHaveTextContent(
      /dataset split update complete/i
    );
  });

  it("shows dataset failure after the changed split save fails", async () => {
    setupMocks(true);
    updateSettingsMock.mockImplementationOnce((_payload, options) => {
      options?.onError?.(new Error("refresh failed"));
    });
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));
    await userEvent.clear(screen.getByLabelText(/train start date/i));
    await userEvent.type(screen.getByLabelText(/train start date/i), "2020-01-01");
    await userEvent.click(screen.getByRole("button", { name: /save dataset/i }));

    const status = screen.getByRole("status", { name: /dataset split failed/i });
    expect(status).toHaveTextContent(/dataset split update failed/i);
    await userEvent.click(screen.getByRole("button", { name: /close/i }));
    expect(screen.queryByRole("status", { name: /dataset split failed/i })).not.toBeInTheDocument();
  });

  it("does not show dataset processing when saved split dates are unchanged", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /dataset split/i }));
    await userEvent.click(screen.getByRole("button", { name: /save dataset/i }));

    expect(updateSettingsMock).toHaveBeenCalledWith({
      dataset: {
        train_start: "2021-01-01",
        train_end: "2022-12-31",
        hidden_test_start: "2023-01-01",
        hidden_test_end: "2025-12-31"
      }
    });
    expect(screen.queryByRole("status", { name: /dataset split processing/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("status", { name: /dataset split saved/i })).not.toBeInTheDocument();
  });

  it("marks stale submissions and restores individual admin change history entries", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));

    expect(screen.getByRole("heading", { name: /admin change history/i })).toBeInTheDocument();
    expect(screen.getByText(/execution.max_leverage/i)).toBeInTheDocument();
    expect(screen.queryByText(/abcdef12/i)).not.toBeInTheDocument();
    expect(screen.getByText(/2 submissions/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /mark previous completed submissions stale/i }));
    expect(markStaleSubmissionsMock).not.toHaveBeenCalled();
    const confirmDialog = screen.getByRole("dialog", { name: /confirm stale mark/i });
    expect(
      within(confirmDialog).getByText(/completed submissions that exist right now/i)
    ).toBeInTheDocument();
    markStaleSubmissionsMock.mockImplementationOnce((_variables, options) => {
      options?.onSuccess?.();
    });
    await userEvent.click(within(confirmDialog).getByRole("button", { name: /^mark stale$/i }));
    expect(markStaleSubmissionsMock).toHaveBeenCalledWith(
      undefined,
      expect.objectContaining({ onSuccess: expect.any(Function) })
    );
    expect(screen.getByRole("status")).toHaveTextContent(/marked successfully/i);
    await userEvent.click(screen.getByRole("button", { name: /restore settings hist-1/i }));
    expect(revertSettingsHistoryMock).toHaveBeenCalledWith("hist-1");
    await userEvent.click(screen.getByRole("button", { name: /revert stale mark stale-1/i }));
    expect(revertStaleMarkMock).toHaveBeenCalledWith("stale-1");
  });

  it("saves a blank top k as unlimited", async () => {
    setupMocks(true);
    (useAdminSettings as Mock).mockReturnValue({
      data: { ...settings, execution: { ...settings.execution, topK: 100 } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn()
    });
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));
    await userEvent.clear(screen.getByRole("spinbutton", { name: /long-short top\/bottom k/i }));
    await userEvent.click(screen.getByRole("button", { name: /save execution/i }));

    expect(updateSettingsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        execution: expect.objectContaining({ top_k: null })
      })
    );
  });

  it("preserves long-short top k when long-short mode is active", async () => {
    setupMocks(true);
    (useAdminSettings as Mock).mockReturnValue({
      data: { ...settings, execution: { ...settings.execution, topK: 33, longOnly: false } },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn()
    });
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));
    await userEvent.click(screen.getByRole("button", { name: /save execution/i }));

    expect(updateSettingsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        execution: expect.objectContaining({ long_only: false, top_k: 33 })
      })
    );
  });

  it("requires at least one market type before saving execution settings", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^execution$/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /1 Shanghai A-share/i }));
    await userEvent.click(screen.getByRole("checkbox", { name: /4 Shenzhen A-share/i }));

    expect(screen.getByRole("button", { name: /save execution/i })).toBeDisabled();

    await userEvent.click(screen.getByRole("checkbox", { name: /4 Shenzhen A-share/i }));
    expect(screen.getByRole("button", { name: /save execution/i })).not.toBeDisabled();
  });

  it("does not render placeholder toolbox or save course controls", () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    expect(screen.queryByRole("tab", { name: /toolbox/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /^messages$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save course/i })).not.toBeInTheDocument();
  });

  it("creates edits archives restores and deletes teams", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^teams$/i }));
    await userEvent.type(screen.getByLabelText(/team name/i), "Gamma");
    await userEvent.type(screen.getByLabelText(/^password$/i), "secret");
    await userEvent.click(screen.getByRole("button", { name: /create team/i }));
    expect(createTeamMock).toHaveBeenCalledWith({ team_name: "Gamma", password: "secret" });

    const alphaRow = screen.getByRole("row", { name: /Alpha/i });
    await userEvent.click(within(alphaRow).getByRole("button", { name: /edit Alpha/i }));
    const editName = within(alphaRow).getByLabelText(/edit team name for Alpha/i);
    await userEvent.clear(editName);
    await userEvent.type(editName, "Alpha Renamed");
    await userEvent.click(screen.getByRole("button", { name: /save team/i }));
    expect(updateTeamMock).toHaveBeenCalledWith({
      teamId: "team-a",
      team: { team_name: "Alpha Renamed" }
    });

    await userEvent.click(within(alphaRow).getByLabelText(/select Alpha/i));
    await userEvent.click(screen.getByRole("button", { name: /archive selected/i }));
    expect(teamBulkActionMock).toHaveBeenCalledWith({
      team_ids: ["team-a"],
      action: "archive"
    });

    const betaRow = screen.getByRole("row", { name: /Beta/i });
    expect(within(betaRow).getByText(/archived/i)).toBeInTheDocument();
    await userEvent.click(within(betaRow).getByRole("button", { name: /copy password for Beta/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("temporary");
  });

  it("groups active teams by cohort with ungrouped teams last", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^teams$/i }));

    const activeTeamsTable = screen.getByRole("table", { name: /active teams/i });
    expect(within(activeTeamsTable).getByRole("row", { name: /Hidden cohort 1 team/i })).toBeInTheDocument();
    expect(within(activeTeamsTable).getByRole("row", { name: /Ungrouped teams 1 team/i })).toBeInTheDocument();

    const activeRows = within(activeTeamsTable).getAllByRole("row").map((row) => row.textContent ?? "");
    expect(activeRows.findIndex((text) => text.includes("Hidden cohort"))).toBeLessThan(
      activeRows.findIndex((text) => text.includes("Ungrouped teams"))
    );
    expect(activeRows.findIndex((text) => text.includes("Alpha"))).toBeLessThan(
      activeRows.findIndex((text) => text.includes("Gamma"))
    );

    const alphaRow = within(activeTeamsTable).getByRole("row", { name: /Alpha/i });
    await userEvent.click(within(alphaRow).getByLabelText(/select Alpha/i));
    await userEvent.click(screen.getByRole("button", { name: /archive selected/i }));
    expect(teamBulkActionMock).toHaveBeenCalledWith({
      team_ids: ["team-a"],
      action: "archive"
    });
  });

  it("manages team cohorts and links to the dedicated cohort history", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^teams$/i }));
    await userEvent.type(screen.getByLabelText(/cohort name/i), "Table 1");
    await userEvent.click(screen.getByRole("button", { name: /create cohort/i }));
    expect(createTeamCohortMock).toHaveBeenCalledWith({
      name: "Table 1",
      team_ids: [],
      history_visible: true,
      submissions_enabled: true
    });

    const cohortTable = screen.getByRole("table", { name: /team cohorts/i });
    const cohortRow = within(cohortTable).getByRole("row", { name: /Hidden cohort/i });
    await userEvent.click(within(cohortRow).getByLabelText(/show history for Hidden cohort/i));
    expect(updateTeamCohortMock).toHaveBeenCalledWith({
      cohortId: "cohort-hidden",
      cohort: { history_visible: true }
    });

    await userEvent.click(within(cohortRow).getByLabelText(/enable submissions for Hidden cohort/i));
    expect(updateTeamCohortMock).toHaveBeenLastCalledWith({
      cohortId: "cohort-hidden",
      cohort: { submissions_enabled: true }
    });

    expect(within(cohortRow).getByLabelText(/include Alpha in Hidden cohort/i)).toBeChecked();
    await userEvent.click(within(cohortRow).getByLabelText(/include Beta in Hidden cohort/i));
    expect(updateTeamCohortMock).toHaveBeenLastCalledWith({
      cohortId: "cohort-hidden",
      cohort: { team_ids: ["team-a", "team-b"] }
    });

    const link = within(cohortRow).getByRole("link", {
      name: /view submissions for Hidden cohort/i
    });
    expect(link).toHaveAttribute("href", "/admin/cohorts/cohort-hidden/submissions");

    await userEvent.click(within(cohortRow).getByRole("button", { name: /delete Hidden cohort/i }));
    expect(deleteTeamCohortMock).toHaveBeenCalledWith("cohort-hidden");
  });

  it("filters submissions, shows raw errors, and protects active deletion", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^submissions$/i }));
    expect(useAdminSubmissions).toHaveBeenLastCalledWith(true, {
      limit: 25,
      offset: 0,
      search: "",
      status: "all",
      sortBy: "submitted_at",
      sortDir: "desc"
    });

    await userEvent.type(screen.getByRole("searchbox", { name: /search submissions/i }), "alpha");
    await waitFor(() => {
      expect(useAdminSubmissions).toHaveBeenLastCalledWith(
        true,
        expect.objectContaining({ search: "alpha", offset: 0 })
      );
    });
    expect(screen.queryByRole("columnheader", { name: /^score$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("row", { name: /#1/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /view raw error for #1/i }));
    expect(viewRawErrorMock).toHaveBeenCalledWith("sub-1", expect.any(Object));
    const rawErrorDialog = screen.getByRole("dialog", { name: /raw error for #1/i });
    expect(rawErrorDialog).toHaveAttribute("aria-modal", "true");
    expect(rawErrorDialog).toHaveTextContent("Traceback raw error");
    await userEvent.click(within(rawErrorDialog).getByRole("button", { name: /cancel/i }));

    await userEvent.click(screen.getByLabelText(/select #1/i));
    await userEvent.click(screen.getByRole("button", { name: /delete selected/i }));
    expect(deleteSubmissionsMock).toHaveBeenCalledWith({
      submission_ids: ["sub-1"],
      force: false
    });

    await userEvent.clear(screen.getByRole("searchbox", { name: /search submissions/i }));
    expect(screen.getByText(/1 active/i)).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/allow active deletion/i));
    await userEvent.click(screen.getByLabelText(/select #2/i));
    await userEvent.click(screen.getByRole("button", { name: /delete selected/i }));
    expect(deleteSubmissionsMock).toHaveBeenLastCalledWith({
      submission_ids: ["sub-2"],
      force: true
    });
  });

  it("reruns selected and all submissions from the admin submissions tab", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^submissions$/i }));
    await userEvent.click(screen.getByLabelText(/select #1/i));
    await userEvent.click(screen.getByRole("button", { name: /rerun selected/i }));

    expect(rerunSubmissionsMock).toHaveBeenCalledWith(
      {
        scope: "selected",
        submission_ids: ["sub-1"]
      },
      expect.any(Object)
    );
    expect(screen.getByText(/1 queued, 0 skipped/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^rerun all$/i }));
    const dialog = screen.getByRole("dialog", { name: /rerun all submissions/i });
    await userEvent.click(within(dialog).getByRole("button", { name: /confirm rerun all/i }));

    expect(rerunSubmissionsMock).toHaveBeenLastCalledWith({ scope: "all" }, expect.any(Object));
  });

  it("opens uploaded Python source from admin submissions", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^submissions$/i }));
    await userEvent.click(screen.getByRole("button", { name: /view code for #1/i }));

    expect(viewSourceMock).toHaveBeenCalledWith("sub-1", expect.any(Object));
    const sourceDialog = screen.getByRole("dialog", { name: /source code for #1/i });
    expect(sourceDialog).toHaveAttribute("aria-modal", "true");
    expect(sourceDialog).toHaveTextContent("def alpha_strategy");
    const highlightedCode = within(sourceDialog).getByLabelText(/python source code/i);
    expect(highlightedCode).toHaveAttribute("data-language", "python");
    expect(within(highlightedCode).getByText("def")).toHaveAttribute("data-token", "keyword");
    expect(within(highlightedCode).getByText("alpha_strategy")).toHaveAttribute("data-token", "function");
  });

  it("renders the admin submissions tab in Chinese", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: ChineseWrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^提交$/i }));

    expect(screen.getByRole("searchbox", { name: /搜索提交/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "编号" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "轨道" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "操作" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /查看 #1 的代码/i })).toBeInTheDocument();
    expect(screen.getAllByText("隐藏测试")).toHaveLength(2);
  });

  it("distinguishes team and cohort wording in the Chinese teams tab", async () => {
    setupMocks(true);
    render(<AdminConsoleView />, { wrapper: ChineseWrapper });

    await userEvent.click(screen.getByRole("tab", { name: /^队伍$/i }));

    expect(screen.getByRole("table", { name: /活跃队伍/i })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: /队伍分组/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/分组名称/i)).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /未分组队伍 1 个队伍/i })).toBeInTheDocument();
    expect(screen.queryByText("团队分组")).not.toBeInTheDocument();
  });
});
