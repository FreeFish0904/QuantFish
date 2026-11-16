from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
from typing import Iterable

from quantfish.team_cohorts.models import TeamCohort


_LOCKS: dict[Path, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()


class TeamCohortRepository:
    def __init__(self, runtime_root: Path | str):
        self.path = Path(runtime_root) / "repositories" / "team_cohorts.json"
        self._lock = _path_lock(self.path)

    def list_all(self) -> list[TeamCohort]:
        with self._lock:
            return [TeamCohort.from_dict(item) for item in _read_json_list(self.path)]

    def get(self, cohort_id: str) -> TeamCohort | None:
        for cohort in self.list_all():
            if cohort.cohort_id == cohort_id:
                return cohort
        return None

    def save_all(self, cohorts: Iterable[TeamCohort]) -> None:
        ordered = sorted(cohorts, key=lambda cohort: (cohort.created_at, cohort.name, cohort.cohort_id))
        with self._lock:
            _atomic_write_json(self.path, [cohort.to_dict() for cohort in ordered])


def _path_lock(path: Path) -> threading.RLock:
    resolved = path.resolve()
    with _LOCKS_GUARD:
        lock = _LOCKS.get(resolved)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[resolved] = lock
        return lock


def _read_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _atomic_write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)
