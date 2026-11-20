import { Navigate, type RouteObject } from "react-router-dom";

import { App } from "./app/App";
import {
  AdminConsoleView,
  AdminCohortSubmissionsView,
  CompareView,
  DashboardView,
  HistoryView,
  LandingView,
  LeaderboardView,
  LoginView,
  SubmissionDetailView,
  SubmissionView
} from "./app/lazyViews";
import { RouteElement, RouteError } from "./app/routeElements";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <RouteElement><LandingView /></RouteElement>,
    errorElement: <RouteError />
  },
  {
    element: <App />,
    errorElement: <RouteError />,
    children: [
      { path: "dashboard", element: <RouteElement><DashboardView /></RouteElement>, errorElement: <RouteError /> },
      { path: "login", element: <RouteElement><LoginView /></RouteElement>, errorElement: <RouteError /> },
      { path: "submit", element: <RouteElement><SubmissionView /></RouteElement>, errorElement: <RouteError /> },
      { path: "leaderboard", element: <RouteElement><LeaderboardView /></RouteElement>, errorElement: <RouteError /> },
      { path: "history", element: <RouteElement><HistoryView /></RouteElement>, errorElement: <RouteError /> },
      { path: "submissions/:submissionId", element: <RouteElement><SubmissionDetailView /></RouteElement>, errorElement: <RouteError /> },
      { path: "compare", element: <RouteElement><CompareView /></RouteElement>, errorElement: <RouteError /> },
      { path: "admin", element: <RouteElement><AdminConsoleView /></RouteElement>, errorElement: <RouteError /> },
      { path: "admin/cohorts/:cohortId/submissions", element: <RouteElement><AdminCohortSubmissionsView /></RouteElement>, errorElement: <RouteError /> },
      { path: "*", element: <Navigate replace to="/" /> }
    ]
  }
];
