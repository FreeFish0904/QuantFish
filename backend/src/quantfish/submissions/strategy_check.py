"""Pre-check a student strategy file without scoring it.

Run as `python -m quantfish.submissions.strategy_check ...` from a throw-away
directory so a runaway strategy can be killed by the caller instead of hanging
the web process. The runner writes a JSON payload to `--result` (never to
stdout, which the student code is free to spam) and exits non-zero when the
strategy does not produce usable signals.

The check executes `generate_signals` for the last N trading dates of the
configured window: enough to catch import errors, wrong return types, invalid
stock codes and empty output, without paying for a full panel build.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pandas as pd

from quantfish.factor_execution import (
    StrategyExecutionConfig,
    StrategySignalError,
    execute_student_strategy,
)
from quantfish.market_types import normalize_allowed_market_types
from quantfish.platform_config import ConfigRepository
from quantfish.submissions.models import SubmissionDataTrack, _submission_data_track
from quantfish.submissions.track_config import track_release_root

SAMPLE_CODE_LIMIT = 5


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-check one QuantFish strategy.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument(
        "--data-track",
        choices=[item.value for item in SubmissionDataTrack],
        default=SubmissionDataTrack.HIDDEN_TEST.value,
    )
    parser.add_argument("--max-trading-dates", type=int, default=20)
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    track = _submission_data_track(args.data_track)
    started = time.perf_counter()
    try:
        config = ConfigRepository(config_path).load()
        window = config.data_releases.release_window(track.value)
        execution_config = StrategyExecutionConfig(
            data_start=window.start,
            scoring_end=window.end,
            allowed_market_types=normalize_allowed_market_types(
                getattr(config.execution, "allowed_market_types", None)
            ),
            max_trading_dates=args.max_trading_dates,
        )
        with (
            open(os.devnull, "w", encoding="utf-8") as sink,
            redirect_stdout(sink),
            redirect_stderr(sink),
        ):
            execution = execute_student_strategy(
                Path(args.strategy),
                _resolve_release_root(config_path, track_release_root(config, track)),
                execution_config,
            )
        payload = _success_payload(execution.scores, execution.diagnostics, track)
    except StrategySignalError as exc:
        payload = _failure_payload("invalid_signals", str(exc), track)
    except Exception as exc:
        payload = _failure_payload(
            "strategy_error",
            f"{type(exc).__name__}: {exc}",
            track,
        )
        payload["traceback"] = traceback.format_exc(limit=5)
    payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    Path(args.result).write_text(json.dumps(payload), encoding="utf-8")
    return 0 if payload["ok"] else 1


def _success_payload(
    scores: pd.DataFrame,
    diagnostics: dict,  # type: ignore[type-arg]
    track: SubmissionDataTrack,
) -> dict:  # type: ignore[type-arg]
    dates = (
        scores["date"] if "date" in scores.columns else pd.Series(dtype="datetime64[ns]")
    )
    unique_dates = sorted(pd.to_datetime(dates).dropna().unique().tolist())
    codes = sorted(set(scores["code"])) if "code" in scores.columns else []
    trading_dates_checked = int(diagnostics.get("trading_dates_checked") or 0)
    signal_dates = len(unique_dates)
    if signal_dates == 0:
        return {
            "ok": False,
            "code": "no_signals",
            "message": (
                "generate_signals returned no usable rows for the last "
                f"{trading_dates_checked} trading dates"
            ),
            "data_track": track.value,
            "trading_dates_checked": trading_dates_checked,
            "signal_rows": 0,
            "signal_dates": 0,
            "warnings": [],
        }
    warnings: list[str] = []
    if signal_dates < trading_dates_checked:
        warnings.append(
            f"signals were produced on {signal_dates} of {trading_dates_checked} "
            "checked trading dates"
        )
    return {
        "ok": True,
        "code": "ok",
        "message": "strategy produced usable signals",
        "data_track": track.value,
        "trading_dates_checked": trading_dates_checked,
        "signal_rows": len(scores),
        "signal_dates": signal_dates,
        "first_signal_date": _iso_date(unique_dates[0]),
        "last_signal_date": _iso_date(unique_dates[-1]),
        "sample_codes": [str(code) for code in codes[:SAMPLE_CODE_LIMIT]],
        "warnings": warnings,
    }


def _failure_payload(
    code: str,
    message: str,
    track: SubmissionDataTrack,
) -> dict:  # type: ignore[type-arg]
    return {
        "ok": False,
        "code": code,
        "message": message,
        "data_track": track.value,
        "warnings": [],
    }


def _iso_date(value: object) -> str | None:
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def _resolve_release_root(config_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    config_dir = config_path.resolve().parent
    base_dir = config_dir.parent if config_dir.name == "config" else config_dir
    return base_dir / path


if __name__ == "__main__":
    raise SystemExit(main())
