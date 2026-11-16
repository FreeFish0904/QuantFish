from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path


@dataclass(frozen=True)
class WebSettings:
    runtime_root: Path = Path("runs/web_platform")
    config_path: Path = Path("config/platform.yaml")
    frontend_dist: Path = Path("frontend/dist")
    max_upload_bytes: int = 1_000_000
    submission_cooldown_seconds: float = 2.0
    scoring_timeout_seconds: int = 120
    engine_version: str = field(default_factory=lambda: _default_engine_version())
    cors_allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: _cors_allowed_origins()
    )
    student_exports_enabled: bool = True
    admin_password: str = field(
        default_factory=lambda: os.environ.get("QUANTFISH_ADMIN_PASSWORD", "")
    )
    admin_session_secret: str = field(
        default_factory=lambda: os.environ.get("QUANTFISH_ADMIN_SESSION_SECRET", "")
    )
    participant_session_secret: str = field(
        default_factory=lambda: os.environ.get(
            "QUANTFISH_PARTICIPANT_SESSION_SECRET",
            "",
        )
    )

    @property
    def submissions_root(self) -> Path:
        return self.runtime_root / "submissions"

    @property
    def reports_root(self) -> Path:
        return self.runtime_root / "reports"

    @property
    def exports_root(self) -> Path:
        return self.runtime_root / "exports"

    @property
    def repositories_root(self) -> Path:
        return self.runtime_root / "repositories"

    def ensure_runtime_dirs(self) -> None:
        for path in (
            self.runtime_root,
            self.submissions_root,
            self.reports_root,
            self.exports_root,
            self.repositories_root,
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def _default_engine_version() -> str:
    override = os.environ.get("QUANTFISH_ENGINE_VERSION", "").strip()
    if override:
        return override
    try:
        package_version = version("quantfish")
    except PackageNotFoundError:
        package_version = "0.1.0"
    package_root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(package_root.rglob("*.py")):
        relative_path = path.relative_to(package_root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"quantfish-{package_version}+source.{digest.hexdigest()[:12]}"


def _cors_allowed_origins() -> tuple[str, ...]:
    raw = os.environ.get("QUANTFISH_CORS_ALLOWED_ORIGINS", "")
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())
