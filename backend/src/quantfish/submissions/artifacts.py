from __future__ import annotations

import copy
import json
import math
from collections import OrderedDict
from pathlib import Path
from typing import Any

import pandas as pd


PUBLIC_DIAGNOSTIC_KEYS = {
    "canonical_panel",
    "capital",
    "data_start",
    "execution_mode",
    "group_count",
    "industry_neutralization",
    "investable_universe",
    "long_only_universe",
    "price_inputs",
    "price_policy",
    "scoring_dates",
    "scoring_end",
    "scoring_start",
    "stale_positions",
    "signal_rows",
    "trading_dates",
}


def report_artifacts_available(report_dir: Path | str) -> bool:
    root = Path(report_dir)
    return (root / "summary.csv").is_file() and (root / "graph_data.json").is_file()


class ReportArtifactReader:
    def __init__(self, max_cache_entries: int = 128) -> None:
        self._max_cache_entries = max(0, max_cache_entries)
        self._cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()

    def read(self, report_dir: Path | str, *, include_parquet: bool = True) -> dict[str, Any]:
        root = Path(report_dir)
        key = self._cache_key(root, include_parquet)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return copy.deepcopy(cached)

        try:
            artifacts = {
                "summary": self._read_summary(root / "summary.csv"),
                "graph_data": self._read_json(root / "graph_data.json"),
                "diagnostics": self._read_diagnostics(root / "diagnostics.json"),
                "performance_table": self._read_performance_records(
                    root / "performance_by_year.csv"
                ),
                "parquet": self._read_parquet_artifacts(root) if include_parquet else {},
            }
        except _ArtifactReadInProgress:
            return _empty_artifacts()
        self._remember(key, artifacts)
        return copy.deepcopy(artifacts)

    def _cache_key(self, root: Path, include_parquet: bool) -> tuple[Any, ...]:
        paths = [
            root / "summary.csv",
            root / "performance_by_year.csv",
            root / "graph_data.json",
            root / "diagnostics.json",
        ]
        if include_parquet:
            paths.extend(sorted(root.glob("*.parquet")))
        return (
            root.resolve().as_posix(),
            include_parquet,
            tuple(_file_fingerprint(path) for path in paths),
        )

    def _remember(self, key: tuple[Any, ...], artifacts: dict[str, Any]) -> None:
        if self._max_cache_entries <= 0:
            return
        self._cache[key] = copy.deepcopy(artifacts)
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cache_entries:
            self._cache.popitem(last=False)

    def _read_summary(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            frame = pd.read_csv(path)
        except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
            raise _ArtifactReadInProgress from error
        records = _records(frame)
        return records[0] if records else {}

    def _read_records(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            frame = pd.read_csv(path)
        except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError) as error:
            raise _ArtifactReadInProgress from error
        if "period" in frame.columns:
            frame["period"] = frame["period"].astype(str)
        return _records(frame)

    def _read_performance_records(self, path: Path) -> list[dict[str, Any]]:
        records = self._read_records(path)
        normalized = []
        for record in records:
            row = dict(record)
            legacy_returns = row.pop("returns", None)
            if legacy_returns is not None:
                period = str(row.get("period", "")).lower()
                if period == "all" and row.get("annualized_return") is None:
                    row["annualized_return"] = legacy_returns
                    row.setdefault("total_return", None)
                elif row.get("total_return") is None:
                    row["total_return"] = legacy_returns
                    row.setdefault("annualized_return", None)
            normalized.append(row)
        return normalized

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise _ArtifactReadInProgress from error
        return _json_ready(payload)

    def _read_diagnostics(self, path: Path) -> dict[str, Any]:
        diagnostics = self._read_json(path)
        return {
            key: value
            for key, value in diagnostics.items()
            if key in PUBLIC_DIAGNOSTIC_KEYS
        }

    def _read_parquet_artifacts(self, root: Path) -> dict[str, list[dict[str, Any]]]:
        artifacts: dict[str, list[dict[str, Any]]] = {}
        for path in sorted(root.glob("*.parquet")):
            artifacts[path.stem] = _records(pd.read_parquet(path))
        return artifacts


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return _json_ready(frame.to_dict("records"))


class _ArtifactReadInProgress(RuntimeError):
    pass


def _empty_artifacts() -> dict[str, Any]:
    return {
        "summary": {},
        "graph_data": {},
        "diagnostics": {},
        "performance_table": [],
        "parquet": {},
    }


def _file_fingerprint(path: Path) -> tuple[str, int | None, int | None]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return (path.name, None, None)
    return (path.name, stat.st_mtime_ns, stat.st_size)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, pd.Timestamp):
        timestamp = value.to_pydatetime()
        if timestamp.hour == 0 and timestamp.minute == 0 and timestamp.second == 0:
            return timestamp.date().isoformat()
        return timestamp.isoformat()
    if pd.isna(value):
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value
