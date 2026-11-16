from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Protocol
import uuid

from quantfish.platform_config import ConfigRepository
from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionDataTrack,
    SubmissionMetrics,
    SubmissionStatus,
    Team,
    _submission_data_track,
)
from quantfish.submissions.repositories import SubmissionRepository, TeamRepository
from quantfish.submissions.storage import SubmissionStorage


class SubmissionRunner(Protocol):
    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        ...

    def score(
        self,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> SubmissionMetrics | None:
        ...


class SubmissionQueue(Protocol):
    def pump(self) -> None:
        ...


class SubmissionCooldownError(ValueError):
    def __init__(self, seconds_remaining: int) -> None:
        noun = "second" if seconds_remaining == 1 else "seconds"
        super().__init__(
            f"Please wait {seconds_remaining} {noun} before submitting another strategy."
        )
        self.seconds_remaining = seconds_remaining


class SubmissionCohortDisabledError(ValueError):
    pass


class SubmissionService:
    def __init__(
        self,
        team_repository: TeamRepository,
        submission_repository: SubmissionRepository,
        storage: SubmissionStorage,
        runner: SubmissionRunner,
        config_repository: ConfigRepository | None = None,
        team_cohort_service: Any | None = None,
        scoring_dispatcher: SubmissionQueue | None = None,
        submission_cooldown_seconds: float = 2.0,
    ):
        self.team_repository = team_repository
        self.submission_repository = submission_repository
        self.storage = storage
        self.runner = runner
        self.config_repository = config_repository
        self.team_cohort_service = team_cohort_service
        self.scoring_dispatcher = scoring_dispatcher
        self.submission_cooldown_seconds = submission_cooldown_seconds

    def set_scoring_dispatcher(self, scoring_dispatcher: SubmissionQueue) -> None:
        self.scoring_dispatcher = scoring_dispatcher

    def submit_strategy(
        self,
        *,
        team_name: str,
        password: str,
        filename: str,
        content: bytes,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> Submission:
        track = _submission_data_track(data_track)
        team = self.team_repository.resolve_login(team_name)
        if (
            team is None
            or team.archived_at is not None
            or not self.team_repository.verify_password(team_name, password)
        ):
            raise PermissionError("invalid team credentials")
        return self._submit_strategy_for_team(
            team=team,
            filename=filename,
            content=content,
            data_track=track,
        )

    def submit_strategy_for_team(
        self,
        *,
        team_id: str,
        filename: str,
        content: bytes,
        data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
    ) -> Submission:
        track = _submission_data_track(data_track)
        team = self.team_repository.get(team_id)
        if team is None or team.archived_at is not None:
            raise PermissionError("invalid team credentials")
        return self._submit_strategy_for_team(
            team=team,
            filename=filename,
            content=content,
            data_track=track,
        )

    def submission_source_for_team(self, submission_id: str, team_id: str) -> str:
        submission = self.submission_repository.get(submission_id)
        if submission is None:
            raise KeyError(submission_id)
        if submission.team_id != team_id:
            raise PermissionError("submission does not belong to current team")
        return self.storage.read_strategy_text(submission.strategy_path)

    def _submit_strategy_for_team(
        self,
        *,
        team: Team,
        filename: str,
        content: bytes,
        data_track: SubmissionDataTrack,
    ) -> Submission:
        config_snapshot = self._config_snapshot()
        if config_snapshot is not None and not _submissions_enabled(config_snapshot):
            raise ValueError("Submissions are disabled")
        if (
            self.team_cohort_service is not None
            and not self.team_cohort_service.team_submissions_enabled(team.team_id)
        ):
            raise SubmissionCohortDisabledError("team cohort submissions are disabled")
        self._enforce_submission_cooldown(team)

        submission_id = uuid.uuid4().hex
        strategy_path = self.storage.store_strategy(submission_id, filename, content)
        report_dir = self.storage.prepare_report_dir(submission_id)
        submission = Submission(
            submission_id=submission_id,
            team_id=team.team_id,
            status=SubmissionStatus.QUEUED,
            strategy_path=strategy_path.as_posix(),
            report_dir=report_dir.as_posix(),
            fingerprints=None,
            original_filename=filename,
            data_track=data_track,
            submission_number=None,
            config_snapshot=config_snapshot,
        )
        submission = self.submission_repository.create(submission)
        if self.scoring_dispatcher is not None:
            self.scoring_dispatcher.pump()
        return submission

    def _config_snapshot(self) -> dict[str, Any] | None:
        if self.config_repository is None:
            return None
        return self.config_repository.load().to_dict()

    def _enforce_submission_cooldown(self, team: Team) -> None:
        if self.submission_cooldown_seconds <= 0:
            return
        team_submissions = self.submission_repository.list_for_team(team.team_id)
        if not team_submissions:
            return
        latest = max(
            team_submissions,
            key=lambda submission: _submitted_at_datetime(submission.submitted_at),
        )
        latest_at = _submitted_at_datetime(latest.submitted_at)
        elapsed_seconds = (datetime.now(timezone.utc) - latest_at).total_seconds()
        remaining = self.submission_cooldown_seconds - elapsed_seconds
        if remaining > 0:
            raise SubmissionCooldownError(max(1, math.ceil(remaining)))


def _submissions_enabled(config_snapshot: dict[str, Any]) -> bool:
    execution = config_snapshot.get("execution")
    if not isinstance(execution, dict):
        return True
    return bool(execution.get("submissions_enabled", True))


def _submitted_at_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
