"""Structured, dependency-free logging helpers.

The platform is one uvicorn process plus short-lived score-worker
subprocesses, so plain `logging` to stderr is enough. What matters here is the
shape of each line: `event=<name> key=value key=value`, which keeps logs
greppable without pulling in a JSON stack.

Rules:

- log identifiers (`submission_id`, `team_id`), never passwords, session
  cookies or uploaded strategy bodies;
- log durations as milliseconds, so slow requests and slow scores stand out;
- raise the level with `QUANTFISH_LOG_LEVEL` instead of editing the code.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

LOGGER_NAME = "quantfish"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
_DEFAULT_LEVEL = "INFO"
_SEPARATORS = frozenset(' \t\n"=')
_configured = False


def configure_logging(level: str | int | None = None) -> None:
    """Install the stderr handler once; safe to call from every entry point."""
    global _configured
    root = logging.getLogger()
    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root.addHandler(handler)
        _configured = True
    root.setLevel(_coerce_level(level))


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return a `quantfish.*` logger so all platform logs share one prefix."""
    if name == LOGGER_NAME or name.startswith(f"{LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    /,
    **fields: Any,
) -> None:
    """Log one structured line, skipping the work when the level is off."""
    if not logger.isEnabledFor(level):
        return
    logger.log(level, "%s", format_event(event, fields))


def format_event(event: str, fields: dict[str, Any]) -> str:
    parts = [f"event={event}"]
    for key in sorted(fields):
        value = fields[key]
        if value is None:
            continue
        parts.append(f"{key}={_format_value(value)}")
    return " ".join(parts)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if not text:
        return '""'
    if any(character in _SEPARATORS for character in text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _coerce_level(level: str | int | None) -> int:
    raw = level if level is not None else os.environ.get("QUANTFISH_LOG_LEVEL")
    if raw is None or raw == "":
        raw = _DEFAULT_LEVEL
    if isinstance(raw, int):
        return raw
    resolved = logging.getLevelName(str(raw).strip().upper())
    return resolved if isinstance(resolved, int) else logging.INFO
