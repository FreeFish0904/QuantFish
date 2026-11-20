import gc
import json
import re
import subprocess
import sys
import threading
import time
import warnings
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

import pandas as pd
import pytest

from quantfish.backtest.simulator import TerminalStalePositionsError
from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.data.release_lock import ReleaseLockManager
from quantfish.leaderboard.ranking import ScoringWeights
from quantfish.platform_config import (
    BacktestConfig,
    ConfigRepository,
    CourseConfig,
    DataReleasesConfig,
    ExecutionConfig,
    PlatformConfig,
)
from quantfish.submissions.artifacts import ReportArtifactReader
from quantfish.submissions.dispatcher import SubmissionScoringDispatcher
from quantfish.submissions.error_details import WORKER_FAILURE_FILE, submission_has_raw_error
from quantfish.submissions.listing import SubmissionListParams, submission_page
from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionDataTrack,
    SubmissionMetrics,
    SubmissionStatus,
    Team,
    submission_list_payload,
    team_public_payload,
)
from quantfish.submissions.repositories import SubmissionRepository, TeamRepository
from quantfish.submissions.runners import BacktestSubmissionRunner
from quantfish.submissions.score_worker import main as score_worker_main
from quantfish.submissions.score_worker import score_submission
from quantfish.submissions.service import SubmissionCooldownError, SubmissionService
from quantfish.submissions.storage import SubmissionStorage


class FakeRunner:
    def __init__(self, *, fail: bool = False, fingerprint_fail: bool = False) -> None:
        self.fail = fail
        self.fingerprint_fail = fingerprint_fail
        self.calls: list[tuple[Path, Path]] = []

    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        if self.fingerprint_fail:
            raise RuntimeError("fingerprint setup exploded")
        return ScoreFingerprints(
            config_sha256="config",
            hidden_catalog_sha256="catalog",
            strategy_sha256=f"strategy:{strategy_path.read_text(encoding='utf-8')}",
            engine_version="fake-engine",
            data_track=data_track,
        )

    def score(
        self,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> SubmissionMetrics:
        self.calls.append((strategy_path, report_dir, data_track))
        if self.fail:
            raise RuntimeError("scoring exploded")
        report_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {
                    "total_return": 0.12,
                    "annual_return": 0.25,
                    "sharpe": 1.5,
                    "max_drawdown": -0.04,
                    "average_turnover": 0.2,
                    "win_rate": 0.6,
                    "trading_days": 2,
                }
            ]
        ).to_csv(report_dir / "summary.csv", index=False)
        pd.DataFrame(
            [
                {"date": pd.Timestamp("2024-01-02"), "daily_return": 0.01},
                {"date": pd.Timestamp("2024-01-03"), "daily_return": 0.02},
            ]
        ).to_parquet(report_dir / "daily_returns.parquet", index=False)
        pd.DataFrame(
            [
                {
                    "period": "2024",
                    "long": 0.5,
                    "short": -0.5,
                    "long_count": 10,
                    "short_count": 10,
                    "sharpe": 1.5,
                    "total_return": 0.25,
                    "annualized_return": 31.5,
                    "turnover": 0.2,
                    "drawdown": 0.04,
                    "fitness": 1.6,
                    "calmar": 6.25,
                },
                {
                    "period": "all",
                    "long": 0.5,
                    "short": -0.5,
                    "long_count": 10,
                    "short_count": 10,
                    "sharpe": 1.5,
                    "total_return": 0.25,
                    "annualized_return": 31.5,
                    "turnover": 0.2,
                    "drawdown": 0.04,
                    "fitness": 1.6,
                    "calmar": 6.25,
                },
            ]
        ).to_csv(report_dir / "performance_by_year.csv", index=False)
        (report_dir / "graph_data.json").write_text(
            json.dumps({"equity": [{"date": "2024-01-03", "equity": 1.03}]}),
            encoding="utf-8",
        )
        (report_dir / "diagnostics.json").write_text(
            json.dumps({"signal_rows": 4}),
            encoding="utf-8",
        )
        return SubmissionMetrics(
            total_return=0.12,
            annual_return=0.25,
            sharpe=1.5,
            max_drawdown=-0.04,
            average_turnover=0.2,
            win_rate=0.6,
            trading_days=2,
        )


class PumpRecorder:
    def __init__(self) -> None:
        self.calls = 0

    def pump(self) -> None:
        self.calls += 1


def _service(
    tmp_path: Path, runner: FakeRunner
) -> tuple[SubmissionService, TeamRepository, SubmissionRepository, SubmissionStorage]:
    teams = TeamRepository(tmp_path / "runtime")
    submissions = SubmissionRepository(tmp_path / "runtime")
    storage = SubmissionStorage(tmp_path / "runtime", max_upload_bytes=200)
    teams.save(
        Team.from_plaintext_password(team_id="team-a", display_name="Team A", password="secret")
    )
    return SubmissionService(teams, submissions, storage, runner), teams, submissions, storage


def _write_report_artifacts(report_dir: Path) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"total_return": 0.12, "sharpe": 1.5}]).to_csv(
        report_dir / "summary.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "period": "2024",
                "long": 0.5,
                "short": -0.5,
                "long_count": 10,
                "short_count": 10,
                "sharpe": 1.5,
                "returns": 0.25,
                "turnover": 0.2,
                "drawdown": 0.04,
                "fitness": 1.6,
                "calmar": 6.25,
            },
            {
                "period": "all",
                "long": 0.5,
                "short": -0.5,
                "long_count": 10,
                "short_count": 10,
                "sharpe": 1.5,
                "returns": 0.31,
                "turnover": 0.2,
                "drawdown": 0.04,
                "fitness": 1.6,
                "calmar": 7.75,
            },
        ]
    ).to_csv(report_dir / "performance_by_year.csv", index=False)
    (report_dir / "graph_data.json").write_text(
        json.dumps({"equity": [{"date": "2024-01-03", "equity": 1.03}]}),
        encoding="utf-8",
    )
    (report_dir / "diagnostics.json").write_text(
        json.dumps({"signal_rows": 4}),
        encoding="utf-8",
    )
    pd.DataFrame([{"date": pd.Timestamp("2024-01-03"), "daily_return": 0.01}]).to_parquet(
        report_dir / "daily_returns.parquet",
        index=False,
    )


