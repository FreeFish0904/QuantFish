from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.submissions.failure_summary import (
    CATEGORY_DATA_RELEASE,
    CATEGORY_INVALID_SIGNALS,
    CATEGORY_OTHER,
    CATEGORY_STALE_POSITIONS,
    CATEGORY_TIMEOUT,
    CATEGORY_WORKER_CRASH,
    build_failure_summary,
    classify_failure,
)
from quantfish.submissions.models import Submission, SubmissionDataTrack, SubmissionStatus
from quantfish.web_app.app import create_app
from quantfish.web_app.settings import WebSettings


def _config_path(tmp_path: Path) -> Path:
    config_path = tmp_path / "platform.yaml"
    if not config_path.exists():
        ConfigRepository(config_path).save(PlatformConfig.default())
    return config_path


def _submission(
    submission_id: str,
    *,
    status: SubmissionStatus = SubmissionStatus.FAILED,
    report_dir: Path | None = None,
    error_message: str | None = None,
    team_id: str = "team-alpha",
    submitted_at: datetime | None = None,
    submission_number: int | None = None,
) -> Submission:
    return Submission(
        submission_id=submission_id,
        team_id=team_id,
        status=status,
        strategy_path=f"/tmp/{submission_id}/generate_signals.py",
        report_dir=(report_dir or Path("/tmp") / submission_id).as_posix(),
        fingerprints=None,
        original_filename="generate_signals.py",
        data_track=SubmissionDataTrack.LEARNING,
        submission_number=submission_number,
        error_message=error_message,
        submitted_at=(submitted_at or datetime.now(UTC)).replace(microsecond=0).isoformat(),
    )


def _since(days: int = 7) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def test_classify_failure_prefers_the_worker_code() -> None:
    assert classify_failure("anything", "terminal_stale_positions") == CATEGORY_STALE_POSITIONS
    assert classify_failure("Scoring timed out after 120 seconds", None) == CATEGORY_TIMEOUT
    assert classify_failure("student strategy must define callable generate_signals", None) == (
        CATEGORY_INVALID_SIGNALS
    )
    assert classify_failure("score worker returned invalid JSON", None) == CATEGORY_WORKER_CRASH
    assert classify_failure("release has no usable rows for stock.daily_returns", None) == (
        CATEGORY_DATA_RELEASE
    )
    assert classify_failure("something else entirely", None) == CATEGORY_OTHER


def test_summary_groups_failures_and_keeps_the_latest_samples(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    submissions = [
        _submission(
            "sub-timeout",
            error_message="scoring timed out after 120 seconds",
            submitted_at=now - timedelta(hours=1),
            submission_number=1,
        ),
        _submission(
            "sub-signals",
            error_message="student strategy must define callable generate_signals",
            submitted_at=now - timedelta(hours=2),
            submission_number=2,
        ),
        _submission(
            "sub-signals-2",
            error_message="signals must include code and score columns",
            submitted_at=now - timedelta(hours=3),
            submission_number=3,
        ),
        _submission(
            "sub-ok",
            status=SubmissionStatus.COMPLETED,
            submitted_at=now - timedelta(hours=4),
            submission_number=4,
        ),
        _submission(
            "sub-old",
            error_message="scoring timed out after 120 seconds",
            submitted_at=now - timedelta(days=30),
            submission_number=5,
        ),
    ]

    summary = build_failure_summary(
        submissions,
        team_names={"team-alpha": "Team Alpha"},
        since=_since(7),
        window_days=7,
        limit=2,
    ).to_payload()

    assert summary["window_days"] == 7
    assert summary["total_submissions"] == 4
    assert summary["failed_submissions"] == 3
    assert summary["status_counts"] == {"completed": 1, "failed": 3}
    assert summary["categories"] == [
        {"category": CATEGORY_TIMEOUT, "count": 1, "sample_submission_ids": ["sub-timeout"]},
        {
            "category": CATEGORY_INVALID_SIGNALS,
            "count": 2,
            "sample_submission_ids": ["sub-signals", "sub-signals-2"],
        },
    ]
    assert [item["submission_id"] for item in summary["recent_failures"]] == [
        "sub-timeout",
        "sub-signals",
    ]
    assert summary["recent_failures"][0]["team_name"] == "Team Alpha"
    assert summary["recent_failures"][0]["data_track"] == "learning"


def test_summary_reads_the_worker_failure_code_and_raw_log_flag(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "sub-stale"
    report_dir.mkdir(parents=True)
    (report_dir / "worker_failure.json").write_text(
        json.dumps({"code": "terminal_stale_positions", "message": "stale"}),
        encoding="utf-8",
    )
    (report_dir / "worker_error.log").write_text("Traceback…", encoding="utf-8")

    summary = build_failure_summary(
        [_submission("sub-stale", report_dir=report_dir)],
        team_names={},
        since=_since(1),
        window_days=1,
    ).to_payload()

    sample = summary["recent_failures"][0]
    assert sample["category"] == CATEGORY_STALE_POSITIONS
    assert sample["worker_code"] == "terminal_stale_positions"
    assert sample["has_raw_log"] is True
    assert sample["team_name"] == "team-alpha"


def test_summary_trims_long_error_messages(tmp_path: Path) -> None:
    summary = build_failure_summary(
        [_submission("sub-long", error_message="x" * 500)],
        team_names={},
        since=_since(1),
        window_days=1,
    ).to_payload()

    assert len(summary["recent_failures"][0]["error_message"]) == 200


def test_summary_is_empty_without_failures(tmp_path: Path) -> None:
    summary = build_failure_summary(
        [_submission("sub-ok", status=SubmissionStatus.QUEUED)],
        team_names={},
        since=_since(7),
        window_days=7,
    ).to_payload()

    assert summary["failed_submissions"] == 0
    assert summary["categories"] == []
    assert summary["recent_failures"] == []
    assert summary["status_counts"] == {"queued": 1}


def _client(tmp_path: Path) -> TestClient:
    settings = WebSettings(
        runtime_root=tmp_path / "runtime",
        config_path=_config_path(tmp_path),
        frontend_dist=tmp_path / "missing-frontend-dist",
        admin_password="quantfish-admin",
        admin_session_secret="test-session-secret",
        participant_session_secret="test-participant-session-secret",
        student_exports_enabled=False,
    )
    return TestClient(create_app(settings))


def test_failures_endpoint_requires_an_admin_session(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/admin/failures")

    assert response.status_code == 401


def test_failures_endpoint_reports_grouped_failures(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        client.post("/api/admin/login", json={"password": "quantfish-admin"})
        client.post(
            "/api/admin/teams",
            json={"team_name": "Team Alpha", "password": "secret"},
        )
        services = client.app.state.services
        team = services.team_repository.resolve_login("Team Alpha")
        assert team is not None
        services.submission_repository.create(
            _submission(
                "sub-failed",
                team_id=team.team_id,
                error_message="scoring timed out after 120 seconds",
            )
        )

        response = client.get("/api/admin/failures?days=7&limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_days"] == 7
    assert payload["failed_submissions"] == 1
    assert payload["status_counts"] == {"failed": 1}
    assert payload["categories"] == [
        {
            "category": CATEGORY_TIMEOUT,
            "count": 1,
            "sample_submission_ids": ["sub-failed"],
        }
    ]
    assert payload["recent_failures"][0]["team_name"] == "Team Alpha"


def test_failures_endpoint_rejects_an_unsupported_window(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        client.post("/api/admin/login", json={"password": "quantfish-admin"})
        response = client.get("/api/admin/failures?days=365")

    assert response.status_code == 422
