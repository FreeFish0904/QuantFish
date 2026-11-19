from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.web_app.app import create_app
from quantfish.web_app.readiness import build_readiness_report
from quantfish.web_app.settings import WebSettings


def _config(tmp_path: Path) -> Path:
    config_path = tmp_path / "platform.yaml"
    if not config_path.exists():
        ConfigRepository(config_path).save(PlatformConfig.default())
    return config_path


def _settings(
    tmp_path: Path,
    *,
    config_path: Path | None = None,
    frontend_dist: Path | None = None,
    runtime_root: Path | None = None,
) -> WebSettings:
    return WebSettings(
        runtime_root=runtime_root or tmp_path / "runtime",
        config_path=config_path or _config(tmp_path),
        frontend_dist=frontend_dist or tmp_path / "missing-frontend-dist",
        admin_password="quantfish-admin",
        admin_session_secret="test-session-secret",
        participant_session_secret="test-participant-session-secret",
        student_exports_enabled=False,
    )


class _Store:
    def ping(self) -> None:
        return None


class _BrokenStore:
    def ping(self) -> None:
        raise sqlite3.OperationalError("database is locked")


class _Config:
    def load(self) -> object:
        return object()


class _Dispatcher:
    def __init__(self, started: bool = True, stopped: bool = False) -> None:
        self.started = started
        self.stopped = stopped

    def status(self) -> dict[str, object]:
        return {
            "started": self.started,
            "stopped": self.stopped,
            "active_submissions": 2,
        }


def _report(
    settings: WebSettings,
    *,
    store: object | None = None,
    config: object | None = None,
    dispatcher: object | None = None,
):
    return build_readiness_report(
        settings=settings,
        submission_repository=store or _Store(),  # type: ignore[arg-type]
        config_repository=config or _Config(),  # type: ignore[arg-type]
        scoring_dispatcher=dispatcher or _Dispatcher(),  # type: ignore[arg-type]
    )


def test_ready_reports_ok_for_a_healthy_instance(tmp_path: Path) -> None:
    frontend_dist = tmp_path / "dist"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")

    app = create_app(_settings(tmp_path, frontend_dist=frontend_dist))

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "QuantFish"
    assert {check["name"] for check in payload["checks"]} == {
        "runtime_root",
        "submission_store",
        "platform_config",
        "frontend_bundle",
        "scoring_dispatcher",
    }
    assert all(check["ok"] for check in payload["checks"])


def test_ready_degrades_but_stays_available_without_a_frontend_bundle(
    tmp_path: Path,
) -> None:
    app = create_app(_settings(tmp_path, frontend_dist=tmp_path / "no-dist"))

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["frontend_bundle"]["ok"] is False
    assert checks["frontend_bundle"]["critical"] is False


def test_ready_returns_503_when_the_platform_config_is_missing(
    tmp_path: Path,
) -> None:
    app = create_app(_settings(tmp_path, config_path=tmp_path / "absent.yaml"))

    with TestClient(app) as client:
        response = client.get("/api/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unavailable"
    checks = {check["name"]: check for check in payload["checks"]}
    assert checks["platform_config"]["ok"] is False
    assert checks["platform_config"]["critical"] is True


def test_ready_returns_503_when_the_submission_store_fails(tmp_path: Path) -> None:
    report = _report(_settings(tmp_path), store=_BrokenStore())

    assert report.status == "unavailable"
    assert report.http_status_code == 503
    check = next(item for item in report.checks if item.name == "submission_store")
    assert check.ok is False
    assert check.detail is not None
    assert "OperationalError" in check.detail


def test_ready_returns_503_when_the_runtime_root_is_not_writable(
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "runtime"
    blocked.write_text("not a directory", encoding="utf-8")

    report = _report(_settings(tmp_path, runtime_root=blocked))

    assert report.http_status_code == 503
    check = next(item for item in report.checks if item.name == "runtime_root")
    assert check.critical is True
    assert check.ok is False


def test_stopped_dispatcher_only_degrades(tmp_path: Path) -> None:
    report = _report(
        _settings(tmp_path),
        dispatcher=_Dispatcher(started=False, stopped=True),
    )

    assert report.status == "degraded"
    assert report.http_status_code == 200
    check = next(item for item in report.checks if item.name == "scoring_dispatcher")
    assert check.ok is False


def test_ready_payload_reports_dispatcher_load(tmp_path: Path) -> None:
    report = _report(_settings(tmp_path))

    check = next(item for item in report.checks if item.name == "scoring_dispatcher")
    assert check.ok is True
    assert check.detail == "active=2"


def test_api_requests_are_logged_with_a_request_id(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="quantfish.web.request")
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        response = client.get("/api/leaderboard")

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 12
    lines = [record.getMessage() for record in caplog.records]
    assert any(
        "event=request" in line
        and "path=/api/leaderboard" in line
        and f"request_id={request_id}" in line
        for line in lines
    )


def test_health_probes_are_not_logged_as_requests(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="quantfish.web.request")
    app = create_app(_settings(tmp_path))

    with TestClient(app) as client:
        client.get("/api/health")

    assert not [
        record for record in caplog.records if "event=request" in record.getMessage()
    ]


def test_container_healthcheck_probes_readiness_not_liveness() -> None:
    project_root = Path(__file__).resolve().parents[2]

    dockerfile = (project_root / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    compose = (project_root / "deploy" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert "/api/ready" in dockerfile
    assert "/api/ready" in compose
    assert "/api/health" not in dockerfile
    assert "/api/health" not in compose
