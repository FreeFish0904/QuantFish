from __future__ import annotations

import errno
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class ReleaseLockCancelled(RuntimeError):
    pass


class ReleaseLockManager:
    def __init__(self, root: Path | str, *, poll_interval_seconds: float = 0.05):
        self.root = Path(root)
        self.poll_interval_seconds = max(0.001, poll_interval_seconds)

    @contextmanager
    def read(
        self,
        release_name: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Iterator[None]:
        data_lock = self._acquire_file(
            self._lock_path(release_name, "data"),
            shared=True,
            should_cancel=should_cancel,
        )
        data_acquired = False
        try:
            with self._acquire_file(
                self._lock_path(release_name, "gate"),
                shared=True,
                should_cancel=should_cancel,
            ):
                data_lock.__enter__()
                data_acquired = True
            yield
        finally:
            if data_acquired:
                data_lock.__exit__(None, None, None)

    @contextmanager
    def write(
        self,
        release_name: str,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Iterator[None]:
        with self._acquire_file(
            self._lock_path(release_name, "gate"),
            shared=False,
            should_cancel=should_cancel,
        ), self._acquire_file(
            self._lock_path(release_name, "data"),
            shared=False,
            should_cancel=should_cancel,
        ):
            yield

    @contextmanager
    def _acquire_file(
        self,
        lock_path: Path,
        *,
        shared: bool,
        should_cancel: Callable[[], bool] | None,
    ) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        _ensure_lock_byte(descriptor)
        acquired = False
        try:
            while not acquired:
                if should_cancel is not None and should_cancel():
                    raise ReleaseLockCancelled(
                        f"cancelled while waiting for {lock_path.stem} release lock"
                    )
                try:
                    _lock_file(descriptor, shared=shared)
                    acquired = True
                except OSError as exc:
                    if not _is_lock_contention(exc):
                        raise
                    time.sleep(self.poll_interval_seconds)
            yield
        finally:
            if acquired:
                _unlock_file(descriptor)
            os.close(descriptor)

    def _lock_path(self, release_name: str, purpose: str) -> Path:
        if not release_name or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_-"
            for character in release_name
        ):
            raise ValueError(f"invalid release lock name: {release_name}")
        return self.root / f"{release_name}.{purpose}.lock"


def _ensure_lock_byte(descriptor: int) -> None:
    if os.fstat(descriptor).st_size == 0:
        os.write(descriptor, b"\0")
    os.lseek(descriptor, 0, os.SEEK_SET)


def _lock_file(descriptor: int, *, shared: bool) -> None:
    if os.name == "nt":
        os.lseek(descriptor, 0, os.SEEK_SET)
        mode = msvcrt.LK_NBRLCK if shared else msvcrt.LK_NBLCK
        msvcrt.locking(descriptor, mode, 1)
        return
    mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
    fcntl.flock(descriptor, mode | fcntl.LOCK_NB)


def _unlock_file(descriptor: int) -> None:
    if os.name == "nt":
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    fcntl.flock(descriptor, fcntl.LOCK_UN)


def _is_lock_contention(exc: OSError) -> bool:
    if isinstance(exc, BlockingIOError):
        return True
    return os.name == "nt" and exc.errno in {
        errno.EACCES,
        errno.EAGAIN,
        errno.EDEADLK,
    }
