from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Mapping
import uuid


@dataclass(frozen=True)
class AdminSettingsHistoryEntry:
    entry_id: str
    created_at: str
    entry_type: str = "settings_change"
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    settings: dict[str, Any] = field(default_factory=dict)
    stale_marked: bool = False
    affected_submission_ids: tuple[str, ...] = field(default_factory=tuple)
    reverted_at: str | None = None
    config_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "created_at": self.created_at,
            "entry_type": self.entry_type,
            "config_sha256": self.config_sha256,
            "changed_fields": list(self.changed_fields),
            "settings": self.settings,
            "stale_marked": self.stale_marked,
            "affected_submission_ids": list(self.affected_submission_ids),
            "affected_count": len(self.affected_submission_ids),
            "reverted_at": self.reverted_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AdminSettingsHistoryEntry":
        settings = data.get("settings")
        if not isinstance(settings, Mapping):
            settings = {}
        entry_type = str(data.get("entry_type") or "settings_change")
        affected_submission_ids = data.get("affected_submission_ids") or []
        return cls(
            entry_id=str(data["entry_id"]),
            created_at=str(data["created_at"]),
            entry_type=entry_type,
            changed_fields=tuple(str(item) for item in data.get("changed_fields", [])),
            settings=dict(settings),
            stale_marked=bool(data.get("stale_marked", entry_type == "stale_mark")),
            affected_submission_ids=tuple(str(item) for item in affected_submission_ids),
            reverted_at=(
                str(data["reverted_at"]) if data.get("reverted_at") is not None else None
            ),
            config_sha256=(
                str(data["config_sha256"]) if data.get("config_sha256") is not None else None
            ),
        )


class AdminSettingsHistoryRepository:
    def __init__(self, runtime_root: Path | str):
        self.path = Path(runtime_root) / "repositories" / "admin_settings_history.json"
        self._lock = _path_lock(self.path)

    def list_recent(self) -> list[AdminSettingsHistoryEntry]:
        with self._lock:
            return [
                AdminSettingsHistoryEntry.from_dict(item)
                for item in _read_json_list(self.path)
            ]

    def get(self, entry_id: str) -> AdminSettingsHistoryEntry | None:
        for entry in self.list_recent():
            if entry.entry_id == entry_id:
                return entry
        return None

    def record_settings_change(
        self,
        previous_config: Any,
        updated_config: Any,
        *,
        stale_marked: bool = False,
    ) -> AdminSettingsHistoryEntry | None:
        previous_settings = _settings_payload(previous_config)
        updated_settings = _settings_payload(updated_config)
        changed_fields = tuple(_changed_fields(previous_settings, updated_settings))
        if not changed_fields:
            return None
        entry = AdminSettingsHistoryEntry(
            entry_id=uuid.uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            entry_type="settings_change",
            changed_fields=changed_fields,
            settings=previous_settings,
            stale_marked=stale_marked,
        )
        self.prepend(entry)
        return entry

    def record_stale_mark(
        self,
        submission_ids: list[str],
    ) -> AdminSettingsHistoryEntry:
        entry = AdminSettingsHistoryEntry(
            entry_id=uuid.uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            entry_type="stale_mark",
            settings={},
            stale_marked=True,
            affected_submission_ids=tuple(submission_ids),
        )
        self.prepend(entry)
        return entry

    def revert_stale_mark(self, entry_id: str) -> AdminSettingsHistoryEntry:
        with self._lock:
            entries = self.list_recent()
            updated_entries: list[AdminSettingsHistoryEntry] = []
            updated: AdminSettingsHistoryEntry | None = None
            for entry in entries:
                if entry.entry_id == entry_id:
                    if entry.entry_type != "stale_mark":
                        raise ValueError("history entry is not a stale mark")
                    updated = (
                        entry
                        if entry.reverted_at is not None
                        else AdminSettingsHistoryEntry(
                            entry_id=entry.entry_id,
                            created_at=entry.created_at,
                            entry_type=entry.entry_type,
                            changed_fields=entry.changed_fields,
                            settings=entry.settings,
                            stale_marked=entry.stale_marked,
                            affected_submission_ids=entry.affected_submission_ids,
                            reverted_at=datetime.now(timezone.utc).isoformat(),
                            config_sha256=entry.config_sha256,
                        )
                    )
                    updated_entries.append(updated)
                else:
                    updated_entries.append(entry)
            if updated is None:
                raise KeyError(entry_id)
            _atomic_write_json(
                self.path,
                [item.to_dict() for item in updated_entries],
            )
            return updated

    def active_stale_submission_ids(self) -> set[str]:
        active: set[str] = set()
        for entry in self.list_recent():
            if entry.entry_type == "stale_mark" and entry.reverted_at is None:
                active.update(entry.affected_submission_ids)
        return active

    def prepend(self, entry: AdminSettingsHistoryEntry) -> None:
        with self._lock:
            entries = [entry, *self.list_recent()]
            _atomic_write_json(
                self.path,
                [item.to_dict() for item in entries],
            )


def _settings_payload(config: Any) -> dict[str, Any]:
    payload = config.to_dict() if hasattr(config, "to_dict") else _json_ready(config)
    return dict(payload) if isinstance(payload, Mapping) else {}


def _changed_fields(previous: Any, updated: Any, prefix: str = "") -> list[str]:
    if isinstance(previous, Mapping) and isinstance(updated, Mapping):
        fields: list[str] = []
        for key in sorted(set(previous) | set(updated)):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            fields.extend(
                _changed_fields(
                    previous.get(key),
                    updated.get(key),
                    child_prefix,
                )
            )
        return fields
    if isinstance(previous, (list, tuple)) or isinstance(updated, (list, tuple)):
        return [] if list(previous or []) == list(updated or []) else [prefix]
    return [] if previous == updated else [prefix]


def _json_ready(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


_PATH_LOCKS: dict[Path, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _path_lock(path: Path) -> threading.RLock:
    key = path.resolve()
    with _PATH_LOCKS_GUARD:
        if key not in _PATH_LOCKS:
            _PATH_LOCKS[key] = threading.RLock()
        return _PATH_LOCKS[key]


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8") or "[]")
    if not isinstance(data, list):
        raise ValueError(f"expected JSON list in {path}")
    return [dict(item) for item in data]


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