def test_submission_repository_migrates_json_to_sqlite_once(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    repository_dir = runtime / "repositories"
    repository_dir.mkdir(parents=True)
    legacy_submissions = [
        Submission(
            submission_id="legacy-one",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path="/tmp/legacy-one.py",
            report_dir="/tmp/legacy-one-report",
            fingerprints=ScoreFingerprints(
                config_sha256="config-a",
                hidden_catalog_sha256="catalog-a",
                strategy_sha256="strategy-a",
                engine_version="engine-a",
            ),
            original_filename="one.py",
            submission_number=7,
            metrics=SubmissionMetrics(sharpe=1.2, calmar=2.4, trading_days=10),
            submitted_at="2026-06-20T09:00:00+00:00",
            scored_at="2026-06-20T09:05:00+00:00",
            config_snapshot={"backtest": {"capital": 1_000_000}},
        ),
        Submission(
            submission_id="legacy-two",
            team_id="team-beta",
            status=SubmissionStatus.FAILED,
            strategy_path="/tmp/legacy-two.py",
            report_dir="/tmp/legacy-two-report",
            fingerprints=None,
            original_filename="two.py",
            data_track=SubmissionDataTrack.LEARNING,
            submission_number=8,
            error_message="boom",
            submitted_at="2026-06-20T10:00:00+00:00",
        ),
    ]
    legacy_path = repository_dir / "submissions.json"
    legacy_path.write_text(
        json.dumps([submission.to_dict() for submission in legacy_submissions], indent=2) + "\n",
        encoding="utf-8",
    )

    first_repository = SubmissionRepository(runtime)
    first = first_repository.list_all()
    second_repository = SubmissionRepository(runtime)
    second = second_repository.list_all()

    assert (repository_dir / "quantfish.db").is_file()
    assert [submission.submission_id for submission in first] == ["legacy-one", "legacy-two"]
    assert [submission.submission_id for submission in second] == ["legacy-one", "legacy-two"]
    assert second[0].metrics == SubmissionMetrics(sharpe=1.2, calmar=2.4, trading_days=10)
    assert second[0].fingerprints is not None
    assert second[0].fingerprints.strategy_sha256 == "strategy-a"
    assert second[0].config_snapshot == {"backtest": {"capital": 1_000_000}}

    first_repository.save(
        Submission(
            submission_id="new-sqlite-only",
            team_id="team-alpha",
            status=SubmissionStatus.QUEUED,
            strategy_path="/tmp/new.py",
            report_dir="/tmp/new-report",
            fingerprints=None,
            original_filename="new.py",
            submitted_at="2026-06-20T11:00:00+00:00",
        )
    )

    legacy_after_save = json.loads(legacy_path.read_text(encoding="utf-8"))
    assert [item["submission_id"] for item in legacy_after_save] == ["legacy-one", "legacy-two"]
    assert [submission.submission_id for submission in second_repository.list_all()] == [
        "legacy-one",
        "legacy-two",
        "new-sqlite-only",
    ]


def test_submission_repository_closes_its_connections(tmp_path: Path) -> None:
    """Repository calls must release the SQLite handle instead of leaving it to the GC.

    `with sqlite3.Connection` only commits or rolls back; it never closes. Every
    read and write used to leak a descriptor plus the -wal/-shm handles, which
    surfaced as `ResourceWarning: unclosed database` only once warnings were on.
    """
    repository = SubmissionRepository(tmp_path / "runtime")
    submission = Submission(
        submission_id="leak-check",
        team_id="team-alpha",
        status=SubmissionStatus.QUEUED,
        strategy_path="/tmp/leak-check.py",
        report_dir="/tmp/leak-check-report",
        fingerprints=None,
        original_filename="leak.py",
        submitted_at="2026-06-20T12:00:00+00:00",
    )
    repository.save(submission)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert repository.get("leak-check") is not None
        repository.list_all()
        repository.list_for_team("team-alpha")
        repository.count_for_team("team-alpha")
        repository.count_all()
        repository.count_by_team()
        repository.status_counts()
        repository.next_submission_number()
        repository.requeue_running()
        repository.save(submission)
        repository.ping()
        assert repository.delete("leak-check") is True
        gc.collect()

    leaked = [warning for warning in caught if issubclass(warning.category, ResourceWarning)]
    assert leaked == []


def test_submission_repository_pages_filtered_rows_and_counts_by_team(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    rows = [
        Submission(
            submission_id="alpha-low",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path="/tmp/alpha-low.py",
            report_dir="/tmp/alpha-low-report",
            fingerprints=None,
            original_filename="alpha_low.py",
            submission_number=1,
            metrics=SubmissionMetrics(sharpe=1.0, calmar=1.0),
            submitted_at="2026-06-20T09:00:00+00:00",
        ),
        Submission(
            submission_id="beta-high",
            team_id="team-beta",
            status=SubmissionStatus.COMPLETED,
            strategy_path="/tmp/beta-high.py",
            report_dir="/tmp/beta-high-report",
            fingerprints=None,
            original_filename="beta_high.py",
            submission_number=2,
            metrics=SubmissionMetrics(sharpe=2.0, calmar=5.0),
            submitted_at="2026-06-20T10:00:00+00:00",
        ),
        Submission(
            submission_id="beta-learning",
            team_id="team-beta",
            status=SubmissionStatus.QUEUED,
            strategy_path="/tmp/beta-learning.py",
            report_dir="/tmp/beta-learning-report",
            fingerprints=None,
            original_filename="beta_learning.py",
            data_track=SubmissionDataTrack.LEARNING,
            submission_number=3,
            submitted_at="2026-06-20T11:00:00+00:00",
        ),
    ]
    for row in rows:
        repository.save(row)

    page = repository.list_page(
        SubmissionListParams(
            limit=1,
            offset=0,
            search="beta",
            status="completed",
            sort_by="calmar",
            sort_dir="desc",
        ),
        team_names={"team-alpha": "Alpha Desk", "team-beta": "Beta Desk"},
        score_for=lambda submission: submission.metrics.calmar if submission.metrics else None,
    )

    assert page.total_count == 1
    assert [submission.submission_id for submission in page.items] == ["beta-high"]
    assert repository.count_by_team() == {"team-alpha": 1, "team-beta": 2}
    assert repository.status_counts() == {"completed": 2, "queued": 1}


@pytest.mark.parametrize(
    ("search", "expected_tracks"),
    [
        ("2020", [SubmissionDataTrack.LEARNING_3, SubmissionDataTrack.LEARNING_2]),
        ("learning window 2", [SubmissionDataTrack.LEARNING_2]),
        ("test", [SubmissionDataTrack.HIDDEN_TEST]),
        (
            "learning",
            [
                SubmissionDataTrack.LEARNING_3,
                SubmissionDataTrack.LEARNING_2,
                SubmissionDataTrack.LEARNING_1,
                SubmissionDataTrack.LEARNING,
            ],
        ),
    ],
)
def test_submission_repository_track_search_matches_in_memory_listing(
    tmp_path: Path,
    search: str,
    expected_tracks: list[SubmissionDataTrack],
) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    rows = [
        Submission(
            submission_id=f"submission-{track.value}",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path=f"/tmp/{track.value}.py",
            report_dir=f"/tmp/{track.value}-report",
            fingerprints=None,
            original_filename=f"strategy-{track.value}.py",
            data_track=track,
            submission_number=index,
            submitted_at=f"2026-06-20T{index:02d}:00:00+00:00",
        )
        for index, track in enumerate(SubmissionDataTrack, start=1)
    ]
    for row in rows:
        repository.save(row)

    params = SubmissionListParams(search=search)
    team_names = {"team-alpha": "Alpha Desk"}
    sqlite_page = repository.list_page(params, team_names=team_names)
    memory_page = submission_page(rows, team_names=team_names, params=params)

    assert [row.data_track for row in sqlite_page.items] == expected_tracks
    assert [row.submission_id for row in sqlite_page.items] == [
        row.submission_id for row in memory_page.items
    ]


def test_submission_repository_sql_sorts_without_python_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from quantfish.leaderboard.sql_scoring import score_sort_expression

    repository = SubmissionRepository(tmp_path / "runtime")
    rows = [
        Submission(
            submission_id="alpha",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path="/tmp/alpha.py",
            report_dir="/tmp/alpha-report",
            fingerprints=None,
            original_filename="alpha.py",
            submission_number=1,
            metrics=SubmissionMetrics(
                total_return=0.10,
                annual_return=0.10,
                sharpe=1.0,
                max_drawdown=-0.20,
                calmar=0.5,
            ),
            submitted_at="2026-06-20T09:00:00+00:00",
        ),
        Submission(
            submission_id="beta",
            team_id="team-beta",
            status=SubmissionStatus.COMPLETED,
            strategy_path="/tmp/beta.py",
            report_dir="/tmp/beta-report",
            fingerprints=None,
            original_filename="beta.py",
            submission_number=2,
            metrics=SubmissionMetrics(
                total_return=0.30,
                annual_return=0.30,
                sharpe=3.0,
                max_drawdown=-0.05,
                calmar=6.0,
            ),
            submitted_at="2026-06-20T10:00:00+00:00",
        ),
        Submission(
            submission_id="gamma",
            team_id="team-gamma",
            status=SubmissionStatus.FAILED,
            strategy_path="/tmp/gamma.py",
            report_dir="/tmp/gamma-report",
            fingerprints=None,
            original_filename="gamma.py",
            submission_number=3,
            metrics=None,
            submitted_at="2026-06-20T11:00:00+00:00",
        ),
    ]
    for row in rows:
        repository.save(row)

    def fail_python_fallback(*args: object, **kwargs: object) -> list[Submission]:
        raise AssertionError("list_page should not fetch every filtered row for sorting")

    monkeypatch.setattr(repository, "_filtered_submissions", fail_python_fallback)
    team_names = {
        "team-alpha": "Zulu Desk",
        "team-beta": "Alpha Desk",
        "team-gamma": "Middle Desk",
    }

    by_team = repository.list_page(
        SubmissionListParams(limit=3, sort_by="team_name", sort_dir="asc"),
        team_names=team_names,
    )
    by_sharpe = repository.list_page(
        SubmissionListParams(limit=3, sort_by="sharpe", sort_dir="desc"),
        team_names=team_names,
    )
    score_expression, score_values = score_sort_expression(ScoringWeights())
    by_score = repository.list_page(
        SubmissionListParams(limit=3, sort_by="score", sort_dir="desc"),
        team_names=team_names,
        sql_sort_expressions={"score": (score_expression, score_values)},
    )

    assert [submission.submission_id for submission in by_team.items] == [
        "beta",
        "gamma",
        "alpha",
    ]
    assert [submission.submission_id for submission in by_sharpe.items] == [
        "beta",
        "alpha",
        "gamma",
    ]
    assert [submission.submission_id for submission in by_score.items] == [
        "beta",
        "alpha",
        "gamma",
    ]


def test_submission_repository_lists_queued_and_requeues_running(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    _queued_submission(repository, tmp_path, "queued-old", 1)
    _queued_submission(repository, tmp_path, "queued-active", 2)
    _queued_submission(repository, tmp_path, "queued-new", 3)
    _queued_submission(
        repository,
        tmp_path,
        "running",
        4,
        status=SubmissionStatus.RUNNING,
    )
    _queued_submission(
        repository,
        tmp_path,
        "completed",
        5,
        status=SubmissionStatus.COMPLETED,
    )

    queued = repository.list_queued(limit=2, exclude_submission_ids={"queued-active"})
    requeued = repository.requeue_running()

    assert [submission.submission_id for submission in queued] == [
        "queued-old",
        "queued-new",
    ]
    assert requeued == 1
    assert repository.get("running").status == SubmissionStatus.QUEUED
    assert repository.get("completed").status == SubmissionStatus.COMPLETED


def test_report_artifact_reader_can_skip_parquet_for_detail_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_dir = tmp_path / "report"
    _write_report_artifacts(report_dir)
    reader = ReportArtifactReader()

    def fail_parquet_read(_root: Path) -> dict[str, list[dict[str, object]]]:
        raise AssertionError("detail artifact read should not load parquet")

    monkeypatch.setattr(reader, "_read_parquet_artifacts", fail_parquet_read)

    artifacts = reader.read(report_dir, include_parquet=False)

    assert artifacts["summary"]["total_return"] == pytest.approx(0.12)
    assert artifacts["graph_data"]["equity"][0]["equity"] == pytest.approx(1.03)
    assert artifacts["diagnostics"] == {"signal_rows": 4}
    assert artifacts["performance_table"][0] == {
        "period": "2024",
        "long": 0.5,
        "short": -0.5,
        "long_count": 10,
        "short_count": 10,
        "sharpe": 1.5,
        "total_return": 0.25,
        "annualized_return": None,
        "turnover": 0.2,
        "drawdown": 0.04,
        "fitness": 1.6,
        "calmar": 6.25,
    }
    assert artifacts["performance_table"][1]["period"] == "all"
    assert artifacts["performance_table"][1]["total_return"] is None
    assert artifacts["performance_table"][1]["annualized_return"] == pytest.approx(0.31)
    assert artifacts["parquet"] == {}


def test_report_artifact_reader_caches_unchanged_lightweight_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_dir = tmp_path / "report"
    _write_report_artifacts(report_dir)
    reader = ReportArtifactReader(max_cache_entries=4)

    first = reader.read(report_dir, include_parquet=False)
    first["summary"]["total_return"] = 99

    def fail_summary_read(_path: Path) -> dict[str, object]:
        raise AssertionError("unchanged report should be served from cache")

    monkeypatch.setattr(reader, "_read_summary", fail_summary_read)

    second = reader.read(report_dir, include_parquet=False)

    assert second["summary"]["total_return"] == pytest.approx(0.12)


def test_report_artifact_reader_does_not_cache_an_in_progress_json_file(
    tmp_path: Path,
) -> None:
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    graph_path = report_dir / "graph_data.json"
    graph_path.write_text('{"equity":', encoding="utf-8")
    reader = ReportArtifactReader(max_cache_entries=4)

    assert reader.read(report_dir, include_parquet=False) == {
        "summary": {},
        "graph_data": {},
        "diagnostics": {},
        "performance_table": [],
        "parquet": {},
    }

    graph_path.write_text(
        '{"equity": [{"date": "2024-01-03", "equity": 1.03}]}',
        encoding="utf-8",
    )

    artifacts = reader.read(report_dir, include_parquet=False)
    assert artifacts["graph_data"]["equity"][0]["equity"] == pytest.approx(1.03)


def test_submission_service_queues_upload_and_returns_without_scoring(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    pump = PumpRecorder()
    service, teams, submissions, _storage = _service(tmp_path, runner)
    service.set_scoring_dispatcher(pump)

    submission = service.submit_strategy(
        team_name="Team A",
        password="secret",
        filename="alpha.py",
        content=b"def generate_signals(data):\n    return []\n",
    )

    stored = submissions.get(submission.submission_id)
    assert stored is not None
    assert stored.status == SubmissionStatus.QUEUED
    assert stored.error_message is None
    assert stored.metrics is None
    assert runner.calls == []
    assert pump.calls == 1

    assert team_public_payload(teams.get("team-a")) == {
        "team_id": "team-a",
        "display_name": "Team A",
    }
    assert submission_list_payload(stored)["status"] == "queued"
    assert stored.data_track == SubmissionDataTrack.HIDDEN_TEST
    assert submission_list_payload(stored)["data_track"] == "hidden_test"


def test_submission_service_accepts_learning_track_upload(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    service, _teams, submissions, _storage = _service(tmp_path, runner)

    submission = service.submit_strategy(
        team_name="Team A",
        password="secret",
        filename="alpha.py",
        content=b"def generate_signals(data):\n    return []\n",
        data_track=SubmissionDataTrack.LEARNING,
    )

    stored = submissions.get(submission.submission_id)
    assert stored is not None
    assert stored.data_track == SubmissionDataTrack.LEARNING
    assert submission_list_payload(stored)["data_track"] == "learning"


def test_submission_service_rejects_auth_failure_before_storing_upload(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    service, _teams, submissions, _storage = _service(tmp_path, runner)

    with pytest.raises(PermissionError, match="invalid team credentials"):
        service.submit_strategy(
            team_name="Team A",
            password="wrong",
            filename="alpha.py",
            content=b"def generate_signals(data):\n    return []\n",
        )

    assert runner.calls == []
    assert submissions.list_all() == []


def test_submission_service_rejects_disabled_submissions_before_storing_upload(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(submissions_enabled=False),
        )
    )
    service, _teams, submissions, storage = _service(tmp_path, runner)
    service.config_repository = ConfigRepository(config_path)

    with pytest.raises(ValueError, match="Submissions are disabled"):
        service.submit_strategy(
            team_name="Team A",
            password="secret",
            filename="alpha.py",
            content=b"def generate_signals(data):\n    return []\n",
        )

    assert runner.calls == []
    assert submissions.list_all() == []
    assert not storage.submissions_root.exists()


def test_submission_service_rejects_same_team_uploads_inside_cooldown(
    tmp_path: Path,
) -> None:
    runner = FakeRunner()
    pump = PumpRecorder()
    service, _teams, submissions, storage = _service(tmp_path, runner)
    service.set_scoring_dispatcher(pump)

    first = service.submit_strategy(
        team_name="Team A",
        password="secret",
        filename="alpha.py",
        content=b"def generate_signals(data):\n    return []\n",
    )

    assert pump.calls == 1
    assert len(submissions.list_all()) == 1
    assert len(list(storage.submissions_root.iterdir())) == 1

    with pytest.raises(
        SubmissionCooldownError,
        # A wall-clock 2 s window can report 1 s on a slow machine.
        match=r"Please wait [12] seconds? before submitting another strategy",
    ):
        service.submit_strategy(
            team_name="Team A",
            password="secret",
            filename="beta.py",
            content=b"def generate_signals(data):\n    return []\n",
        )

    assert pump.calls == 1
    assert [submission.submission_id for submission in submissions.list_all()] == [
        first.submission_id
    ]
    assert len(list(storage.submissions_root.iterdir())) == 1

    stored_first = submissions.get(first.submission_id)
    assert stored_first is not None
    old_enough = datetime.now(UTC) - timedelta(seconds=3)
    submissions.save(
        replace(
            stored_first,
            submitted_at=old_enough.replace(microsecond=0).isoformat(),
        )
    )

    third = service.submit_strategy(
        team_name="Team A",
        password="secret",
        filename="gamma.py",
        content=b"def generate_signals(data):\n    return []\n",
    )

    assert third.submission_id != first.submission_id
    assert pump.calls == 2
    assert len(submissions.list_all()) == 2
    assert len(list(storage.submissions_root.iterdir())) == 2


class ControlledScoreHandle:
    def __init__(self, name: str, metrics: SubmissionMetrics | None = None) -> None:
        self.name = name
        self.metrics = metrics or SubmissionMetrics(total_return=0.12, trading_days=2)
        self.started = threading.Event()
        self.release = threading.Event()
        self.terminated = False

    def wait(self) -> SubmissionMetrics:
        self.started.set()
        assert self.release.wait(5), f"timed out waiting to release {self.name}"
        if self.terminated:
            raise RuntimeError("worker terminated")
        return self.metrics

    def terminate(self) -> None:
        self.terminated = True
        self.release.set()


class ControlledRunner:
    def __init__(self, handles: list[ControlledScoreHandle]) -> None:
        self.handles = list(handles)
        self.started: list[str] = []
        self.fingerprint_failures_remaining = 0

    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        if self.fingerprint_failures_remaining > 0:
            self.fingerprint_failures_remaining -= 1
            raise RuntimeError("fingerprint setup exploded")
        return ScoreFingerprints(
            config_sha256="config",
            hidden_catalog_sha256="catalog",
            strategy_sha256=strategy_path.read_text(encoding="utf-8"),
            engine_version="fake-engine",
            data_track=data_track,
        )

    def current_config_snapshot(self) -> dict[str, object]:
        return {"course": {"name": "QuantFish"}}

    def start_score(
        self,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ControlledScoreHandle:
        handle = self.handles.pop(0)
        self.started.append(f"{strategy_path.parent.name}:{data_track.value}")
        return handle


def _write_dispatcher_config(path: Path, concurrency: int) -> ConfigRepository:
    repository = ConfigRepository(path)
    repository.save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(max_concurrent_scoring=concurrency),
        )
    )
    return repository


def _queued_submission(
    repository: SubmissionRepository,
    root: Path,
    submission_id: str,
    number: int,
    status: SubmissionStatus = SubmissionStatus.QUEUED,
    data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
) -> Submission:
    strategy_path = root / submission_id / "generate_signals.py"
    report_dir = root / submission_id / "report"
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    submission = Submission(
        submission_id=submission_id,
        team_id="team-a",
        status=status,
        strategy_path=strategy_path.as_posix(),
        report_dir=report_dir.as_posix(),
        fingerprints=None,
        original_filename=f"{submission_id}.py",
        submission_number=number,
        data_track=data_track,
    )
    repository.save(submission)
    return submission


def _wait_for_status(
    repository: SubmissionRepository,
    submission_id: str,
    status: SubmissionStatus,
) -> Submission:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        submission = repository.get(submission_id)
        if submission is not None and submission.status == status:
            return submission
        time.sleep(0.01)
    raise AssertionError(f"{submission_id} did not reach {status}")


def test_dispatcher_runs_queued_submissions_fifo_with_single_slot(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    for index in range(1, 4):
        _queued_submission(repository, tmp_path, f"sub-{index}", index)
    handles = [ControlledScoreHandle(f"sub-{index}") for index in range(1, 4)]
    runner = ControlledRunner(handles)
    dispatcher = SubmissionScoringDispatcher(
        repository,
        runner,
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1),
    )

    dispatcher.pump()

    assert handles[0].started.wait(5)
    assert runner.started == ["sub-1:hidden_test"]
    assert repository.get("sub-1").status == SubmissionStatus.RUNNING
    assert repository.get("sub-2").status == SubmissionStatus.QUEUED

    handles[0].release.set()
    _wait_for_status(repository, "sub-1", SubmissionStatus.COMPLETED)
    assert handles[1].started.wait(5)
    assert runner.started == ["sub-1:hidden_test", "sub-2:hidden_test"]

    handles[1].release.set()
    _wait_for_status(repository, "sub-2", SubmissionStatus.COMPLETED)
    assert handles[2].started.wait(5)
    handles[2].release.set()
    dispatcher.stop()


def test_dispatcher_holds_track_read_lock_for_fingerprinting_and_full_score(
    tmp_path: Path,
) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    _queued_submission(
        repository,
        tmp_path,
        "sub-learning-1",
        1,
        data_track=SubmissionDataTrack.LEARNING_1,
    )
    handle = ControlledScoreHandle("sub-learning-1")
    lock_manager = ReleaseLockManager(tmp_path / "locks", poll_interval_seconds=0.01)
    dispatcher = SubmissionScoringDispatcher(
        repository,
        ControlledRunner([handle]),
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1),
        release_lock_manager=lock_manager,
    )

    dispatcher.pump()
    assert handle.started.wait(5)
    writer_entered = threading.Event()

    def acquire_same_track_writer() -> None:
        with lock_manager.write("learning_1"):
            writer_entered.set()

    writer = threading.Thread(target=acquire_same_track_writer)
    writer.start()

    assert not writer_entered.wait(timeout=0.1)
    with lock_manager.write("learning_2"):
        pass

    handle.release.set()
    _wait_for_status(
        repository,
        "sub-learning-1",
        SubmissionStatus.COMPLETED,
    )
    assert writer_entered.wait(timeout=1)
    writer.join(timeout=1)
    assert not writer.is_alive()
    dispatcher.stop()


def test_dispatcher_honors_configured_concurrency(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    for index in range(1, 4):
        _queued_submission(repository, tmp_path, f"sub-{index}", index)
    handles = [ControlledScoreHandle(f"sub-{index}") for index in range(1, 4)]
    dispatcher = SubmissionScoringDispatcher(
        repository,
        ControlledRunner(handles),
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=2),
    )

    dispatcher.pump()

    assert handles[0].started.wait(5)
    assert handles[1].started.wait(5)
    assert not handles[2].started.is_set()
    handles[0].release.set()
    handles[1].release.set()
    handles[2].release.set()
    dispatcher.stop()


def test_dispatcher_uses_updated_concurrency_without_restart(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    for index in range(1, 3):
        _queued_submission(repository, tmp_path, f"sub-{index}", index)
    handles = [ControlledScoreHandle("sub-1"), ControlledScoreHandle("sub-2")]
    config = _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1)
    dispatcher = SubmissionScoringDispatcher(repository, ControlledRunner(handles), config)

    dispatcher.pump()
    assert handles[0].started.wait(5)
    assert not handles[1].started.is_set()
    ConfigRepository(config.path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(max_concurrent_scoring=2),
        )
    )
    dispatcher.pump()

    assert handles[1].started.wait(5)
    handles[0].release.set()
    handles[1].release.set()
    dispatcher.stop()


def test_dispatcher_marks_failures_and_continues_queue(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    _queued_submission(repository, tmp_path, "sub-1", 1)
    _queued_submission(repository, tmp_path, "sub-2", 2)
    second = ControlledScoreHandle("sub-2")
    runner = ControlledRunner([second])
    runner.fingerprint_failures_remaining = 1
    dispatcher = SubmissionScoringDispatcher(
        repository,
        runner,
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1),
    )

    dispatcher.pump()

    failed = _wait_for_status(repository, "sub-1", SubmissionStatus.FAILED)
    assert failed.error_message == "fingerprint setup exploded"
    assert second.started.wait(5)
    second.release.set()
    dispatcher.stop()


def test_dispatcher_saves_track_specific_config_snapshot(tmp_path: Path) -> None:
    class TrackAwareRunner(ControlledRunner):
        def current_config_snapshot(
            self,
            data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
        ) -> dict[str, object]:
            if data_track == SubmissionDataTrack.LEARNING:
                return {
                    "backtest": {
                        "data_start": "2010-01-01",
                        "scoring_start": "2010-01-01",
                        "scoring_end": "2022-12-31",
                    }
                }
            return {
                "backtest": {
                    "data_start": "2023-01-01",
                    "scoring_start": "2023-01-01",
                    "scoring_end": "2025-12-31",
                }
            }

    repository = SubmissionRepository(tmp_path / "runtime")
    _queued_submission(
        repository,
        tmp_path,
        "sub-learning",
        1,
        data_track=SubmissionDataTrack.LEARNING,
    )
    handle = ControlledScoreHandle("sub-learning")
    runner = TrackAwareRunner([handle])
    dispatcher = SubmissionScoringDispatcher(
        repository,
        runner,
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1),
    )

    dispatcher.pump()

    assert handle.started.wait(5)
    handle.release.set()
    stored = _wait_for_status(repository, "sub-learning", SubmissionStatus.COMPLETED)
    dispatcher.stop()

    assert runner.started == ["sub-learning:learning"]
    assert stored.config_snapshot == {
        "backtest": {
            "data_start": "2010-01-01",
            "scoring_start": "2010-01-01",
            "scoring_end": "2022-12-31",
        }
    }


def test_dispatcher_force_cancel_does_not_resurrect_deleted_submission(
    tmp_path: Path,
) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    _queued_submission(repository, tmp_path, "sub-1", 1)
    handle = ControlledScoreHandle("sub-1")
    dispatcher = SubmissionScoringDispatcher(
        repository,
        ControlledRunner([handle]),
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1),
    )
    dispatcher.pump()
    assert handle.started.wait(5)

    assert dispatcher.cancel_submission("sub-1") is True
    assert handle.terminated is True
    repository.delete("sub-1")
    time.sleep(0.05)

    assert repository.get("sub-1") is None
    dispatcher.stop()


