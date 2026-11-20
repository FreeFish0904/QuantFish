from __future__ import annotations

from pathlib import Path
from typing import Any

from quantfish.submissions.artifacts import ReportArtifactReader
from quantfish.submissions.models import SubmissionMetrics


def score_summary_for_submission(
    submission: Any,
    artifact_reader: Any | None = None,
) -> dict[str, Any]:
    stored_summary = submission.metrics.to_dict() if getattr(submission, "metrics", None) else {}
    artifact_summary = _artifact_summary(submission, artifact_reader)
    if not artifact_summary:
        return stored_summary
    merged = dict(stored_summary)
    for key, value in SubmissionMetrics.from_summary(artifact_summary).to_dict().items():
        if value is not None and merged.get(key) is None:
            merged[key] = value
    return merged


def metrics_for_submission(
    submission: Any,
    artifact_reader: Any | None = None,
) -> SubmissionMetrics | None:
    summary = score_summary_for_submission(submission, artifact_reader)
    if not summary:
        return None
    return SubmissionMetrics.from_summary(summary)


def _artifact_summary(
    submission: Any,
    artifact_reader: Any | None,
) -> dict[str, Any]:
    report_dir = Path(getattr(submission, "report_dir", ""))
    if not (report_dir / "summary.csv").is_file():
        return {}
    reader = artifact_reader or ReportArtifactReader()
    try:
        artifacts = reader.read(report_dir, include_parquet=False)
    except Exception:
        return {}
    summary = artifacts.get("summary")
    return summary if isinstance(summary, dict) else {}
