from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from quantfish.submissions.listing import (
    SubmissionListParams,
    SubmissionPage,
    data_tracks_matching_search,
)
from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionDataTrack,
    SubmissionMetrics,
    SubmissionStatus,
    Team,
    _utc_now,
    hash_team_password,
    verify_team_password,
)


class TeamRepository:
    def __init__(self, runtime_root: Path | str):
        self.path = Path(runtime_root) / "repositories" / "teams.json"
        self._lock = _path_lock(self.path)
        self._cache_fingerprint: tuple[str, int | None, int | None] | None = None
        self._cache_items: list[Team] | None = None

    def list_all(self) -> list[Team]:
        with self._lock:
            return list(self._list_all_locked())

    def list_active(self) -> list[Team]:
        return [team for team in self.list_all() if team.archived_at is None]

    def list_archived(self) -> list[Team]:
        return [team for team in self.list_all() if team.archived_at is not None]

    def get(self, team_id: str) -> Team | None:
        for team in self.list_all():
            if team.team_id == team_id:
                return team
        return None

    def find_by_display_name(self, display_name: str) -> Team | None:
        normalized = _normalize_team_name(display_name)
        for team in self.list_all():
            if _normalize_team_name(team.display_name) == normalized:
                return team
        return None

    def resolve_login(self, login: str) -> Team | None:
        return self.find_by_display_name(login.strip())

    def save(self, team: Team) -> None:
        with self._lock:
            teams = {existing.team_id: existing for existing in self._list_all_locked()}
            teams[team.team_id] = team
            ordered = [teams[key] for key in sorted(teams)]
            _atomic_write_json(
                self.path,
                [item.to_dict() for item in ordered],
            )
            self._remember_locked(ordered)

    def create_team(self, *, team_id: str, display_name: str, password: str) -> Team:
        team = Team.from_plaintext_password(
            team_id=team_id, display_name=display_name, password=password
        )
        self.save(team)
        return team

    def create_team_with_name(self, *, display_name: str, password: str) -> Team:
        name = display_name.strip()
        if not name:
            raise ValueError("team name is required")
        if self.find_by_display_name(name) is not None:
            raise ValueError(f"team already exists: {name}")
        return self.create_team(
            team_id=_new_team_id(),
            display_name=name,
            password=password,
        )

    def update_team(
        self,
        team_id: str,
        *,
        display_name: str | None = None,
        password: str | None = None,
    ) -> Team:
        team = self.get(team_id)
        if team is None:
            raise KeyError(team_id)
        changes: dict[str, Any] = {}
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise ValueError("team name is required")
            existing = self.find_by_display_name(name)
            if existing is not None and existing.team_id != team_id:
                raise ValueError(f"team already exists: {name}")
            changes["display_name"] = name
        if password is not None:
            if not password:
                raise ValueError("team password is required")
            changes["password_hash"] = hash_team_password(password)
        updated = replace(team, **changes)
        self.save(updated)
        return updated

    def archive(self, team_id: str) -> bool:
        team = self.get(team_id)
        if team is None:
            return False
        if team.archived_at is not None:
            return False
        self.save(replace(team, archived_at=_utc_now()))
        return True

    def restore(self, team_id: str) -> bool:
        team = self.get(team_id)
        if team is None:
            return False
        if team.archived_at is None:
            return False
        self.save(replace(team, archived_at=None))
        return True

    def delete(self, team_id: str) -> bool:
        with self._lock:
            existing = self._list_all_locked()
            teams = [team for team in existing if team.team_id != team_id]
            if len(teams) == len(existing):
                return False
            _atomic_write_json(self.path, [team.to_dict() for team in teams])
            self._remember_locked(teams)
            return True

    def verify_password(self, team_name: str, password: str) -> bool:
        team = self.resolve_login(team_name)
        return (
            team is not None
            and team.archived_at is None
            and verify_team_password(password, team.password_hash)
        )

    def _list_all_locked(self) -> list[Team]:
        fingerprint = _json_file_fingerprint(self.path)
        if self._cache_fingerprint == fingerprint and self._cache_items is not None:
            return list(self._cache_items)
        teams = [Team.from_dict(item) for item in _read_json_list(self.path)]
        self._cache_fingerprint = fingerprint
        self._cache_items = list(teams)
        return teams

    def _remember_locked(self, teams: list[Team]) -> None:
        self._cache_fingerprint = _json_file_fingerprint(self.path)
        self._cache_items = list(teams)