def test_dispatcher_start_requeues_abandoned_running_submissions(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    _queued_submission(
        repository,
        tmp_path,
        "sub-abandoned",
        1,
        status=SubmissionStatus.RUNNING,
    )
    handle = ControlledScoreHandle("sub-abandoned")
    dispatcher = SubmissionScoringDispatcher(
        repository,
        ControlledRunner([handle]),
        _write_dispatcher_config(tmp_path / "platform.yaml", concurrency=1),
    )

    dispatcher.start()

    assert handle.started.wait(5)
    assert repository.get("sub-abandoned").status == SubmissionStatus.RUNNING
    handle.release.set()
    dispatcher.stop()


def test_submission_repository_loads_legacy_status_names(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    repository_path = runtime / "repositories" / "submissions.json"
    repository_path.parent.mkdir(parents=True)
    repository_path.write_text(
        json.dumps(
            [
                {
                    "submission_id": "sub-uploaded",
                    "team_id": "team-a",
                    "status": "uploaded",
                    "strategy_path": "strategy.py",
                    "report_dir": "report",
                    "fingerprints": None,
                    "original_filename": "strategy.py",
                    "submitted_at": "2026-06-18T08:00:00Z",
                },
                {
                    "submission_id": "sub-succeeded",
                    "team_id": "team-a",
                    "status": "succeeded",
                    "strategy_path": "strategy.py",
                    "report_dir": "report",
                    "fingerprints": None,
                    "original_filename": "strategy.py",
                    "submitted_at": "2026-06-18T09:00:00Z",
                },
            ]
        ),
        encoding="utf-8",
    )

    submissions = SubmissionRepository(runtime).list_all()

    assert [submission.status for submission in submissions] == [
        SubmissionStatus.QUEUED,
        SubmissionStatus.COMPLETED,
    ]
    assert [submission.submission_number for submission in submissions] == [1, 2]
    assert [submission.data_track for submission in submissions] == [
        SubmissionDataTrack.HIDDEN_TEST,
        SubmissionDataTrack.HIDDEN_TEST,
    ]


def test_submission_repository_persists_learning_data_track(tmp_path: Path) -> None:
    repository = SubmissionRepository(tmp_path / "runtime")
    repository.save(
        Submission(
            submission_id="sub-learning",
            team_id="team-a",
            status=SubmissionStatus.QUEUED,
            strategy_path="strategy.py",
            report_dir="report",
            fingerprints=None,
            original_filename="strategy.py",
            data_track=SubmissionDataTrack.LEARNING,
        )
    )

    reloaded = repository.get("sub-learning")

    assert reloaded is not None
    assert reloaded.data_track == SubmissionDataTrack.LEARNING


def test_submission_storage_validates_uploads_and_generates_student_text(
    tmp_path: Path,
) -> None:
    storage = SubmissionStorage(tmp_path / "runtime", max_upload_bytes=80)

    with pytest.raises(ValueError, match=re.escape("Python .py")):
        storage.store_strategy("sub-1", "strategy.txt", b"print('no')\n")
    with pytest.raises(ValueError, match="exceeds"):
        storage.store_strategy("sub-1", "strategy.py", b"x" * 81)

    path = storage.store_strategy(
        "sub-1",
        "strategy.py",
        b"def generate_signals(data):\n    return []\n",
    )
    assert path.name == "generate_signals.py"
    assert path.read_text(encoding="utf-8").startswith("def generate_signals")
    starter_text = storage.starter_strategy_text()
    compile(starter_text, "starter-strategy.py", "exec")
    assert "价格成交额动量 starter strategy" in starter_text
    assert "当天收益越高、成交越活跃" in starter_text
    assert "学生主要负责构造 score" in starter_text
    assert "generate_signals" in starter_text
    assert "dretwd" in starter_text
    assert "dnvaltrd" in starter_text
    assert "numeric_columns" in starter_text
    assert "pd.DataFrame" in starter_text
    assert "generate_signals.py" in storage.quickstart_text()
    assert "pytest backend/tests/test_factor_execution.py" in storage.quickstart_text()


@dataclass(frozen=True)
class AdapterSettings:
    config_path: Path
    engine_version: str
    scoring_timeout_seconds: int = 120


class FakePopen:
    stdout_payload = json.dumps({"total_return": 0.25, "trading_days": 3})
    stderr_payload = ""
    returncode_payload = 0
    timeout = False
    calls: ClassVar[dict[str, object]] = {}
    terminated = False
    killed = False

    def __init__(
        self,
        command: list[str],
        *,
        stdout: object,
        stderr: object,
        text: bool,
        cwd: Path,
        env: dict[str, str],
        start_new_session: bool,
    ):
        type(self).calls = {
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "text": text,
            "cwd": cwd,
            "env": env,
            "start_new_session": start_new_session,
        }
        self.pid = 999_999
        self.returncode = None

    def communicate(self, timeout: int | None = None) -> tuple[str, str]:
        type(self).calls["timeout"] = timeout
        if type(self).timeout:
            raise subprocess.TimeoutExpired(type(self).calls["command"], timeout)
        self.returncode = type(self).returncode_payload
        return type(self).stdout_payload, type(self).stderr_payload

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        type(self).terminated = True
        self.returncode = -15

    def kill(self) -> None:
        type(self).killed = True
        self.returncode = -9


def _reset_fake_popen() -> None:
    FakePopen.stdout_payload = json.dumps({"total_return": 0.25, "trading_days": 3})
    FakePopen.stderr_payload = ""
    FakePopen.returncode_payload = 0
    FakePopen.timeout = False
    FakePopen.calls = {}
    FakePopen.terminated = False
    FakePopen.killed = False


def test_backtest_submission_runner_uses_configured_hidden_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    hidden_root = tmp_path / "hidden"
    hidden_root.mkdir()
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root=(tmp_path / "raw").as_posix(),
                learning_output_root=(tmp_path / "learning").as_posix(),
                hidden_output_root=hidden_root.as_posix(),
                learning_start=date(2022, 1, 1),
                learning_end=date(2022, 12, 31),
                hidden_start=date(2023, 1, 3),
                hidden_end=date(2023, 1, 5),
            ),
            backtest=BacktestConfig(
                data_start=date(2022, 1, 1),
                scoring_start=date(2023, 1, 3),
                scoring_end=date(2023, 1, 5),
                group_count=3,
            ),
        )
    )
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_run_student_backtest(
        strategy: Path, data_root: Path, config: PlatformConfig
    ) -> object:
        calls["strategy"] = strategy
        calls["data_root"] = data_root
        calls["scoring_start"] = config.backtest.scoring_start.isoformat()
        calls["scoring_end"] = config.backtest.scoring_end.isoformat()
        calls["group_count"] = config.backtest.group_count
        return object()

    def fake_write_backtest_report(result: object, report_dir: Path) -> list[Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "summary.csv"
        pd.DataFrame([{"total_return": 0.5, "trading_days": 7}]).to_csv(
            summary_path,
            index=False,
        )
        (report_dir / "graph_data.json").write_text("{}", encoding="utf-8")
        (report_dir / "diagnostics.json").write_text("{}", encoding="utf-8")
        return [summary_path]

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.run_student_backtest",
        fake_run_student_backtest,
    )
    monkeypatch.setattr(
        "quantfish.submissions.score_worker.write_backtest_report",
        fake_write_backtest_report,
    )

    metrics = score_submission(config_path, strategy_path, tmp_path / "report")
    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))
    fingerprints = runner.current_fingerprints(strategy_path)

    assert calls == {
        "strategy": strategy_path,
        "data_root": hidden_root,
        "scoring_start": "2023-01-03",
        "scoring_end": "2023-01-05",
        "group_count": 3,
    }
    assert metrics.total_return == pytest.approx(0.5)
    assert metrics.trading_days == 7
    assert fingerprints.engine_version == "engine-x"
    assert fingerprints.data_track == SubmissionDataTrack.HIDDEN_TEST


