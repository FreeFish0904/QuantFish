from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from quantfish.admin_console.settings_history import AdminSettingsHistoryRepository
from quantfish.leaderboard.ranking import ScoringWeights, calculate_leaderboard_score
from quantfish.leaderboard.sql_scoring import score_sort_expression
from quantfish.platform_config import ConfigRepository, ConfigService
from quantfish.submissions.error_details import raw_submission_error, submission_has_raw_error
from quantfish.submissions.failure_summary import build_failure_summary
from quantfish.submissions.listing import (
    SubmissionListParams,
    team_name_map,
)
from quantfish.submissions.models import (
    Submission,
    SubmissionStatus,
    submission_label,
)
from quantfish.submissions.result_staleness import is_zero_result_stale
from quantfish.submissions.score_summary import score_summary_for_submission

_RELEASE_GENERATION_UNAVAILABLE = object()


class AdminConsoleService:
    def __init__(
        self,
        settings: Any,
        team_repository: Any,
        storage: Any,
        submission_repository: Any | None = None,
        submission_runner: Any | None = None,
        scoring_dispatcher: Any | None = None,
        student_export_service: Any | None = None,
        artifact_reader: Any | None = None,
        settings_history_repository: AdminSettingsHistoryRepository | None = None,
        team_cohort_service: Any | None = None,
    ):
        self.settings = settings
        self.team_repository = team_repository
        self.storage = storage
        self.submission_repository = submission_repository
        self.submission_runner = submission_runner
        self.scoring_dispatcher = scoring_dispatcher
        self.student_export_service = student_export_service
        self.artifact_reader = artifact_reader
        self.settings_history_repository = settings_history_repository
        self.team_cohort_service = team_cohort_service

    def settings_payload(self) -> dict[str, Any]:
        config = ConfigRepository(self.settings.config_path).load()
        payload = config.to_dict()
        payload["dataset"] = {
            "train_start": config.data_releases.learning_start.isoformat(),
            "train_end": config.data_releases.learning_end.isoformat(),
            "hidden_test_start": config.data_releases.hidden_start.isoformat(),
            "hidden_test_end": config.data_releases.hidden_end.isoformat(),
        }
        payload["execution_limits"] = {
            "max_upload_bytes": self.settings.max_upload_bytes,
            "scoring_timeout_seconds": config.execution.submission_timeout_seconds,
            "engine_version": self.settings.engine_version,
        }
        payload["runtime"] = {
            "runtime_root": str(self.settings.runtime_root),
            "frontend_dist": str(self.settings.frontend_dist),
        }
        payload["settings_history"] = [
            entry.to_dict()
            for entry in (
                self.settings_history_repository.list_recent()
                if self.settings_history_repository is not None
                else []
            )
        ]
        return payload

    def update_settings(
        self,
        *,
        dataset: dict[str, Any] | None = None,
        backtest: dict[str, Any] | None = None,
        scoring: dict[str, Any] | None = None,
        execution: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data_releases: dict[str, Any] = {}
        backtest_updates: dict[str, Any] = dict(backtest or {})
        if dataset:
            if "train_start" in dataset:
                data_releases["learning_start"] = dataset["train_start"]
                backtest_updates["data_start"] = dataset["train_start"]
            if "train_end" in dataset:
                data_releases["learning_end"] = dataset["train_end"]
            if "hidden_test_start" in dataset:
                data_releases["hidden_start"] = dataset["hidden_test_start"]
                backtest_updates["scoring_start"] = dataset["hidden_test_start"]
            if "hidden_test_end" in dataset:
                data_releases["hidden_end"] = dataset["hidden_test_end"]
                backtest_updates["scoring_end"] = dataset["hidden_test_end"]
        repository = ConfigRepository(self.settings.config_path)
        config_service = ConfigService(repository)
        current = repository.load()
        updated = config_service.build_updated(
            data_releases=data_releases or None,
            backtest=backtest_updates or None,
            scoring=scoring,
            execution=execution,
        )
        return self._persist_settings_change(repository, current, updated)

    def revert_settings_history(self, entry_id: str) -> dict[str, Any]:
        if self.settings_history_repository is None:
            raise KeyError(entry_id)
        entry = self.settings_history_repository.get(entry_id)
        if entry is None:
            raise KeyError(entry_id)
        if entry.entry_type != "settings_change":
            raise ValueError("history entry is not a settings change")
        repository = ConfigRepository(self.settings.config_path)
        config_service = ConfigService(repository)
        current = repository.load()
        updated = config_service.build_updated(
            course=_history_section(entry.settings, "course"),
            data_releases=_history_section(entry.settings, "data_releases"),
            backtest=_history_section(entry.settings, "backtest"),
            scoring=_history_section(entry.settings, "scoring"),
            execution=_history_section(entry.settings, "execution"),
        )
        return self._persist_settings_change(repository, current, updated)

    def _persist_settings_change(
        self,
        repository: ConfigRepository,
        current: Any,
        updated: Any,
    ) -> dict[str, Any]:
        dataset_dates_changed = current.data_releases != updated.data_releases
        if dataset_dates_changed:
            self._requeue_running_submissions_for_dataset_change()
        if (
            dataset_dates_changed
            and self.settings.student_exports_enabled
            and self.student_export_service is not None
        ):
            self.student_export_service.refresh(updated)
        repository.save(updated)
        if self.settings_history_repository is not None:
            self.settings_history_repository.record_settings_change(
                current,
                updated,
                stale_marked=False,
            )
        if self.scoring_dispatcher is not None:
            self.scoring_dispatcher.pump()
        return self.settings_payload()

    def mark_completed_submissions_stale(self) -> dict[str, Any]:
        if self.settings_history_repository is None:
            raise RuntimeError("settings history repository unavailable")
        submissions = (
            self.submission_repository.list_all() if self.submission_repository is not None else []
        )
        submission_ids = [
            submission.submission_id
            for submission in submissions
            if submission.status == SubmissionStatus.COMPLETED
        ]
        self.settings_history_repository.record_stale_mark(submission_ids)
        return self.settings_payload()

    def revert_stale_mark(self, entry_id: str) -> dict[str, Any]:
        if self.settings_history_repository is None:
            raise KeyError(entry_id)
        self.settings_history_repository.revert_stale_mark(entry_id)
        return self.settings_payload()

    def active_stale_submission_ids(self) -> set[str]:
        stale_ids = (
            self.settings_history_repository.active_stale_submission_ids()
            if self.settings_history_repository is not None
            else set()
        )
        if self.submission_repository is None or self.submission_runner is None:
            return stale_ids
        generation_for = getattr(
            self.submission_runner,
            "current_release_generation",
            None,
        )
        if not callable(generation_for):
            return stale_ids
        generation_by_track: dict[Any, str | object | None] = {}
        for submission in self.submission_repository.list_all():
            if submission.status != SubmissionStatus.COMPLETED:
                continue
            if submission.data_track not in generation_by_track:
                try:
                    generation_by_track[submission.data_track] = generation_for(
                        submission.data_track
                    )
                except Exception:
                    generation_by_track[submission.data_track] = _RELEASE_GENERATION_UNAVAILABLE
            current_generation = generation_by_track[submission.data_track]
            fingerprints = submission.fingerprints
            if (
                current_generation is _RELEASE_GENERATION_UNAVAILABLE
                or (fingerprints is None and current_generation is not None)
                or (
                    fingerprints is not None
                    and (
                        current_generation is not None
                        or fingerprints.release_generation is not None
                    )
                    and fingerprints.release_generation != current_generation
                )
            ):
                stale_ids.add(submission.submission_id)
        return stale_ids

    def scoring_weights(self) -> ScoringWeights:
        config = ConfigRepository(self.settings.config_path).load()
        return ScoringWeights(**config.scoring.__dict__)

    def list_teams(self) -> dict[str, list[dict[str, Any]]]:
        counts = self._submission_counts_by_team()
        cohorts = self._cohorts()
        cohort_by_team = {
            team_id: cohort for cohort in cohorts for team_id in getattr(cohort, "team_ids", ())
        }
        active = [
            self._team_record(
                team,
                submission_count=counts.get(team.team_id, 0),
                cohort=cohort_by_team.get(team.team_id),
            )
            for team in self.team_repository.list_active()
        ]
        archived = [
            self._team_record(
                team,
                submission_count=counts.get(team.team_id, 0),
                cohort=cohort_by_team.get(team.team_id),
            )
            for team in self.team_repository.list_archived()
        ]
        return {
            "teams": active,
            "active_teams": active,
            "archived_teams": archived,
            "cohorts": [self._cohort_record(cohort) for cohort in cohorts],
        }

    def create_team_cohort(
        self,
        *,
        name: str,
        team_ids: list[str],
        history_visible: bool,
        submissions_enabled: bool,
    ) -> dict[str, Any]:
        if self.team_cohort_service is None:
            raise RuntimeError("team cohort service unavailable")
        cohort = self.team_cohort_service.create_cohort(
            name=name,
            team_ids=team_ids,
            history_visible=history_visible,
            submissions_enabled=submissions_enabled,
        )
        return self._cohort_record(cohort)

    def update_team_cohort(
        self,
        cohort_id: str,
        *,
        name: str | None = None,
        team_ids: list[str] | None = None,
        history_visible: bool | None = None,
        submissions_enabled: bool | None = None,
    ) -> dict[str, Any]:
        if self.team_cohort_service is None:
            raise KeyError(cohort_id)
        cohort = self.team_cohort_service.update_cohort(
            cohort_id,
            name=name,
            team_ids=team_ids,
            history_visible=history_visible,
            submissions_enabled=submissions_enabled,
        )
        return self._cohort_record(cohort)

    def delete_team_cohort(self, cohort_id: str) -> dict[str, bool]:
        if self.team_cohort_service is None:
            raise KeyError(cohort_id)
        deleted = self.team_cohort_service.delete_cohort(cohort_id)
        if not deleted:
            raise KeyError(cohort_id)
        return {"deleted": True}

    def create_team(
        self,
        *,
        team_name: str,
        password: str,
    ) -> dict[str, Any]:
        team = self.team_repository.create_team_with_name(
            display_name=team_name,
            password=password,
        )
        record = self._team_record(team)
        record["password"] = password
        return record

    def update_team(
        self,
        team_id: str,
        *,
        team_name: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        team = self.team_repository.update_team(
            team_id,
            display_name=team_name,
            password=password,
        )
        record = self._team_record(team)
        if password:
            record["password"] = password
        return record

    def bulk_team_action(self, team_ids: list[str], action: str) -> dict[str, Any]:
        counts = {
            "archived": 0,
            "restored": 0,
            "deleted": 0,
            "skipped": 0,
        }
        for team_id in team_ids:
            if action == "archive":
                counts["archived"] += int(self.team_repository.archive(team_id))
            elif action == "restore":
                counts["restored"] += int(self.team_repository.restore(team_id))
            elif action == "delete":
                if self._submission_count(team_id) > 0:
                    counts["skipped"] += 1
                    continue
                counts["deleted"] += int(self.team_repository.delete(team_id))
            else:
                raise ValueError(f"unsupported team action: {action}")
        return counts

    def list_admin_submissions(self) -> list[dict[str, Any]]:
        if self.submission_repository is None:
            return []
        stale_submission_ids = self.active_stale_submission_ids()
        weights = self.scoring_weights()
        team_names = team_name_map(self.team_repository.list_all())
        return [
            self._admin_submission_record(
                submission,
                stale_submission_ids,
                weights,
                team_names=team_names,
                include_raw_error=False,
            )
            for submission in self.submission_repository.list_all()
        ]

    def failure_summary(self, *, days: int = 7, limit: int = 20) -> dict[str, Any]:
        """Group the failures of the last `days` days by likely cause."""
        window_days = max(1, int(days))
        since = datetime.now(UTC) - timedelta(days=window_days)
        submissions = (
            [] if self.submission_repository is None else self.submission_repository.list_all()
        )
        return build_failure_summary(
            submissions,
            team_names=team_name_map(self.team_repository.list_all()),
            since=since,
            window_days=window_days,
            limit=max(1, int(limit)),
        ).to_payload()

    def list_admin_submission_page(self, params: SubmissionListParams) -> dict[str, Any]:
        if self.submission_repository is None:
            return {
                "submissions": [],
                "total_count": 0,
                "limit": params.limit,
                "offset": params.offset,
                "has_next": False,
            }
        weights = self.scoring_weights()
        team_names = team_name_map(self.team_repository.list_all())
        score_expression, score_values = score_sort_expression(weights)
        filtered_params = replace(
            params,
            excluded_team_ids=self._hidden_history_team_ids(),
        )
        page = self.submission_repository.list_page(
            filtered_params,
            team_names=team_names,
            score_for=lambda submission: _submission_score(
                submission,
                weights,
                self.artifact_reader,
            ),
            sql_sort_expressions={"score": (score_expression, score_values)},
        )
        stale_submission_ids = self.active_stale_submission_ids()
        return {
            "submissions": [
                self._admin_submission_record(
                    submission,
                    stale_submission_ids,
                    weights,
                    team_names=team_names,
                    include_raw_error=False,
                )
                for submission in page.items
            ],
            **page.metadata(),
        }

    def list_cohort_submission_page(
        self,
        cohort_id: str,
        params: SubmissionListParams,
    ) -> dict[str, Any]:
        if self.submission_repository is None or self.team_cohort_service is None:
            return {
                "submissions": [],
                "total_count": 0,
                "limit": params.limit,
                "offset": params.offset,
                "has_next": False,
            }
        cohort = self.team_cohort_service.get_cohort(cohort_id)
        if cohort is None:
            raise KeyError(cohort_id)
        weights = self.scoring_weights()
        team_names = team_name_map(self.team_repository.list_all())
        score_expression, score_values = score_sort_expression(weights)
        page = self.submission_repository.list_page(
            replace(params, team_ids=tuple(cohort.team_ids), team_id=None),
            team_names=team_names,
            score_for=lambda submission: _submission_score(
                submission,
                weights,
                self.artifact_reader,
            ),
            sql_sort_expressions={"score": (score_expression, score_values)},
        )
        stale_submission_ids = self.active_stale_submission_ids()
        return {
            "submissions": [
                self._admin_submission_record(
                    submission,
                    stale_submission_ids,
                    weights,
                    team_names=team_names,
                    include_raw_error=False,
                )
                for submission in page.items
            ],
            **page.metadata(),
        }

    def delete_submissions(
        self,
        submission_ids: list[str],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        deleted_ids: list[str] = []
        skipped_ids: list[str] = []
        deleted_paths: list[str] = []
        if self.submission_repository is None:
            return _deletion_payload(deleted_ids, skipped_ids, deleted_paths)

        for submission_id in submission_ids:
            submission = self.submission_repository.get(submission_id)
            if submission is None:
                skipped_ids.append(submission_id)
                continue
            if not force and not _is_terminal(submission.status):
                skipped_ids.append(submission_id)
                continue
            if force and self.scoring_dispatcher is not None:
                self.scoring_dispatcher.cancel_submission(submission_id)
            deleted_paths.extend(
                self.storage.delete_upload_files_safely([submission.strategy_path])
            )
            self.submission_repository.delete(submission_id)
            deleted_ids.append(submission_id)
        if force and self.scoring_dispatcher is not None:
            self.scoring_dispatcher.pump()
        return _deletion_payload(deleted_ids, skipped_ids, deleted_paths)

    def rerun_submissions(
        self,
        *,
        scope: str,
        submission_ids: list[str],
    ) -> dict[str, Any]:
        if self.submission_repository is None:
            return _rerun_payload([], [])
        candidates = [
            submission
            for submission in self.submission_repository.list_all()
            if self._submission_visible(submission)
        ]
        return self._rerun_submission_candidates(
            candidates,
            scope=scope,
            submission_ids=submission_ids,
        )

    def rerun_cohort_submissions(
        self,
        cohort_id: str,
        *,
        scope: str,
        submission_ids: list[str],
    ) -> dict[str, Any]:
        if self.submission_repository is None or self.team_cohort_service is None:
            raise KeyError(cohort_id)
        cohort = self.team_cohort_service.get_cohort(cohort_id)
        if cohort is None:
            raise KeyError(cohort_id)
        cohort_team_ids = set(cohort.team_ids)
        candidates = [
            submission
            for submission in self.submission_repository.list_all()
            if submission.team_id in cohort_team_ids
        ]
        return self._rerun_submission_candidates(
            candidates,
            scope=scope,
            submission_ids=submission_ids,
        )

    def _rerun_submission_candidates(
        self,
        candidates: list[Submission],
        *,
        scope: str,
        submission_ids: list[str],
    ) -> dict[str, Any]:
        candidate_by_id = {submission.submission_id: submission for submission in candidates}
        queued_ids: list[str] = []
        skipped_ids: list[str] = []
        if scope == "all":
            for submission in candidates:
                if not _is_terminal(submission.status):
                    skipped_ids.append(submission.submission_id)
                    continue
                self.submission_repository.save(_submission_for_rescore(submission))
                queued_ids.append(submission.submission_id)
        elif scope == "selected":
            seen: set[str] = set()
            for submission_id in submission_ids:
                if submission_id in seen:
                    skipped_ids.append(submission_id)
                    continue
                seen.add(submission_id)
                submission = candidate_by_id.get(submission_id)
                if submission is None:
                    skipped_ids.append(submission_id)
                    continue
                if not _is_terminal(submission.status):
                    skipped_ids.append(submission_id)
                    continue
                self.submission_repository.save(_submission_for_rescore(submission))
                queued_ids.append(submission_id)
        else:
            raise ValueError(f"unsupported rerun scope: {scope}")

        if queued_ids and self.scoring_dispatcher is not None:
            self.scoring_dispatcher.pump()
        return _rerun_payload(queued_ids, skipped_ids)

    def backfill_short_profit_metrics(self) -> dict[str, Any]:
        if self.submission_repository is None:
            return {"queued": 0, "submission_ids": []}
        queued_ids: list[str] = []
        for submission in self.submission_repository.list_all():
            if submission.status != SubmissionStatus.COMPLETED:
                continue
            if _has_annualized_short_profit(submission, self.artifact_reader):
                continue
            self.submission_repository.save(_submission_for_rescore(submission))
            queued_ids.append(submission.submission_id)
        if queued_ids and self.scoring_dispatcher is not None:
            self.scoring_dispatcher.pump()
        return {"queued": len(queued_ids), "submission_ids": queued_ids}

    def submission_source(self, submission_id: str) -> str:
        if self.submission_repository is None:
            raise KeyError(submission_id)
        submission = self.submission_repository.get(submission_id)
        if submission is None or not self._submission_visible(submission):
            raise KeyError(submission_id)
        return self.storage.read_strategy_text(submission.strategy_path)

    def cohort_submission_source(self, cohort_id: str, submission_id: str) -> str:
        submission = self._cohort_submission(cohort_id, submission_id)
        return self.storage.read_strategy_text(submission.strategy_path)

    def submission_raw_error(self, submission_id: str) -> str:
        if self.submission_repository is None:
            raise KeyError(submission_id)
        submission = self.submission_repository.get(submission_id)
        if submission is None or not self._submission_visible(submission):
            raise KeyError(submission_id)
        error = raw_submission_error(submission)
        if error is None:
            raise FileNotFoundError(submission.report_dir)
        return error

    def cohort_submission_raw_error(self, cohort_id: str, submission_id: str) -> str:
        submission = self._cohort_submission(cohort_id, submission_id)
        error = raw_submission_error(submission)
        if error is None:
            raise FileNotFoundError(submission.report_dir)
        return error

    def starter_strategy_text(self) -> str:
        return self.storage.starter_strategy_text()

    def quickstart_text(self) -> str:
        return self.storage.quickstart_text()

    def _team_record(
        self,
        team: Any,
        *,
        submission_count: int | None = None,
        cohort: Any | None = None,
    ) -> dict[str, Any]:
        status = "archived" if team.archived_at else "active"
        return {
            "team_id": team.team_id,
            "team_name": team.display_name,
            "display_name": team.display_name,
            "submission_count": (
                self._submission_count(team.team_id)
                if submission_count is None
                else submission_count
            ),
            "created_at": team.created_at,
            "status": status,
            "password": None,
            "cohort_id": getattr(cohort, "cohort_id", None),
            "cohort_name": getattr(cohort, "name", None),
            "history_visible": True if cohort is None else bool(cohort.history_visible),
            "submissions_enabled": True if cohort is None else bool(cohort.submissions_enabled),
        }

    def _cohorts(self) -> list[Any]:
        if self.team_cohort_service is None:
            return []
        return self.team_cohort_service.list_cohorts()

    def _cohort_record(self, cohort: Any) -> dict[str, Any]:
        return self.team_cohort_service.cohort_payload(cohort)

    def _submission_count(self, team_id: str) -> int:
        if self.submission_repository is None:
            return 0
        return self.submission_repository.count_for_team(team_id)

    def _submission_counts_by_team(self) -> dict[str, int]:
        if self.submission_repository is None:
            return {}
        count_by_team = getattr(self.submission_repository, "count_by_team", None)
        if callable(count_by_team):
            return count_by_team()
        return {
            team.team_id: self.submission_repository.count_for_team(team.team_id)
            for team in self.team_repository.list_all()
        }

    def _hidden_history_team_ids(self) -> tuple[str, ...]:
        if self.team_cohort_service is None:
            return ()
        return tuple(sorted(self.team_cohort_service.hidden_history_team_ids()))

    def _submission_visible(self, submission: Submission) -> bool:
        if self.team_cohort_service is None:
            return True
        return bool(self.team_cohort_service.is_submission_visible(submission))

    def _cohort_submission(self, cohort_id: str, submission_id: str) -> Submission:
        if self.submission_repository is None or self.team_cohort_service is None:
            raise KeyError(submission_id)
        cohort = self.team_cohort_service.get_cohort(cohort_id)
        if cohort is None:
            raise KeyError(cohort_id)
        submission = self.submission_repository.get(submission_id)
        if submission is None or submission.team_id not in set(cohort.team_ids):
            raise KeyError(submission_id)
        return submission

    def _admin_submission_record(
        self,
        submission: Submission,
        stale_submission_ids: set[str] | None = None,
        weights: ScoringWeights | None = None,
        *,
        team_names: dict[str, str] | None = None,
        include_raw_error: bool = True,
    ) -> dict[str, Any]:
        names = (
            team_names if team_names is not None else team_name_map(self.team_repository.list_all())
        )
        scoring_weights = weights or self.scoring_weights()
        score_summary = score_summary_for_submission(submission, self.artifact_reader)
        stale = self._is_stale(
            submission,
            stale_submission_ids,
            summary=score_summary,
        )
        payload = {
            "submission_id": submission.submission_id,
            "submission_number": submission.submission_number or 0,
            "submission_label": submission_label(submission.submission_number or 0),
            "team_id": submission.team_id,
            "team_name": names.get(submission.team_id, submission.team_id),
            "type": "python",
            "data_track": submission.data_track.value,
            "status": _admin_status(submission.status),
            "stale": stale,
            "selectable": _is_terminal(submission.status),
            "score": _score_from_summary(score_summary, scoring_weights),
            "filename": submission.original_filename,
            "submitted_at": submission.submitted_at,
            "finished_at": submission.scored_at,
            "raw_error": raw_submission_error(submission) if include_raw_error else None,
            "config_snapshot": submission.config_snapshot,
            "file_paths": {
                "strategy_path": submission.strategy_path,
                "report_dir": submission.report_dir,
            },
        }
        if not include_raw_error:
            payload.pop("raw_error", None)
            payload["has_raw_error"] = submission_has_raw_error(submission)
        return payload

    def _is_stale(
        self,
        submission: Submission,
        stale_submission_ids: set[str] | None = None,
        summary: Mapping[str, Any] | None = None,
    ) -> bool:
        if submission.status != SubmissionStatus.COMPLETED:
            return False
        stale_ids = (
            stale_submission_ids
            if stale_submission_ids is not None
            else self.active_stale_submission_ids()
        )
        return submission.submission_id in stale_ids or is_zero_result_stale(
            submission,
            summary,
        )

    def _requeue_running_submissions_for_dataset_change(self) -> int:
        if self.submission_repository is None:
            return 0
        requeued = 0
        for submission in self.submission_repository.list_all():
            if submission.status != SubmissionStatus.RUNNING:
                continue
            if self.scoring_dispatcher is not None:
                self.scoring_dispatcher.cancel_submission(submission.submission_id)
            self.submission_repository.save(_submission_for_rescore(submission))
            requeued += 1
        return requeued


def _admin_status(status: SubmissionStatus) -> str:
    return {
        SubmissionStatus.QUEUED: "queued",
        SubmissionStatus.RUNNING: "running",
        SubmissionStatus.COMPLETED: "completed",
        SubmissionStatus.FAILED: "failed",
    }[status]


def _is_terminal(status: SubmissionStatus) -> bool:
    return status in {SubmissionStatus.COMPLETED, SubmissionStatus.FAILED}


def _submission_score(
    submission: Submission,
    weights: ScoringWeights,
    artifact_reader: Any | None = None,
) -> float | None:
    summary = score_summary_for_submission(submission, artifact_reader)
    return _score_from_summary(summary, weights)


def _score_from_summary(
    summary: Mapping[str, Any],
    weights: ScoringWeights,
) -> float | None:
    if not summary:
        return None
    return calculate_leaderboard_score(summary, weights)


def _has_annualized_short_profit(
    submission: Submission,
    artifact_reader: Any | None = None,
) -> bool:
    summary = score_summary_for_submission(submission, artifact_reader)
    return summary.get("annualized_short_profit") is not None


def _submission_for_rescore(submission: Submission) -> Submission:
    return replace(
        submission,
        status=SubmissionStatus.QUEUED,
        fingerprints=None,
        metrics=None,
        error_message=None,
        scored_at=None,
        config_snapshot=None,
    )


def _deletion_payload(
    deleted_ids: list[str],
    skipped_ids: list[str],
    deleted_paths: list[str],
) -> dict[str, Any]:
    return {
        "deleted": len(deleted_ids),
        "skipped": len(skipped_ids),
        "deleted_submission_ids": deleted_ids,
        "skipped_submission_ids": skipped_ids,
        "deleted_file_paths": deleted_paths,
    }


def _rerun_payload(
    queued_ids: list[str],
    skipped_ids: list[str],
) -> dict[str, Any]:
    return {
        "queued": len(queued_ids),
        "skipped": len(skipped_ids),
        "queued_submission_ids": queued_ids,
        "skipped_submission_ids": skipped_ids,
    }


def _history_section(settings: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    value = settings.get(key)
    return dict(value) if isinstance(value, Mapping) else None
