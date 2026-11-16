import {
  Gauge,
  GitCompare,
  History,
  Settings,
  Trophy,
  UploadCloud
} from "lucide-react";

import type { NavItem } from "./NavButton";

export const navItems: NavItem[] = [
  { key: "dashboard", labelKey: "nav.dashboard", shortLabelKey: "nav.dashboardShort", icon: Gauge, href: "/" },
  { key: "submit", labelKey: "nav.submit", shortLabelKey: "nav.submitShort", icon: UploadCloud, href: "/submit" },
  { key: "leaderboard", labelKey: "nav.leaderboard", shortLabelKey: "nav.leaderboardShort", icon: Trophy, href: "/leaderboard" },
  { key: "history", labelKey: "nav.history", shortLabelKey: "nav.historyShort", icon: History, href: "/history" },
  { key: "compare", labelKey: "nav.compare", shortLabelKey: "nav.compareShort", icon: GitCompare, href: "/compare" },
  { key: "admin", labelKey: "nav.admin", shortLabelKey: "nav.adminShort", icon: Settings, href: "/admin" }
];