def test_score_worker_uses_learning_release_and_dates_for_learning_track(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    learning_root = tmp_path / "learning"
    hidden_root = tmp_path / "hidden"
    learning_root.mkdir()
    hidden_root.mkdir()
    (learning_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root=(tmp_path / "raw").as_posix(),
                learning_output_root=learning_root.as_posix(),
                hidden_output_root=hidden_root.as_posix(),
                learning_start="2022-01-03",
                learning_end="2022-01-05",
                hidden_start="2023-01-03",
                hidden_end="2023-01-05",
            ),
            backtest=BacktestConfig(
                data_start="2023-01-03",
                scoring_start="2023-01-03",
                scoring_end="2023-01-05",
                group_count=3,
            ),
        )
    )
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_run_student_backtest(
        strategy: Path, data_root: Path, config: PlatformConfig
    ) -> object:
        calls["strategy"] = strategy
        calls["data_root"] = data_root
        calls["data_start"] = config.backtest.data_start.isoformat()
        calls["scoring_start"] = config.backtest.scoring_start.isoformat()
        calls["scoring_end"] = config.backtest.scoring_end.isoformat()
        calls["terminal_stale_position_policy"] = config.execution.terminal_stale_position_policy
        return object()

    def fake_write_backtest_report(result: object, report_dir: Path) -> list[Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "summary.csv"
        pd.DataFrame([{"total_return": 0.5, "trading_days": 3}]).to_csv(
            summary_path,
            index=False,
        )
        return [summary_path]

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.run_student_backtest",
        fake_run_student_backtest,
    )
    monkeypatch.setattr(
        "quantfish.submissions.score_worker.write_backtest_report",
        fake_write_backtest_report,
    )

    metrics = score_submission(
        config_path,
        strategy_path,
        tmp_path / "report",
        data_track=SubmissionDataTrack.LEARNING,
    )
    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))
    snapshot = runner.current_config_snapshot(SubmissionDataTrack.LEARNING)

    assert calls == {
        "strategy": strategy_path,
        "data_root": learning_root,
        "data_start": "2022-01-03",
        "scoring_start": "2022-01-03",
        "scoring_end": "2022-01-05",
        "terminal_stale_position_policy": "carry",
    }
    assert metrics.trading_days == 3
    assert snapshot["backtest"]["data_start"] == "2022-01-03"
    assert snapshot["backtest"]["scoring_start"] == "2022-01-03"
    assert snapshot["backtest"]["scoring_end"] == "2022-01-05"
    assert snapshot["execution"]["terminal_stale_position_policy"] == "carry"


