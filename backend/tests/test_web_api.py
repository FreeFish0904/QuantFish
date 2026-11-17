from datetime import datetime
import json
from pathlib import Path
import re
import time
import zipfile

from fastapi.testclient import TestClient
import pytest

from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionDataTrack,
    SubmissionMetrics,
    SubmissionStatus,
)
from quantfish.submissions.staleness import (
    ScoreFingerprintContext,
    config_sha256,
    sha256_file,
)
from quantfish.submissions import score_worker
from quantfish.web_app.app import create_app
from quantfish.web_app.settings import WebSettings


def _settings(
    tmp_path: Path,
    *,
    config_path: Path | None = None,
    submission_cooldown_seconds: float = 2.0,
) -> WebSettings:
    return WebSettings(
        runtime_root=tmp_path / "runtime",
        config_path=config_path or _default_config(tmp_path),
        admin_password="quantfish-admin",
        admin_session_secret="test-session-secret",
        participant_session_secret="test-participant-session-secret",
        student_exports_enabled=False,
        submission_cooldown_seconds=submission_cooldown_seconds,
    )


def _expected_execution_parameters(
    *,
    config_path: Path = Path("config/platform.yaml"),
    data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
) -> dict:
    config = ConfigRepository(config_path).load().to_dict()
    backtest = config["backtest"]
    execution = config["execution"]
    return {
        "data_track": data_track.value,
        "data_start": backtest["data_start"],
        "scoring_start": backtest["scoring_start"],
        "scoring_end": backtest["scoring_end"],
        "capital": backtest["capital"],
        "group_count": backtest["group_count"],
        "industry_neutralization": backtest["industry_neutralization"],
        "price_policy": backtest["price_policy"],
        "execution_price": backtest["execution_price"],
        "mark_price": backtest["mark_price"],
        "long_only_benchmark": backtest["long_only_benchmark"],
        "long_only_risk_free_rate": backtest["long_only_risk_free_rate"],
        "long_only_min_beta_observations": backtest[
            "long_only_min_beta_observations"
        ],
        "commission_rate": execution["commission_rate"],
        "slippage_rate": execution["slippage_rate"],
        "sell_stamp_duty_rate": execution["sell_stamp_duty_rate"],
        "max_leverage": execution["max_leverage"],
        "top_k": execution["top_k"],
        "long_only": execution["long_only"],
        "long_only_weighting": execution["long_only_weighting"],
        "long_only_target_count": execution["long_only_target_count"],
        "max_position_weight": execution["max_position_weight"],
        "max_participation_rate": execution["max_participation_rate"],
        "min_listing_days": execution["min_listing_days"],
        "terminal_stale_position_policy": execution[
            "terminal_stale_position_policy"
        ],
        "allowed_market_types": execution["allowed_market_types"],
        "submission_timeout_enabled": execution["submission_timeout_enabled"],
        "submission_timeout_seconds": execution["submission_timeout_seconds"],
    }


def _copied_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "platform.yaml"
    ConfigRepository(config_path).save(PlatformConfig.default())
    return config_path


def _default_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "platform.yaml"
    if not config_path.exists():
        ConfigRepository(config_path).save(PlatformConfig.default())
    return config_path


def _login(client: TestClient) -> None:
    response = client.post("/api/admin/login", json={"password": "quantfish-admin"})
    assert response.status_code == 200


