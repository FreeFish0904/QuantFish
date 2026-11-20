import threading
import time
from pathlib import Path

import pytest

from quantfish.data.release_lock import ReleaseLockCancelled, ReleaseLockManager


def test_release_lock_allows_readers_and_blocks_writer_for_the_same_track(
    tmp_path: Path,
) -> None:
    manager = ReleaseLockManager(tmp_path / "locks", poll_interval_seconds=0.005)
    second_reader_entered = threading.Event()
    release_second_reader = threading.Event()
    writer_entered = threading.Event()

    def read_release() -> None:
        with manager.read("learning_1"):
            second_reader_entered.set()
            assert release_second_reader.wait(timeout=1)

    def write_release() -> None:
        with manager.write("learning_1"):
            writer_entered.set()

    with manager.read("learning_1"):
        reader_thread = threading.Thread(target=read_release)
        reader_thread.start()
        assert second_reader_entered.wait(timeout=1)

        writer_thread = threading.Thread(target=write_release)
        writer_thread.start()
        assert not writer_entered.wait(timeout=0.05)

        release_second_reader.set()
        reader_thread.join(timeout=1)
        assert not reader_thread.is_alive()
        assert not writer_entered.wait(timeout=0.05)

    writer_thread.join(timeout=1)
    assert not writer_thread.is_alive()
    assert writer_entered.is_set()


def test_release_lock_wait_can_be_cancelled(tmp_path: Path) -> None:
    manager = ReleaseLockManager(tmp_path / "locks", poll_interval_seconds=0.005)
    cancel = threading.Event()
    errors: list[Exception] = []

    def wait_for_release() -> None:
        try:
            with manager.read("learning_2", should_cancel=cancel.is_set):
                raise AssertionError("cancelled reader acquired the lock")
        except Exception as exc:
            errors.append(exc)

    with manager.write("learning_2"):
        thread = threading.Thread(target=wait_for_release)
        thread.start()
        cancel.set()
        thread.join(timeout=1)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], ReleaseLockCancelled)


def test_waiting_writer_prevents_later_readers_from_leapfrogging(
    tmp_path: Path,
) -> None:
    manager = ReleaseLockManager(tmp_path / "locks", poll_interval_seconds=0.005)
    writer_started = threading.Event()
    writer_entered = threading.Event()
    release_writer = threading.Event()
    later_reader_entered = threading.Event()

    def write_release() -> None:
        writer_started.set()
        with manager.write("learning_3"):
            writer_entered.set()
            assert release_writer.wait(timeout=1)

    def read_release() -> None:
        with manager.read("learning_3"):
            later_reader_entered.set()

    with manager.read("learning_3"):
        writer_thread = threading.Thread(target=write_release)
        writer_thread.start()
        assert writer_started.wait(timeout=1)
        time.sleep(0.05)

        reader_thread = threading.Thread(target=read_release)
        reader_thread.start()
        assert not writer_entered.wait(timeout=0.05)
        assert not later_reader_entered.wait(timeout=0.05)

    assert writer_entered.wait(timeout=1)
    assert not later_reader_entered.is_set()
    release_writer.set()
    writer_thread.join(timeout=1)
    reader_thread.join(timeout=1)

    assert not writer_thread.is_alive()
    assert not reader_thread.is_alive()
    assert later_reader_entered.is_set()


def test_release_lock_rejects_unsafe_track_names(tmp_path: Path) -> None:
    manager = ReleaseLockManager(tmp_path / "locks")

    with (
        pytest.raises(ValueError, match="invalid release lock name"),
        manager.write("../learning_1"),
    ):
        pass
