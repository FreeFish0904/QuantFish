import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type Mock, beforeEach, describe, expect, it, vi } from "vitest";

import { I18nProvider } from "../../shared/i18n";
import { AdminCohortSubmissionsView } from "./cohortSubmissionsView";

vi.mock("react-router-dom", () => ({
  Link: ({ children, to }: { children: React.ReactNode; to: string }) => <a href={to}>{children}</a>,
  useParams: () => ({ cohortId: "cohort-hidden" })
}));

vi.mock("./model", () => ({
  useAdminSession: vi.fn(),
  useAdminTeams: vi.fn(),
  useAdminCohortSubmissions: vi.fn(),
  useAdminCohortSubmissionSource: vi.fn(),
  useAdminCohortSubmissionRawError: vi.fn(),
  useAdminSubmissionSource: vi.fn(),
  useAdminSubmissionRawError: vi.fn(),
  useDeleteAdminSubmissions: vi.fn(),
  useRerunAdminCohortSubmissions: vi.fn()
}));

import {
  useAdminCohortSubmissionRawError,
  useAdminCohortSubmissions,
  useAdminCohortSubmissionSource,
  useAdminSession,
  useAdminSubmissionRawError,
  useAdminSubmissionSource,
  useDeleteAdminSubmissions,
  useRerunAdminCohortSubmissions,
  useAdminTeams
} from "./model";

const rerunCohortSubmissionsMock = vi.fn();

function Wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });
  return (
    <I18nProvider defaultLanguage="en">
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </I18nProvider>
  );
}

const teams = {
  activeTeams: [
    {
      teamId: "team-a",
      teamName: "Alpha",
      displayName: "Alpha",
      submissionCount: 1,
      createdAt: "2026-06-19T10:00:00Z",
      status: "active",
      password: null,
      cohortId: "cohort-hidden",
      cohortName: "Hidden cohort",
      historyVisible: false,
      submissionsEnabled: false
    }
  ],
  archivedTeams: [],
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

const cohortSubmissions = {
  records: [
    {
      id: "hidden-alpha",
      submissionNumber: 1,
      submissionLabel: "#1",
      teamId: "team-a",
      teamName: "Alpha",
      type: "python",
      dataTrack: "hidden_test",
      status: "completed",
      stale: false,
      selectable: true,
      score: 1.2,
      filename: "alpha.py",
      submittedAt: "2026-06-19T10:00:00Z",
      finishedAt: "2026-06-19T10:01:00Z",
      rawError: null,
      hasRawError: false,
      configSnapshot: null,
      filePaths: { strategy_path: "/tmp/alpha.py" }
    }
  ],
  totalCount: 1,
  limit: 25,
  offset: 0,
  hasNext: false
};

beforeEach(() => {
  vi.clearAllMocks();
  (useAdminSession as Mock).mockReturnValue({
    data: { authenticated: true },
    isLoading: false,
    isError: false,
    error: null
  });
  (useAdminTeams as Mock).mockReturnValue({
    data: teams,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  });
  (useAdminCohortSubmissions as Mock).mockReturnValue({
    data: cohortSubmissions,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn()
  });
  (useAdminCohortSubmissionSource as Mock).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null
  });
  (useAdminCohortSubmissionRawError as Mock).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null
  });
  (useAdminSubmissionSource as Mock).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null
  });
  (useAdminSubmissionRawError as Mock).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null
  });
  (useDeleteAdminSubmissions as Mock).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null
  });
  (useRerunAdminCohortSubmissions as Mock).mockReturnValue({
    mutate: rerunCohortSubmissionsMock,
    isPending: false,
    error: null
  });
  rerunCohortSubmissionsMock.mockImplementation((_payload, options) => {
    options?.onSuccess?.({
      queued: 1,
      skipped: 0,
      queued_submission_ids: ["hidden-alpha"],
      skipped_submission_ids: []
    });
  });
});

describe("AdminCohortSubmissionsView", () => {
  it("renders the dedicated hidden cohort submission history", () => {
    render(<AdminCohortSubmissionsView />, { wrapper: Wrapper });

    expect(screen.getByRole("heading", { name: /Hidden cohort submissions/i })).toBeInTheDocument();
    expect(screen.getByText(/Hidden from normal history/i)).toBeInTheDocument();
    expect(screen.getByText(/1 team selected/i)).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /#1/i })).toBeInTheDocument();
    expect(useAdminCohortSubmissions).toHaveBeenCalledWith(
      true,
      "cohort-hidden",
      expect.objectContaining({ limit: 25, offset: 0 })
    );
  });

  it("reruns selected and all submissions in the cohort context", async () => {
    render(<AdminCohortSubmissionsView />, { wrapper: Wrapper });

    await userEvent.click(screen.getByLabelText(/select #1/i));
    await userEvent.click(screen.getByRole("button", { name: /rerun selected/i }));

    expect(useRerunAdminCohortSubmissions).toHaveBeenCalledWith("cohort-hidden");
    expect(rerunCohortSubmissionsMock).toHaveBeenCalledWith(
      {
        scope: "selected",
        submission_ids: ["hidden-alpha"]
      },
      expect.any(Object)
    );
    expect(screen.getByText(/1 queued, 0 skipped/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^rerun all$/i }));
    const dialog = screen.getByRole("dialog", { name: /rerun all submissions/i });
    await userEvent.click(screen.getByRole("button", { name: /confirm rerun all/i }));

    expect(dialog).toHaveTextContent("This queues every completed or failed submission in this admin context.");
    expect(rerunCohortSubmissionsMock).toHaveBeenLastCalledWith({ scope: "all" }, expect.any(Object));
  });
});