class SubmissionRepository:
    def __init__(self, runtime_root: Path | str):
        self.path = Path(runtime_root) / "repositories" / "submissions.json"
        self.db_path = Path(runtime_root) / "repositories" / "quantfish.db"
        self._lock = _path_lock(self.db_path)
        with self._lock:
            self._ensure_storage()

    def list_all(self) -> list[Submission]:
        with self._lock:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM submissions
                    ORDER BY
                        COALESCE(submission_number, 9223372036854775807) ASC,
                        submitted_at ASC,
                        submission_id ASC
                    """
                ).fetchall()
            return [_submission_from_row(row) for row in rows]

    def list_for_team(self, team_id: str) -> list[Submission]:
        with self._lock:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM submissions
                    WHERE team_id = ?
                    ORDER BY
                        COALESCE(submission_number, 9223372036854775807) ASC,
                        submitted_at ASC,
                        submission_id ASC
                    """,
                    (team_id,),
                ).fetchall()
            return [_submission_from_row(row) for row in rows]

    def list_for_track(self, data_track: SubmissionDataTrack) -> list[Submission]:
        with self._lock:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM submissions
                    WHERE data_track = ?
                    ORDER BY
                        COALESCE(submission_number, 9223372036854775807) ASC,
                        submitted_at ASC,
                        submission_id ASC
                    """,
                    (data_track.value,),
                ).fetchall()
            return [_submission_from_row(row) for row in rows]

    def list_queued(
        self,
        *,
        limit: int,
        exclude_submission_ids: set[str] | None = None,
    ) -> list[Submission]:
        if limit <= 0:
            return []
        clauses = ["status = ?"]
        values: list[Any] = [SubmissionStatus.QUEUED.value]
        excluded = sorted(exclude_submission_ids or set())
        if excluded:
            placeholders = ", ".join("?" for _ in excluded)
            clauses.append(f"submission_id NOT IN ({placeholders})")
            values.extend(excluded)
        values.append(limit)
        with self._lock:
            with self._connection() as connection:
                rows = connection.execute(
                    f"""
                    SELECT * FROM submissions
                    WHERE {" AND ".join(clauses)}
                    ORDER BY
                        COALESCE(submission_number, 9223372036854775807) ASC,
                        submitted_at ASC,
                        submission_id ASC
                    LIMIT ?
                    """,
                    values,
                ).fetchall()
            return [_submission_from_row(row) for row in rows]

    def requeue_running(self) -> int:
        with self._lock:
            with self._connection() as connection:
                cursor = connection.execute(
                    """
                    UPDATE submissions
                    SET status = ?,
                        error_message = NULL,
                        scored_at = NULL
                    WHERE status = ?
                    """,
                    (SubmissionStatus.QUEUED.value, SubmissionStatus.RUNNING.value),
                )
                connection.commit()
            return int(cursor.rowcount)

    def get(self, submission_id: str) -> Submission | None:
        with self._lock:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT * FROM submissions WHERE submission_id = ?",
                    (submission_id,),
                ).fetchone()
            return _submission_from_row(row) if row is not None else None

    def count_for_team(self, team_id: str) -> int:
        with self._lock:
            with self._connection() as connection:
                value = connection.execute(
                    "SELECT COUNT(*) FROM submissions WHERE team_id = ?",
                    (team_id,),
                ).fetchone()[0]
            return int(value)

    def count_all(self) -> int:
        with self._lock:
            with self._connection() as connection:
                value = connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
            return int(value)

    def ping(self) -> None:
        """Cheap readiness probe: raise if the database cannot answer."""
        with self._lock:
            connection = self._connect()
            try:
                connection.execute("SELECT 1").fetchone()
            finally:
                connection.close()

    def count_by_team(self) -> dict[str, int]:
        with self._lock:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT team_id, COUNT(*) AS count
                    FROM submissions
                    GROUP BY team_id
                    """
                ).fetchall()
            return {str(row["team_id"]): int(row["count"]) for row in rows}

    def status_counts(self) -> dict[str, int]:
        with self._lock:
            with self._connection() as connection:
                rows = connection.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM submissions
                    GROUP BY status
                    """
                ).fetchall()
            return {str(row["status"]): int(row["count"]) for row in rows}

    def next_submission_number(self) -> int:
        with self._lock:
            with self._connection() as connection:
                value = connection.execute(
                    "SELECT COALESCE(MAX(submission_number), 0) + 1 FROM submissions"
                ).fetchone()[0]
            return int(value)

    def create(self, submission: Submission) -> Submission:
        with self._lock:
            if submission.submission_number is None:
                next_number = self.next_submission_number()
                submission = replace(submission, submission_number=next_number)
            with self._connection() as connection:
                _upsert_submission(connection, submission)
                connection.commit()
            return submission

    def save(self, submission: Submission) -> None:
        with self._lock, self._connection() as connection:
            _upsert_submission(connection, submission)
            connection.commit()

    def delete(self, submission_id: str) -> bool:
        with self._lock:
            with self._connection() as connection:
                cursor = connection.execute(
                    "DELETE FROM submissions WHERE submission_id = ?",
                    (submission_id,),
                )
                connection.commit()
            return cursor.rowcount > 0

    def list_page(
        self,
        params: SubmissionListParams,
        *,
        team_names: dict[str, str],
        score_for: Callable[[Submission], float | None] | None = None,
        sql_sort_expressions: Mapping[str, tuple[str, Sequence[Any]]] | None = None,
    ) -> SubmissionPage:
        limit = max(1, params.limit) if params.limit is not None else None
        offset = max(0, params.offset)
        normalized = replace(params, limit=limit, offset=offset)
        where_sql, values = _submission_where(normalized, team_names)
        order_sql = _submission_order_sql(
            normalized,
            team_names,
            sql_sort_expressions or {},
        )
        with self._lock, self._connection() as connection:
            total_count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM submissions {where_sql}",
                    values,
                ).fetchone()[0]
            )
            sql = f"SELECT * FROM submissions {where_sql} {order_sql.sql}"
            query_values = list(values) + list(order_sql.values)
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                query_values.extend([limit, offset])
            elif offset:
                sql += " LIMIT -1 OFFSET ?"
                query_values.append(offset)
            rows = connection.execute(sql, query_values).fetchall()
        return SubmissionPage(
            items=[_submission_from_row(row) for row in rows],
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def _filtered_submissions(
        self,
        params: SubmissionListParams,
        team_names: dict[str, str],
    ) -> list[Submission]:
        where_sql, values = _submission_where(params, team_names)
        with self._lock, self._connection() as connection:
            rows = connection.execute(
                f"""
                    SELECT * FROM submissions
                    {where_sql}
                    ORDER BY submitted_at ASC, submission_id ASC
                    """,
                values,
            ).fetchall()
        return [_submission_from_row(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Open a connection that is committed and closed on the way out.

        `with self._connect() as connection` only commits (or rolls back); the
        connection itself is left to the garbage collector, which leaks a file
        descriptor plus the WAL/-shm handles for every repository call.
        """
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _ensure_storage(self) -> None:
        with self._connection() as connection:
            _create_submission_schema(connection)
            count = int(connection.execute("SELECT COUNT(*) FROM submissions").fetchone()[0])
            if count == 0 and self.path.exists():
                submissions = [
                    Submission.from_dict(item)
                    for item in _read_json_list(self.path)
                ]
                for submission in _backfill_submission_numbers(submissions):
                    _upsert_submission(connection, submission)
            connection.commit()


