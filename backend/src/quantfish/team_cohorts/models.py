from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class TeamCohort:
    cohort_id: str
    name: str
    team_ids: tuple[str, ...] = ()
    history_visible: bool = True
    submissions_enabled: bool = True
    created_at: str = ""
    updated_at: str = ""

    def with_updates(self, **changes: Any) -> TeamCohort:
        return replace(self, updated_at=utc_now(), **changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cohort_id": self.cohort_id,
            "name": self.name,
            "team_ids": list(self.team_ids),
            "history_visible": self.history_visible,
            "submissions_enabled": self.submissions_enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TeamCohort:
        created_at = str(data.get("created_at") or utc_now())
        return cls(
            cohort_id=str(data["cohort_id"]),
            name=str(data["name"]),
            team_ids=_unique_texts(data.get("team_ids") or []),
            history_visible=bool(data.get("history_visible", True)),
            submissions_enabled=bool(data.get("submissions_enabled", True)),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
        )


def _unique_texts(values: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    if not isinstance(values, list):
        return ()
    for value in values:
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return tuple(ordered)
