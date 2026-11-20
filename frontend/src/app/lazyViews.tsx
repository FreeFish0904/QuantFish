import { lazy } from "react";

// Route-level code splitting lives in its own module so `routes.tsx` stays a
// plain data module. A file that mixes component and non-component exports
// breaks React Fast Refresh (`react-refresh/only-export-components`).
export const AdminConsoleView = lazy(() =>
  import("../features/admin").then((module) => ({ default: module.AdminConsoleView }))
);
export const AdminCohortSubmissionsView = lazy(() =>
  import("../features/admin").then((module) => ({ default: module.AdminCohortSubmissionsView }))
);
export const CompareView = lazy(() =>
  import("../features/compare").then((module) => ({ default: module.CompareView }))
);
export const DashboardView = lazy(() =>
  import("../features/dashboard").then((module) => ({ default: module.DashboardView }))
);
export const HistoryView = lazy(() =>
  import("../features/history").then((module) => ({ default: module.HistoryView }))
);
export const LandingView = lazy(() =>
  import("../features/landing").then((module) => ({ default: module.LandingView }))
);
export const LeaderboardView = lazy(() =>
  import("../features/leaderboard").then((module) => ({ default: module.LeaderboardView }))
);
export const LoginView = lazy(() =>
  import("../features/session").then((module) => ({ default: module.LoginView }))
);
export const SubmissionDetailView = lazy(() =>
  import("../features/submission-detail").then((module) => ({ default: module.SubmissionDetailView }))
);
export const SubmissionView = lazy(() =>
  import("../features/submissions").then((module) => ({ default: module.SubmissionView }))
);