def _create_submission_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            submission_id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            status TEXT NOT NULL,
            strategy_path TEXT NOT NULL,
            report_dir TEXT NOT NULL,
            fingerprints_json TEXT,
            original_filename TEXT NOT NULL,
            data_track TEXT NOT NULL,
            submission_number INTEGER,
            metrics_json TEXT,
            error_message TEXT,
            submitted_at TEXT NOT NULL,
            scored_at TEXT,
            config_snapshot_json TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_submissions_status
            ON submissions(status);
        CREATE INDEX IF NOT EXISTS idx_submissions_team
            ON submissions(team_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_track
            ON submissions(data_track);
        CREATE INDEX IF NOT EXISTS idx_submissions_submitted_at
            ON submissions(submitted_at DESC, submission_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_number
            ON submissions(submission_number DESC);
        CREATE INDEX IF NOT EXISTS idx_submissions_queue_order
            ON submissions(status, submission_number, submitted_at, submission_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_track_status_submitted
            ON submissions(data_track, status, submitted_at DESC, submission_id);
        CREATE INDEX IF NOT EXISTS idx_submissions_team_track_status
            ON submissions(team_id, data_track, status);
        CREATE INDEX IF NOT EXISTS idx_submissions_metric_sharpe
            ON submissions(CAST(json_extract(metrics_json, '$.sharpe') AS REAL));
        CREATE INDEX IF NOT EXISTS idx_submissions_metric_calmar
            ON submissions(CAST(json_extract(metrics_json, '$.calmar') AS REAL));
        CREATE INDEX IF NOT EXISTS idx_submissions_metric_total_return
            ON submissions(CAST(json_extract(metrics_json, '$.total_return') AS REAL));
        CREATE INDEX IF NOT EXISTS idx_submissions_metric_max_drawdown
            ON submissions(CAST(json_extract(metrics_json, '$.max_drawdown') AS REAL));
        """
    )


def _upsert_submission(
    connection: sqlite3.Connection,
    submission: Submission,
) -> None:
    connection.execute(
        """
        INSERT INTO submissions (
            submission_id,
            team_id,
            status,
            strategy_path,
            report_dir,
            fingerprints_json,
            original_filename,
            data_track,
            submission_number,
            metrics_json,
            error_message,
            submitted_at,
            scored_at,
            config_snapshot_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(submission_id) DO UPDATE SET
            team_id = excluded.team_id,
            status = excluded.status,
            strategy_path = excluded.strategy_path,
            report_dir = excluded.report_dir,
            fingerprints_json = excluded.fingerprints_json,
            original_filename = excluded.original_filename,
            data_track = excluded.data_track,
            submission_number = excluded.submission_number,
            metrics_json = excluded.metrics_json,
            error_message = excluded.error_message,
            submitted_at = excluded.submitted_at,
            scored_at = excluded.scored_at,
            config_snapshot_json = excluded.config_snapshot_json
        """,
        (
            submission.submission_id,
            submission.team_id,
            submission.status.value,
            submission.strategy_path,
            submission.report_dir,
            _json_dumps(
                submission.fingerprints.to_dict()
                if submission.fingerprints is not None
                else None
            ),
            submission.original_filename,
            submission.data_track.value,
            submission.submission_number,
            _json_dumps(
                submission.metrics.to_dict()
                if submission.metrics is not None
                else None
            ),
            submission.error_message,
            submission.submitted_at,
            submission.scored_at,
            _json_dumps(submission.config_snapshot),
        ),
    )


def _submission_from_row(row: sqlite3.Row) -> Submission:
    fingerprints = _json_loads(row["fingerprints_json"])
    metrics = _json_loads(row["metrics_json"])
    config_snapshot = _json_loads(row["config_snapshot_json"])
    return Submission(
        submission_id=str(row["submission_id"]),
        team_id=str(row["team_id"]),
        status=SubmissionStatus(str(row["status"])),
        strategy_path=str(row["strategy_path"]),
        report_dir=str(row["report_dir"]),
        fingerprints=(
            ScoreFingerprints.from_dict(fingerprints)
            if isinstance(fingerprints, dict)
            else None
        ),
        original_filename=str(row["original_filename"] or "strategy.py"),
        data_track=SubmissionDataTrack(str(row["data_track"])),
        submission_number=(
            int(row["submission_number"])
            if row["submission_number"] is not None
            else None
        ),
        metrics=SubmissionMetrics.from_dict(metrics) if isinstance(metrics, dict) else None,
        error_message=(
            str(row["error_message"]) if row["error_message"] is not None else None
        ),
        submitted_at=str(row["submitted_at"]),
        scored_at=str(row["scored_at"]) if row["scored_at"] is not None else None,
        config_snapshot=config_snapshot if isinstance(config_snapshot, dict) else None,
    )


def _submission_where(
    params: SubmissionListParams,
    team_names: dict[str, str],
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if params.status:
        clauses.append("status = ?")
        values.append(params.status)
    if params.data_track is not None:
        clauses.append("data_track = ?")
        values.append(params.data_track.value)
    if params.team_id is not None:
        clauses.append("team_id = ?")
        values.append(params.team_id)
    if params.team_ids is not None:
        if params.team_ids:
            placeholders = ", ".join("?" for _ in params.team_ids)
            clauses.append(f"team_id IN ({placeholders})")
            values.extend(params.team_ids)
        else:
            clauses.append("1 = 0")
    if params.excluded_team_ids:
        placeholders = ", ".join("?" for _ in params.excluded_team_ids)
        clauses.append(f"team_id NOT IN ({placeholders})")
        values.extend(params.excluded_team_ids)

    query = params.search.strip().casefold()
    if query:
        like = f"%{query}%"
        search_clauses = [
            "lower(submission_id) LIKE ?",
            "lower(team_id) LIKE ?",
            "lower(status) LIKE ?",
            "lower(data_track) LIKE ?",
            "lower(original_filename) LIKE ?",
            "CAST(submission_number AS TEXT) LIKE ?",
            "('#' || CAST(submission_number AS TEXT)) LIKE ?",
        ]
        values.extend([like] * len(search_clauses))
        matching_team_ids = [
            team_id
            for team_id, display_name in team_names.items()
            if query in display_name.casefold()
        ]
        if matching_team_ids:
            placeholders = ", ".join("?" for _ in matching_team_ids)
            search_clauses.append(f"team_id IN ({placeholders})")
            values.extend(matching_team_ids)
        matching_data_tracks = data_tracks_matching_search(query)
        if matching_data_tracks:
            placeholders = ", ".join("?" for _ in matching_data_tracks)
            search_clauses.append(f"data_track IN ({placeholders})")
            values.extend(track.value for track in matching_data_tracks)
        clauses.append("(" + " OR ".join(search_clauses) + ")")

    if not clauses:
        return "", values
    return "WHERE " + " AND ".join(clauses), values


def _requires_python_sort(params: SubmissionListParams) -> bool:
    return params.sort_by in {
        "team_name",
        "score",
        "sharpe",
        "calmar",
        "total_return",
        "return",
        "drawdown",
        "max_drawdown",
    }


@dataclass(frozen=True)
class _OrderSql:
    sql: str
    values: list[Any]


def _submission_order_sql(
    params: SubmissionListParams,
    team_names: dict[str, str],
    sql_sort_expressions: Mapping[str, tuple[str, Sequence[Any]]],
) -> _OrderSql:
    direction = "ASC" if params.sort_dir == "asc" else "DESC"
    expression, expression_values = _submission_sort_expression(
        params.sort_by,
        team_names,
        sql_sort_expressions,
    )
    tie_direction = (
        "ASC"
        if params.sort_by in {"submission_number", "id"} and direction == "ASC"
        else "DESC"
    )
    return _OrderSql(
        sql=(
            f"ORDER BY ({expression}) IS NULL ASC, ({expression}) {direction}, "
            f"submitted_at {tie_direction}, submission_id ASC"
        ),
        values=list(expression_values) + list(expression_values),
    )


def _submission_sort_expression(
    sort_by: str,
    team_names: dict[str, str],
    sql_sort_expressions: Mapping[str, tuple[str, Sequence[Any]]],
) -> tuple[str, list[Any]]:
    if sort_by == "team_name":
        return _team_name_sort_expression(team_names)
    if sort_by in sql_sort_expressions:
        expression, values = sql_sort_expressions[sort_by]
        return expression, list(values)
    metric_field = {
        "sharpe": "sharpe",
        "calmar": "calmar",
        "total_return": "total_return",
        "return": "total_return",
        "drawdown": "max_drawdown",
        "max_drawdown": "max_drawdown",
    }.get(sort_by)
    if metric_field is not None:
        return f"CAST(json_extract(metrics_json, '$.{metric_field}') AS REAL)", []
    column = {
        "submission_number": "submission_number",
        "id": "submission_number",
        "status": "status",
        "data_track": "data_track",
        "scored_at": "scored_at",
        "filename": "original_filename",
        "submitted_at": "submitted_at",
    }.get(sort_by, "submitted_at")
    return column, []


def _team_name_sort_expression(team_names: dict[str, str]) -> tuple[str, list[Any]]:
    if not team_names:
        return "lower(team_id)", []
    values: list[Any] = []
    clauses: list[str] = ["CASE team_id"]
    for team_id, display_name in sorted(team_names.items()):
        clauses.append("WHEN ? THEN ?")
        values.extend([team_id, display_name.casefold()])
    clauses.append("ELSE lower(team_id) END")
    return " ".join(clauses), values


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


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


def _json_file_fingerprint(path: Path) -> tuple[str, int | None, int | None]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return (path.as_posix(), None, None)
    return (path.as_posix(), stat.st_mtime_ns, stat.st_size)


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


def _normalize_team_name(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _new_team_id() -> str:
    return f"team-{uuid.uuid4().hex[:12]}"


def _backfill_submission_numbers(submissions: list[Submission]) -> list[Submission]:
    next_number = (
        max((submission.submission_number or 0 for submission in submissions), default=0)
        + 1
    )
    backfilled: list[Submission] = []
    for submission in sorted(submissions, key=lambda item: item.submitted_at):
        if submission.submission_number is None:
            backfilled.append(replace(submission, submission_number=next_number))
            next_number += 1
        else:
            backfilled.append(submission)
    return backfilled
