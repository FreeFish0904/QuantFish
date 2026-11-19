from __future__ import annotations

import logging
from pathlib import Path

import pytest

from quantfish import observability
from quantfish.observability import (
    configure_logging,
    format_event,
    get_logger,
    log_event,
)
from quantfish.submissions.runners import ScoreWorkerHandle, _tail


@pytest.fixture(autouse=True)
def _reset_logging(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(observability, "_configured", False)
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    for handler in list(root.handlers):
        if handler not in original_handlers:
            root.removeHandler(handler)
    root.setLevel(original_level)


def test_format_event_sorts_keys_and_skips_none() -> None:
    line = format_event(
        "score_completed",
        {"submission_id": "sub-1", "sharpe": 1.25, "team_id": None},
    )

    assert line == "event=score_completed sharpe=1.25 submission_id=sub-1"


def test_format_event_quotes_values_with_separators() -> None:
    line = format_event(
        "request_failed",
        {"detail": 'boom "quoted"', "path": "/api/leaderboard", "empty": ""},
    )

    assert 'detail="boom \\"quoted\\""' in line
    assert 'empty=""' in line
    assert " path=/api/leaderboard" in line


def test_format_event_renders_booleans_as_json_literals() -> None:
    assert format_event("ready", {"ok": True, "stopped": False}) == (
        "event=ready ok=true stopped=false"
    )


def test_configure_logging_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    root = logging.getLogger()
    before = len(root.handlers)

    configure_logging("WARNING")
    configure_logging("WARNING")

    assert len(root.handlers) == before + 1
    assert root.level == logging.WARNING


def test_configure_logging_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFISH_LOG_LEVEL", "debug")

    configure_logging()

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_falls_back_to_info_for_unknown_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUANTFISH_LOG_LEVEL", "chatty")

    configure_logging()

    assert logging.getLogger().level == logging.INFO


def test_get_logger_keeps_the_quantfish_prefix() -> None:
    assert get_logger("web.request").name == "quantfish.web.request"
    assert get_logger("quantfish.web.request").name == "quantfish.web.request"
    assert get_logger().name == "quantfish"


def test_log_event_skips_formatting_when_the_level_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logger = get_logger("test.disabled")
    logger.setLevel(logging.WARNING)
    called: list[str] = []
    monkeypatch.setattr(
        observability,
        "format_event",
        lambda event, fields: called.append(event) or "",
    )

    log_event(logger, logging.DEBUG, "ignored")
    log_event(logger, logging.WARNING, "kept")

    assert called == ["kept"]


class _FailedWorkerProcess:
    returncode = 1

    def __init__(self, stderr: str) -> None:
        self.stderr = stderr

    def communicate(self, timeout: int | None = None) -> tuple[str, str]:
        return "", self.stderr


def test_failed_score_worker_logs_the_stderr_tail(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="quantfish.submissions.runner")
    process = _FailedWorkerProcess("Traceback (most recent call last):\nValueError: boom")
    handle = ScoreWorkerHandle(process, ["python", "-m"], None, tmp_path)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError):
        handle.wait()

    lines = [record.getMessage() for record in caplog.records]
    assert any(
        "event=score_worker_failed" in line and "ValueError: boom" in line
        for line in lines
    )


def test_stderr_tail_is_empty_for_blank_output() -> None:
    assert _tail(None) is None
    assert _tail("   \n") is None


def test_stderr_tail_keeps_the_end_of_long_output() -> None:
    text = "x" * 5000 + "tail-marker"

    trimmed = _tail(text)

    assert trimmed is not None
    assert trimmed.endswith("tail-marker")
    assert len(trimmed) == 2000