def test_backtest_submission_runner_caches_fingerprint_context_until_release_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    hidden_root = tmp_path / "hidden"
    data_path = hidden_root / "data.csv"
    hidden_root.mkdir()
    data_path.write_text("value\n1\n", encoding="utf-8")
    DataCatalog(
        root=hidden_root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id="sample",
                aliases=[],
                csmar_table_code=None,
                relative_path="data.csv",
                format="csv",
                is_static=False,
            )
        ],
        metadata={"release_generation": "generation-1"},
    ).save(hidden_root / "data_catalog.json")
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root=(tmp_path / "raw").as_posix(),
                learning_output_root=(tmp_path / "learning").as_posix(),
                hidden_output_root=hidden_root.as_posix(),
            ),
            backtest=BacktestConfig(),
        )
    )
    calls: list[Path] = []

    def fake_sha256_release(path: Path | str) -> str:
        calls.append(Path(path))
        return f"release-{len(calls)}"

    monkeypatch.setattr("quantfish.submissions.runners.sha256_release", fake_sha256_release)
    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))

    first = runner.current_fingerprint_context(SubmissionDataTrack.HIDDEN_TEST)
    second = runner.current_fingerprint_context(SubmissionDataTrack.HIDDEN_TEST)

    assert first == second
    assert first.hidden_catalog_sha256 == "release-1"
    assert first.release_generation == "generation-1"
    assert runner.current_release_generation(SubmissionDataTrack.HIDDEN_TEST) == ("generation-1")
    assert calls == [hidden_root / "data_catalog.json"]

    data_path.write_text("value\n123\n", encoding="utf-8")
    third = runner.current_fingerprint_context(SubmissionDataTrack.HIDDEN_TEST)

    assert third.hidden_catalog_sha256 == "release-2"
    assert third.release_generation == "generation-1"
    assert len(calls) == 2


