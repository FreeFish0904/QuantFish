from __future__ import annotations

from typing import Any

from quantfish.submissions.models import SubmissionDataTrack, _submission_data_track


def public_data_tracks(services: Any) -> list[SubmissionDataTrack]:
    config = _platform_config(services)
    tracks = [
        SubmissionDataTrack.LEARNING,
    ]
    for track in (
        SubmissionDataTrack.LEARNING_1,
        SubmissionDataTrack.LEARNING_2,
        SubmissionDataTrack.LEARNING_3,
    ):
        if config is None or (
            config.data_releases.release_window(track.value).end < config.data_releases.hidden_start
        ):
            tracks.append(track)
    if config is None or config.execution.hidden_test_enabled:
        tracks.insert(0, SubmissionDataTrack.HIDDEN_TEST)
    return tracks


def default_public_data_track(services: Any) -> SubmissionDataTrack:
    if hidden_test_enabled(services):
        return SubmissionDataTrack.HIDDEN_TEST
    return SubmissionDataTrack.LEARNING


def ensure_public_data_track_enabled(
    services: Any,
    data_track: SubmissionDataTrack | str,
) -> SubmissionDataTrack:
    track = _submission_data_track(data_track)
    if track not in public_data_tracks(services):
        if track == SubmissionDataTrack.HIDDEN_TEST:
            raise ValueError("hidden test track is not currently open")
        raise ValueError(f"{track.value} track is not currently open")
    return track


def hidden_test_enabled(services: Any) -> bool:
    config = _platform_config(services)
    return True if config is None else bool(config.execution.hidden_test_enabled)


def _platform_config(services: Any) -> Any | None:
    config_repository = getattr(
        getattr(services, "submission_service", None),
        "config_repository",
        None,
    )
    if config_repository is None:
        return None
    return config_repository.load()
