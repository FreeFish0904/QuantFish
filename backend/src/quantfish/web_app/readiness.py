"""Readiness probing for `GET /api/ready`.

`/api/health` answers "is this process alive". This module answers the question
an operator actually has: "can this instance serve students right now", i.e. is
the runtime directory writable, is the submission store reachable, does the
platform config parse.

Checks are split into `critical` (a failure makes the endpoint return 503) and
optional ones (a failure only downgrades the status to `degraded`), so a
half-provisioned demo deployment still reports reachable instead of flapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from quantfish.web_app.settings import WebSettings

STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_UNAVAILABLE = "unavailable"


class SubmissionStore(Protocol):
    def ping(self) -> None: ...


class ConfigLoader(Protocol):
    def load(self) -> Any: ...


class ScoringDispatcher(Protocol):
    def status(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    critical: bool
    ok: bool
    detail: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "critical": self.critical,
            "ok": self.ok,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple[ReadinessCheck, ...]

    @property
    def status(self) -> str:
        if any(check.critical and not check.ok for check in self.checks):
            return STATUS_UNAVAILABLE
        if any(not check.ok for check in self.checks):
            return STATUS_DEGRADED
        return STATUS_OK

    @property
    def http_status_code(self) -> int:
        return 503 if self.status == STATUS_UNAVAILABLE else 200


def build_readiness_report(
    *,
    settings: WebSettings,
    submission_repository: SubmissionStore,
    config_repository: ConfigLoader,
    scoring_dispatcher: ScoringDispatcher,
) -> ReadinessReport:
    checks = [
        _check_runtime_root(settings),
        _check_submission_store(submission_repository),
        _check_platform_config(config_repository, settings),
        _check_frontend_bundle(settings),
        _check_scoring_dispatcher(scoring_dispatcher),
    ]
    return ReadinessReport(checks=tuple(checks))


def _check_runtime_root(settings: WebSettings) -> ReadinessCheck:
    probe = settings.runtime_root / ".readiness-probe"
    try:
        settings.runtime_root.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return ReadinessCheck(
            name="runtime_root",
            critical=True,
            ok=False,
            detail=f"runtime root is not writable: {type(exc).__name__}",
        )
    return ReadinessCheck(name="runtime_root", critical=True, ok=True)


def _check_submission_store(repository: SubmissionStore) -> ReadinessCheck:
    try:
        repository.ping()
    except Exception as exc:
        return ReadinessCheck(
            name="submission_store",
            critical=True,
            ok=False,
            detail=f"submission database is unreachable: {type(exc).__name__}",
        )
    return ReadinessCheck(name="submission_store", critical=True, ok=True)


def _check_platform_config(
    repository: ConfigLoader,
    settings: WebSettings,
) -> ReadinessCheck:
    if not Path(settings.config_path).exists():
        return ReadinessCheck(
            name="platform_config",
            critical=True,
            ok=False,
            detail="config/platform.yaml is missing",
        )
    try:
        repository.load()
    except Exception as exc:
        return ReadinessCheck(
            name="platform_config",
            critical=True,
            ok=False,
            detail=f"platform config does not load: {type(exc).__name__}",
        )
    return ReadinessCheck(name="platform_config", critical=True, ok=True)


def _check_frontend_bundle(settings: WebSettings) -> ReadinessCheck:
    index = Path(settings.frontend_dist) / "index.html"
    if not index.is_file():
        return ReadinessCheck(
            name="frontend_bundle",
            critical=False,
            ok=False,
            detail="frontend build is missing; the API is up but the UI is not served",
        )
    return ReadinessCheck(name="frontend_bundle", critical=False, ok=True)


def _check_scoring_dispatcher(dispatcher: ScoringDispatcher) -> ReadinessCheck:
    try:
        state = dispatcher.status()
    except Exception as exc:
        return ReadinessCheck(
            name="scoring_dispatcher",
            critical=False,
            ok=False,
            detail=f"dispatcher state is unavailable: {type(exc).__name__}",
        )
    if state.get("stopped") or not state.get("started"):
        return ReadinessCheck(
            name="scoring_dispatcher",
            critical=False,
            ok=False,
            detail="scoring dispatcher is not running; submissions will queue",
        )
    return ReadinessCheck(
        name="scoring_dispatcher",
        critical=False,
        ok=True,
        detail=f"active={state.get('active_submissions', 0)}",
    )
