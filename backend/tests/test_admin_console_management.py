import zipfile
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from quantfish.data.release_jobs import ReleaseBuildAlreadyRunning
from quantfish.platform_config import (
    ConfigRepository,
    DataReleasesConfig,
    ExecutionConfig,
    PlatformConfig,
)
from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionDataTrack,
    SubmissionMetrics,
    SubmissionStatus,
    Team,
)
from quantfish.submissions.staleness import ScoreFingerprintContext, sha256_file
from quantfish.web_app.app import create_app
from quantfish.web_app.settings import WebSettings


def _settings(tmp_path: Path, *, student_exports_enabled: bool = False) -> WebSettings:
    return WebSettings(
        runtime_root=tmp_path / "runtime",
        config_path=tmp_path / "platform.yaml",
        admin_password="quantfish-admin",
        admin_session_secret="test-session-secret",
        participant_session_secret="test-participant-session-secret",
        student_exports_enabled=student_exports_enabled,
    )


def _login(client: TestClient) -> None:
    response = client.post("/api/admin/login", json={"password": "quantfish-admin"})
    assert response.status_code == 200


def _write_student_export_source_data(root: Path) -> None:
    stock_dir = root / "distribute" / "stock"
    stock_dir.mkdir(parents=True)
    (stock_dir / "daily_returns.csv").write_text(
        "\n".join(
            [
                "TradingDate,Symbol,Ret",
                "2022-06-01,000001,0.01",
                "2023-06-01,000001,0.02",
                "2024-06-01,000001,0.03",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    market_dir = root / "distribute" / "market"
    market_dir.mkdir(parents=True)
    (market_dir / "index_daily.csv").write_text(
        "\n".join(
            [
                "indexcd,idxtrd01,idxtrd05,idxtrd08",
                "000300,2022-06-01,3900.0,1.0",
                "000300,2023-06-01,4000.0,1.0",
                "000300,2024-06-01,4100.0,1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class ContextCountingRunner:
    def __init__(self) -> None:
        self.context_calls = 0
        self.fingerprint_calls = 0
        self.context = ScoreFingerprintContext(
            config_sha256="config",
            hidden_catalog_sha256="catalog",
            engine_version="fake",
            data_track=SubmissionDataTrack.HIDDEN_TEST,
        )

    def current_fingerprint_context(
        self,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprintContext:
        self.context_calls += 1
        return ScoreFingerprintContext(
            config_sha256=self.context.config_sha256,
            hidden_catalog_sha256=self.context.hidden_catalog_sha256,
            engine_version=self.context.engine_version,
            data_track=data_track,
        )

    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        self.fingerprint_calls += 1
        return ScoreFingerprints(
            config_sha256=self.context.config_sha256,
            hidden_catalog_sha256=self.context.hidden_catalog_sha256,
            strategy_sha256=sha256_file(strategy_path),
            engine_version=self.context.engine_version,
            data_track=data_track,
        )

    def current_config_snapshot(self) -> dict[str, object]:
        return {}


class ExportRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.configs: list[PlatformConfig] = []

    def refresh(self, config: PlatformConfig) -> None:
        self.configs.append(config)
        if self.fail:
            raise RuntimeError("export refresh failed")


class PumpRecorder:
    def __init__(self) -> None:
        self.cancelled: list[str] = []
        self.pumps = 0

    def cancel_submission(self, submission_id: str) -> bool:
        self.cancelled.append(submission_id)
        return True

    def pump(self) -> None:
        self.pumps += 1


def test_admin_login_sets_httponly_session_cookie(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    assert client.get("/api/admin/settings").status_code == 401
    bad_login = client.post("/api/admin/login", json={"password": "wrong"})
    assert bad_login.status_code == 401

    login = client.post("/api/admin/login", json={"password": "quantfish-admin"})

    assert login.status_code == 200
    assert login.json() == {"authenticated": True}
    cookie = login.headers["set-cookie"]
    assert "quantfish_admin_session=" in cookie
    assert "HttpOnly" in cookie

    assert client.get("/api/admin/session").json() == {"authenticated": True}
    assert client.get("/api/admin/settings").status_code == 200

    logout = client.post("/api/admin/logout")

    assert logout.status_code == 200
    assert logout.json() == {"authenticated": False}
    assert client.get("/api/admin/settings").status_code == 401


def test_admin_data_release_routes_require_auth_and_start_selected_tracks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    service = app.state.services.data_release_build_service
    status_payload = {
        "source_available": True,
        "buildable_release_names": ["learning_1", "learning_2", "learning_3"],
        "releases": [
            {
                "release_name": "learning_1",
                "start": "2010-01-02",
                "end": "2015-12-31",
                "output_root": "data_releases/learning_1",
                "status": "missing",
                "last_built_at": None,
            }
        ],
        "job": None,
    }
    started: list[list[str]] = []
    job_payload = {
        "job_id": "job-1",
        "status": "queued",
        "release_names": ["learning_1", "learning_3"],
        "progress_percent": 0,
        "tracks": [
            {
                "release_name": release_name,
                "status": "queued",
                "phase": "queued",
                "progress_percent": 0,
                "completed_datasets": 0,
                "total_datasets": 0,
                "current_dataset": None,
                "error_message": None,
            }
            for release_name in ("learning_1", "learning_3")
        ],
        "created_at": "2026-07-24T08:00:00+00:00",
        "started_at": None,
        "finished_at": None,
        "current_release_name": None,
        "error_message": None,
    }
    monkeypatch.setattr(service, "status_payload", lambda: status_payload)

    def start(release_names: list[str]) -> dict[str, object]:
        started.append(release_names)
        return job_payload

    monkeypatch.setattr(service, "start", start)

    assert client.get("/api/admin/data-releases").status_code == 401
    assert (
        client.post(
            "/api/admin/data-releases/build",
            json={"release_names": ["learning_1"]},
        ).status_code
        == 401
    )
    _login(client)

    status_response = client.get("/api/admin/data-releases")
    start_response = client.post(
        "/api/admin/data-releases/build",
        json={"release_names": ["learning_1", "learning_3"]},
    )

    assert status_response.status_code == 200
    assert status_response.json() == status_payload
    assert start_response.status_code == 202
    assert start_response.json() == job_payload
    assert started == [["learning_1", "learning_3"]]
    assert (
        client.post(
            "/api/admin/data-releases/build",
            json={"release_names": ["learning"]},
        ).status_code
        == 422
    )


def test_admin_data_release_route_returns_conflict_for_active_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)
    _login(client)
    service = app.state.services.data_release_build_service

    def fail_start(_release_names: list[str]) -> None:
        raise ReleaseBuildAlreadyRunning("data release build already running: job-1")

    monkeypatch.setattr(service, "start", fail_start)

    response = client.post(
        "/api/admin/data-releases/build",
        json={"release_names": ["learning_2"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "data release build already running: job-1"


def test_admin_can_update_dataset_scoring_and_execution_settings(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    client = TestClient(create_app(settings))
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={
            "dataset": {
                "train_start": "2021-01-01",
                "train_end": "2022-06-30",
                "hidden_test_start": "2022-07-01",
                "hidden_test_end": "2024-12-31",
            },
            "scoring": {
                "sharpe_weight": 45.0,
                "sharpe_target": 2.0,
                "annual_return_weight": 35.0,
                "annual_return_target": 0.3,
                "drawdown_weight": 15.0,
                "drawdown_limit": 0.3,
                "turnover_weight": 5.0,
                "turnover_limit": 3.0,
                "short_profit_weight": 35.0,
                "short_profit_target": 0.25,
                "minimum_slice_trading_days": 120,
            },
            "execution": {
                "commission_rate": 0.001,
                "slippage_rate": 0.002,
                "sell_stamp_duty_rate": 0.0007,
                "max_leverage": 1.6,
                "top_k": 12,
                "allowed_market_types": [1, 4, 64],
                "submissions_enabled": False,
                "max_concurrent_scoring": 2,
                "submission_timeout_seconds": 45,
                "submission_timeout_enabled": True,
                "long_only": True,
                "terminal_stale_position_policy": "carry",
            },
            "backtest": {
                "capital": 1_250_000,
                "industry_neutralization": True,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset"] == {
        "train_start": "2021-01-01",
        "train_end": "2022-06-30",
        "hidden_test_start": "2022-07-01",
        "hidden_test_end": "2024-12-31",
    }
    assert payload["backtest"]["capital"] == 1_250_000
    assert payload["backtest"]["industry_neutralization"] is True
    assert payload["backtest"]["data_start"] == "2021-01-01"
    assert payload["backtest"]["scoring_start"] == "2022-07-01"
    assert payload["scoring"]["short_profit_weight"] == 35.0
    assert payload["scoring"]["short_profit_target"] == 0.25
    assert payload["execution"]["submissions_enabled"] is False
    assert "python_enabled" not in payload["execution"]
    assert payload["execution"]["allowed_market_types"] == [1, 4, 64]
    assert payload["execution"]["sell_stamp_duty_rate"] == pytest.approx(0.0007)
    assert payload["execution"]["terminal_stale_position_policy"] == "carry"

    stored = ConfigRepository(settings.config_path).load()
    assert stored.data_releases.learning_start.isoformat() == "2021-01-01"
    assert stored.data_releases.learning_end.isoformat() == "2022-06-30"
    assert stored.data_releases.hidden_start.isoformat() == "2022-07-01"
    assert stored.data_releases.hidden_end.isoformat() == "2024-12-31"
    assert stored.backtest.data_start.isoformat() == "2021-01-01"
    assert stored.backtest.scoring_start.isoformat() == "2022-07-01"
    assert stored.backtest.scoring_end.isoformat() == "2024-12-31"
    assert stored.backtest.capital == 1_250_000
    assert stored.backtest.industry_neutralization is True
    assert stored.scoring.minimum_slice_trading_days == 120
    assert stored.execution.allowed_market_types == (1, 4, 64)
    assert stored.execution.sell_stamp_duty_rate == pytest.approx(0.0007)
    assert stored.execution.terminal_stale_position_policy == "carry"
    assert stored.execution.submissions_enabled is False
    assert stored.execution.long_only is True

    invalid = client.patch(
        "/api/admin/settings",
        json={"backtest": {"capital": 0}},
    )
    assert invalid.status_code == 400
    assert "capital must be positive" in invalid.json()["detail"]
    assert ConfigRepository(settings.config_path).load().backtest.capital == 1_250_000


def test_admin_settings_refreshes_student_exports_before_saving(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, student_exports_enabled=True)
    app = create_app(settings)
    recorder = ExportRecorder()
    app.state.services.admin_service.student_export_service = recorder
    client = TestClient(app)
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={
            "dataset": {
                "train_start": "2021-01-01",
                "train_end": "2022-06-30",
                "hidden_test_start": "2022-07-01",
                "hidden_test_end": "2024-12-31",
            }
        },
    )

    assert response.status_code == 200
    assert len(recorder.configs) == 1
    proposed = recorder.configs[0]
    assert proposed.data_releases.learning_start.isoformat() == "2021-01-01"
    assert proposed.data_releases.learning_end.isoformat() == "2022-06-30"
    assert proposed.data_releases.hidden_start.isoformat() == "2022-07-01"
    assert proposed.data_releases.hidden_end.isoformat() == "2024-12-31"
    assert proposed.backtest.data_start.isoformat() == "2021-01-01"
    assert proposed.backtest.scoring_start.isoformat() == "2022-07-01"
    assert proposed.backtest.scoring_end.isoformat() == "2024-12-31"
    assert ConfigRepository(settings.config_path).load() == proposed


def test_admin_execution_settings_do_not_refresh_student_exports(tmp_path: Path) -> None:
    settings = _settings(tmp_path, student_exports_enabled=True)
    ConfigRepository(settings.config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(top_k=100),
        )
    )
    app = create_app(settings)
    recorder = ExportRecorder()
    app.state.services.admin_service.student_export_service = recorder
    client = TestClient(app)
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={"execution": {"top_k": None}},
    )

    assert response.status_code == 200
    assert response.json()["execution"]["top_k"] is None
    assert recorder.configs == []
    assert ConfigRepository(settings.config_path).load().execution.top_k is None


def test_admin_market_scope_settings_do_not_refresh_student_exports(tmp_path: Path) -> None:
    settings = _settings(tmp_path, student_exports_enabled=True)
    ConfigRepository(settings.config_path).save(PlatformConfig.default())
    app = create_app(settings)
    recorder = ExportRecorder()
    app.state.services.admin_service.student_export_service = recorder
    client = TestClient(app)
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={"execution": {"allowed_market_types": [1, 4, 64]}},
    )

    assert response.status_code == 200
    assert response.json()["execution"]["allowed_market_types"] == [1, 4, 64]
    assert recorder.configs == []
    assert ConfigRepository(settings.config_path).load().execution.allowed_market_types == (
        1,
        4,
        64,
    )


def test_disabled_submissions_reject_public_uploads(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    ConfigRepository(settings.config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=PlatformConfig.default().data_releases,
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=ExecutionConfig(submissions_enabled=False),
        )
    )
    app = create_app(settings)
    app.state.services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )
    client = TestClient(app)

    response = client.post(
        "/api/submissions",
        data={"team_name": "Alpha Desk", "password": "secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Submissions are disabled"
    assert app.state.services.submission_repository.list_all() == []


def test_admin_dataset_settings_rebuild_student_download_with_new_learning_data(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, student_exports_enabled=True)
    raw_data_root = tmp_path / "new_data"
    _write_student_export_source_data(raw_data_root)
    ConfigRepository(settings.config_path).save(
        PlatformConfig(
            course=PlatformConfig.default().course,
            data_releases=DataReleasesConfig(
                raw_data_root=raw_data_root.as_posix(),
                learning_output_root=(tmp_path / "releases" / "learning").as_posix(),
                hidden_output_root=(tmp_path / "releases" / "hidden_test").as_posix(),
                learning_start=PlatformConfig.default().data_releases.learning_start,
                learning_end=PlatformConfig.default().data_releases.learning_end,
                hidden_start=PlatformConfig.default().data_releases.hidden_start,
                hidden_end=PlatformConfig.default().data_releases.hidden_end,
            ),
            backtest=PlatformConfig.default().backtest,
            scoring=PlatformConfig.default().scoring,
            execution=PlatformConfig.default().execution,
        )
    )
    client = TestClient(create_app(settings))
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={
            "dataset": {
                "train_start": "2022-01-01",
                "train_end": "2023-06-30",
                "hidden_test_start": "2023-07-01",
                "hidden_test_end": "2024-12-31",
            }
        },
    )

    assert response.status_code == 200
    zip_path = settings.exports_root / "student" / "learning-data.zip"
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        with archive.open("data_releases/learning/distribute/stock/daily_returns.csv") as handle:
            learning_returns = pd.read_csv(handle)
    assert learning_returns["TradingDate"].tolist() == ["2022-06-01", "2023-06-01"]
    assert "docs/student/README.md" in names


def test_dataset_update_preserves_completed_results_until_manual_stale_mark(
    tmp_path: Path,
) -> None:
    runner = ContextCountingRunner()
    settings = _settings(tmp_path, student_exports_enabled=True)
    app = create_app(settings, submission_runner=runner)
    services = app.state.services
    export_recorder = ExportRecorder()
    pump_recorder = PumpRecorder()
    services.admin_service.student_export_service = export_recorder
    services.admin_service.scoring_dispatcher = pump_recorder
    services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )
    strategy_path = settings.submissions_root / "sub-old" / "generate_signals.py"
    strategy_path.parent.mkdir(parents=True)
    strategy_path.write_text(
        "def generate_signals(data):\n    return []\n",
        encoding="utf-8",
    )
    old_fingerprints = runner.current_fingerprints(
        strategy_path,
        SubmissionDataTrack.LEARNING,
    )
    services.submission_repository.save(
        Submission(
            submission_id="sub-old",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(settings.reports_root / "sub-old").as_posix(),
            fingerprints=old_fingerprints,
            original_filename="old.py",
            data_track=SubmissionDataTrack.LEARNING,
            metrics=SubmissionMetrics(total_return=0.2, sharpe=1.1),
            scored_at="2026-01-01T00:00:00+00:00",
        )
    )
    services.submission_repository.save(
        Submission(
            submission_id="sub-running",
            team_id="team-alpha",
            status=SubmissionStatus.RUNNING,
            strategy_path=strategy_path.as_posix(),
            report_dir=(settings.reports_root / "sub-running").as_posix(),
            fingerprints=old_fingerprints,
            original_filename="running.py",
            data_track=SubmissionDataTrack.LEARNING,
        )
    )
    runner.context = ScoreFingerprintContext(
        config_sha256="new-config",
        hidden_catalog_sha256="new-catalog",
        engine_version="fake",
        data_track=SubmissionDataTrack.LEARNING,
    )
    client = TestClient(app)
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={
            "dataset": {
                "train_start": "2020-01-01",
                "train_end": "2022-12-31",
                "hidden_test_start": "2023-01-01",
                "hidden_test_end": "2025-12-31",
            }
        },
    )

    assert response.status_code == 200
    assert len(export_recorder.configs) == 1
    assert pump_recorder.cancelled == ["sub-running"]
    assert pump_recorder.pumps == 1
    completed = services.submission_repository.get("sub-old")
    running = services.submission_repository.get("sub-running")
    assert completed is not None
    assert running is not None
    assert completed.status == SubmissionStatus.COMPLETED
    assert completed.metrics == SubmissionMetrics(total_return=0.2, sharpe=1.1)
    assert completed.fingerprints == old_fingerprints
    assert completed.scored_at == "2026-01-01T00:00:00+00:00"
    assert running.status == SubmissionStatus.QUEUED
    assert running.fingerprints is None

    mark_response = client.post("/api/admin/stale-marks")
    assert mark_response.status_code == 200
    assert mark_response.json()["settings_history"][0]["affected_submission_ids"] == ["sub-old"]
    assert client.get("/api/submissions/sub-old").json()["stale"] is True


def test_admin_settings_does_not_save_when_export_refresh_fails(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, student_exports_enabled=True)
    ConfigRepository(settings.config_path).save(PlatformConfig.default())
    app = create_app(settings)
    app.state.services.admin_service.student_export_service = ExportRecorder(fail=True)
    client = TestClient(app)
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={
            "dataset": {
                "train_start": "2021-01-01",
                "train_end": "2022-06-30",
                "hidden_test_start": "2022-07-01",
                "hidden_test_end": "2024-12-31",
            }
        },
    )

    assert response.status_code == 500
    assert "export refresh failed" in response.json()["detail"]
    assert ConfigRepository(settings.config_path).load() == PlatformConfig.default()


def test_admin_team_lifecycle_uses_generated_ids_and_never_lists_passwords(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    client = TestClient(create_app(settings))
    _login(client)

    created = client.post(
        "/api/admin/teams",
        json={"team_name": "Alpha Desk", "password": "first-secret"},
    )

    assert created.status_code == 200
    team = created.json()
    assert team["team_name"] == "Alpha Desk"
    assert team["password"] == "first-secret"
    assert team["team_id"].startswith("team-")

    teams_text = (settings.repositories_root / "teams.json").read_text(encoding="utf-8")
    assert "first-secret" not in teams_text

    listed = client.get("/api/admin/teams").json()
    assert listed["active_teams"][0]["team_name"] == "Alpha Desk"
    assert listed["active_teams"][0]["password"] is None

    edited = client.patch(
        f"/api/admin/teams/{team['team_id']}",
        json={"team_name": "Alpha Renamed", "password": "second-secret"},
    )

    assert edited.status_code == 200
    assert edited.json()["team_name"] == "Alpha Renamed"
    assert edited.json()["password"] == "second-secret"
    assert "second-secret" not in (settings.repositories_root / "teams.json").read_text(
        encoding="utf-8"
    )

    assert client.post(
        "/api/submissions",
        data={"team_name": "Alpha Renamed", "password": "second-secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    ).status_code in {200, 500}

    archive = client.post(
        "/api/admin/teams/bulk-action",
        json={"team_ids": [team["team_id"]], "action": "archive"},
    )
    assert archive.status_code == 200
    assert archive.json()["archived"] == 1
    listed_after_archive = client.get("/api/admin/teams").json()
    assert listed_after_archive["active_teams"] == []
    assert listed_after_archive["archived_teams"][0]["status"] == "archived"

    delete = client.post(
        "/api/admin/teams/bulk-action",
        json={"team_ids": [team["team_id"]], "action": "delete"},
    )
    assert delete.status_code == 200
    assert delete.json()["deleted"] == 0
    assert delete.json()["skipped"] == 1

    restore = client.post(
        "/api/admin/teams/bulk-action",
        json={"team_ids": [team["team_id"]], "action": "restore"},
    )
    assert restore.status_code == 200
    assert restore.json()["restored"] == 1


def test_admin_team_cohorts_manage_membership_and_dedicated_history(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    services = app.state.services
    client = TestClient(app)
    _login(client)

    alpha = client.post(
        "/api/admin/teams",
        json={"team_name": "Alpha Desk", "password": "alpha-secret"},
    ).json()
    beta = client.post(
        "/api/admin/teams",
        json={"team_name": "Beta Fund", "password": "beta-secret"},
    ).json()

    cohort_response = client.post(
        "/api/admin/team-cohorts",
        json={
            "name": "Table 1",
            "team_ids": [alpha["team_id"]],
            "history_visible": False,
            "submissions_enabled": True,
        },
    )

    assert cohort_response.status_code == 200
    cohort = cohort_response.json()
    assert cohort["name"] == "Table 1"
    assert cohort["team_ids"] == [alpha["team_id"]]
    assert cohort["history_visible"] is False
    assert cohort["submissions_enabled"] is True

    listed = client.get("/api/admin/teams").json()
    alpha_record = next(
        team for team in listed["active_teams"] if team["team_id"] == alpha["team_id"]
    )
    beta_record = next(
        team for team in listed["active_teams"] if team["team_id"] == beta["team_id"]
    )
    assert alpha_record["cohort_id"] == cohort["cohort_id"]
    assert alpha_record["cohort_name"] == "Table 1"
    assert alpha_record["history_visible"] is False
    assert alpha_record["submissions_enabled"] is True
    assert beta_record["cohort_id"] is None
    assert beta_record["history_visible"] is True
    assert listed["cohorts"] == [cohort]

    strategy_path = settings.submissions_root / "alpha-hidden" / "generate_signals.py"
    strategy_path.parent.mkdir(parents=True)
    strategy_source = "def generate_signals(data):\n    return []\n"
    strategy_path.write_text(strategy_source, encoding="utf-8")
    report_dir = settings.reports_root / "alpha-hidden"
    report_dir.mkdir(parents=True)
    (report_dir / "worker_error.log").write_text("cohort raw error", encoding="utf-8")
    services.submission_repository.save(
        Submission(
            submission_id="alpha-hidden",
            team_id=alpha["team_id"],
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=report_dir.as_posix(),
            fingerprints=ScoreFingerprints(
                config_sha256="config",
                hidden_catalog_sha256="catalog",
                strategy_sha256="strategy",
                engine_version="fake",
            ),
            original_filename="alpha.py",
            metrics=SubmissionMetrics(total_return=0.2, sharpe=1.1),
        )
    )

    regular_admin_history = client.get("/api/admin/submissions").json()
    cohort_history = client.get(f"/api/admin/team-cohorts/{cohort['cohort_id']}/submissions").json()

    assert regular_admin_history["submissions"] == []
    assert cohort_history["total_count"] == 1
    assert cohort_history["submissions"][0]["submission_id"] == "alpha-hidden"
    cohort_source = client.get(
        f"/api/admin/team-cohorts/{cohort['cohort_id']}/submissions/alpha-hidden/source"
    )
    cohort_raw_error = client.get(
        f"/api/admin/team-cohorts/{cohort['cohort_id']}/submissions/alpha-hidden/raw-error"
    )
    assert cohort_source.status_code == 200
    assert cohort_source.text == strategy_source
    assert cohort_raw_error.status_code == 200
    assert cohort_raw_error.text == "cohort raw error"

    updated = client.patch(
        f"/api/admin/team-cohorts/{cohort['cohort_id']}",
        json={
            "name": "Table 2",
            "team_ids": [beta["team_id"]],
            "history_visible": True,
            "submissions_enabled": False,
        },
    ).json()
    assert updated["name"] == "Table 2"
    assert updated["team_ids"] == [beta["team_id"]]
    assert updated["submissions_enabled"] is False

    relisted = client.get("/api/admin/teams").json()
    moved_alpha = next(
        team for team in relisted["active_teams"] if team["team_id"] == alpha["team_id"]
    )
    moved_beta = next(
        team for team in relisted["active_teams"] if team["team_id"] == beta["team_id"]
    )
    assert moved_alpha["cohort_id"] is None
    assert moved_alpha["history_visible"] is True
    assert moved_beta["cohort_id"] == cohort["cohort_id"]
    assert moved_beta["submissions_enabled"] is False

    delete = client.delete(f"/api/admin/team-cohorts/{cohort['cohort_id']}")
    assert delete.status_code == 200
    assert delete.json() == {"deleted": True}
    assert client.get("/api/admin/teams").json()["cohorts"] == []


def test_admin_submission_records_include_raw_details_and_delete_safely(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    services = app.state.services

    class CancelRecorder:
        def __init__(self) -> None:
            self.cancelled: list[str] = []
            self.pumps = 0

        def cancel_submission(self, submission_id: str) -> bool:
            self.cancelled.append(submission_id)
            return True

        def pump(self) -> None:
            self.pumps += 1

    cancel_recorder = CancelRecorder()
    services.admin_service.scoring_dispatcher = cancel_recorder
    services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )

    safe_strategy = settings.submissions_root / "sub-done" / "generate_signals.py"
    safe_strategy.parent.mkdir(parents=True)
    safe_strategy.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    outside_strategy = tmp_path / "outside.py"
    outside_strategy.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")

    report_dir = settings.reports_root / "sub-done"
    report_dir.mkdir(parents=True)
    (report_dir / "worker_error.log").write_text("Traceback: raw failure", encoding="utf-8")

    fingerprints = ScoreFingerprints(
        config_sha256="config",
        hidden_catalog_sha256="catalog",
        strategy_sha256="strategy",
        engine_version="engine",
    )
    services.submission_repository.save(
        Submission(
            submission_id="sub-done",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path=safe_strategy.as_posix(),
            report_dir=report_dir.as_posix(),
            fingerprints=fingerprints,
            original_filename="done.py",
            metrics=SubmissionMetrics(total_return=0.2, sharpe=1.1),
            config_snapshot={"course": {"name": "QuantFish"}},
        )
    )
    services.submission_repository.save(
        Submission(
            submission_id="sub-active",
            team_id="team-alpha",
            status=SubmissionStatus.RUNNING,
            strategy_path=outside_strategy.as_posix(),
            report_dir=(settings.reports_root / "sub-active").as_posix(),
            fingerprints=fingerprints,
            original_filename="active.py",
            metrics=None,
        )
    )

    client = TestClient(app)

    unauthorized_source = client.get("/api/admin/submissions/sub-done/source")
    assert unauthorized_source.status_code == 401

    _login(client)

    submissions_response = client.get("/api/admin/submissions")
    submissions_payload = submissions_response.json()
    assert submissions_payload["total_count"] == 2
    assert submissions_payload["limit"] == 100
    records = submissions_payload["submissions"]
    done = next(item for item in records if item["submission_id"] == "sub-done")
    active = next(item for item in records if item["submission_id"] == "sub-active")
    assert done["status"] == "completed"
    assert done["has_raw_error"] is True
    assert "raw_error" not in done
    assert done["config_snapshot"] == {"course": {"name": "QuantFish"}}
    assert done["file_paths"]["strategy_path"] == safe_strategy.as_posix()
    assert active["selectable"] is False

    raw_error_response = client.get("/api/admin/submissions/sub-done/raw-error")
    assert raw_error_response.status_code == 200
    assert raw_error_response.text == "Traceback: raw failure"

    source_response = client.get("/api/admin/submissions/sub-done/source")
    assert source_response.status_code == 200
    assert source_response.headers["content-type"].startswith("text/plain")
    assert source_response.text == "def generate_signals(data):\n    return []\n"

    delete = client.post(
        "/api/admin/submissions/delete",
        json={"submission_ids": ["sub-done", "sub-active"], "force": False},
    )

    assert delete.status_code == 200
    delete_payload = delete.json()
    assert delete_payload["deleted"] == 1
    assert delete_payload["skipped"] == 1
    assert safe_strategy.exists() is False
    assert outside_strategy.exists() is True
    assert services.submission_repository.get("sub-done") is None
    assert services.submission_repository.get("sub-active") is not None

    forced = client.post(
        "/api/admin/submissions/delete",
        json={"submission_ids": ["sub-active"], "force": True},
    )

    assert forced.status_code == 200
    assert forced.json()["deleted"] == 1
    assert cancel_recorder.cancelled == ["sub-active"]
    assert cancel_recorder.pumps == 1
    assert outside_strategy.exists() is True


def test_admin_rerun_all_requeues_terminal_visible_submissions_and_preserves_history_order(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    services = app.state.services
    pump_recorder = PumpRecorder()
    services.admin_service.scoring_dispatcher = pump_recorder
    services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )
    strategy_path = settings.submissions_root / "strategy.py"
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    fingerprints = ScoreFingerprints(
        config_sha256="config",
        hidden_catalog_sha256="catalog",
        strategy_sha256="strategy",
        engine_version="engine",
    )
    rows = [
        ("completed-old", SubmissionStatus.COMPLETED, 1, "2026-06-19T09:00:00+00:00"),
        ("failed-middle", SubmissionStatus.FAILED, 2, "2026-06-19T10:00:00+00:00"),
        ("queued-new", SubmissionStatus.QUEUED, 3, "2026-06-19T11:00:00+00:00"),
        ("running-latest", SubmissionStatus.RUNNING, 4, "2026-06-19T12:00:00+00:00"),
    ]
    for submission_id, status, submission_number, submitted_at in rows:
        services.submission_repository.save(
            Submission(
                submission_id=submission_id,
                team_id="team-alpha",
                status=status,
                strategy_path=strategy_path.as_posix(),
                report_dir=(settings.reports_root / submission_id).as_posix(),
                fingerprints=fingerprints,
                original_filename=f"{submission_id}.py",
                submission_number=submission_number,
                metrics=SubmissionMetrics(total_return=0.2, sharpe=1.1)
                if status == SubmissionStatus.COMPLETED
                else None,
                error_message="failed" if status == SubmissionStatus.FAILED else None,
                submitted_at=submitted_at,
                scored_at="2026-06-20T00:00:00+00:00"
                if status in {SubmissionStatus.COMPLETED, SubmissionStatus.FAILED}
                else None,
            )
        )
    client = TestClient(app)
    _login(client)
    before = client.get(
        "/api/submissions",
        params={"sort_by": "submission_number", "sort_dir": "asc"},
    ).json()["submissions"]

    response = client.post("/api/admin/submissions/rerun", json={"scope": "all"})

    assert response.status_code == 200
    assert response.json() == {
        "queued": 2,
        "skipped": 2,
        "queued_submission_ids": ["completed-old", "failed-middle"],
        "skipped_submission_ids": ["queued-new", "running-latest"],
    }
    assert pump_recorder.pumps == 1
    assert pump_recorder.cancelled == []
    completed = services.submission_repository.get("completed-old")
    failed = services.submission_repository.get("failed-middle")
    queued = services.submission_repository.get("queued-new")
    running = services.submission_repository.get("running-latest")
    assert completed is not None
    assert failed is not None
    assert queued is not None
    assert running is not None
    assert completed.status == SubmissionStatus.QUEUED
    assert completed.metrics is None
    assert completed.error_message is None
    assert completed.scored_at is None
    assert completed.submission_number == 1
    assert completed.submitted_at == "2026-06-19T09:00:00+00:00"
    assert failed.status == SubmissionStatus.QUEUED
    assert failed.error_message is None
    assert queued.status == SubmissionStatus.QUEUED
    assert running.status == SubmissionStatus.RUNNING
    after = client.get(
        "/api/submissions",
        params={"sort_by": "submission_number", "sort_dir": "asc"},
    ).json()["submissions"]
    assert [row["submission_id"] for row in after] == [row["submission_id"] for row in before]


def test_admin_rerun_selected_requeues_terminal_rows_and_reports_skips(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    services = app.state.services
    pump_recorder = PumpRecorder()
    services.admin_service.scoring_dispatcher = pump_recorder
    services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )
    strategy_path = settings.submissions_root / "strategy.py"
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    fingerprints = ScoreFingerprints(
        config_sha256="config",
        hidden_catalog_sha256="catalog",
        strategy_sha256="strategy",
        engine_version="engine",
    )
    for submission_id, status in [
        ("completed-sub", SubmissionStatus.COMPLETED),
        ("running-sub", SubmissionStatus.RUNNING),
    ]:
        services.submission_repository.save(
            Submission(
                submission_id=submission_id,
                team_id="team-alpha",
                status=status,
                strategy_path=strategy_path.as_posix(),
                report_dir=(settings.reports_root / submission_id).as_posix(),
                fingerprints=fingerprints,
                original_filename=f"{submission_id}.py",
                metrics=SubmissionMetrics(total_return=0.2, sharpe=1.1)
                if status == SubmissionStatus.COMPLETED
                else None,
            )
        )
    client = TestClient(app)
    _login(client)

    response = client.post(
        "/api/admin/submissions/rerun",
        json={
            "scope": "selected",
            "submission_ids": [
                "completed-sub",
                "running-sub",
                "missing-sub",
                "completed-sub",
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "queued": 1,
        "skipped": 3,
        "queued_submission_ids": ["completed-sub"],
        "skipped_submission_ids": ["running-sub", "missing-sub", "completed-sub"],
    }
    assert pump_recorder.pumps == 1
    assert services.submission_repository.get("completed-sub").status == SubmissionStatus.QUEUED
    assert services.submission_repository.get("running-sub").status == SubmissionStatus.RUNNING


def test_admin_cohort_rerun_all_is_scoped_to_hidden_cohort_submissions(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    services = app.state.services
    pump_recorder = PumpRecorder()
    services.admin_service.scoring_dispatcher = pump_recorder
    client = TestClient(app)
    _login(client)
    alpha = client.post(
        "/api/admin/teams",
        json={"team_name": "Alpha Desk", "password": "secret"},
    ).json()
    beta = client.post(
        "/api/admin/teams",
        json={"team_name": "Beta Desk", "password": "secret"},
    ).json()
    cohort = client.post(
        "/api/admin/team-cohorts",
        json={
            "name": "Hidden cohort",
            "team_ids": [alpha["team_id"]],
            "history_visible": False,
            "submissions_enabled": True,
        },
    ).json()
    strategy_path = settings.submissions_root / "strategy.py"
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    fingerprints = ScoreFingerprints(
        config_sha256="config",
        hidden_catalog_sha256="catalog",
        strategy_sha256="strategy",
        engine_version="engine",
    )
    for submission_id, team_id in [
        ("alpha-hidden", alpha["team_id"]),
        ("beta-visible", beta["team_id"]),
    ]:
        services.submission_repository.save(
            Submission(
                submission_id=submission_id,
                team_id=team_id,
                status=SubmissionStatus.COMPLETED,
                strategy_path=strategy_path.as_posix(),
                report_dir=(settings.reports_root / submission_id).as_posix(),
                fingerprints=fingerprints,
                original_filename=f"{submission_id}.py",
                metrics=SubmissionMetrics(total_return=0.2, sharpe=1.1),
            )
        )

    response = client.post(
        f"/api/admin/team-cohorts/{cohort['cohort_id']}/submissions/rerun",
        json={"scope": "all"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "queued": 1,
        "skipped": 0,
        "queued_submission_ids": ["alpha-hidden"],
        "skipped_submission_ids": [],
    }
    assert pump_recorder.pumps == 1
    assert services.submission_repository.get("alpha-hidden").status == SubmissionStatus.QUEUED
    assert services.submission_repository.get("beta-visible").status == SubmissionStatus.COMPLETED


def test_admin_rerun_requires_authentication(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    client = TestClient(app)

    response = client.post("/api/admin/submissions/rerun", json={"scope": "all"})
    cohort_response = client.post(
        "/api/admin/team-cohorts/cohort-hidden/submissions/rerun",
        json={"scope": "all"},
    )

    assert response.status_code == 401
    assert cohort_response.status_code == 401


def test_admin_backfill_short_profit_requeues_only_missing_completed_submissions(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    services = app.state.services
    pump_recorder = PumpRecorder()
    services.admin_service.scoring_dispatcher = pump_recorder
    services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )
    strategy_path = settings.submissions_root / "strategy.py"
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    fingerprints = ScoreFingerprints(
        config_sha256="config",
        hidden_catalog_sha256="catalog",
        strategy_sha256="strategy",
        engine_version="engine",
    )
    for submission_id, metrics in [
        ("missing-short-profit", SubmissionMetrics(total_return=0.2, sharpe=1.1)),
        (
            "already-backfilled",
            SubmissionMetrics(total_return=0.2, sharpe=1.1, annualized_short_profit=0.05),
        ),
    ]:
        services.submission_repository.save(
            Submission(
                submission_id=submission_id,
                team_id="team-alpha",
                status=SubmissionStatus.COMPLETED,
                strategy_path=strategy_path.as_posix(),
                report_dir=(settings.reports_root / submission_id).as_posix(),
                fingerprints=fingerprints,
                original_filename=f"{submission_id}.py",
                metrics=metrics,
            )
        )
    services.submission_repository.save(
        Submission(
            submission_id="failed-missing",
            team_id="team-alpha",
            status=SubmissionStatus.FAILED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(settings.reports_root / "failed-missing").as_posix(),
            fingerprints=fingerprints,
            original_filename="failed.py",
            metrics=None,
        )
    )
    client = TestClient(app)
    _login(client)

    response = client.post("/api/admin/submissions/backfill-short-profit")

    assert response.status_code == 200
    assert response.json() == {
        "queued": 1,
        "submission_ids": ["missing-short-profit"],
    }
    assert pump_recorder.pumps == 1
    assert (
        services.submission_repository.get("missing-short-profit").status == SubmissionStatus.QUEUED
    )
    assert services.submission_repository.get("missing-short-profit").metrics is None
    assert (
        services.submission_repository.get("already-backfilled").status
        == SubmissionStatus.COMPLETED
    )
    assert services.submission_repository.get("failed-missing").status == SubmissionStatus.FAILED


def test_admin_submission_list_does_not_call_fingerprints_for_stale_state(
    tmp_path: Path,
) -> None:
    runner = ContextCountingRunner()
    settings = _settings(tmp_path)
    app = create_app(settings, submission_runner=runner)
    services = app.state.services
    services.team_repository.save(
        Team.from_plaintext_password(
            team_id="team-alpha", display_name="Alpha Desk", password="secret"
        )
    )
    for index in range(2):
        strategy_path = settings.submissions_root / f"sub-{index}" / "generate_signals.py"
        strategy_path.parent.mkdir(parents=True)
        strategy_path.write_text(
            f"def generate_signals(data):\n    return [{index}]\n",
            encoding="utf-8",
        )
        services.submission_repository.save(
            Submission(
                submission_id=f"sub-{index}",
                team_id="team-alpha",
                status=SubmissionStatus.COMPLETED,
                strategy_path=strategy_path.as_posix(),
                report_dir=(settings.reports_root / f"sub-{index}").as_posix(),
                fingerprints=runner.current_fingerprints(strategy_path),
                original_filename=f"strategy-{index}.py",
                metrics=SubmissionMetrics(total_return=0.1, sharpe=1.0),
            )
        )
    runner.context_calls = 0
    runner.fingerprint_calls = 0
    client = TestClient(app)
    _login(client)

    response = client.get("/api/admin/submissions")

    assert response.status_code == 200
    assert len(response.json()["submissions"]) == 2
    assert runner.context_calls == 0
    assert runner.fingerprint_calls == 0
