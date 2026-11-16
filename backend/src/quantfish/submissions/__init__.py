"""Submission scoring domain for the QuantFish classroom web platform."""

from quantfish.submissions.artifacts import ReportArtifactReader
from quantfish.submissions.dispatcher import SubmissionScoringDispatcher
from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionMetrics,
    SubmissionStatus,
    Team,
    submission_detail_payload,
    submission_list_payload,
    team_public_payload,
)
from quantfish.submissions.repositories import SubmissionRepository, TeamRepository
from quantfish.submissions.runners import BacktestSubmissionRunner
from quantfish.submissions.service import SubmissionService
from quantfish.submissions.storage import SubmissionStorage

__all__ = [
    "BacktestSubmissionRunner",
    "ReportArtifactReader",
    "ScoreFingerprints",
    "Submission",
    "SubmissionMetrics",
    "SubmissionRepository",
    "SubmissionScoringDispatcher",
    "SubmissionService",
    "SubmissionStatus",
    "SubmissionStorage",
    "Team",
    "TeamRepository",
    "submission_detail_payload",
    "submission_list_payload",
    "team_public_payload",
]
