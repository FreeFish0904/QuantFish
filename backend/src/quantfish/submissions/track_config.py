from __future__ import annotations

from dataclasses import replace
from typing import Any

from quantfish.submissions.models import SubmissionDataTrack, _submission_data_track


def track_release_root(
    config: Any,
    data_track: SubmissionDataTrack | str,
) -> str:
    track = _submission_data_track(data_track)
    return config.data_releases.release_window(track.value).output_root


def track_scoring_config(
    config: Any,
    data_track: SubmissionDataTrack | str,
) -> Any:
    track = _submission_data_track(data_track)
    if track == SubmissionDataTrack.HIDDEN_TEST:
        return config
    window = config.data_releases.release_window(track.value)
    return replace(
        config,
        backtest=replace(
            config.backtest,
            data_start=window.start,
            scoring_start=window.start,
            scoring_end=window.end,
            # Historical releases do not currently have complete HS300 coverage.
            # Keep their long-only execution intact and score portfolio returns
            # without requiring a benchmark. Hidden-test scoring remains unchanged.
            long_only_benchmark="none",
        ),
        execution=replace(
            config.execution,
            # Historical windows can end while otherwise valid positions are
            # suspended. Mark those positions at their last valid close rather
            # than rejecting the entire learning-track backtest. Hidden-test
            # settlement remains governed by the configured strict policy.
            terminal_stale_position_policy="carry",
        ),
    )
