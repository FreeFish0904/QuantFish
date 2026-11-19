from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from quantfish.submissions.artifacts import report_artifacts_available
from quantfish.submissions.models import submission_execution_parameters, submission_label
from quantfish.submissions.score_summary import metrics_for_submission


class ComparisonService:
    def __init__(
        self,
        submission_repository: Any,
        team_repository: Any,
        artifact_reader: Any,
        team_cohort_service: Any | None = None,
    ):
        self.submission_repository = submission_repository
        self.team_repository = team_repository
        self.artifact_reader = artifact_reader
        self.team_cohort_service = team_cohort_service

    def compare(
        self,
        submission_ids: Sequence[str],
        *,
        include_graph_data: bool = False,
    ) -> dict[str, Any]:
        submissions = []
        for submission_id in submission_ids:
            submission = self.submission_repository.get(submission_id)
            if submission is None:
                continue
            if not self._submission_visible(submission):
                continue
            team = self.team_repository.get(submission.team_id)
            artifacts = {}
            report_dir = Path(submission.report_dir)
            if report_dir.exists() and (
                submission.status.value == "completed"
                or report_artifacts_available(report_dir)
            ):
                artifacts = self.artifact_reader.read(report_dir, include_parquet=False)
            graph_data_source = artifacts.get("graph_data", {})
            graph_data = graph_data_source if isinstance(graph_data_source, dict) else {}
            compared_submission = {
                "submission_id": submission.submission_id,
                "submission_number": submission.submission_number or 0,
                "submission_label": submission_label(submission.submission_number or 0),
                "team_id": submission.team_id,
                "team_name": team.display_name if team else submission.team_id,
                "status": submission.status.value,
                "data_track": submission.data_track.value,
                "metrics": (
                    metrics.to_dict()
                    if (
                        metrics := metrics_for_submission(
                            submission,
                            self.artifact_reader,
                        )
                    )
                    else None
                ),
                "equity": graph_data.get("equity", []),
                "drawdown": graph_data.get("drawdown", []),
                "execution_parameters": submission_execution_parameters(submission),
            }
            if include_graph_data:
                compared_submission["graph_data"] = graph_data
            submissions.append(
                compared_submission
            )
        return {"submissions": submissions}

    def _submission_visible(self, submission: Any) -> bool:
        if self.team_cohort_service is None:
            return True
        return bool(self.team_cohort_service.is_submission_visible(submission))