def test_backtest_submission_runner_caches_fingerprint_contexts_per_track(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    learning_root = tmp_path / "learning"
    hidden_root = tmp_path / "hidden"
    learning_root.mkdir()
    hidden_root.mkdir()
    (learning_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root=(tmp_path / "raw").as_posix(),
                learning_output_root=learning_root.as_posix(),
                hidden_output_root=hidden_root.as_posix(),
            ),
            backtest=BacktestConfig(),
        )
    )
    calls: list[Path] = []

    def fake_sha256_release(path: Path | str) -> str:
        path = Path(path)
        calls.append(path)
        return f"release:{path.parent.name}"

    monkeypatch.setattr("quantfish.submissions.runners.sha256_release", fake_sha256_release)
    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))

    hidden_first = runner.current_fingerprint_context(SubmissionDataTrack.HIDDEN_TEST)
    learning_first = runner.current_fingerprint_context(SubmissionDataTrack.LEARNING)
    hidden_second = runner.current_fingerprint_context(SubmissionDataTrack.HIDDEN_TEST)
    learning_second = runner.current_fingerprint_context(SubmissionDataTrack.LEARNING)

    assert hidden_second == hidden_first
    assert learning_second == learning_first
    assert calls == [
        hidden_root / "data_catalog.json",
        learning_root / "data_catalog.json",
    ]


