import { Loader2, LogIn, UploadCloud, UserRound } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { useI18n } from "../../shared/i18n";
import { Button } from "../../shared/ui/Button/Button";
import { Card } from "../../shared/ui/Card/Card";
import { ErrorState } from "../../shared/ui/ErrorState/ErrorState";
import { PasswordInput } from "../../shared/ui/PasswordInput/PasswordInput";
import { useParticipantLogin, useParticipantSession } from "./model";
import styles from "./view.module.css";

export function LoginView() {
  const { t } = useI18n();
  const [teamName, setTeamName] = useState("");
  const [password, setPassword] = useState("");
  const login = useParticipantLogin();
  const session = useParticipantSession();
  const activeSession = login.data?.authenticated
    ? login.data
    : session.data?.authenticated
      ? session.data
      : null;
  const canSubmit = teamName.trim().length > 0 && password.length > 0 && !login.isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    login.mutate({ team_name: teamName.trim(), password });
  }

  return (
    <section aria-labelledby="login-title" className={styles.view}>
      <header className={styles.header}>
        <p className={styles.muted}>{t("session.eyebrow")}</p>
        <h1 id="login-title">{t("session.title")}</h1>
        <p>{t("session.description")}</p>
      </header>

      <Card className={styles.card} header={<h2>{t("session.cardTitle")}</h2>}>
        {activeSession?.team_name ? (
          <div className={styles.activeSession}>
            <strong>
              <UserRound aria-hidden="true" size={18} />
              {t("session.loggedInAs", { team: activeSession.team_name })}
            </strong>
            <Link className={styles.submitLink} to="/submit">
              <UploadCloud aria-hidden="true" size={17} />
              {t("session.submitStrategy")}
            </Link>
          </div>
        ) : (
          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.field}>
              <label htmlFor="participant-team-name">{t("session.teamNameLabel")}</label>
              <input
                autoComplete="username"
                className={styles.input}
                id="participant-team-name"
                name="teamName"
                onChange={(event) => setTeamName(event.target.value)}
                required
                value={teamName}
              />
            </div>
            <div className={styles.field}>
              <label htmlFor="participant-team-password">{t("session.passwordLabel")}</label>
              <PasswordInput
                autoComplete="current-password"
                id="participant-team-password"
                inputClassName={styles.input}
                name="password"
                onChange={(event) => setPassword(event.target.value)}
                required
                value={password}
              />
            </div>
            <p className={styles.formHint} id="participant-login-hint">
              {t("session.loginHint")}
            </p>
            <Button aria-describedby="participant-login-hint" disabled={!canSubmit} type="submit">
              {login.isPending ? (
                <Loader2 aria-hidden="true" className={styles.spinner} size={17} />
              ) : (
                <LogIn aria-hidden="true" size={17} />
              )}
              {login.isPending ? t("session.loggingIn") : t("session.login")}
            </Button>
          </form>
        )}

        {login.error ? (
          <div className={styles.error}>
            <ErrorState message={login.error.message} title={t("session.loginErrorTitle")} />
          </div>
        ) : null}
      </Card>
    </section>
  );
}
