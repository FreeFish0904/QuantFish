from __future__ import annotations

import json
from pathlib import Path
from typing import Any


RAW_ERROR_LOGS = ("worker_error.log", "worker_stderr.log", "worker_stdout.log")
WORKER_FAILURE_FILE = "worker_failure.json"


def worker_failure_message(report_dir: Path | str) -> str | None:
    path = Path(report_dir) / WORKER_FAILURE_FILE
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, str):
        return None
    normalized = message.strip()
    return normalized or None


def submission_has_raw_error(submission: Any) -> bool:
    report_dir = Path(str(getattr(submission, "report_dir", "")))
    for filename in RAW_ERROR_LOGS:
        try:
            if (report_dir / filename).stat().st_size > 0:
                return True
        except OSError:
            continue
    error_message = getattr(submission, "error_message", None)
    return bool(str(error_message).strip()) if error_message is not None else False


def raw_submission_error(submission: Any) -> str | None:
    report_dir = Path(str(getattr(submission, "report_dir", "")))
    for filename in RAW_ERROR_LOGS:
        path = report_dir / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    error_message = getattr(submission, "error_message", None)
    if error_message is None:
        return None
    text = str(error_message).strip()
    return text or None
