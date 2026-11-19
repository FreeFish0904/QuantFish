from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pandas as pd

from quantfish.backtest import run_student_backtest
from quantfish.backtest.report_writer import write_backtest_report
from quantfish.backtest.simulator import TerminalStalePositionsError
from quantfish.platform_config import ConfigRepository
from quantfish.submissions.error_details import WORKER_FAILURE_FILE
from quantfish.submissions.models import (
    SubmissionDataTrack,
    SubmissionMetrics,
    _submission_data_track,
)
from quantfish.submissions.track_config import track_release_root, track_scoring_config


def score_submission(
    config_path: Path,
    strategy_path: Path,
    report_dir: Path,
    data_track: SubmissionDataTrack | str = SubmissionDataTrack.HIDDEN_TEST,
) -> SubmissionMetrics:
    config = ConfigRepository(config_path).load()
    track = _submission_data_track(data_track)
    scoring_config = track_scoring_config(config, track)
    result = run_student_backtest(
        strategy_path,
        _config_relative_path(config_path, track_release_root(config, track)),
        scoring_config,
    )
    write_backtest_report(result, report_dir)
    return _metrics_from_summary_csv(report_dir / "summary.csv")


def _config_relative_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    config_dir = config_path.resolve().parent
    base_dir = config_dir.parent if config_dir.name == "config" else config_dir
    return base_dir / path


def _metrics_from_summary_csv(path: Path) -> SubmissionMetrics:
    frame = pd.read_csv(path)
    summary = frame.to_dict("records")[0] if not frame.empty else {}
    return SubmissionMetrics.from_summary(summary)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score one QuantFish submission.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--report-dir", required=True)
    parser.add_argument(
        "--data-track",
        choices=[item.value for item in SubmissionDataTrack],
        default=SubmissionDataTrack.HIDDEN_TEST.value,
    )
    args = parser.parse_args(argv)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "worker_error.log").unlink(missing_ok=True)
    (report_dir / WORKER_FAILURE_FILE).unlink(missing_ok=True)

    original_argv = list(sys.argv)
    sys.argv = ["quantfish-score-worker"]
    try:
        with (
            (report_dir / "worker_stdout.log").open("w", encoding="utf-8") as out,
            (report_dir / "worker_stderr.log").open("w", encoding="utf-8") as err,
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            metrics = score_submission(
                Path(args.config),
                Path(args.strategy),
                report_dir,
                data_track=args.data_track,
            )
    except Exception as exc:
        (report_dir / "worker_error.log").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        failure = {
            "code": "score_worker_failed",
            "message": "score worker failed",
        }
        if isinstance(exc, TerminalStalePositionsError):
            failure = {
                "code": "terminal_stale_positions",
                "message": exc.public_message,
            }
        (report_dir / WORKER_FAILURE_FILE).write_text(
            json.dumps(failure, ensure_ascii=False),
            encoding="utf-8",
        )
        print("scoring failed", file=sys.stderr)
        return 1
    finally:
        sys.argv = original_argv
    print(json.dumps(metrics.to_dict(), allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
