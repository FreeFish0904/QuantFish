from pathlib import Path

import pytest

from quantfish.web_app.app import (
    _missing_app_credentials,
    create_app,
)
from quantfish.web_app.settings import WebSettings, _default_engine_version


def test_environment_credentials_must_all_be_explicit(monkeypatch) -> None:
    names = (
        "QUANTFISH_ADMIN_PASSWORD",
        "QUANTFISH_ADMIN_SESSION_SECRET",
        "QUANTFISH_PARTICIPANT_SESSION_SECRET",
    )
    for name in names:
        monkeypatch.delenv(name, raising=False)

    assert _missing_app_credentials(WebSettings()) == names

    for name in names:
        monkeypatch.setenv(name, f"explicit-{name.lower()}")

    assert _missing_app_credentials(WebSettings()) == ()


def test_create_app_rejects_missing_credentials_before_writing_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in (
        "QUANTFISH_ADMIN_PASSWORD",
        "QUANTFISH_ADMIN_SESSION_SECRET",
        "QUANTFISH_PARTICIPANT_SESSION_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = WebSettings(runtime_root=tmp_path / "runtime")

    assert _missing_app_credentials(settings) == (
        "QUANTFISH_ADMIN_PASSWORD",
        "QUANTFISH_ADMIN_SESSION_SECRET",
        "QUANTFISH_PARTICIPANT_SESSION_SECRET",
    )
    with pytest.raises(
        ValueError,
        match="web app construction requires explicit credentials",
    ):
        create_app(settings)
    assert not settings.runtime_root.exists()


def test_create_app_accepts_explicit_programmatic_credentials(tmp_path: Path) -> None:
    settings = WebSettings(
        runtime_root=tmp_path / "runtime",
        admin_password="explicit-admin-password",
        admin_session_secret="explicit-admin-session-secret",
        participant_session_secret="explicit-participant-session-secret",
    )

    app = create_app(settings)

    assert _missing_app_credentials(settings) == ()
    assert app.state.services.settings is settings


def test_default_engine_version_tracks_source_and_supports_override(monkeypatch) -> None:
    monkeypatch.delenv("QUANTFISH_ENGINE_VERSION", raising=False)
    _default_engine_version.cache_clear()
    source_version = _default_engine_version()
    assert source_version.startswith("quantfish-")
    assert "+source." in source_version

    monkeypatch.setenv("QUANTFISH_ENGINE_VERSION", "course-engine-2026-07-18")
    _default_engine_version.cache_clear()
    assert _default_engine_version() == "course-engine-2026-07-18"
    _default_engine_version.cache_clear()