def test_backtest_submission_runner_bounds_fingerprint_context_cache(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "platform.yaml"
    learning_root = tmp_path / "learning"
    hidden_root = tmp_path / "hidden"
    learning_root.mkdir()
    hidden_root.mkdir()
    (learning_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root=(tmp_path / "raw").as_posix(),
                learning_output_root=learning_root.as_posix(),
                hidden_output_root=hidden_root.as_posix(),
            ),
            backtest=BacktestConfig(),
        )
    )
    runner = BacktestSubmissionRunner(
        AdapterSettings(config_path, "engine-x"),
        fingerprint_context_cache_entries=1,
    )

    runner.current_fingerprint_context(SubmissionDataTrack.HIDDEN_TEST)
    runner.current_fingerprint_context(SubmissionDataTrack.LEARNING)

    assert len(runner._fingerprint_context_cache) == 1


def test_backtest_submission_runner_fingerprints_learning_release_separately(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "platform.yaml"
    learning_root = tmp_path / "learning"
    hidden_root = tmp_path / "hidden"
    learning_root.mkdir()
    hidden_root.mkdir()
    (learning_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root=(tmp_path / "raw").as_posix(),
                learning_output_root=learning_root.as_posix(),
                hidden_output_root=hidden_root.as_posix(),
            ),
            backtest=BacktestConfig(),
        )
    )
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))

    hidden = runner.current_fingerprints(strategy_path, SubmissionDataTrack.HIDDEN_TEST)
    learning = runner.current_fingerprints(strategy_path, SubmissionDataTrack.LEARNING)

    assert hidden.data_track == SubmissionDataTrack.HIDDEN_TEST
    assert learning.data_track == SubmissionDataTrack.LEARNING
    assert hidden.hidden_catalog_sha256 == learning.hidden_catalog_sha256
    (learning_root / "learning.csv").write_text("x\n1\n", encoding="utf-8")
    DataCatalog(
        root=learning_root.as_posix(),
        datasets=[
            DatasetSpec(
                dataset_id="learning",
                aliases=[],
                csmar_table_code=None,
                relative_path="learning.csv",
                format="csv",
                is_static=False,
            )
        ],
    ).save(learning_root / "data_catalog.json")
    changed_learning = runner.current_fingerprints(strategy_path, SubmissionDataTrack.LEARNING)
    assert changed_learning.hidden_catalog_sha256 != learning.hidden_catalog_sha256


def test_score_worker_resolves_relative_hidden_release_from_config_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    worker_cwd = tmp_path / "worker"
    hidden_root = project_root / "data_releases" / "hidden_test"
    hidden_root.mkdir(parents=True)
    worker_cwd.mkdir()
    (hidden_root / "data_catalog.json").write_text('{"datasets": []}\n', encoding="utf-8")
    config_dir = project_root / "config"
    config_dir.mkdir()
    config_path = config_dir / "platform.yaml"
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=CourseConfig(name="QuantFish"),
            data_releases=DataReleasesConfig(
                raw_data_root="raw",
                learning_output_root="learning",
                hidden_output_root="data_releases/hidden_test",
            ),
            backtest=BacktestConfig(group_count=3),
        )
    )
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    calls: dict[str, object] = {}

    def fake_run_student_backtest(
        strategy: Path, data_root: Path, config: PlatformConfig
    ) -> object:
        calls["strategy"] = strategy
        calls["data_root"] = data_root
        calls["group_count"] = config.backtest.group_count
        return object()

    def fake_write_backtest_report(result: object, report_dir: Path) -> list[Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "summary.csv"
        pd.DataFrame([{"total_return": 0.5, "trading_days": 7}]).to_csv(
            summary_path,
            index=False,
        )
        return [summary_path]

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.run_student_backtest",
        fake_run_student_backtest,
    )
    monkeypatch.setattr(
        "quantfish.submissions.score_worker.write_backtest_report",
        fake_write_backtest_report,
    )
    monkeypatch.chdir(worker_cwd)

    metrics = score_submission(config_path, strategy_path, tmp_path / "report")

    assert calls == {
        "strategy": strategy_path,
        "data_root": hidden_root,
        "group_count": 3,
    }
    assert metrics.trading_days == 7


