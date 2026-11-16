import { LoaderCircle } from "lucide-react";
import { lazy, Suspense, type ReactNode } from "react";
import type { RouteObject } from "react-router-dom";

import { App } from "./app/App";
import { useI18n } from "./shared/i18n";
import { ErrorState } from "./shared/ui/ErrorState/ErrorState";
import styles from "./routes.module.css";

const AdminConsoleView = lazy(() => import("./features/admin").then((module) => ({ default: module.AdminConsoleView })));
const AdminCohortSubmissionsView = lazy(() =>
  import("./features/admin").then((module) => ({ default: module.AdminCohortSubmissionsView }))
);
const CompareView = lazy(() => import("./features/compare").then((module) => ({ default: module.CompareView })));
const DashboardView = lazy(() => import("./features/dashboard").then((module) => ({ default: module.DashboardView })));
const HistoryView = lazy(() => import("./features/history").then((module) => ({ default: module.HistoryView })));
const LeaderboardView = lazy(() => import("./features/leaderboard").then((module) => ({ default: module.LeaderboardView })));
const LoginView = lazy(() => import("./features/session").then((module) => ({ default: module.LoginView })));
const SubmissionDetailView = lazy(() =>
  import("./features/submission-detail").then((module) => ({ default: module.SubmissionDetailView }))
);
const SubmissionView = lazy(() => import("./features/submissions").then((module) => ({ default: module.SubmissionView })));

function RouteLoading() {
  const { t } = useI18n();
  return (
    <div className={styles.routePlaceholder} role="status" aria-live="polite">
      <LoaderCircle aria-hidden="true" className={styles.spinner} />
      <span>{t("common.loading")}</span>
    </div>
  );
}

function RouteError() {
  const { t } = useI18n();
  return (
    <div className={styles.errorWrapper}>
      <ErrorState
        title={t("common.error")}
        onRetry={() => window.location.reload()}
      />
    </div>
  );
}

function RouteElement({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<RouteLoading />}>
      {children}
    </Suspense>
  );
}

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <App />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <RouteElement><DashboardView /></RouteElement>, errorElement: <RouteError /> },
      { path: "login", element: <RouteElement><LoginView /></RouteElement>, errorElement: <RouteError /> },
      { path: "submit", element: <RouteElement><SubmissionView /></RouteElement>, errorElement: <RouteError /> },
      { path: "leaderboard", element: <RouteElement><LeaderboardView /></RouteElement>, errorElement: <RouteError /> },
      { path: "history", element: <RouteElement><HistoryView /></RouteElement>, errorElement: <RouteError /> },
      { path: "submissions/:submissionId", element: <RouteElement><SubmissionDetailView /></RouteElement>, errorElement: <RouteError /> },
      { path: "compare", element: <RouteElement><CompareView /></RouteElement>, errorElement: <RouteError /> },
      { path: "admin", element: <RouteElement><AdminConsoleView /></RouteElement>, errorElement: <RouteError /> },
      { path: "admin/cohorts/:cohortId/submissions", element: <RouteElement><AdminCohortSubmissionsView /></RouteElement>, errorElement: <RouteError /> }
    ]
  }
];
