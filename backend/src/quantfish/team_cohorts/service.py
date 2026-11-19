from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from quantfish.team_cohorts.models import TeamCohort, utc_now
from quantfish.team_cohorts.repository import TeamCohortRepository


class TeamCohortService:
    def __init__(self, repository: TeamCohortRepository, team_repository: Any):
        self.repository = repository
        self.team_repository = team_repository

    def list_cohorts(self) -> list[TeamCohort]:
        return self.repository.list_all()

    def get_cohort(self, cohort_id: str) -> TeamCohort | None:
        return self.repository.get(cohort_id)

    def create_cohort(
        self,
        *,
        name: str,
        team_ids: Iterable[str] = (),
        history_visible: bool = True,
        submissions_enabled: bool = True,
    ) -> TeamCohort:
        cohorts = self.repository.list_all()
        normalized_name = _clean_name(name)
        _ensure_unique_name(cohorts, normalized_name)
        clean_team_ids = self._validated_team_ids(team_ids)
        now = utc_now()
        cohort = TeamCohort(
            cohort_id=f"cohort-{uuid.uuid4().hex[:12]}",
            name=normalized_name,
            team_ids=clean_team_ids,
            history_visible=history_visible,
            submissions_enabled=submissions_enabled,
            created_at=now,
            updated_at=now,
        )
        self.repository.save_all(_replace_with_single_membership(cohorts, cohort))
        return cohort

    def update_cohort(
        self,
        cohort_id: str,
        *,
        name: str | None = None,
        team_ids: Iterable[str] | None = None,
        history_visible: bool | None = None,
        submissions_enabled: bool | None = None,
    ) -> TeamCohort:
        cohorts = self.repository.list_all()
        current = next((cohort for cohort in cohorts if cohort.cohort_id == cohort_id), None)
        if current is None:
            raise KeyError(cohort_id)
        changes: dict[str, Any] = {}
        if name is not None:
            normalized_name = _clean_name(name)
            _ensure_unique_name(cohorts, normalized_name, current_id=cohort_id)
            changes["name"] = normalized_name
        if team_ids is not None:
            changes["team_ids"] = self._validated_team_ids(team_ids)
        if history_visible is not None:
            changes["history_visible"] = history_visible
        if submissions_enabled is not None:
            changes["submissions_enabled"] = submissions_enabled
        updated = current.with_updates(**changes)
        self.repository.save_all(_replace_with_single_membership(cohorts, updated))
        return updated

    def delete_cohort(self, cohort_id: str) -> bool:
        cohorts = self.repository.list_all()
        remaining = [cohort for cohort in cohorts if cohort.cohort_id != cohort_id]
        deleted = len(remaining) != len(cohorts)
        if deleted:
            self.repository.save_all(remaining)
        return deleted

    def cohort_by_team_id(self) -> dict[str, TeamCohort]:
        mapping: dict[str, TeamCohort] = {}
        for cohort in self.repository.list_all():
            for team_id in cohort.team_ids:
                mapping[team_id] = cohort
        return mapping

    def cohort_for_team(self, team_id: str) -> TeamCohort | None:
        return self.cohort_by_team_id().get(team_id)

    def hidden_history_team_ids(self) -> set[str]:
        hidden: set[str] = set()
        for cohort in self.repository.list_all():
            if not cohort.history_visible:
                hidden.update(cohort.team_ids)
        return hidden

    def visible_history_team_ids(self, team_ids: Iterable[str]) -> set[str]:
        hidden = self.hidden_history_team_ids()
        return {team_id for team_id in team_ids if team_id not in hidden}

    def is_submission_visible(self, submission: Any) -> bool:
        return str(submission.team_id) not in self.hidden_history_team_ids()

    def filter_visible_submissions(self, submissions: Iterable[Any]) -> list[Any]:
        hidden = self.hidden_history_team_ids()
        return [submission for submission in submissions if submission.team_id not in hidden]

    def team_submissions_enabled(self, team_id: str) -> bool:
        cohort = self.cohort_for_team(team_id)
        return True if cohort is None else cohort.submissions_enabled

    def cohort_payload(self, cohort: TeamCohort) -> dict[str, Any]:
        return cohort.to_dict()

    def _validated_team_ids(self, team_ids: Iterable[str]) -> tuple[str, ...]:
        existing = {team.team_id for team in self.team_repository.list_all()}
        clean: list[str] = []
        seen: set[str] = set()
        for raw_team_id in team_ids:
            team_id = str(raw_team_id)
            if team_id in seen:
                continue
            if team_id not in existing:
                raise ValueError(f"unknown team: {team_id}")
            seen.add(team_id)
            clean.append(team_id)
        return tuple(clean)


def _replace_with_single_membership(
    cohorts: list[TeamCohort],
    updated: TeamCohort,
) -> list[TeamCohort]:
    updated_team_ids = set(updated.team_ids)
    result: list[TeamCohort] = []
    for cohort in cohorts:
        if cohort.cohort_id == updated.cohort_id:
            result.append(updated)
            continue
        if not updated_team_ids:
            result.append(cohort)
            continue
        remaining_team_ids = tuple(
            team_id for team_id in cohort.team_ids if team_id not in updated_team_ids
        )
        if remaining_team_ids == cohort.team_ids:
            result.append(cohort)
        else:
            result.append(replace(cohort, team_ids=remaining_team_ids, updated_at=utc_now()))
    if all(cohort.cohort_id != updated.cohort_id for cohort in cohorts):
        result.append(updated)
    return result


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("cohort name is required")
    return cleaned


def _ensure_unique_name(
    cohorts: list[TeamCohort],
    name: str,
    *,
    current_id: str | None = None,
) -> None:
    normalized = name.casefold()
    for cohort in cohorts:
        if cohort.cohort_id != current_id and cohort.name.casefold() == normalized:
            raise ValueError(f"cohort already exists: {name}")
