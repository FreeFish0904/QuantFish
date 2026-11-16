from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from quantfish.platform_config import ConfigRepository, PlatformConfig
from quantfish.submissions.models import SubmissionDataTrack
from quantfish.submissions.track_config import track_release_root, track_scoring_config
from quantfish.submissions.track_visibility import (
    ensure_public_data_track_enabled,
    public_data_tracks,
)


@pytest.mark.parametrize(
    ("track", "expected_root", "expected_start", "expected_end"),
    [
        (
            SubmissionDataTrack.LEARNING_1,
            "isolated/learning_1",
            date(2010, 1, 2),
            date(2015, 12, 31),
        ),
        (
            SubmissionDataTrack.LEARNING_2,
            "isolated/learning_2",
            date(2015, 1, 1),
            date(2020, 12, 31),
        ),
        (
            SubmissionDataTrack.LEARNING_3,
            "isolated/learning_3",
            date(2020, 1, 1),
            date(2022, 12, 31),
        ),
    ],
)
def test_learning_window_tracks_use_their_own_release_and_scoring_dates(
    track: SubmissionDataTrack,
    expected_root: str,
    expected_start: date,
    expected_end: date,
) -> None:
    default = PlatformConfig.default()
    config = replace(
        default,
        data_releases=replace(
            default.data_releases,
            learning_output_root="isolated/learning",
        ),
    ).validate()

    scoring_config = track_scoring_config(config, track)

    assert track_release_root(config, track) == expected_root
    assert scoring_config.backtest.data_start == expected_start
    assert scoring_config.backtest.scoring_start == expected_start
    assert scoring_config.backtest.scoring_end == expected_end
    assert scoring_config.backtest.long_only_benchmark == "none"
    assert scoring_config.execution.terminal_stale_position_policy == "carry"


def test_legacy_learning_track_carries_terminal_stale_positions() -> None:
    config = PlatformConfig.default()

    scoring_config = track_scoring_config(config, SubmissionDataTrack.LEARNING)

    assert scoring_config.execution.terminal_stale_position_policy == "carry"


def test_hidden_track_keeps_hs300_active_return_scoring() -> None:
    config = PlatformConfig.default()

    scoring_config = track_scoring_config(config, SubmissionDataTrack.HIDDEN_TEST)

    assert scoring_config.backtest.long_only_benchmark == "hs300"
    assert scoring_config.execution.terminal_stale_position_policy == "reject"


def test_learning_windows_that_overlap_hidden_data_are_not_public(
    tmp_path: Path,
) -> None:
    default = PlatformConfig.default()
    config = replace(
        default,
        data_releases=replace(
            default.data_releases,
            learning_start=date(2010, 1, 2),
            learning_end=date(2019, 12, 31),
            hidden_start=date(2020, 1, 1),
        ),
        execution=replace(default.execution, hidden_test_enabled=False),
    ).validate()
    repository = ConfigRepository(tmp_path / "platform.yaml")
    repository.save(config)
    services = SimpleNamespace(
        submission_service=SimpleNamespace(config_repository=repository)
    )

    assert public_data_tracks(services) == [
        SubmissionDataTrack.LEARNING,
        SubmissionDataTrack.LEARNING_1,
    ]
    with pytest.raises(ValueError, match="learning_2 track is not currently open"):
        ensure_public_data_track_enabled(services, SubmissionDataTrack.LEARNING_2)
