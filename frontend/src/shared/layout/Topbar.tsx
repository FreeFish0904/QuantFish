import { LoaderCircle, LogIn, LogOut, Moon, Sun, UserRound } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "../i18n";
import { useTheme } from "../theme/ThemeContext";
import styles from "./Layout.module.css";

type ParticipantSession = {
  authenticated: boolean;
  team_name?: string | null;
};

export function Topbar({
  language,
  logoutPending,
  onLogout,
  onToggleLanguage,
  participantSession,
  sessionLoading
}: {
  language: "EN" | "中";
  logoutPending: boolean;
  onLogout: () => void;
  onToggleLanguage: () => void;
  participantSession?: ParticipantSession;
  sessionLoading: boolean;
}) {
  const { t } = useI18n();
  const { cycleTheme, resolvedTheme, theme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const themeLabel =
    theme === "system" ? t("common.themeSystem") : isDark ? t("common.themeDark") : t("common.themeLight");
  const loggedIn = participantSession?.authenticated === true;
  const teamName = participantSession?.team_name ?? "";

  return (
    <header className={styles.topbar}>
      <div>
        <p className={styles.eyebrow}>{t("brand.eyebrow")}</p>
        <h1 className={styles.pageTitle}>{t("brand.pageTitle")}</h1>
      </div>
      <div className={styles.actions}>
        <span className={styles.livePill}>
          <span aria-hidden="true" className={styles.pulseDot} />
          {t("common.live")}
        </span>
        <div
          className={styles.accountBox}
          data-authenticated={loggedIn ? "true" : "false"}
          role="group"
          aria-label={t("session.accountStatus")}
        >
          <span className={styles.accountIdentity}>
            {sessionLoading ? (
              <LoaderCircle aria-hidden="true" className={styles.spinner} size={17} />
            ) : (
              <UserRound aria-hidden="true" size={17} />
            )}
            <span className={styles.accountText}>
              {loggedIn
                ? t("session.loggedInAs", { team: teamName })
                : sessionLoading
                  ? t("common.loading")
                  : t("session.notLoggedIn")}
            </span>
          </span>
          {loggedIn ? (
            <button
              className={styles.iconButton}
              disabled={logoutPending}
              type="button"
              aria-label={t("session.logout")}
              title={t("session.logout")}
              onClick={onLogout}
            >
              <LogOut aria-hidden="true" size={17} />
            </button>
          ) : (
            <Link className={styles.loginLink} to="/login">
              <LogIn aria-hidden="true" size={16} />
              {t("session.login")}
            </Link>
          )}
        </div>
        <button
          className={styles.iconButton}
          type="button"
          aria-label={`${t("common.toggleTheme")} (${themeLabel})`}
          title={`${t("common.toggleTheme")} (${themeLabel})`}
          onClick={cycleTheme}
        >
          {isDark ? <Moon aria-hidden="true" size={18} /> : <Sun aria-hidden="true" size={18} />}
        </button>
        <button
          className={styles.languageToggle}
          type="button"
          aria-label={t("common.toggleLanguage")}
          onClick={onToggleLanguage}
        >
          {language}
        </button>
      </div>
    </header>
  );
}