def _create_team(client: TestClient, team_name: str = "Team Alpha", password: str = "secret") -> dict:
    _login(client)
    response = client.post(
        "/api/admin/teams",
        json={"team_name": team_name, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def _participant_login(
    client: TestClient,
    team_name: str = "Team Alpha",
    password: str = "secret",
) -> None:
    response = client.post(
        "/api/session/login",
        json={"team_name": team_name, "password": password},
    )
    assert response.status_code == 200


def _wait_for_submission(
    client: TestClient,
    submission_id: str,
    status: str = "completed",
) -> dict:
    deadline = time.monotonic() + 5
    last_payload: dict | None = None
    while time.monotonic() < deadline:
        response = client.get(f"/api/submissions/{submission_id}")
        assert response.status_code == 200
        last_payload = response.json()
        if last_payload["status"] == status:
            return last_payload
        time.sleep(0.01)
    raise AssertionError(f"{submission_id} did not reach {status}: {last_payload}")


def _store_submission(
    app: object,
    *,
    submission_id: str,
    team_id: str,
    submitted_at: str,
    status: SubmissionStatus = SubmissionStatus.COMPLETED,
    data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    metrics: SubmissionMetrics | None = None,
    original_filename: str | None = None,
) -> Submission:
    services = app.state.services
    settings = services.admin_service.settings
    strategy_path = settings.submissions_root / submission_id / "generate_signals.py"
    strategy_path.parent.mkdir(parents=True)
    strategy_text = f"def generate_signals(data):\n    return [{submission_id!r}]\n"
    strategy_path.write_text(strategy_text, encoding="utf-8")
    submission = Submission(
        submission_id=submission_id,
        team_id=team_id,
        status=status,
        strategy_path=strategy_path.as_posix(),
        report_dir=(settings.reports_root / submission_id).as_posix(),
        fingerprints=ScoreFingerprints(
            config_sha256="config",
            hidden_catalog_sha256="catalog",
            strategy_sha256=strategy_text,
            engine_version="fake",
            data_track=data_track,
        ),
        original_filename=original_filename or f"{submission_id}.py",
        metrics=metrics or SubmissionMetrics(total_return=0.1, sharpe=1.0),
        data_track=data_track,
        submitted_at=submitted_at,
    )
    services.submission_repository.save(submission)
    return submission


class FakeSubmissionRunner:
    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        return ScoreFingerprints(
            config_sha256="config",
            hidden_catalog_sha256="catalog",
            strategy_sha256=strategy_path.read_text(encoding="utf-8"),
            engine_version="fake",
            data_track=data_track,
        )

    def score(
        self,
        strategy_path: Path,
        report_dir: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> SubmissionMetrics:
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "summary.csv").write_text(
            "total_return,annual_return,sharpe,max_drawdown,average_turnover,average_short_exposure,short_total_return,annualized_short_profit,win_rate,trading_days\n"
            "0.21,0.18,1.7,-0.08,0.32,-0.5,0.08,0.10,0.56,250\n",
            encoding="utf-8",
        )
        (report_dir / "performance_by_year.csv").write_text(
            "period,long,short,long_count,short_count,sharpe,total_return,annualized_return,turnover,drawdown,fitness,calmar\n"
            "2026,0.5,-0.5,12,12,1.7,0.18,45.36,0.32,0.08,1.8,567.0\n"
            "all,0.5,-0.5,12,12,1.7,0.18,45.36,0.32,0.08,1.8,567.0\n",
            encoding="utf-8",
        )
        (report_dir / "graph_data.json").write_text(
            '{"equity":[{"date":"2026-01-01","equity":1.0},{"date":"2026-01-02","equity":1.21}],'
            '"drawdown":[{"date":"2026-01-02","drawdown":-0.08}]}',
            encoding="utf-8",
        )
        (report_dir / "diagnostics.json").write_text(
            '{"strategy_path":"/tmp/hidden/strategy.py",'
            '"data_root":"/tmp/hidden/data",'
            '"scoring_dates":["2026-01-01","2026-01-02"]}',
            encoding="utf-8",
        )
        return SubmissionMetrics(
            total_return=0.21,
            annual_return=0.18,
            sharpe=1.7,
            max_drawdown=-0.08,
            average_turnover=0.32,
            average_short_exposure=-0.5,
            short_total_return=0.08,
            annualized_short_profit=0.10,
            win_rate=0.56,
            trading_days=250,
        )


class TrackFingerprintRunner(FakeSubmissionRunner):
    def __init__(self) -> None:
        self.release_sha_by_track = {
            track: "catalog" for track in SubmissionDataTrack
        }
        self.release_generation_by_track: dict[SubmissionDataTrack, str | None] = {
            track: None for track in SubmissionDataTrack
        }

    def current_release_generation(
        self,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> str | None:
        return self.release_generation_by_track[data_track]

    def current_fingerprint_context(
        self,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprintContext:
        return ScoreFingerprintContext(
            config_sha256="config",
            hidden_catalog_sha256=self.release_sha_by_track[data_track],
            engine_version="fake",
            data_track=data_track,
            release_generation=self.release_generation_by_track[data_track],
        )

    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        return ScoreFingerprints(
            config_sha256="config",
            hidden_catalog_sha256=self.release_sha_by_track[data_track],
            strategy_sha256=strategy_path.read_text(encoding="utf-8"),
            engine_version="fake",
            data_track=data_track,
            release_generation=self.release_generation_by_track[data_track],
        )


class ConfigAwareFingerprintRunner(FakeSubmissionRunner):
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def current_fingerprint_context(
        self,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprintContext:
        return ScoreFingerprintContext(
            config_sha256=config_sha256(ConfigRepository(self.config_path).load()),
            hidden_catalog_sha256="catalog",
            engine_version="fake",
            data_track=data_track,
        )

    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        return ScoreFingerprints(
            config_sha256=config_sha256(ConfigRepository(self.config_path).load()),
            hidden_catalog_sha256="catalog",
            strategy_sha256=sha256_file(strategy_path),
            engine_version="fake",
            data_track=data_track,
        )


class FakeStudentExportService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True)
        self.learning_zip = self.root / "learning-data.zip"
        self.environment_zip = self.root / "environment-macos-arm64.zip"
        with zipfile.ZipFile(self.learning_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("data_releases/learning/data_catalog.json", "{}")
        with zipfile.ZipFile(self.environment_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("README.zh-CN.md", "# QuantFish")

    def learning_data_zip_path(self) -> Path:
        return self.learning_zip

    def environment_zip_path(self, platform: str) -> Path:
        if platform == "macos-arm64":
            return self.environment_zip
        return self.root / f"environment-{platform}.zip"

    def environment_options(self) -> dict:
        return {
            "platforms": [
                {
                    "platform": "macos-arm64",
                    "label": "macOS Apple Silicon",
                    "architecture": "arm64",
                    "status": "available",
                    "size_bytes": self.environment_zip.stat().st_size,
                    "updated_at": "2026-06-20T00:00:00+00:00",
                    "download_url": "/api/downloads/environment/macos-arm64.zip",
                },
                {
                    "platform": "windows-x86_64",
                    "label": "Windows 64-bit",
                    "architecture": "x86_64",
                    "status": "missing",
                    "size_bytes": None,
                    "updated_at": None,
                    "download_url": None,
                },
            ]
        }


class FailingFingerprintRunner(FakeSubmissionRunner):
    def current_fingerprints(
        self,
        strategy_path: Path,
        data_track: SubmissionDataTrack = SubmissionDataTrack.HIDDEN_TEST,
    ) -> ScoreFingerprints:
        raise RuntimeError("fingerprint unavailable")


class ContextCountingRunner(FakeSubmissionRunner):
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


def test_health_route_reports_runtime_status(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["app"] == "QuantFish"
    assert "runtime_root" not in response.json()


def test_frontend_deep_links_fall_back_to_spa_index(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "frontend-dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text(
        "<!doctype html><title>QuantFish</title><div id=\"root\"></div>",
        encoding="utf-8",
    )
    client = TestClient(
        create_app(
            WebSettings(
                runtime_root=tmp_path / "runtime",
                admin_password="quantfish-admin",
                admin_session_secret="test-session-secret",
                participant_session_secret="test-participant-session-secret",
                frontend_dist=frontend_dist,
            )
        )
    )

    deep_link_response = client.get("/leaderboard")
    api_not_found_response = client.get("/api/not-found")

    assert deep_link_response.status_code == 200
    assert "QuantFish" in deep_link_response.text
    assert deep_link_response.headers["content-type"].startswith("text/html")
    assert api_not_found_response.status_code == 404


def test_participant_login_session_cookie_and_logout(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    team = _create_team(client)

    login_response = client.post(
        "/api/session/login",
        json={"team_name": "Team Alpha", "password": "secret"},
    )

    assert login_response.status_code == 200
    assert login_response.json() == {
        "authenticated": True,
        "team_id": team["team_id"],
        "team_name": "Team Alpha",
    }
    set_cookie = login_response.headers["set-cookie"]
    assert "quantfish_submission_session=" in set_cookie
    assert "quantfish_admin_session=" not in set_cookie

    session_response = client.get("/api/session")
    assert session_response.status_code == 200
    assert session_response.json() == {
        "authenticated": True,
        "team_id": team["team_id"],
        "team_name": "Team Alpha",
    }

    logout_response = client.post("/api/session/logout")

    assert logout_response.status_code == 200
    assert logout_response.json() == {
        "authenticated": False,
        "team_id": None,
        "team_name": None,
    }
    assert "quantfish_submission_session=" in logout_response.headers["set-cookie"]
    assert client.get("/api/session").json() == {
        "authenticated": False,
        "team_id": None,
        "team_name": None,
    }


def test_submission_upload_returns_429_inside_same_team_cooldown(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _create_team(client)

    first_response = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )
    second_response = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy_again.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    # The cooldown is a wall-clock 2 s window, so a slow machine can report 1 s.
    detail = second_response.json()["detail"]
    assert re.fullmatch(
        r"Please wait [12] seconds? before submitting another strategy\.", detail
    ), detail
    assert len(app.state.services.submission_repository.list_all()) == 1


def test_logged_in_participant_can_upload_without_retyping_credentials(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    team = _create_team(client)
    login_response = client.post(
        "/api/session/login",
        json={"team_name": "Team Alpha", "password": "secret"},
    )
    assert login_response.status_code == 200

    upload_response = client.post(
        "/api/submissions",
        data={"data_track": "learning"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n",
                "text/x-python",
            )
        },
    )

    assert upload_response.status_code == 200
    submission = upload_response.json()
    assert submission["team_id"] == team["team_id"]
    assert submission["team_name"] == "Team Alpha"
    assert submission["data_track"] == "learning"

    client.post("/api/session/logout")
    unauthenticated_upload = client.post(
        "/api/submissions",
        data={"data_track": "hidden_test"},
        files={"file": ("strategy.py", b"def generate_signals(data):\n    return []\n", "text/x-python")},
    )
    assert unauthenticated_upload.status_code == 401
    assert unauthenticated_upload.json()["detail"] == "team login required"


def test_logged_in_participant_can_view_only_own_submission_source(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    alpha = services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="alpha-secret",
    )
    beta = services.team_repository.create_team(
        team_id="team-beta",
        display_name="Beta Fund",
        password="beta-secret",
    )
    settings = services.admin_service.settings

    def store_source_submission(
        submission_id: str,
        team_id: str,
        source: str,
    ) -> Submission:
        strategy_path = settings.submissions_root / submission_id / "generate_signals.py"
        strategy_path.parent.mkdir(parents=True)
        strategy_path.write_text(source, encoding="utf-8")
        submission = Submission(
            submission_id=submission_id,
            team_id=team_id,
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(settings.reports_root / submission_id).as_posix(),
            fingerprints=ScoreFingerprints(
                config_sha256="config",
                hidden_catalog_sha256="catalog",
                strategy_sha256=f"sha256:{submission_id}",
                engine_version="fake",
            ),
            original_filename=f"{submission_id}.py",
            metrics=SubmissionMetrics(total_return=0.1, sharpe=1.0),
            submitted_at="2026-06-20T09:00:00+00:00",
        )
        services.submission_repository.save(submission)
        return submission

    alpha_source = "def generate_signals(data):\n    return ['alpha-only-source']\n"
    beta_source = "def generate_signals(data):\n    return ['beta-only-source']\n"
    alpha_submission = store_source_submission("alpha-source", alpha.team_id, alpha_source)
    beta_submission = store_source_submission("beta-source", beta.team_id, beta_source)
    missing_source = store_source_submission(
        "missing-source",
        alpha.team_id,
        "def generate_signals(data):\n    return ['missing-source']\n",
    )
    Path(missing_source.strategy_path).unlink()

    anonymous = TestClient(app)
    unauthenticated = anonymous.get(
        f"/api/submissions/{alpha_submission.submission_id}/source"
    )

    client = TestClient(app)
    login_response = client.post(
        "/api/session/login",
        json={"team_name": "Alpha Desk", "password": "alpha-secret"},
    )
    own_source = client.get(f"/api/submissions/{alpha_submission.submission_id}/source")
    other_source = client.get(f"/api/submissions/{beta_submission.submission_id}/source")
    missing = client.get(f"/api/submissions/{missing_source.submission_id}/source")
    listed = client.get("/api/submissions").json()
    detail = client.get(f"/api/submissions/{alpha_submission.submission_id}").json()

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["detail"] == "team login required"
    assert login_response.status_code == 200
    assert own_source.status_code == 200
    assert own_source.headers["content-type"].startswith("text/plain")
    assert own_source.text == alpha_source
    assert other_source.status_code == 403
    assert other_source.json()["detail"] == "submission does not belong to current team"
    assert missing.status_code == 404
    assert missing.json()["detail"] == "submission source not found"
    assert alpha_source not in json.dumps(listed)
    assert alpha_source not in json.dumps(detail)
    assert "strategy_path" not in detail
    assert "report_dir" not in detail


def test_submission_upload_detail_leaderboard_and_compare_routes(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)
    expected_execution_parameters = _expected_execution_parameters(
        config_path=app.state.services.settings.config_path
    )

    team_response = client.post(
        "/api/admin/teams",
        json={
            "team_name": "Team Alpha",
            "password": "secret",
        },
    )
    assert team_response.status_code == 200

    upload_response = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n",
                "text/x-python",
            )
        },
    )
    assert upload_response.status_code == 200
    submission = upload_response.json()
    assert submission["status"] == "queued"
    assert submission["metrics"] is None
    assert submission["score"] is None
    assert submission["submission_number"] == 1
    assert submission["submission_label"] == "#1"
    assert submission["data_track"] == "hidden_test"

    detail = _wait_for_submission(client, submission["submission_id"])
    assert detail["submission_number"] == 1
    assert detail["submission_label"] == "#1"
    assert detail["data_track"] == "hidden_test"
    assert detail["metrics"]["sharpe"] == 1.7
    assert detail["metrics"]["average_short_exposure"] == pytest.approx(-0.5)
    assert detail["metrics"]["short_total_return"] == pytest.approx(0.08)
    assert detail["metrics"]["annualized_short_profit"] == pytest.approx(0.10)
    expected_score = (
        45.0 * (1.7 / 2.0)
        + 35.0 * (0.18 / 0.30)
        - 15.0 * (0.08 / 0.30)
        - 5.0 * (0.32 / 3.0)
        - 50.0 * (0.10 / 0.30)
    )
    assert detail["score"] == pytest.approx(expected_score)
    assert detail["artifacts"]["summary"]["total_return"] == 0.21
    assert detail["performance_table"][0] == {
        "period": "2026",
        "long": 0.5,
        "short": -0.5,
        "long_count": 12,
        "short_count": 12,
        "sharpe": 1.7,
        "total_return": 0.18,
        "annualized_return": 45.36,
        "turnover": 0.32,
        "drawdown": 0.08,
        "fitness": 1.8,
        "calmar": 567.0,
    }
    assert detail["artifacts"]["graph_data"]["equity"][1]["equity"] == 1.21
    assert detail["artifacts"]["diagnostics"] == {
        "scoring_dates": ["2026-01-01", "2026-01-02"]
    }
    assert detail["execution_parameters"] == expected_execution_parameters
    assert "strategy_path" not in detail
    assert "report_dir" not in detail

    leaderboard_response = client.get("/api/leaderboard")
    assert leaderboard_response.status_code == 200
    leaderboard = leaderboard_response.json()
    assert leaderboard["rows"][0]["team_name"] == "Team Alpha"
    assert leaderboard["rows"][0]["rank"] == 1
    assert leaderboard["rows"][0]["badge"] == "gold"
    assert leaderboard["rows"][0]["metric"] == "sharpe"
    assert leaderboard["rows"][0]["metric_value"] == pytest.approx(1.7)
    assert leaderboard["rows"][0]["score"] == pytest.approx(1.7)

    compare_response = client.get(
        "/api/compare",
        params=[("submission_id", submission["submission_id"])],
    )
    assert compare_response.status_code == 200
    compared = compare_response.json()["submissions"][0]
    assert compared["team_name"] == "Team Alpha"
    assert compared["submission_number"] == 1
    assert compared["submission_label"] == "#1"
    assert compared["data_track"] == "hidden_test"
    assert compared["metrics"]["average_short_exposure"] == pytest.approx(-0.5)
    assert compared["metrics"]["short_total_return"] == pytest.approx(0.08)
    assert compared["metrics"]["annualized_short_profit"] == pytest.approx(0.10)
    assert compared["execution_parameters"] == expected_execution_parameters
    assert "graph_data" not in compared

    rich_compare_response = client.get(
        "/api/compare",
        params=[
            ("submission_id", submission["submission_id"]),
            ("include_graph_data", "true"),
        ],
    )
    assert rich_compare_response.status_code == 200
    rich_compared = rich_compare_response.json()["submissions"][0]
    assert rich_compared["execution_parameters"] == expected_execution_parameters
    assert rich_compared["graph_data"]["equity"][1]["equity"] == 1.21
    assert rich_compared["graph_data"]["drawdown"][0]["drawdown"] == -0.08


@pytest.mark.parametrize(
    "data_track",
    ["learning", "learning_1", "learning_2", "learning_3"],
)
def test_learning_tracks_run_history_detail_compare_and_track_leaderboard(
    tmp_path: Path,
    data_track: str,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)
    assert client.post(
        "/api/admin/teams",
        json={"team_name": "Team Alpha", "password": "secret"},
    ).status_code == 200

    upload_response = client.post(
        "/api/submissions",
        data={
            "team_name": "Team Alpha",
            "password": "secret",
            "data_track": data_track,
        },
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n",
                "text/x-python",
            )
        },
    )

    assert upload_response.status_code == 200
    submission = upload_response.json()
    assert submission["data_track"] == data_track
    detail = _wait_for_submission(client, submission["submission_id"])
    assert detail["status"] == "completed"
    assert detail["data_track"] == data_track
    assert detail["metrics"]["sharpe"] == 1.7

    history = client.get("/api/submissions").json()["submissions"]
    assert len(history) == 1
    assert history[0]["submission_id"] == submission["submission_id"]
    assert history[0]["data_track"] == data_track

    leaderboard = client.get("/api/leaderboard").json()
    assert leaderboard == {
        "rows": [],
        "count": 0,
        "total_count": 0,
        "limit": None,
        "offset": 0,
        "has_next": False,
    }

    track_leaderboard = client.get(
        "/api/leaderboard",
        params={"data_track": data_track},
    ).json()
    assert track_leaderboard["count"] == 1
    assert track_leaderboard["rows"][0]["id"] == submission["submission_id"]
    assert track_leaderboard["rows"][0]["team_name"] == "Team Alpha"
    assert track_leaderboard["rows"][0]["rank"] == 1

    dashboard = client.get("/api/dashboard").json()
    assert dashboard["submission_count"] == 1
    assert dashboard["latest"] == []

    compare_response = client.get(
        "/api/compare",
        params=[("submission_id", submission["submission_id"])],
    )
    assert compare_response.status_code == 200
    compared = compare_response.json()["submissions"][0]
    assert compared["submission_id"] == submission["submission_id"]
    assert compared["data_track"] == data_track


def test_submission_history_and_detail_expose_raw_error_logs(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path), submission_runner=FakeSubmissionRunner())
    client = TestClient(app)
    team = _create_team(client)
    strategy_path = tmp_path / "broken_strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    raise RuntimeError('boom')\n", encoding="utf-8")
    report_dir = tmp_path / "runtime" / "reports" / "failed-submission"
    report_dir.mkdir(parents=True)
    (report_dir / "worker_error.log").write_text(
        "Traceback (most recent call last):\nRuntimeError: boom\n",
        encoding="utf-8",
    )
    submission = Submission(
        submission_id="failed-submission",
        team_id=team["team_id"],
        status=SubmissionStatus.FAILED,
        strategy_path=strategy_path.as_posix(),
        report_dir=report_dir.as_posix(),
        fingerprints=None,
        original_filename="broken_strategy.py",
        error_message="scoring failed",
    )
    app.state.services.submission_repository.save(submission)
    _participant_login(client)

    history_response = client.get("/api/submissions")
    detail_response = client.get("/api/submissions/failed-submission")

    assert history_response.status_code == 200
    assert history_response.json()["total_count"] == 1
    assert history_response.json()["limit"] == 100
    history_row = history_response.json()["submissions"][0]
    assert history_row["error_message"] == "scoring failed"
    assert history_row["has_raw_error"] is True
    assert "raw_error" not in history_row

    raw_error_response = client.get("/api/submissions/failed-submission/raw-error")
    assert raw_error_response.status_code == 200
    assert raw_error_response.text == "Traceback (most recent call last):\nRuntimeError: boom"

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["error_message"] == "scoring failed"
    assert detail["raw_error"] is None


def test_hidden_test_toggle_only_controls_new_hidden_uploads(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    app = create_app(
        _settings(
            tmp_path,
            config_path=config_path,
            submission_cooldown_seconds=0,
        ),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)
    assert client.post(
        "/api/admin/teams",
        json={"team_name": "Team Alpha", "password": "secret"},
    ).status_code == 200

    hidden_upload = client.post(
        "/api/submissions",
        data={
            "team_name": "Team Alpha",
            "password": "secret",
            "data_track": "hidden_test",
        },
        files={
            "file": (
                "hidden.py",
                b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n",
                "text/x-python",
            )
        },
    )
    learning_upload = client.post(
        "/api/submissions",
        data={
            "team_name": "Team Alpha",
            "password": "secret",
            "data_track": "learning",
        },
        files={
            "file": (
                "learning.py",
                b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n",
                "text/x-python",
            )
        },
    )
    assert hidden_upload.status_code == 200
    assert learning_upload.status_code == 200
    hidden_submission = hidden_upload.json()
    learning_submission = learning_upload.json()
    hidden_detail_before_toggle = _wait_for_submission(client, hidden_submission["submission_id"])
    _wait_for_submission(client, learning_submission["submission_id"])
    assert hidden_detail_before_toggle["stale"] is False

    settings_response = client.patch(
        "/api/admin/settings",
        json={"execution": {"hidden_test_enabled": False}},
    )
    assert settings_response.status_code == 200
    assert settings_response.json()["execution"]["hidden_test_enabled"] is False

    options = client.get("/api/submissions/options")
    assert options.status_code == 200
    assert options.json() == {
        "available_data_tracks": [
            "learning",
            "learning_1",
            "learning_2",
            "learning_3",
        ]
    }

    blocked_hidden_upload = client.post(
        "/api/submissions",
        data={
            "team_name": "Team Alpha",
            "password": "secret",
            "data_track": "hidden_test",
        },
        files={
            "file": (
                "blocked.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )
    assert blocked_hidden_upload.status_code == 400
    assert "hidden test track is not currently open" in blocked_hidden_upload.json()["detail"]

    default_upload = client.post(
        "/api/submissions",
        data={
            "team_name": "Team Alpha",
            "password": "secret",
        },
        files={
            "file": (
                "default.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )
    assert default_upload.status_code == 200
    assert default_upload.json()["data_track"] == "learning"

    history = client.get("/api/submissions").json()["submissions"]
    assert [row["submission_id"] for row in history] == [
        hidden_submission["submission_id"],
        learning_submission["submission_id"],
        default_upload.json()["submission_id"],
    ]
    assert history[0]["data_track"] == "hidden_test"
    assert history[0]["stale"] is False

    hidden_detail = client.get(f"/api/submissions/{hidden_submission['submission_id']}")
    assert hidden_detail.status_code == 200
    assert hidden_detail.json()["data_track"] == "hidden_test"
    assert hidden_detail.json()["stale"] is False

    compare_response = client.get(
        "/api/compare",
        params=[
            ("submission_id", hidden_submission["submission_id"]),
            ("submission_id", learning_submission["submission_id"]),
        ],
    )
    assert compare_response.status_code == 200
    compared = compare_response.json()["submissions"]
    assert [row["submission_id"] for row in compared] == [
        hidden_submission["submission_id"],
        learning_submission["submission_id"],
    ]

    leaderboard = client.get("/api/leaderboard").json()
    assert leaderboard["count"] == 1
    assert leaderboard["rows"][0]["id"] == hidden_submission["submission_id"]
    assert leaderboard["rows"][0]["stale"] is False
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["submission_count"] == 3
    assert dashboard["latest"][0]["id"] == hidden_submission["submission_id"]
    assert dashboard["latest"][0]["stale"] is False

    admin_submissions = client.get("/api/admin/submissions").json()["submissions"]
    assert {row["submission_id"] for row in admin_submissions} >= {
        hidden_submission["submission_id"],
        learning_submission["submission_id"],
    }


def test_submission_detail_includes_configured_score_breakdown(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    app = create_app(
        _settings(tmp_path, config_path=config_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)

    scoring_response = client.patch(
        "/api/admin/settings",
        json={
            "scoring": {
                "sharpe_weight": 3.0,
                "sharpe_target": 2.0,
                "annual_return_weight": 2.0,
                "annual_return_target": 0.2,
                "drawdown_weight": 4.0,
                "drawdown_limit": 0.1,
                "turnover_weight": 1.0,
                "turnover_limit": 0.5,
                "short_profit_weight": 10.0,
                "short_profit_target": 0.2,
                "minimum_slice_trading_days": 1,
            }
        },
    )
    assert scoring_response.status_code == 200

    team_response = client.post(
        "/api/admin/teams",
        json={
            "team_name": "Team Alpha",
            "password": "secret",
        },
    )
    assert team_response.status_code == 200

    upload_response = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n",
                "text/x-python",
            )
        },
    )
    assert upload_response.status_code == 200
    submission = upload_response.json()

    detail = _wait_for_submission(client, submission["submission_id"])
    breakdown = {row["key"]: row for row in detail["score_breakdown"]}

    assert detail["score"] == pytest.approx(-4.49)
    assert detail["score_calculation"] == (
        "Score = clamp(1.700 / 2.000, -1, 1) × 3.000 "
        "+ clamp(0.180 / 0.200, -1, 1) × 2.000 "
        "- clamp(abs(-0.080) / 0.100, 0, 1) × 4.000 "
        "- clamp(0.320 / 0.500, 0, 1) × 1.000 "
        "- clamp(0.100 / 0.200, 0, 1) × 10.000 = -4.490"
    )
    assert breakdown["sharpe"]["metric_value"] == pytest.approx(1.7)
    assert breakdown["sharpe"]["weight"] == pytest.approx(3.0)
    assert breakdown["sharpe"]["contribution"] == pytest.approx(2.55)
    assert breakdown["annual_return"]["contribution"] == pytest.approx(1.8)
    assert breakdown["drawdown_penalty"]["metric_value"] == pytest.approx(-0.08)
    assert breakdown["drawdown_penalty"]["contribution"] == pytest.approx(-3.2)
    assert breakdown["turnover_penalty"]["metric_value"] == pytest.approx(0.32)
    assert breakdown["turnover_penalty"]["contribution"] == pytest.approx(-0.64)
    assert breakdown["short_profit_penalty"]["metric_value"] == pytest.approx(0.10)
    assert breakdown["short_profit_penalty"]["contribution"] == pytest.approx(-5.0)

    history = client.get("/api/submissions").json()["submissions"]
    leaderboard = client.get("/api/leaderboard").json()["rows"]

    assert history[0]["score"] == pytest.approx(-4.49)
    assert leaderboard[0]["metric"] == "sharpe"
    assert leaderboard[0]["score"] == pytest.approx(1.7)


def test_existing_submission_scores_are_recalculated_from_report_short_profit(
    tmp_path: Path,
) -> None:
    app = create_app(_settings(tmp_path), submission_runner=FakeSubmissionRunner())
    client = TestClient(app)
    team = _create_team(client)
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    report_dir = tmp_path / "runtime" / "reports" / "legacy-submission"
    report_dir.mkdir(parents=True)
    (report_dir / "summary.csv").write_text(
        "total_return,annual_return,sharpe,max_drawdown,average_turnover,average_short_exposure,short_total_return,annualized_short_profit,win_rate,terminal_stale_position_count,terminal_stale_gross_exposure,trading_days\n"
        "0.21,0.18,1.7,-0.08,0.32,-0.5,0.08,0.10,0.56,3,0.058303,250\n",
        encoding="utf-8",
    )
    (report_dir / "graph_data.json").write_text("{}", encoding="utf-8")
    submission = Submission(
        submission_id="legacy-submission",
        team_id=team["team_id"],
        status=SubmissionStatus.COMPLETED,
        strategy_path=strategy_path.as_posix(),
        report_dir=report_dir.as_posix(),
        fingerprints=app.state.services.submission_runner.current_fingerprints(strategy_path),
        original_filename="strategy.py",
        metrics=SubmissionMetrics(
            annual_return=0.18,
            sharpe=1.7,
            max_drawdown=-0.08,
            average_turnover=0.32,
            win_rate=0.56,
            trading_days=250,
        ),
    )
    app.state.services.submission_repository.save(submission)

    expected_score = (
        45.0 * (1.7 / 2.0)
        + 35.0 * (0.18 / 0.30)
        - 15.0 * (0.08 / 0.30)
        - 5.0 * (0.32 / 3.0)
        - 50.0 * (0.10 / 0.30)
    )

    leaderboard = client.get("/api/leaderboard").json()["rows"]
    detail = client.get("/api/submissions/legacy-submission").json()
    admin_submissions = client.get("/api/admin/submissions").json()["submissions"]

    assert leaderboard[0]["metric"] == "sharpe"
    assert leaderboard[0]["score"] == pytest.approx(1.7)
    assert detail["score"] == pytest.approx(expected_score)
    assert admin_submissions[0]["score"] == pytest.approx(expected_score)
    assert {
        item["key"] for item in detail["score_breakdown"]
    } >= {"short_profit_penalty"}
    assert detail["metrics"]["average_short_exposure"] == pytest.approx(-0.5)
    assert detail["metrics"]["short_total_return"] == pytest.approx(0.08)
    assert detail["metrics"]["annualized_short_profit"] == pytest.approx(0.10)
    assert detail["metrics"]["terminal_stale_position_count"] == 3
    assert detail["metrics"]["terminal_stale_gross_exposure"] == pytest.approx(
        0.058303
    )


def test_score_worker_uses_current_execution_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = _copied_config(tmp_path)
    settings = _settings(tmp_path, config_path=config_path)
    client = TestClient(create_app(settings))
    _login(client)
    response = client.patch(
        "/api/admin/settings",
        json={
            "backtest": {"capital": 1_500_000, "industry_neutralization": True},
            "execution": {
                "commission_rate": 0.001,
                "slippage_rate": 0.002,
                "sell_stamp_duty_rate": 0.0007,
                "max_leverage": 2.5,
                "top_k": 12,
                "max_concurrent_scoring": 3,
                "submission_timeout_seconds": 45,
                "submission_timeout_enabled": False,
                "long_only": True,
                "terminal_stale_position_policy": "carry",
            },
        },
    )
    assert response.status_code == 200

    seen: dict[str, object] = {}

    def fake_run_student_backtest(strategy_path: Path, data_root: Path, config: object) -> object:
        seen["config"] = config
        return type("Result", (), {})()

    monkeypatch.setattr(score_worker, "run_student_backtest", fake_run_student_backtest)
    monkeypatch.setattr(score_worker, "write_backtest_report", lambda _result, _report_dir: None)
    monkeypatch.setattr(
        score_worker,
        "_metrics_from_summary_csv",
        lambda _path: SubmissionMetrics.from_summary({"total_return": 0.1}),
    )

    score_worker.score_submission(
        settings.config_path,
        tmp_path / "strategy.py",
        tmp_path / "reports",
    )

    config = seen["config"]
    assert config.backtest.capital == 1_500_000
    assert config.backtest.industry_neutralization is True
    assert config.execution.commission_rate == 0.001
    assert config.execution.slippage_rate == 0.002
    assert config.execution.sell_stamp_duty_rate == 0.0007
    assert config.execution.max_leverage == 2.5
    assert config.execution.top_k == 12
    assert config.execution.long_only is True
    assert config.execution.terminal_stale_position_policy == "carry"


def test_leaderboard_shows_best_submission_per_team_while_history_lists_all(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)

    for team_name in ("Team Alpha", "Team Beta"):
        response = client.post(
            "/api/admin/teams",
            json={"team_name": team_name, "password": "secret"},
        )
        assert response.status_code == 200

    for team_name, body in (
        ("Team Alpha", b"def generate_signals(data):\n    return []\n"),
        ("Team Alpha", b"def generate_signals(data):\n    return data.current('stock.daily_returns')\n"),
        ("Team Beta", b"def generate_signals(data):\n    return []\n"),
    ):
        response = client.post(
            "/api/submissions",
            data={"team_name": team_name, "password": "secret"},
            files={"file": ("strategy.py", body, "text/x-python")},
        )
        assert response.status_code == 200

    leaderboard_response = client.get("/api/leaderboard")
    history_response = client.get("/api/submissions")

    assert leaderboard_response.status_code == 200
    leaderboard = leaderboard_response.json()
    assert leaderboard["count"] == 2
    assert [row["team_name"] for row in leaderboard["rows"]] == [
        "Team Alpha",
        "Team Beta",
    ]
    assert leaderboard["rows"][0]["rank"] == 1
    assert leaderboard["rows"][1]["rank"] == 2

    assert history_response.status_code == 200
    history = history_response.json()["submissions"]
    assert len(history) == 3
    assert [row["team_name"] for row in history].count("Team Alpha") == 2
    assert [row["submission_label"] for row in history] == ["#1", "#2", "#3"]


def test_hidden_team_cohort_is_suppressed_except_dedicated_admin_history(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    client = TestClient(app)
    _login(client)
    alpha = client.post(
        "/api/admin/teams",
        json={"team_name": "Team Alpha", "password": "secret"},
    ).json()
    beta = client.post(
        "/api/admin/teams",
        json={"team_name": "Team Beta", "password": "secret"},
    ).json()

    hidden_submission = _store_submission(
        app,
        submission_id="hidden-alpha",
        team_id=alpha["team_id"],
        submitted_at="2026-06-19T09:00:00+00:00",
        metrics=SubmissionMetrics(total_return=0.8, annual_return=0.8, sharpe=8.0),
    )
    visible_submission = _store_submission(
        app,
        submission_id="visible-beta",
        team_id=beta["team_id"],
        submitted_at="2026-06-19T10:00:00+00:00",
        metrics=SubmissionMetrics(total_return=0.2, annual_return=0.2, sharpe=2.0),
    )
    report_dir = Path(hidden_submission.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "worker_error.log").write_text("hidden raw error", encoding="utf-8")
    cohort = client.post(
        "/api/admin/team-cohorts",
        json={
            "name": "Hidden cohort",
            "team_ids": [alpha["team_id"]],
            "history_visible": False,
            "submissions_enabled": True,
        },
    ).json()
    _participant_login(client, team_name="Team Alpha")

    history = client.get("/api/submissions").json()["submissions"]
    admin_history = client.get("/api/admin/submissions").json()["submissions"]
    leaderboard = client.get("/api/leaderboard").json()["rows"]
    dashboard = client.get("/api/dashboard").json()
    compare = client.get(
        "/api/compare",
        params={
            "submission_id": [
                hidden_submission.submission_id,
                visible_submission.submission_id,
            ]
        },
    ).json()["submissions"]
    hidden_detail = client.get(f"/api/submissions/{hidden_submission.submission_id}")
    hidden_raw_error = client.get(
        f"/api/submissions/{hidden_submission.submission_id}/raw-error"
    )
    hidden_admin_source = client.get(
        f"/api/admin/submissions/{hidden_submission.submission_id}/source"
    )
    cohort_history = client.get(
        f"/api/admin/team-cohorts/{cohort['cohort_id']}/submissions"
    ).json()

    assert [row["submission_id"] for row in history] == [visible_submission.submission_id]
    assert [row["submission_id"] for row in admin_history] == [visible_submission.submission_id]
    assert [row["id"] for row in leaderboard] == [visible_submission.submission_id]
    assert dashboard["submission_count"] == 1
    assert dashboard["team_count"] == 1
    assert [row["id"] for row in dashboard["latest"]] == [visible_submission.submission_id]
    assert [row["submission_id"] for row in compare] == [visible_submission.submission_id]
    assert hidden_detail.status_code == 404
    assert hidden_raw_error.status_code == 404
    assert hidden_admin_source.status_code == 404
    assert cohort_history["total_count"] == 1
    assert cohort_history["submissions"][0]["submission_id"] == hidden_submission.submission_id

    client.patch(
        f"/api/admin/team-cohorts/{cohort['cohort_id']}",
        json={"history_visible": True},
    )

    restored_history = client.get("/api/submissions").json()["submissions"]
    restored_leaderboard = client.get("/api/leaderboard").json()["rows"]

    assert {row["submission_id"] for row in restored_history} == {
        hidden_submission.submission_id,
        visible_submission.submission_id,
    }
    assert restored_leaderboard[0]["id"] == hidden_submission.submission_id


def test_team_cohort_submission_toggle_blocks_uploads_without_blocking_login(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)
    team = client.post(
        "/api/admin/teams",
        json={"team_name": "Team Alpha", "password": "secret"},
    ).json()
    client.post(
        "/api/admin/team-cohorts",
        json={
            "name": "Paused cohort",
            "team_ids": [team["team_id"]],
            "history_visible": True,
            "submissions_enabled": False,
        },
    )

    credential_upload = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )
    login = client.post(
        "/api/session/login",
        json={"team_name": "Team Alpha", "password": "secret"},
    )
    session_upload = client.post(
        "/api/submissions",
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )

    assert credential_upload.status_code == 403
    assert credential_upload.json()["detail"] == "team cohort submissions are disabled"
    assert login.status_code == 200
    assert session_upload.status_code == 403
    assert session_upload.json()["detail"] == "team cohort submissions are disabled"


def test_leaderboard_data_track_filter_keeps_best_learning_submission_per_team(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    for team_id, name in (
        ("team-alpha", "Alpha Desk"),
        ("team-beta", "Beta Desk"),
        ("team-hidden", "Hidden Desk"),
    ):
        services.team_repository.create_team(
            team_id=team_id,
            display_name=name,
            password="secret",
        )
    _store_submission(
        app,
        submission_id="hidden-best",
        team_id="team-hidden",
        submitted_at="2026-06-19T08:00:00+00:00",
        data_track=SubmissionDataTrack.HIDDEN_TEST,
        metrics=SubmissionMetrics(
            annual_return=0.80,
            sharpe=8.0,
            max_drawdown=-0.01,
        ),
    )
    _store_submission(
        app,
        submission_id="alpha-learning-old",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(
            annual_return=0.10,
            sharpe=1.0,
            max_drawdown=-0.04,
        ),
    )
    _store_submission(
        app,
        submission_id="alpha-learning-best",
        team_id="team-alpha",
        submitted_at="2026-06-19T10:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(
            annual_return=0.40,
            sharpe=4.0,
            max_drawdown=-0.05,
        ),
    )
    _store_submission(
        app,
        submission_id="beta-learning",
        team_id="team-beta",
        submitted_at="2026-06-19T11:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(
            annual_return=0.20,
            sharpe=2.0,
            max_drawdown=-0.02,
        ),
    )

    hidden_payload = TestClient(app).get("/api/leaderboard").json()
    learning_payload = TestClient(app).get(
        "/api/leaderboard",
        params={"data_track": "learning"},
    ).json()

    assert [row["id"] for row in hidden_payload["rows"]] == ["hidden-best"]
    assert hidden_payload["count"] == 1
    assert [row["id"] for row in learning_payload["rows"]] == [
        "alpha-learning-best",
        "beta-learning",
    ]
    assert [row["rank"] for row in learning_payload["rows"]] == [1, 2]


def test_release_rebuild_marks_only_existing_completed_track_scores_ineligible(
    tmp_path: Path,
) -> None:
    runner = TrackFingerprintRunner()
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=runner,
    )
    services = app.state.services
    for team_id, name in (
        ("team-one", "Team One"),
        ("team-two", "Team Two"),
    ):
        services.team_repository.create_team(
            team_id=team_id,
            display_name=name,
            password="secret",
        )
    completed_metrics = SubmissionMetrics(
        annual_return=0.2,
        sharpe=2.0,
        max_drawdown=-0.1,
        annualized_short_profit=0.1,
        trading_days=250,
    )
    _store_submission(
        app,
        submission_id="learning-one-old-score",
        team_id="team-one",
        submitted_at="2026-06-20T09:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING_1,
        metrics=completed_metrics,
    )
    _store_submission(
        app,
        submission_id="learning-two-current-score",
        team_id="team-two",
        submitted_at="2026-06-20T10:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING_2,
        metrics=completed_metrics,
    )
    _store_submission(
        app,
        submission_id="learning-one-failed",
        team_id="team-two",
        submitted_at="2026-06-20T11:00:00+00:00",
        status=SubmissionStatus.FAILED,
        data_track=SubmissionDataTrack.LEARNING_1,
    )

    runner.release_sha_by_track[SubmissionDataTrack.LEARNING_1] = "rebuilt-catalog"
    runner.release_generation_by_track[SubmissionDataTrack.LEARNING_1] = (
        "learning-1-generation-2"
    )

    client = TestClient(app)
    learning_1_rows = client.get(
        "/api/leaderboard",
        params={"data_track": "learning_1"},
    ).json()["rows"]
    learning_2_rows = client.get(
        "/api/leaderboard",
        params={"data_track": "learning_2"},
    ).json()["rows"]
    rebuilt_row = next(row for row in learning_1_rows if row["id"] == "learning-one-old-score")
    failed_row = next(row for row in learning_1_rows if row["id"] == "learning-one-failed")
    other_track_row = learning_2_rows[0]
    assert rebuilt_row["stale"] is True
    assert rebuilt_row["eligible"] is False
    assert failed_row["eligible"] is False
    assert other_track_row["stale"] is False
    assert other_track_row["eligible"] is True

    _login(client)
    rerun = client.post(
        "/api/admin/submissions/rerun",
        json={
            "scope": "selected",
            "submission_ids": ["learning-one-old-score"],
        },
    )
    assert rerun.status_code == 200
    assert rerun.json()["queued_submission_ids"] == ["learning-one-old-score"]
    rescored_detail = _wait_for_submission(client, "learning-one-old-score")
    assert rescored_detail["fingerprints"]["release_generation"] == (
        "learning-1-generation-2"
    )

    rescored_row = next(
        row
        for row in client.get(
            "/api/leaderboard",
            params={"data_track": "learning_1"},
        ).json()["rows"]
        if row["id"] == "learning-one-old-score"
    )
    assert rescored_row["stale"] is False
    assert rescored_row["eligible"] is True


def test_leaderboard_ranks_learning_track_by_requested_objective_metric(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    for team_id, name in (
        ("team-alpha", "Alpha Desk"),
        ("team-beta", "Beta Desk"),
    ):
        services.team_repository.create_team(
            team_id=team_id,
            display_name=name,
            password="secret",
        )
    _store_submission(
        app,
        submission_id="alpha-sharpe",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(
            annual_return=0.20,
            sharpe=4.0,
            max_drawdown=-0.20,
            calmar=1.0,
        ),
    )
    _store_submission(
        app,
        submission_id="alpha-calmar",
        team_id="team-alpha",
        submitted_at="2026-06-19T10:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(
            annual_return=0.15,
            sharpe=2.0,
            max_drawdown=-0.03,
            calmar=5.0,
        ),
    )
    _store_submission(
        app,
        submission_id="beta-risk",
        team_id="team-beta",
        submitted_at="2026-06-19T11:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(
            annual_return=0.08,
            sharpe=3.0,
            max_drawdown=-0.02,
            calmar=2.0,
        ),
    )
    client = TestClient(app)

    sharpe_payload = client.get(
        "/api/leaderboard",
        params={"data_track": "learning", "metric": "sharpe"},
    ).json()
    maxdd_payload = client.get(
        "/api/leaderboard",
        params={"data_track": "learning", "metric": "max_drawdown"},
    ).json()
    paginated_maxdd_payload = client.get(
        "/api/leaderboard",
        params={"data_track": "learning", "metric": "max_drawdown", "limit": 2},
    ).json()
    calmar_payload = client.get(
        "/api/leaderboard",
        params={"data_track": "learning", "metric": "calmar"},
    ).json()

    assert [row["id"] for row in sharpe_payload["rows"]] == [
        "alpha-sharpe",
        "beta-risk",
    ]
    assert sharpe_payload["rows"][0]["metric"] == "sharpe"
    assert sharpe_payload["rows"][0]["metric_value"] == pytest.approx(4.0)
    assert sharpe_payload["rows"][0]["score"] == pytest.approx(4.0)
    assert [row["id"] for row in maxdd_payload["rows"]] == [
        "beta-risk",
        "alpha-calmar",
    ]
    assert [row["id"] for row in paginated_maxdd_payload["rows"]] == [
        "beta-risk",
        "alpha-calmar",
    ]
    assert maxdd_payload["rows"][0]["metric"] == "max_drawdown"
    assert maxdd_payload["rows"][0]["metric_value"] == pytest.approx(-0.02)
    assert [row["id"] for row in calmar_payload["rows"]] == [
        "alpha-calmar",
        "beta-risk",
    ]
    assert calmar_payload["rows"][0]["metric"] == "calmar"
    assert calmar_payload["rows"][0]["metric_value"] == pytest.approx(5.0)


def test_leaderboard_uses_stored_metrics_without_reading_report_artifacts(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="secret",
    )
    report_dir = tmp_path / "reports" / "sub-alpha"
    report_dir.mkdir(parents=True)
    (report_dir / "summary.csv").write_text(
        "sharpe,annual_return,max_drawdown\n99,99,-0.99\n",
        encoding="utf-8",
    )

    class CountingArtifactReader:
        calls = 0

        def read(self, *_args: object, **_kwargs: object) -> dict[str, object]:
            self.calls += 1
            return {"summary": {"sharpe": 99.0}}

    artifact_reader = CountingArtifactReader()
    object.__setattr__(services, "artifact_reader", artifact_reader)
    _store_submission(
        app,
        submission_id="sub-alpha",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        metrics=SubmissionMetrics(
            annual_return=0.20,
            sharpe=2.0,
            max_drawdown=-0.04,
            annualized_short_profit=0.10,
        ),
    )
    stored = services.submission_repository.get("sub-alpha")
    services.submission_repository.save(
        Submission(
            submission_id=stored.submission_id,
            team_id=stored.team_id,
            status=stored.status,
            strategy_path=stored.strategy_path,
            report_dir=report_dir.as_posix(),
            fingerprints=stored.fingerprints,
            original_filename=stored.original_filename,
            data_track=stored.data_track,
            submission_number=stored.submission_number,
            metrics=stored.metrics,
            error_message=stored.error_message,
            submitted_at=stored.submitted_at,
            scored_at=stored.scored_at,
            config_snapshot=stored.config_snapshot,
        )
    )

    response = TestClient(app).get("/api/leaderboard")

    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert artifact_reader.calls == 0
    assert row["summary"]["sharpe"] == pytest.approx(2.0)


def test_submission_history_paginates_after_global_filter_and_sort(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="secret",
    )
    services.team_repository.create_team(
        team_id="team-beta",
        display_name="Beta Desk",
        password="secret",
    )
    services.team_repository.create_team(
        team_id="team-gamma",
        display_name="Gamma Desk",
        password="secret",
    )
    _store_submission(
        app,
        submission_id="alpha-old",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
    )
    _store_submission(
        app,
        submission_id="beta-newest",
        team_id="team-beta",
        submitted_at="2026-06-19T11:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
    )
    _store_submission(
        app,
        submission_id="beta-older",
        team_id="team-beta",
        submitted_at="2026-06-19T10:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
    )
    _store_submission(
        app,
        submission_id="gamma-hidden",
        team_id="team-gamma",
        submitted_at="2026-06-19T12:00:00+00:00",
    )

    response = TestClient(app).get(
        "/api/submissions",
        params={
            "limit": 1,
            "offset": 1,
            "search": "beta",
            "data_track": "learning",
            "sort_by": "submitted_at",
            "sort_dir": "desc",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 2
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert payload["has_next"] is False
    assert [row["submission_id"] for row in payload["submissions"]] == ["beta-older"]


def test_submission_history_sorts_by_calmar_metric(tmp_path: Path) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="secret",
    )
    services.team_repository.create_team(
        team_id="team-beta",
        display_name="Beta Desk",
        password="secret",
    )
    _store_submission(
        app,
        submission_id="newer-low-calmar",
        team_id="team-alpha",
        submitted_at="2026-06-19T11:00:00+00:00",
        metrics=SubmissionMetrics(sharpe=4.0, max_drawdown=-0.02, calmar=1.0),
    )
    _store_submission(
        app,
        submission_id="older-high-calmar",
        team_id="team-beta",
        submitted_at="2026-06-19T09:00:00+00:00",
        metrics=SubmissionMetrics(sharpe=1.0, max_drawdown=-0.08, calmar=5.0),
    )
    _store_submission(
        app,
        submission_id="failed-without-metrics",
        team_id="team-beta",
        submitted_at="2026-06-19T12:00:00+00:00",
        status=SubmissionStatus.FAILED,
        metrics=None,
    )

    response = TestClient(app).get(
        "/api/submissions",
        params={
            "limit": 10,
            "offset": 0,
            "sort_by": "calmar",
            "sort_dir": "desc",
        },
    )

    assert response.status_code == 200
    rows = response.json()["submissions"]
    assert [row["submission_id"] for row in rows] == [
        "older-high-calmar",
        "newer-low-calmar",
        "failed-without-metrics",
    ]
    assert rows[0]["metrics"]["calmar"] == pytest.approx(5.0)


def test_paginated_submission_history_enriches_only_visible_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="secret",
    )
    for index in range(3):
        _store_submission(
            app,
            submission_id=f"sub-{index}",
            team_id="team-alpha",
            submitted_at=f"2026-06-19T0{index}:00:00+00:00",
        )
    summarized: list[str] = []
    stale_checked: list[str] = []
    raw_text_checked: list[str] = []
    raw_presence_checked: list[str] = []

    def fake_summary(submission: Submission, artifact_reader: object | None = None) -> dict:
        summarized.append(submission.submission_id)
        return submission.metrics.to_dict() if submission.metrics else {}

    def fake_stale(*args: object, **kwargs: object) -> bool:
        submission = args[1]
        assert isinstance(submission, Submission)
        stale_checked.append(submission.submission_id)
        return False

    def fake_raw_error(submission: Submission) -> str | None:
        raw_text_checked.append(submission.submission_id)
        return None

    def fake_has_raw_error(submission: Submission) -> bool:
        raw_presence_checked.append(submission.submission_id)
        return False

    monkeypatch.setattr("quantfish.submissions.routes.score_summary_for_submission", fake_summary)
    monkeypatch.setattr("quantfish.submissions.routes._submission_stale", fake_stale)
    monkeypatch.setattr("quantfish.submissions.routes.raw_submission_error", fake_raw_error)
    monkeypatch.setattr("quantfish.submissions.routes.submission_has_raw_error", fake_has_raw_error)

    response = TestClient(app).get(
        "/api/submissions",
        params={
            "limit": 1,
            "offset": 1,
            "sort_by": "submission_number",
            "sort_dir": "asc",
        },
    )

    assert response.status_code == 200
    assert [row["submission_id"] for row in response.json()["submissions"]] == ["sub-1"]
    assert summarized == ["sub-1"]
    assert stale_checked == ["sub-1"]
    assert raw_text_checked == []
    assert raw_presence_checked == ["sub-1"]


def test_leaderboard_paginates_after_global_ranking_and_search(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    for team_id, name in (
        ("team-alpha", "Alpha Desk"),
        ("team-beta", "Beta Desk"),
        ("team-gamma", "Gamma Desk"),
    ):
        services.team_repository.create_team(team_id=team_id, display_name=name, password="secret")
    _store_submission(
        app,
        submission_id="alpha-mid",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        metrics=SubmissionMetrics(total_return=0.2, annual_return=0.2, sharpe=2.0),
    )
    _store_submission(
        app,
        submission_id="beta-best",
        team_id="team-beta",
        submitted_at="2026-06-19T10:00:00+00:00",
        metrics=SubmissionMetrics(total_return=0.5, annual_return=0.5, sharpe=5.0),
    )
    _store_submission(
        app,
        submission_id="gamma-low",
        team_id="team-gamma",
        submitted_at="2026-06-19T11:00:00+00:00",
        metrics=SubmissionMetrics(total_return=0.1, annual_return=0.1, sharpe=1.0),
    )

    response = TestClient(app).get(
        "/api/leaderboard",
        params={
            "limit": 1,
            "offset": 1,
            "search": "desk",
            "sort_by": "rank",
            "sort_dir": "asc",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 3
    assert payload["total_count"] == 3
    assert payload["limit"] == 1
    assert payload["offset"] == 1
    assert payload["has_next"] is True
    assert [row["id"] for row in payload["rows"]] == ["alpha-mid"]
    assert payload["rows"][0]["rank"] == 2


def test_leaderboard_no_param_response_includes_total_count_and_uses_track_query(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    hidden = _store_submission(
        app,
        submission_id="hidden-sub",
        team_id="team-hidden",
        submitted_at="2026-06-19T09:00:00+00:00",
        metrics=SubmissionMetrics(total_return=0.2, annual_return=0.2, sharpe=2.0),
    )
    _store_submission(
        app,
        submission_id="learning-sub",
        team_id="team-learning",
        submitted_at="2026-06-19T10:00:00+00:00",
        data_track=SubmissionDataTrack.LEARNING,
        metrics=SubmissionMetrics(total_return=0.9, annual_return=0.9, sharpe=9.0),
    )
    queried_tracks: list[SubmissionDataTrack] = []

    def fail_list_all() -> list[Submission]:
        raise AssertionError("leaderboard should not load every track")

    def list_for_track(track: SubmissionDataTrack) -> list[Submission]:
        queried_tracks.append(track)
        return [hidden]

    services.submission_repository.list_all = fail_list_all
    services.submission_repository.list_for_track = list_for_track

    response = TestClient(app).get("/api/leaderboard")

    assert response.status_code == 200
    payload = response.json()
    assert queried_tracks == [SubmissionDataTrack.HIDDEN_TEST]
    assert payload["count"] == 1
    assert payload["total_count"] == 1
    assert [row["id"] for row in payload["rows"]] == ["hidden-sub"]


def test_leaderboard_sorts_requested_metric_field_independent_of_active_metric(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    for team_id, name in (
        ("team-alpha", "Alpha Desk"),
        ("team-beta", "Beta Desk"),
        ("team-gamma", "Gamma Desk"),
    ):
        services.team_repository.create_team(team_id=team_id, display_name=name, password="secret")
    _store_submission(
        app,
        submission_id="alpha-high-sharpe-low-calmar",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        metrics=SubmissionMetrics(
            total_return=0.05,
            annual_return=0.05,
            sharpe=5.0,
            max_drawdown=-0.10,
            calmar=0.5,
        ),
    )
    _store_submission(
        app,
        submission_id="beta-low-sharpe-high-calmar",
        team_id="team-beta",
        submitted_at="2026-06-19T10:00:00+00:00",
        metrics=SubmissionMetrics(
            total_return=0.20,
            annual_return=0.20,
            sharpe=1.0,
            max_drawdown=-0.02,
            calmar=10.0,
        ),
    )
    _store_submission(
        app,
        submission_id="gamma-without-metrics",
        team_id="team-gamma",
        submitted_at="2026-06-19T11:00:00+00:00",
        status=SubmissionStatus.FAILED,
        metrics=None,
    )

    response = TestClient(app).get(
        "/api/leaderboard",
        params={
            "limit": 10,
            "offset": 0,
            "metric": "sharpe",
            "sort_by": "calmar",
            "sort_dir": "desc",
        },
    )

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert [row["id"] for row in rows] == [
        "beta-low-sharpe-high-calmar",
        "alpha-high-sharpe-low-calmar",
        "gamma-without-metrics",
    ]


def test_paginated_admin_submissions_omit_raw_error_and_fetch_it_lazily(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="secret",
    )
    older = _store_submission(
        app,
        submission_id="failed-older",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        status=SubmissionStatus.FAILED,
        metrics=None,
    )
    newest = _store_submission(
        app,
        submission_id="failed-newer",
        team_id="team-alpha",
        submitted_at="2026-06-19T10:00:00+00:00",
        status=SubmissionStatus.FAILED,
        metrics=None,
    )
    for submission, text in ((older, "older traceback"), (newest, "newer traceback")):
        report_dir = Path(submission.report_dir)
        report_dir.mkdir(parents=True)
        (report_dir / "worker_error.log").write_text(text, encoding="utf-8")
    client = TestClient(app)
    _login(client)

    listed = client.get(
        "/api/admin/submissions",
        params={
            "limit": 1,
            "offset": 0,
            "search": "alpha",
            "status": "failed",
            "sort_by": "submitted_at",
            "sort_dir": "desc",
        },
    )
    raw_error = client.get("/api/admin/submissions/failed-newer/raw-error")

    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total_count"] == 2
    assert payload["has_next"] is True
    assert [row["submission_id"] for row in payload["submissions"]] == ["failed-newer"]
    assert payload["submissions"][0]["has_raw_error"] is True
    assert "raw_error" not in payload["submissions"][0]
    assert raw_error.status_code == 200
    assert raw_error.text == "newer traceback"


def test_team_raw_error_endpoint_returns_own_failed_submission_log(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    services.team_repository.create_team(
        team_id="team-alpha",
        display_name="Alpha Desk",
        password="secret",
    )
    services.team_repository.create_team(
        team_id="team-beta",
        display_name="Beta Desk",
        password="secret",
    )
    submission = _store_submission(
        app,
        submission_id="failed-public",
        team_id="team-alpha",
        submitted_at="2026-06-19T09:00:00+00:00",
        status=SubmissionStatus.FAILED,
        metrics=None,
    )
    report_dir = Path(submission.report_dir)
    report_dir.mkdir(parents=True)
    (report_dir / "worker_error.log").write_text("public traceback", encoding="utf-8")

    client = TestClient(app)
    assert client.get("/api/submissions/failed-public/raw-error").status_code == 401
    _participant_login(client, team_name="Beta Desk")
    assert client.get("/api/submissions/failed-public/raw-error").status_code == 403
    _participant_login(client, team_name="Alpha Desk")
    response = client.get("/api/submissions/failed-public/raw-error")

    assert response.status_code == 200
    assert response.text == "public traceback"


def test_submission_numbers_survive_partial_delete_and_reset_after_full_delete(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path, submission_cooldown_seconds=0),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)

    team_response = client.post(
        "/api/admin/teams",
        json={"team_name": "Team Alpha", "password": "secret"},
    )
    assert team_response.status_code == 200

    submission_ids: list[str] = []
    for index in range(3):
        response = client.post(
            "/api/submissions",
            data={"team_name": "Team Alpha", "password": "secret"},
            files={
                "file": (
                    f"strategy_{index}.py",
                    f"def generate_signals(data):\n    return [{index}]\n".encode(),
                    "text/x-python",
                )
            },
        )
        assert response.status_code == 200
        submission_ids.append(response.json()["submission_id"])

    first_history = client.get("/api/submissions").json()["submissions"]
    assert [row["submission_label"] for row in first_history] == ["#1", "#2", "#3"]

    partial_delete = client.post(
        "/api/admin/submissions/delete",
        json={"submission_ids": [submission_ids[1]], "force": False},
    )
    assert partial_delete.status_code == 200

    fourth_upload = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy_4.py",
                b"def generate_signals(data):\n    return [4]\n",
                "text/x-python",
            )
        },
    )
    assert fourth_upload.status_code == 200
    assert fourth_upload.json()["submission_label"] == "#4"

    after_partial_delete = client.get("/api/submissions").json()["submissions"]
    assert [row["submission_label"] for row in after_partial_delete] == ["#1", "#3", "#4"]

    delete_all = client.post(
        "/api/admin/submissions/delete",
        json={
            "submission_ids": [row["submission_id"] for row in after_partial_delete],
            "force": False,
        },
    )
    assert delete_all.status_code == 200
    assert client.get("/api/submissions").json()["submissions"] == []

    reset_upload = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "secret"},
        files={
            "file": (
                "strategy_reset.py",
                b"def generate_signals(data):\n    return [1]\n",
                "text/x-python",
            )
        },
    )
    assert reset_upload.status_code == 200
    assert reset_upload.json()["submission_label"] == "#1"


def test_leaderboard_ignores_fingerprint_check_errors_without_stale_mark(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FailingFingerprintRunner(),
    )
    services = app.state.services
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    services.submission_repository.save(
        Submission(
            submission_id="sub-stale",
            team_id="team-stale",
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(tmp_path / "report").as_posix(),
            fingerprints=ScoreFingerprints(
                config_sha256="config",
                hidden_catalog_sha256="catalog",
                strategy_sha256="strategy",
                engine_version="engine",
            ),
            original_filename="strategy.py",
            metrics=SubmissionMetrics(sharpe=9.0),
        )
    )

    response = TestClient(app).get("/api/leaderboard")

    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row["stale"] is False
    assert row["eligible"] is True
    assert row["badge"] == "gold"


def test_manual_stale_marks_capture_completed_rows_and_revert_by_event(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    old_completed = _store_submission(
        app,
        submission_id="old-completed",
        team_id="team-alpha",
        status=SubmissionStatus.COMPLETED,
        submitted_at="2026-06-24T09:00:00+00:00",
        metrics=SubmissionMetrics(sharpe=1.0, trading_days=250),
    )
    _store_submission(
        app,
        submission_id="old-failed",
        team_id="team-alpha",
        status=SubmissionStatus.FAILED,
        submitted_at="2026-06-24T09:01:00+00:00",
    )
    _store_submission(
        app,
        submission_id="old-running",
        team_id="team-alpha",
        status=SubmissionStatus.RUNNING,
        submitted_at="2026-06-24T09:02:00+00:00",
    )

    client = TestClient(app)
    _login(client)

    first_mark = client.post("/api/admin/stale-marks")

    assert first_mark.status_code == 200
    first_entry = first_mark.json()["settings_history"][0]
    assert first_entry["entry_type"] == "stale_mark"
    assert first_entry["affected_count"] == 1
    assert first_entry["affected_submission_ids"] == [old_completed.submission_id]
    assert first_entry["reverted_at"] is None
    assert client.get("/api/submissions/old-completed").json()["stale"] is True
    assert client.get("/api/submissions/old-failed").json()["stale"] is False
    assert client.get("/api/submissions/old-running").json()["stale"] is False

    _store_submission(
        app,
        submission_id="new-completed",
        team_id="team-alpha",
        status=SubmissionStatus.COMPLETED,
        submitted_at="2026-06-24T09:03:00+00:00",
        metrics=SubmissionMetrics(sharpe=2.0, trading_days=250),
    )
    assert client.get("/api/submissions/new-completed").json()["stale"] is False

    second_mark = client.post("/api/admin/stale-marks")
    assert second_mark.status_code == 200
    second_entry = second_mark.json()["settings_history"][0]
    assert second_entry["affected_count"] == 2

    revert_first = client.post(
        f"/api/admin/stale-marks/{first_entry['entry_id']}/revert"
    )
    assert revert_first.status_code == 200
    assert client.get("/api/submissions/old-completed").json()["stale"] is True
    assert client.get("/api/submissions/new-completed").json()["stale"] is True

    revert_second = client.post(
        f"/api/admin/stale-marks/{second_entry['entry_id']}/revert"
    )
    assert revert_second.status_code == 200
    assert client.get("/api/submissions/old-completed").json()["stale"] is False
    assert client.get("/api/submissions/new-completed").json()["stale"] is False


def test_zero_result_completed_submission_is_stale_across_response_surfaces(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    zero_submission = _store_submission(
        app,
        submission_id="zero-completed",
        team_id="team-zero",
        status=SubmissionStatus.COMPLETED,
        submitted_at="2026-06-24T09:45:46+00:00",
        metrics=SubmissionMetrics(
            total_return=0.0,
            annual_return=0.0,
            average_year_return=0.0,
            worst_year_return=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            average_turnover=0.0,
            average_short_exposure=0.0,
            short_total_return=0.0,
            annualized_short_profit=0.0,
            calmar=0.0,
            win_rate=0.0,
            trading_days=3159,
        ),
    )
    client = TestClient(app)
    _login(client)

    submissions = client.get("/api/submissions").json()["submissions"]
    detail = client.get(f"/api/submissions/{zero_submission.submission_id}").json()
    leaderboard = client.get("/api/leaderboard").json()["rows"]
    dashboard = client.get("/api/dashboard").json()["latest"]
    admin_submissions = client.get("/api/admin/submissions").json()["submissions"]

    assert submissions[0]["submission_id"] == zero_submission.submission_id
    assert submissions[0]["status"] == "completed"
    assert submissions[0]["stale"] is True
    assert detail["status"] == "completed"
    assert detail["stale"] is True
    assert leaderboard[0]["id"] == zero_submission.submission_id
    assert leaderboard[0]["stale"] is True
    assert leaderboard[0]["eligible"] is False
    assert dashboard[0]["id"] == zero_submission.submission_id
    assert dashboard[0]["stale"] is True
    assert admin_submissions[0]["submission_id"] == zero_submission.submission_id
    assert admin_submissions[0]["status"] == "completed"
    assert admin_submissions[0]["stale"] is True


def test_dashboard_latest_is_ordered_by_submission_time_not_rank(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    old_strategy = tmp_path / "old.py"
    new_strategy = tmp_path / "new.py"
    old_strategy.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    new_strategy.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    fingerprints = ScoreFingerprints(
        config_sha256="config",
        hidden_catalog_sha256="catalog",
        strategy_sha256="def generate_signals(data):\n    return []\n",
        engine_version="fake",
    )
    services.submission_repository.save(
        Submission(
            submission_id="old-winner",
            team_id="team-old",
            status=SubmissionStatus.COMPLETED,
            strategy_path=old_strategy.as_posix(),
            report_dir=(tmp_path / "old-report").as_posix(),
            fingerprints=fingerprints,
            original_filename="old.py",
            metrics=SubmissionMetrics(sharpe=5.0),
            submitted_at="2026-06-19T09:00:00+00:00",
        )
    )
    services.submission_repository.save(
        Submission(
            submission_id="new-lower-score",
            team_id="team-new",
            status=SubmissionStatus.COMPLETED,
            strategy_path=new_strategy.as_posix(),
            report_dir=(tmp_path / "new-report").as_posix(),
            fingerprints=fingerprints,
            original_filename="new.py",
            metrics=SubmissionMetrics(sharpe=1.0),
            submitted_at="2026-06-19T10:00:00+00:00",
        )
    )

    response = TestClient(app).get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["latest"][0]["id"] == "new-lower-score"
    assert response.json()["latest"][1]["id"] == "old-winner"


def test_dashboard_and_leaderboard_do_not_call_fingerprint_checks_for_stale_state(
    tmp_path: Path,
) -> None:
    runner = ContextCountingRunner()
    app = create_app(_settings(tmp_path), submission_runner=runner)
    services = app.state.services
    for index in range(3):
        strategy_path = tmp_path / f"strategy-{index}.py"
        strategy_path.write_text(
            f"def generate_signals(data):\n    return [{index}]\n",
            encoding="utf-8",
        )
        services.submission_repository.save(
            Submission(
                submission_id=f"sub-{index}",
                team_id=f"team-{index}",
                status=SubmissionStatus.COMPLETED,
                strategy_path=strategy_path.as_posix(),
                report_dir=(tmp_path / f"report-{index}").as_posix(),
                fingerprints=runner.current_fingerprints(strategy_path),
                original_filename=f"strategy-{index}.py",
                metrics=SubmissionMetrics(sharpe=float(index + 1)),
                submitted_at=f"2026-06-19T09:0{index}:00+00:00",
            )
        )
    runner.context_calls = 0
    runner.fingerprint_calls = 0
    client = TestClient(app)

    leaderboard_response = client.get("/api/leaderboard")
    dashboard_response = client.get("/api/dashboard")

    assert leaderboard_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert runner.context_calls == 0
    assert runner.fingerprint_calls == 0


def test_dashboard_includes_backend_runner_status_snapshot(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    app = create_app(
        _settings(tmp_path, config_path=config_path),
        submission_runner=FakeSubmissionRunner(),
    )
    services = app.state.services
    queued_strategy = tmp_path / "queued.py"
    running_strategy = tmp_path / "running.py"
    queued_strategy.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    running_strategy.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    services.submission_repository.save(
        Submission(
            submission_id="queued-sub",
            team_id="team-queued",
            status=SubmissionStatus.QUEUED,
            strategy_path=queued_strategy.as_posix(),
            report_dir=(tmp_path / "queued-report").as_posix(),
            fingerprints=None,
            original_filename="queued.py",
            submitted_at="2026-06-19T09:00:00+00:00",
        )
    )
    services.submission_repository.save(
        Submission(
            submission_id="running-sub",
            team_id="team-running",
            status=SubmissionStatus.RUNNING,
            strategy_path=running_strategy.as_posix(),
            report_dir=(tmp_path / "running-report").as_posix(),
            fingerprints=None,
            original_filename="running.py",
            submitted_at="2026-06-19T09:01:00+00:00",
        )
    )
    client = TestClient(app)
    _login(client)

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    execution = ConfigRepository(config_path).load().execution
    expected_timeout = (
        execution.submission_timeout_seconds
        if execution.submission_timeout_enabled
        else None
    )
    runner_status = response.json()["runner_status"]
    assert runner_status["status"] == "online"
    assert runner_status["queued"] == 1
    assert runner_status["running"] == 1
    assert runner_status["submissions_enabled"] is True
    assert runner_status["scoring_timeout_seconds"] == expected_timeout
    assert datetime.fromisoformat(runner_status["updated_at"]).tzinfo is not None

    settings_response = client.patch(
        "/api/admin/settings",
        json={
            "execution": {
                "submissions_enabled": False,
                "submission_timeout_enabled": False,
            }
        },
    )
    assert settings_response.status_code == 200

    disabled_response = client.get("/api/dashboard")

    assert disabled_response.status_code == 200
    disabled_runner_status = disabled_response.json()["runner_status"]
    assert disabled_runner_status["status"] == "offline"
    assert disabled_runner_status["submissions_enabled"] is False
    assert "python_enabled" not in disabled_runner_status
    assert disabled_runner_status["scoring_timeout_seconds"] is None


def test_operational_execution_toggles_do_not_mark_existing_results_stale(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    runner = ConfigAwareFingerprintRunner(config_path)
    app = create_app(
        _settings(tmp_path, config_path=config_path),
        submission_runner=runner,
    )
    strategy_path = tmp_path / "completed.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    app.state.services.submission_repository.save(
        Submission(
            submission_id="completed-sub",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(tmp_path / "completed-report").as_posix(),
            fingerprints=runner.current_fingerprints(strategy_path),
            original_filename="completed.py",
            metrics=SubmissionMetrics(
                total_return=0.21,
                annual_return=0.18,
                sharpe=1.7,
                max_drawdown=-0.08,
                average_turnover=0.32,
                trading_days=250,
            ),
            submitted_at="2026-06-19T09:00:00+00:00",
            scored_at="2026-06-19T09:01:00+00:00",
        )
    )
    client = TestClient(app)
    _login(client)

    before_toggle = client.get("/api/submissions/completed-sub")
    assert before_toggle.status_code == 200
    assert before_toggle.json()["stale"] is False

    settings_response = client.patch(
        "/api/admin/settings",
        json={
            "execution": {
                "submissions_enabled": False,
                "hidden_test_enabled": False,
                "submission_timeout_enabled": False,
            }
        },
    )

    assert settings_response.status_code == 200
    assert settings_response.json()["execution"]["submissions_enabled"] is False
    assert settings_response.json()["execution"]["hidden_test_enabled"] is False
    assert settings_response.json()["execution"]["submission_timeout_enabled"] is False
    after_toggle = client.get("/api/submissions/completed-sub")
    dashboard = client.get("/api/dashboard").json()
    admin_rows = client.get("/api/admin/submissions").json()["submissions"]

    assert after_toggle.json()["stale"] is False
    assert dashboard["runner_status"]["status"] == "offline"
    assert dashboard["latest"][0]["id"] == "completed-sub"
    assert dashboard["latest"][0]["stale"] is False
    assert admin_rows[0]["submission_id"] == "completed-sub"
    assert admin_rows[0]["stale"] is False


def test_admin_settings_changes_create_history_without_stale_results(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    runner = ConfigAwareFingerprintRunner(config_path)
    app = create_app(
        _settings(tmp_path, config_path=config_path),
        submission_runner=runner,
    )
    strategy_path = tmp_path / "completed.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    app.state.services.submission_repository.save(
        Submission(
            submission_id="completed-sub",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(tmp_path / "completed-report").as_posix(),
            fingerprints=runner.current_fingerprints(strategy_path),
            original_filename="completed.py",
            metrics=SubmissionMetrics(total_return=0.21, sharpe=1.7),
            submitted_at="2026-06-24T09:00:00+00:00",
            scored_at="2026-06-24T09:01:00+00:00",
        )
    )
    client = TestClient(app)
    _login(client)

    response = client.patch(
        "/api/admin/settings",
        json={
            "backtest": {"capital": 2_000_000},
            "execution": {
                "max_concurrent_scoring": 4,
                "submission_timeout_seconds": 600,
                "submission_timeout_enabled": False,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["backtest"]["capital"] == 2_000_000
    assert payload["execution"]["max_concurrent_scoring"] == 4
    assert payload["execution"]["submission_timeout_seconds"] == 600
    assert payload["execution"]["submission_timeout_enabled"] is False
    assert len(payload["settings_history"]) == 1
    history = payload["settings_history"][0]
    assert history["entry_type"] == "settings_change"
    assert history["stale_marked"] is False
    assert history["changed_fields"] == [
        "backtest.capital",
        "execution.max_concurrent_scoring",
        "execution.submission_timeout_enabled",
        "execution.submission_timeout_seconds",
    ]
    assert client.get("/api/submissions/completed-sub").json()["stale"] is False


def test_admin_settings_history_revert_restores_previous_settings_without_stale(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    runner = ConfigAwareFingerprintRunner(config_path)
    app = create_app(
        _settings(tmp_path, config_path=config_path),
        submission_runner=runner,
    )
    strategy_path = tmp_path / "completed.py"
    strategy_path.write_text("def generate_signals(data):\n    return []\n", encoding="utf-8")
    app.state.services.submission_repository.save(
        Submission(
            submission_id="completed-sub",
            team_id="team-alpha",
            status=SubmissionStatus.COMPLETED,
            strategy_path=strategy_path.as_posix(),
            report_dir=(tmp_path / "completed-report").as_posix(),
            fingerprints=runner.current_fingerprints(strategy_path),
            original_filename="completed.py",
            metrics=SubmissionMetrics(total_return=0.21, sharpe=1.7),
            submitted_at="2026-06-24T10:00:00+00:00",
            scored_at="2026-06-24T10:01:00+00:00",
        )
    )
    client = TestClient(app)
    _login(client)

    changed = client.patch(
        "/api/admin/settings",
        json={"execution": {"max_leverage": 2.0}},
    )

    assert changed.status_code == 200
    history = changed.json()["settings_history"]
    assert len(history) == 1
    assert history[0]["entry_type"] == "settings_change"
    assert history[0]["changed_fields"] == ["execution.max_leverage"]
    assert history[0]["settings"]["execution"]["max_leverage"] == 1.0
    assert history[0]["stale_marked"] is False
    assert client.get("/api/submissions/completed-sub").json()["stale"] is False

    reverted = client.post(f"/api/admin/settings-history/{history[0]['entry_id']}/revert")

    assert reverted.status_code == 200
    assert reverted.json()["execution"]["max_leverage"] == 1.0
    assert reverted.json()["settings_history"][0]["settings"]["execution"]["max_leverage"] == 2.0
    assert ConfigRepository(config_path).load().execution.max_leverage == 1.0
    assert client.get("/api/submissions/completed-sub").json()["stale"] is False


def test_admin_change_history_keeps_scrolling_entries(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    client = TestClient(create_app(_settings(tmp_path, config_path=config_path)))
    _login(client)

    latest_payload = {}
    for index in range(11):
        response = client.patch(
            "/api/admin/settings",
            json={"execution": {"max_leverage": 1.1 + index / 10}},
        )
        assert response.status_code == 200
        latest_payload = response.json()

    history = latest_payload["settings_history"]
    assert len(history) == 11
    assert history[0]["settings"]["execution"]["max_leverage"] == pytest.approx(2.0)
    assert history[-1]["settings"]["execution"]["max_leverage"] == pytest.approx(1.0)


def test_admin_settings_history_revert_requires_auth_and_known_entry(
    tmp_path: Path,
) -> None:
    config_path = _copied_config(tmp_path)
    client = TestClient(create_app(_settings(tmp_path, config_path=config_path)))

    unauthorized = client.post("/api/admin/settings-history/missing/revert")
    assert unauthorized.status_code == 401

    _login(client)
    missing = client.post("/api/admin/settings-history/missing/revert")
    assert missing.status_code == 404

    unauthorized_stale = TestClient(create_app(_settings(tmp_path))).post("/api/admin/stale-marks")
    assert unauthorized_stale.status_code == 401
    missing_stale = client.post("/api/admin/stale-marks/missing/revert")
    assert missing_stale.status_code == 404


def test_admin_downloads_routes(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    _login(client)

    settings_response = client.get("/api/admin/settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["course"]["name"] == "QuantFish"

    starter_response = client.get("/api/downloads/starter-strategy.py")
    assert starter_response.status_code == 200
    assert "generate_signals" in starter_response.text
    assert "价格成交额动量 starter strategy" in starter_response.text
    assert "当天收益越高、成交越活跃" in starter_response.text
    assert "学生主要负责构造 score" in starter_response.text
    assert "dretwd" in starter_response.text
    assert "dnvaltrd" in starter_response.text
    assert "numeric_columns" in starter_response.text
    assert "pd.DataFrame" in starter_response.text


def test_submission_metrics_schema_exposes_geometric_basis(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    schema = app.openapi()["components"]["schemas"]["SubmissionMetrics"]["properties"]

    for field in (
        "cagr",
        "compounded_total_return",
        "compounded_max_drawdown",
        "compounded_calmar",
        "volatility",
        "sortino",
        "t_stat",
        "t_stat_p_value",
    ):
        assert field in schema


def test_mini_game_routes_are_removed(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    removed_paths = {
        "/api/mini-games/market",
        "/api/mini-games/market/setup",
        "/api/mini-games/market/trades",
        "/api/mini-games/market/ticks",
        "/api/mini-games/market/settle",
        "/api/mini-games/classroom-market/trades",
        "/api/mini-games/classroom-market/ticks",
        "/api/mini-games/messages",
        "/api/admin/mini-game-messages",
        "/api/admin/mini-game-messages/delete",
    }
    assert removed_paths.isdisjoint(app.openapi()["paths"])

    client = TestClient(app)
    _login(client)

    for path in (
        "/api/mini-games/market",
        "/api/mini-games/classroom-market/trades",
        "/api/mini-games/messages",
        "/api/admin/mini-game-messages",
    ):
        assert client.get(path).status_code == 404


def test_student_export_download_routes(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    object.__setattr__(
        app.state.services,
        "student_export_service",
        FakeStudentExportService(tmp_path / "exports"),
    )
    client = TestClient(app)

    options_response = client.get("/api/downloads/environment-options")
    assert options_response.status_code == 200
    options = options_response.json()["platforms"]
    assert options[0]["platform"] == "macos-arm64"
    assert options[0]["status"] == "available"
    assert options[1]["status"] == "missing"

    learning_response = client.get("/api/downloads/learning-data.zip")
    assert learning_response.status_code == 200
    assert learning_response.headers["content-type"].startswith("application/zip")
    assert "learning-data" in learning_response.headers["content-disposition"]

    environment_response = client.get("/api/downloads/environment/macos-arm64.zip")
    assert environment_response.status_code == 200
    assert environment_response.headers["content-type"].startswith("application/zip")
    assert "macos-arm64" in environment_response.headers["content-disposition"]

    missing_response = client.get("/api/downloads/environment/windows-x86_64.zip")
    assert missing_response.status_code == 404
    assert "not available" in missing_response.json()["detail"]


def test_admin_rejects_duplicate_team_without_overwriting_credentials(
    tmp_path: Path,
) -> None:
    app = create_app(
        _settings(tmp_path),
        submission_runner=FakeSubmissionRunner(),
    )
    client = TestClient(app)
    _login(client)

    first_response = client.post(
        "/api/admin/teams",
        json={
            "team_name": "Team Alpha",
            "password": "old-secret",
        },
    )
    duplicate_response = client.post(
        "/api/admin/teams",
        json={
            "team_name": "Team Alpha",
            "password": "new-secret",
        },
    )

    assert first_response.status_code == 200
    assert duplicate_response.status_code == 409
    assert "old-secret" not in (
        tmp_path / "runtime" / "repositories" / "teams.json"
    ).read_text(encoding="utf-8")

    old_password_upload = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "old-secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )
    new_password_upload = client.post(
        "/api/submissions",
        data={"team_name": "Team Alpha", "password": "new-secret"},
        files={
            "file": (
                "strategy.py",
                b"def generate_signals(data):\n    return []\n",
                "text/x-python",
            )
        },
    )

    assert old_password_upload.status_code == 200
    assert new_password_upload.status_code == 401


def test_completed_submission_with_missing_artifacts_does_not_break_api(
    tmp_path: Path,
) -> None:
    app = create_app(_settings(tmp_path))
    services = app.state.services
    report_dir = tmp_path / "runtime" / "submissions" / "sub-missing" / "reports"
    report_dir.mkdir(parents=True)
    services.submission_repository.save(
        Submission(
            submission_id="sub-missing",
            team_id="team-missing",
            status=SubmissionStatus.COMPLETED,
            strategy_path=(tmp_path / "strategy.py").as_posix(),
            report_dir=report_dir.as_posix(),
            fingerprints=None,
            original_filename="strategy.py",
            metrics=SubmissionMetrics(sharpe=1.0),
        )
    )

    client = TestClient(app)
    detail_response = client.get("/api/submissions/sub-missing")
    compare_response = client.get(
        "/api/compare",
        params=[("submission_id", "sub-missing")],
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["artifacts"] == {
        "summary": {},
        "graph_data": {},
        "diagnostics": {},
        "performance_table": [],
        "parquet": {},
    }
    assert detail_response.json()["performance_table"] == []
    assert detail_response.json()["execution_parameters"] is None
    assert compare_response.status_code == 200
    assert compare_response.json()["submissions"][0]["equity"] == []
    assert compare_response.json()["submissions"][0]["drawdown"] == []
    assert compare_response.json()["submissions"][0]["execution_parameters"] is None

    rich_compare_response = client.get(
        "/api/compare",
        params=[("submission_id", "sub-missing"), ("include_graph_data", "true")],
    )
    assert rich_compare_response.status_code == 200
    assert rich_compare_response.json()["submissions"][0]["execution_parameters"] is None
    assert rich_compare_response.json()["submissions"][0]["graph_data"] == {}


def test_submission_detail_reads_complete_report_when_status_is_stale(
    tmp_path: Path,
) -> None:
    app = create_app(_settings(tmp_path))
    services = app.state.services
    report_dir = tmp_path / "runtime" / "reports" / "sub-stale"
    report_dir.mkdir(parents=True)
    (report_dir / "summary.csv").write_text(
        "total_return,annual_return,sharpe,max_drawdown,average_turnover,win_rate,trading_days\n"
        "0.67,0.22,2.1,0.04,0.31,0.58,120\n",
        encoding="utf-8",
    )
    (report_dir / "graph_data.json").write_text(
        '{"equity":[{"date":"2020-01-01","equity":1.0},{"date":"2020-12-31","equity":1.67}],'
        '"drawdown":[{"date":"2020-12-31","drawdown":-0.04}]}',
        encoding="utf-8",
    )
    services.submission_repository.save(
        Submission(
            submission_id="sub-stale",
            team_id="team-stale",
            status=SubmissionStatus.QUEUED,
            strategy_path=(tmp_path / "strategy.py").as_posix(),
            report_dir=report_dir.as_posix(),
            fingerprints=None,
            original_filename="strategy.py",
            metrics=None,
        )
    )

    client = TestClient(app)
    detail_response = client.get("/api/submissions/sub-stale")
    compare_response = client.get(
        "/api/compare",
        params=[("submission_id", "sub-stale"), ("include_graph_data", "true")],
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "queued"
    assert detail["artifacts"]["summary"]["total_return"] == 0.67
    assert detail["artifacts"]["graph_data"]["equity"][1]["equity"] == 1.67
    assert detail["performance_table"] == []
    assert detail["score"] == pytest.approx(
        45.0
        + 35.0 * (0.22 / 0.30)
        - 15.0 * (0.04 / 0.30)
        - 5.0 * (0.31 / 3.0)
    )

    assert compare_response.status_code == 200
    compared = compare_response.json()["submissions"][0]
    assert compared["status"] == "queued"
    assert compared["equity"][1]["equity"] == 1.67
    assert compared["drawdown"][0]["drawdown"] == -0.04
    assert compared["graph_data"]["equity"][1]["equity"] == 1.67


def test_admin_create_team_requires_login(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.post(
        "/api/admin/teams",
        json={
            "team_name": "Team Alpha",
            "password": "secret",
        },
    )

    assert response.status_code == 401


def test_admin_read_routes_require_login(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    for path in ("/api/admin/settings", "/api/admin/teams"):
        assert client.get(path).status_code == 401
    _login(client)
    for path in ("/api/admin/settings", "/api/admin/teams"):
        assert client.get(path).status_code == 200
