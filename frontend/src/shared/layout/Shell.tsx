import { useState, type ReactNode } from "react";

import { useParticipantLogout, useParticipantSession } from "../../features/session/model";
import { useI18n } from "../i18n";
import { useTheme } from "../theme";
import { MobileNav } from "./MobileNav";
import { Sidebar } from "./Sidebar";
import styles from "./Layout.module.css";
import { Topbar } from "./Topbar";

export function Shell({ children }: { children: ReactNode }) {
  const { language, setLanguage } = useI18n();
  const { resolvedTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const participantSession = useParticipantSession();
  const participantLogout = useParticipantLogout();

  return (
    <div className={styles.shell} data-theme={resolvedTheme}>
      <Sidebar collapsed={collapsed} onToggleCollapse={() => setCollapsed((v) => !v)} />
      <div className={styles.workspace}>
        <Topbar
          language={language === "zh" ? "中" : "EN"}
          logoutPending={participantLogout.isPending}
          onToggleLanguage={() => setLanguage(language === "en" ? "zh" : "en")}
          onLogout={() => participantLogout.mutate()}
          participantSession={participantSession.data}
          sessionLoading={participantSession.isLoading}
        />
        <main className={styles.main}>{children}</main>
      </div>
      <MobileNav />
    </div>
  );
}
