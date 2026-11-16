import { Archive, Copy, Eye, EyeOff, RotateCcw, Save, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { useI18n } from "../../../shared/i18n";
import { Button } from "../../../shared/ui/Button/Button";
import { PasswordInput } from "../../../shared/ui/PasswordInput/PasswordInput";
import {
  useCreateTeam,
  useCreateTeamCohort,
  useDeleteTeamCohort,
  useTeamBulkAction,
  useUpdateTeamCohort,
  useUpdateTeam,
  type TeamCollections,
  type TeamCohortRecord,
  type TeamRecord
} from "../model";
import styles from "./Panels.module.css";

type CreateTeamPayload = {
  team_name: string;
  password: string;
};

type TeamUpdatePayload = {
  team_name?: string;
  password?: string;
};

type TeamBulkActionPayload = {
  team_ids: string[];
  action: string;
};

type CreateTeamCohortPayload = {
  name: string;
  team_ids: string[];
  history_visible: boolean;
  submissions_enabled: boolean;
};

type TeamCohortUpdatePayload = {
  name?: string;
  team_ids?: string[];
  history_visible?: boolean;
  submissions_enabled?: boolean;
};

type TeamsPanelProps = {
  teams: TeamCollections;
  isWorking?: boolean;
  isCohortWorking?: boolean;
  onCreate?: (team: CreateTeamPayload) => void;
  onUpdate?: (teamId: string, team: TeamUpdatePayload) => void;
  onBulkAction?: (payload: TeamBulkActionPayload) => void;
  onCreateCohort?: (cohort: CreateTeamCohortPayload) => void;
  onUpdateCohort?: (cohortId: string, cohort: TeamCohortUpdatePayload) => void;
  onDeleteCohort?: (cohortId: string) => void;
};

type ActiveTeamGroup = {
  groupId: string;
  name: string;
  accent: number | "ungrouped";
  teams: TeamRecord[];
};

function formatTime(value: string): string {
  return value.replace("T", " ").replace("Z", "");
}

function selectedIds(selected: Set<string>): string[] {
  return Array.from(selected);
}

function nextCohortTeamIds(
  currentTeamIds: string[],
  teamId: string,
  checked: boolean,
  teamOptions: TeamRecord[]
): string[] {
  const next = new Set(currentTeamIds);
  if (checked) next.add(teamId);
  else next.delete(teamId);
  return teamOptions.filter((team) => next.has(team.teamId)).map((team) => team.teamId);
}

function activeTeamGroups(
  rows: TeamRecord[],
  cohorts: TeamCohortRecord[],
  ungroupedName: string
): ActiveTeamGroup[] {
  const knownCohortIds = new Set(cohorts.map((cohort) => cohort.cohortId));
  const groups: ActiveTeamGroup[] = cohorts
    .map((cohort, index) => ({
      groupId: cohort.cohortId,
      name: cohort.name,
      accent: index % 5,
      teams: rows.filter((team) => team.cohortId === cohort.cohortId)
    }))
    .filter((group) => group.teams.length > 0);
  const ungroupedTeams = rows.filter(
    (team) => team.cohortId === null || !knownCohortIds.has(team.cohortId)
  );
  if (ungroupedTeams.length > 0) {
    groups.push({
      groupId: "ungrouped",
      name: ungroupedName,
      accent: "ungrouped",
      teams: ungroupedTeams
    });
  }
  return groups;
}

function teamCountText(
  count: number,
  t: (key: string, variables?: Record<string, string | number>) => string
): string {
  return count === 1
    ? t("admin.teamGroupCount", { count })
    : t("admin.teamGroupCountPlural", { count });
}

export function TeamsPanel({
  teams,
  isWorking,
  isCohortWorking,
  onCreate,
  onUpdate,
  onBulkAction,
  onCreateCohort,
  onUpdateCohort,
  onDeleteCohort
}: TeamsPanelProps) {
  const { t } = useI18n();
  const fallbackCreate = useCreateTeam();
  const fallbackUpdate = useUpdateTeam();
  const fallbackBulkAction = useTeamBulkAction();
  const fallbackCreateCohort = useCreateTeamCohort();
  const fallbackUpdateCohort = useUpdateTeamCohort();
  const fallbackDeleteCohort = useDeleteTeamCohort();
  const [teamName, setTeamName] = useState("");
  const [password, setPassword] = useState("");
  const [cohortName, setCohortName] = useState("");
  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editPassword, setEditPassword] = useState("");
  const [activeSelected, setActiveSelected] = useState<Set<string>>(new Set());
  const [archivedSelected, setArchivedSelected] = useState<Set<string>>(new Set());
  const [visiblePasswords, setVisiblePasswords] = useState<Set<string>>(new Set());

  const handleCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = teamName.trim();
    if (!trimmedName || password.length === 0) return;
    const payload = { team_name: trimmedName, password };
    if (onCreate) onCreate(payload);
    else fallbackCreate.mutate(payload);
  };

  const handleCreateCohort = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = cohortName.trim();
    if (!trimmedName) return;
    const payload = {
      name: trimmedName,
      team_ids: [],
      history_visible: true,
      submissions_enabled: true
    };
    if (onCreateCohort) onCreateCohort(payload);
    else fallbackCreateCohort.mutate(payload);
    setCohortName("");
  };

  const startEdit = (team: TeamRecord) => {
    setEditingTeamId(team.teamId);
    setEditName(team.teamName);
    setEditPassword("");
  };

  const saveEdit = (team: TeamRecord) => {
    const payload: TeamUpdatePayload = {};
    const trimmedName = editName.trim();
    if (trimmedName.length > 0 && trimmedName !== team.teamName) {
      payload.team_name = trimmedName;
    }
    if (editPassword.length > 0) {
      payload.password = editPassword;
    }
    if (Object.keys(payload).length > 0) {
      if (onUpdate) onUpdate(team.teamId, payload);
      else fallbackUpdate.mutate({ teamId: team.teamId, team: payload });
    }
    setEditingTeamId(null);
    setEditPassword("");
  };

  const toggleActive = (teamId: string) => {
    setActiveSelected((current) => {
      const next = new Set(current);
      if (next.has(teamId)) next.delete(teamId);
      else next.add(teamId);
      return next;
    });
  };

  const toggleArchived = (teamId: string) => {
    setArchivedSelected((current) => {
      const next = new Set(current);
      if (next.has(teamId)) next.delete(teamId);
      else next.add(teamId);
      return next;
    });
  };

  const runActiveBulk = (action: string) => {
    const ids = selectedIds(activeSelected);
    if (ids.length === 0) return;
    const payload = { team_ids: ids, action };
    if (onBulkAction) onBulkAction(payload);
    else fallbackBulkAction.mutate(payload);
    setActiveSelected(new Set());
  };

  const runArchivedBulk = (action: string) => {
    const ids = selectedIds(archivedSelected);
    if (ids.length === 0) return;
    const payload = { team_ids: ids, action };
    if (onBulkAction) onBulkAction(payload);
    else fallbackBulkAction.mutate(payload);
    setArchivedSelected(new Set());
  };

  const copyPassword = (team: TeamRecord) => {
    if (team.password) {
      navigator.clipboard?.writeText(team.password);
    }
  };

  const togglePassword = (teamId: string) => {
    setVisiblePasswords((current) => {
      const next = new Set(current);
      if (next.has(teamId)) next.delete(teamId);
      else next.add(teamId);
      return next;
    });
  };

  const fallbackWorking = fallbackCreate.isPending || fallbackUpdate.isPending || fallbackBulkAction.isPending;
  const working = isWorking ?? fallbackWorking;
  const fallbackCohortWorking =
    fallbackCreateCohort.isPending ||
    fallbackUpdateCohort.isPending ||
    fallbackDeleteCohort.isPending;
  const cohortWorking = isCohortWorking ?? fallbackCohortWorking;
  const teamOptions =
    teams.teams.length > 0 ? teams.teams : [...teams.activeTeams, ...teams.archivedTeams];

  const runCohortUpdate = (cohortId: string, cohort: TeamCohortUpdatePayload) => {
    if (onUpdateCohort) onUpdateCohort(cohortId, cohort);
    else fallbackUpdateCohort.mutate({ cohortId, cohort });
  };

  const runCohortDelete = (cohortId: string) => {
    if (onDeleteCohort) onDeleteCohort(cohortId);
    else fallbackDeleteCohort.mutate(cohortId);
  };

  const renderPassword = (team: TeamRecord) => {
    if (!team.password) {
      return <span className={styles.muted}>{t("admin.passwordResetRequired")}</span>;
    }
    const visible = visiblePasswords.has(team.teamId);
    return (
      <div className={styles.passwordControls}>
        <input readOnly type={visible ? "text" : "password"} value={team.password} />
        <Button
          aria-label={visible ? t("admin.hidePasswordFor", { name: team.teamName }) : t("admin.showPasswordFor", { name: team.teamName })}
          onClick={() => togglePassword(team.teamId)}
          type="button"
          variant="ghost"
        >
          {visible ? <EyeOff aria-hidden="true" size={15} /> : <Eye aria-hidden="true" size={15} />}
        </Button>
        <Button
          aria-label={t("admin.copyPasswordFor", { name: team.teamName })}
          onClick={() => copyPassword(team)}
          type="button"
          variant="ghost"
        >
          <Copy aria-hidden="true" size={15} />
        </Button>
      </div>
    );
  };

  const renderTeamName = (team: TeamRecord) => {
    if (editingTeamId !== team.teamId) return team.teamName;
    return (
      <div className={styles.editStack}>
        <input
          aria-label={t("admin.editTeamName", { name: team.teamName })}
          onChange={(event) => setEditName(event.target.value)}
          value={editName}
        />
        <button
          className={styles.passwordResetToggle}
          onClick={() => setEditPassword((current) => (current.length === 0 ? " " : ""))}
          type="button"
        >
          {t("admin.resetPassword")}
        </button>
        {editPassword.length > 0 ? (
          <PasswordInput
            aria-label={t("admin.newPasswordFor", { name: team.teamName })}
            autoComplete="new-password"
            onChange={(event) => setEditPassword(event.target.value)}
            placeholder={t("admin.passwordPlaceholder")}
            value={editPassword === " " ? "" : editPassword}
          />
        ) : null}
      </div>
    );
  };

  const renderActions = (team: TeamRecord) => {
    if (editingTeamId === team.teamId) {
      return (
        <div className={styles.buttonPair}>
          <Button disabled={working} onClick={() => saveEdit(team)} type="button">
            <Save aria-hidden="true" size={15} />
            {t("admin.saveTeam")}
          </Button>
          <Button onClick={() => setEditingTeamId(null)} type="button" variant="ghost">
            {t("common.cancel")}
          </Button>
        </div>
      );
    }
    return (
      <div className={styles.buttonPair}>
        <Button aria-label={t("admin.editTeam", { name: team.teamName })} onClick={() => startEdit(team)} type="button" variant="ghost">
          {t("admin.edit")}
        </Button>
        {team.status === "archived" ? (
          <Button
            disabled={working}
            onClick={() => {
              const payload = { team_ids: [team.teamId], action: "restore" };
              if (onBulkAction) onBulkAction(payload);
              else fallbackBulkAction.mutate(payload);
            }}
            type="button"
            variant="ghost"
          >
            <RotateCcw aria-hidden="true" size={15} />
            {t("admin.restore")}
          </Button>
        ) : (
          <Button
            disabled={working}
            onClick={() => {
              const payload = { team_ids: [team.teamId], action: "archive" };
              if (onBulkAction) onBulkAction(payload);
              else fallbackBulkAction.mutate(payload);
            }}
            type="button"
            variant="ghost"
          >
            <Archive aria-hidden="true" size={15} />
            {t("admin.archive")}
          </Button>
        )}
      </div>
    );
  };

  const groupAccentClass = (accent: ActiveTeamGroup["accent"]): string => {
    if (accent === "ungrouped") return styles.teamGroupUngrouped;
    const accentClasses = [
      styles.teamGroupCyan,
      styles.teamGroupEmerald,
      styles.teamGroupAmber,
      styles.teamGroupViolet,
      styles.teamGroupRed
    ];
    return accentClasses[accent] ?? styles.teamGroupCyan;
  };

  const renderRows = (rows: TeamRecord[], archived: boolean, grouped = false) =>
    rows.map((team) => (
      <tr className={grouped ? styles.teamGroupMemberRow : undefined} key={team.teamId}>
        <td>
          <input
            aria-label={t("admin.selectTeam", { name: team.teamName })}
            checked={archived ? archivedSelected.has(team.teamId) : activeSelected.has(team.teamId)}
            onChange={() => (archived ? toggleArchived(team.teamId) : toggleActive(team.teamId))}
            type="checkbox"
          />
        </td>
        {archived ? <td>{t("admin.archivedStatus")}</td> : null}
        <td>{renderTeamName(team)}</td>
        <td>{team.submissionCount}</td>
        <td>{formatTime(team.createdAt)}</td>
        <td>{renderPassword(team)}</td>
        <td>{renderActions(team)}</td>
      </tr>
    ));

  const renderActiveTeamGroups = (rows: TeamRecord[]) =>
    activeTeamGroups(rows, teams.cohorts, t("admin.ungroupedTeams")).map((group) => {
      const countText = teamCountText(group.teams.length, t);
      return (
        <tbody
          className={`${styles.teamGroupBody} ${groupAccentClass(group.accent)}`}
          key={group.groupId}
        >
          <tr
            aria-label={`${group.name} ${countText}`}
            className={styles.teamGroupHeaderRow}
          >
            <th colSpan={6} scope="rowgroup">
              <span>{group.name}</span>
              <strong>{countText}</strong>
            </th>
          </tr>
          {renderRows(group.teams, false, true)}
        </tbody>
      );
    });

  const renderCohortRows = (rows: TeamCohortRecord[]) =>
    rows.map((cohort) => (
      <tr aria-label={t("admin.cohortRow", { name: cohort.name })} key={cohort.cohortId}>
        <td>{cohort.name}</td>
        <td>
          <div
            aria-label={t("admin.teamsInCohort", { name: cohort.name })}
            className={styles.cohortTeamPicker}
            role="group"
          >
            <span className={styles.cohortTeamSummary}>
              {cohort.teamIds.length === 0
                ? t("admin.cohortNoTeamsSelected")
                : cohort.teamIds.length === 1
                  ? t("admin.cohortTeamCount", { count: cohort.teamIds.length })
                  : t("admin.cohortTeamCountPlural", { count: cohort.teamIds.length })}
            </span>
            <div className={styles.cohortTeamList}>
              {teamOptions.map((team) => (
                <label className={styles.cohortTeamOption} key={team.teamId}>
                  <input
                    aria-label={t("admin.includeTeamInCohort", {
                      cohort: cohort.name,
                      team: team.teamName
                    })}
                    checked={cohort.teamIds.includes(team.teamId)}
                    disabled={cohortWorking}
                    onChange={(event) =>
                      runCohortUpdate(cohort.cohortId, {
                        team_ids: nextCohortTeamIds(
                          cohort.teamIds,
                          team.teamId,
                          event.currentTarget.checked,
                          teamOptions
                        )
                      })
                    }
                    type="checkbox"
                  />
                  <span>{team.teamName}</span>
                </label>
              ))}
            </div>
          </div>
        </td>
        <td>
          <label className={styles.toggle}>
            <input
              aria-label={
                cohort.historyVisible
                  ? t("admin.hideCohortHistory", { name: cohort.name })
                  : t("admin.showCohortHistory", { name: cohort.name })
              }
              checked={cohort.historyVisible}
              onChange={(event) =>
                runCohortUpdate(cohort.cohortId, {
                  history_visible: event.target.checked
                })
              }
              type="checkbox"
            />
            <span>{t("admin.historyVisible")}</span>
          </label>
        </td>
        <td>
          <label className={styles.toggle}>
            <input
              aria-label={
                cohort.submissionsEnabled
                  ? t("admin.disableCohortSubmissions", { name: cohort.name })
                  : t("admin.enableCohortSubmissions", { name: cohort.name })
              }
              checked={cohort.submissionsEnabled}
              onChange={(event) =>
                runCohortUpdate(cohort.cohortId, {
                  submissions_enabled: event.target.checked
                })
              }
              type="checkbox"
            />
            <span>{t("admin.cohortSubmissionsEnabled")}</span>
          </label>
        </td>
        <td>
          <div className={styles.buttonPair}>
            <Link
              aria-label={t("admin.viewCohortSubmissionsFor", { name: cohort.name })}
              className={styles.buttonLink}
              to={`/admin/cohorts/${encodeURIComponent(cohort.cohortId)}/submissions`}
            >
              {t("admin.viewCohortSubmissions", { name: cohort.name })}
            </Link>
            <Button
              aria-label={t("admin.deleteCohort", { name: cohort.name })}
              disabled={cohortWorking}
              onClick={() => runCohortDelete(cohort.cohortId)}
              type="button"
              variant="ghost"
            >
              <Trash2 aria-hidden="true" size={15} />
              {t("admin.deleteCohortAction")}
            </Button>
          </div>
        </td>
      </tr>
    ));

  return (
    <div className={styles.stack}>
      <form className={styles.createForm} onSubmit={handleCreate}>
        <label className={styles.inlineField} htmlFor="admin-new-team-name">
          <span>{t("admin.teamName")}</span>
          <input
            id="admin-new-team-name"
            onChange={(event) => setTeamName(event.target.value)}
            required
            value={teamName}
          />
        </label>
        <label className={styles.inlineField} htmlFor="admin-new-team-password">
          <span>{t("admin.password")}</span>
          <PasswordInput
            autoComplete="new-password"
            id="admin-new-team-password"
            onChange={(event) => setPassword(event.target.value)}
            required
            value={password}
          />
        </label>
        <Button disabled={working} type="submit">
          {t("admin.createTeam")}
        </Button>
      </form>

      <section className={styles.historySection} aria-labelledby="admin-team-cohorts-title">
        <div className={styles.historyHeader}>
          <h2 id="admin-team-cohorts-title">{t("admin.teamCohorts")}</h2>
        </div>
        <form className={styles.createForm} onSubmit={handleCreateCohort}>
          <label className={styles.inlineField} htmlFor="admin-new-cohort-name">
            <span>{t("admin.cohortName")}</span>
            <input
              id="admin-new-cohort-name"
              onChange={(event) => setCohortName(event.target.value)}
              required
              value={cohortName}
            />
          </label>
          <Button disabled={cohortWorking} type="submit">
            {t("admin.createCohort")}
          </Button>
        </form>
        <div
          aria-label={`${t("admin.teamCohorts")}. ${t("common.tableScrollHint")}`}
          className={styles.tableWrap}
          data-scroll-hint={t("common.tableScrollHint")}
          role="region"
          tabIndex={0}
        >
          <table aria-label={t("admin.teamCohorts")} className={styles.table}>
            <caption>{t("admin.teamCohorts")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("admin.cohortName")}</th>
                <th scope="col">{t("admin.team")}</th>
                <th scope="col">{t("admin.historyVisible")}</th>
                <th scope="col">{t("admin.cohortSubmissionsEnabled")}</th>
                <th scope="col">{t("admin.actions")}</th>
              </tr>
            </thead>
            <tbody>{renderCohortRows(teams.cohorts)}</tbody>
          </table>
        </div>
      </section>

      <div className={styles.bulkBar}>
        <Button disabled={activeSelected.size === 0 || working} onClick={() => runActiveBulk("archive")} type="button" variant="ghost">
          <Archive aria-hidden="true" size={15} />
          {t("admin.archiveSelected")}
        </Button>
        <Button disabled={activeSelected.size === 0 || working} onClick={() => runActiveBulk("delete")} type="button" variant="ghost">
          <Trash2 aria-hidden="true" size={15} />
          {t("admin.deleteSelected")}
        </Button>
      </div>
      <div
        aria-label={`${t("admin.activeTeams")}. ${t("common.tableScrollHint")}`}
        className={styles.tableWrap}
        data-scroll-hint={t("common.tableScrollHint")}
        role="region"
        tabIndex={0}
      >
        <table aria-label={t("admin.activeTeams")} className={styles.table}>
          <caption>{t("admin.activeTeams")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("common.select")}</th>
              <th scope="col">{t("admin.teamName")}</th>
              <th scope="col">{t("admin.submissionCount")}</th>
              <th scope="col">{t("admin.createdTime")}</th>
              <th scope="col">{t("admin.passwordStatus")}</th>
              <th scope="col">{t("admin.actions")}</th>
            </tr>
          </thead>
          {renderActiveTeamGroups(teams.activeTeams)}
        </table>
      </div>

      <div className={styles.bulkBar}>
        <Button disabled={archivedSelected.size === 0 || working} onClick={() => runArchivedBulk("restore")} type="button" variant="ghost">
          <RotateCcw aria-hidden="true" size={15} />
          {t("admin.restoreSelected")}
        </Button>
        <Button disabled={archivedSelected.size === 0 || working} onClick={() => runArchivedBulk("delete")} type="button" variant="ghost">
          <Trash2 aria-hidden="true" size={15} />
          {t("admin.deleteSelected")}
        </Button>
      </div>
      <div
        aria-label={`${t("admin.archivedTeams")}. ${t("common.tableScrollHint")}`}
        className={styles.tableWrap}
        data-scroll-hint={t("common.tableScrollHint")}
        role="region"
        tabIndex={0}
      >
        <table aria-label={t("admin.archivedTeams")} className={styles.table}>
          <caption>{t("admin.archivedTeams")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("common.select")}</th>
              <th scope="col">{t("admin.status")}</th>
              <th scope="col">{t("admin.teamName")}</th>
              <th scope="col">{t("admin.submissionCount")}</th>
              <th scope="col">{t("admin.createdTime")}</th>
              <th scope="col">{t("admin.passwordStatus")}</th>
              <th scope="col">{t("admin.actions")}</th>
            </tr>
          </thead>
          <tbody>{renderRows(teams.archivedTeams, true)}</tbody>
        </table>
      </div>
    </div>
  );
}