def test_backtest_submission_runner_scores_in_isolated_worker_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(submission_timeout_seconds=7),
        )
    )
    strategy_path = tmp_path / "strategy.py"
    report_dir = tmp_path / "report"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    monkeypatch.setenv("QUANTFISH_ADMIN_PASSWORD", "secret-admin-password")
    _reset_fake_popen()
    monkeypatch.setattr("quantfish.submissions.runners.subprocess.Popen", FakePopen)

    runner = BacktestSubmissionRunner(
        AdapterSettings(config_path, "engine-x", scoring_timeout_seconds=7)
    )
    metrics = runner.score(strategy_path, report_dir)

    assert metrics.total_return == pytest.approx(0.25)
    assert metrics.trading_days == 3
    assert FakePopen.calls["timeout"] == 7
    assert FakePopen.calls["stdout"] == subprocess.PIPE
    assert FakePopen.calls["stderr"] == subprocess.PIPE
    assert FakePopen.calls["text"] is True
    assert FakePopen.calls["start_new_session"] is True
    assert FakePopen.calls["cwd"] == report_dir
    assert "QUANTFISH_ADMIN_PASSWORD" not in FakePopen.calls["env"]
    command = FakePopen.calls["command"]
    assert command[:3] == [sys.executable, "-m", "quantfish.submissions.score_worker"]
    assert command[command.index("--config") + 1] == config_path.as_posix()
    assert command[command.index("--strategy") + 1] == strategy_path.as_posix()
    assert command[command.index("--report-dir") + 1] == report_dir.as_posix()
    assert command[command.index("--data-track") + 1] == "hidden_test"


def test_backtest_submission_runner_reports_worker_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(submission_timeout_seconds=5),
        )
    )
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    _reset_fake_popen()
    FakePopen.timeout = True
    monkeypatch.setattr("quantfish.submissions.runners.subprocess.Popen", FakePopen)

    runner = BacktestSubmissionRunner(
        AdapterSettings(config_path, "engine-x", scoring_timeout_seconds=5)
    )
    with pytest.raises(TimeoutError, match="timed out after 5 seconds"):
        runner.score(strategy_path, tmp_path / "report")


def test_backtest_submission_runner_does_not_expose_worker_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(PlatformConfig.default())
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    _reset_fake_popen()
    FakePopen.returncode_payload = 1
    FakePopen.stdout_payload = "printed hidden 2025 return"
    FakePopen.stderr_payload = "/tmp/hidden/path SECRET-HIDDEN-DATA"
    monkeypatch.setattr("quantfish.submissions.runners.subprocess.Popen", FakePopen)

    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))
    with pytest.raises(RuntimeError) as exc_info:
        runner.score(strategy_path, tmp_path / "report")
    message = str(exc_info.value)
    assert "score worker failed" in message
    assert "SECRET-HIDDEN-DATA" not in message
    assert "/tmp/hidden/path" not in message


def test_backtest_submission_runner_uses_sanitized_worker_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(PlatformConfig.default())
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    report_dir = tmp_path / "report"
    report_dir.mkdir()
    (report_dir / WORKER_FAILURE_FILE).write_text(
        json.dumps(
            {
                "code": "terminal_stale_positions",
                "message": (
                    "Backtest ended with 3 unpriced terminal positions (gross exposure 0.125000)"
                ),
            }
        ),
        encoding="utf-8",
    )
    _reset_fake_popen()
    FakePopen.returncode_payload = 1
    FakePopen.stderr_payload = "/tmp/hidden/path SECRET-HIDDEN-DATA"
    monkeypatch.setattr("quantfish.submissions.runners.subprocess.Popen", FakePopen)

    runner = BacktestSubmissionRunner(AdapterSettings(config_path, "engine-x"))
    with pytest.raises(
        RuntimeError,
        match=(
            r"Backtest ended with 3 unpriced terminal positions "
            r"\(gross exposure 0\.125000\)"
        ),
    ):
        runner.score(strategy_path, report_dir)


def test_score_worker_records_terminal_failure_and_clears_it_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(PlatformConfig.default())
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    report_dir = tmp_path / "report"

    def fail_score(*_args: object, **_kwargs: object) -> SubmissionMetrics:
        raise TerminalStalePositionsError(["000001", "000002"], 0.25)

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.score_submission",
        fail_score,
    )
    argv = [
        "--config",
        config_path.as_posix(),
        "--strategy",
        strategy_path.as_posix(),
        "--report-dir",
        report_dir.as_posix(),
    ]

    assert score_worker_main(argv) == 1
    capsys.readouterr()
    assert json.loads((report_dir / WORKER_FAILURE_FILE).read_text(encoding="utf-8")) == {
        "code": "terminal_stale_positions",
        "message": ("Backtest ended with 2 unpriced terminal positions (gross exposure 0.250000)"),
    }
    assert "TerminalStalePositionsError" in (report_dir / "worker_error.log").read_text(
        encoding="utf-8"
    )

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.score_submission",
        lambda *_args, **_kwargs: SubmissionMetrics(total_return=0.1, trading_days=1),
    )

    assert score_worker_main(argv) == 0
    capsys.readouterr()
    assert not (report_dir / WORKER_FAILURE_FILE).exists()
    assert not (report_dir / "worker_error.log").exists()
    (report_dir / "worker_stdout.log").touch()
    (report_dir / "worker_stderr.log").touch()
    assert not submission_has_raw_error(SimpleNamespace(report_dir=report_dir, error_message=None))


def test_score_worker_keeps_student_stdout_out_of_machine_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(PlatformConfig.default())
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    def fake_run_student_backtest(
        strategy: Path, data_root: Path, config: BacktestConfig
    ) -> object:
        print("STUDENT-PRINTED-HIDDEN-DATA")
        return object()

    def fake_write_backtest_report(result: object, report_dir: Path) -> list[Path]:
        report_dir.mkdir(parents=True, exist_ok=True)
        summary_path = report_dir / "summary.csv"
        pd.DataFrame([{"total_return": 0.75, "trading_days": 4}]).to_csv(
            summary_path,
            index=False,
        )
        return [summary_path]

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.run_student_backtest",
        fake_run_student_backtest,
    )
    monkeypatch.setattr(
        "quantfish.submissions.score_worker.write_backtest_report",
        fake_write_backtest_report,
    )

    assert (
        score_worker_main(
            [
                "--config",
                config_path.as_posix(),
                "--strategy",
                strategy_path.as_posix(),
                "--report-dir",
                (tmp_path / "report").as_posix(),
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert "STUDENT-PRINTED-HIDDEN-DATA" not in captured.out
    payload = json.loads(captured.out)
    assert payload["total_return"] == pytest.approx(0.75)
    assert payload["trading_days"] == 4


def test_score_worker_hides_control_argv_while_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "platform.yaml"
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    observed: dict[str, list[str]] = {}
    monkeypatch.setattr(
        sys,
        "argv",
        [
            sys.executable,
            "-m",
            "quantfish.submissions.score_worker",
            "--config",
            "/tmp/hidden-config.yaml",
        ],
    )

    def fake_score_submission(
        config_path: Path,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> SubmissionMetrics:
        observed["argv"] = list(sys.argv)
        return SubmissionMetrics(total_return=0.1, trading_days=1)

    monkeypatch.setattr(
        "quantfish.submissions.score_worker.score_submission",
        fake_score_submission,
    )

    assert (
        score_worker_main(
            [
                "--config",
                config_path.as_posix(),
                "--strategy",
                strategy_path.as_posix(),
                "--report-dir",
                (tmp_path / "report").as_posix(),
            ]
        )
        == 0
    )

    capsys.readouterr()
    assert observed["argv"] == ["quantfish-score-worker"]
