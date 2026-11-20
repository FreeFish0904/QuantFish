from __future__ import annotations

import csv
import re
import warnings
from datetime import timedelta
from pathlib import Path

import pandas as pd
from pandas.errors import ParserError

from quantfish.data.catalog import DataCatalog, DatasetSpec
from quantfish.market_types import (
    filter_by_market_types,
    market_type_candidate_columns,
    market_type_column,
    normalize_allowed_market_types,
)


class FutureDataAccessError(ValueError):
    """Raised when date-aware code asks for rows after its bound date."""


class CSMARCSVRepairError(ValueError):
    """Raised when a malformed CSMAR CSV row cannot be repaired safely."""


TEXT_REPAIR_COLUMNS = [
    "ReaFinResuVari",
    "Idxinfo04",
    "Idxinfo10",
    "ReaRept",
    "Memo",
    "Remark",
    "Remarks",
    "Comnt",
    "Commnt",
    "Description",
]
SHORT_CODE_COLUMNS = {"Idxinfo05", "Idxinfo06", "Idxinfo07", "Idxinfo08", "Idxinfo09"}
SHORT_CODE_RE = re.compile(r"^[A-Za-z0-9_.-]*$")


class DataBundle:
    def __init__(
        self,
        root: Path | str,
        allowed_market_types: list[int] | tuple[int, ...] | None = None,
    ):
        self.root = Path(root)
        self.catalog = DataCatalog.load(self.root / "data_catalog.json")
        self.allowed_market_types = (
            normalize_allowed_market_types(allowed_market_types)
            if allowed_market_types is not None
            else None
        )

    def list_datasets(self) -> list[str]:
        return self.catalog.list_datasets()

    def describe(self, dataset_id_or_alias: str) -> DatasetSpec:
        return self.catalog.describe(dataset_id_or_alias)

    def path(self, dataset_id_or_alias: str) -> Path:
        return self.catalog.path_for(dataset_id_or_alias, self.root)

    def load_raw(self, dataset_id_or_alias: str, columns: list[str] | None = None) -> pd.DataFrame:
        return self._load_raw_for_dated_access(dataset_id_or_alias, columns)

    def _load_raw_for_dated_access(
        self, dataset_id_or_alias: str, columns: list[str] | None = None
    ) -> pd.DataFrame:
        spec = self.describe(dataset_id_or_alias)
        if self.allowed_market_types is None:
            return _read_dataset(self.path(dataset_id_or_alias), spec, columns=columns)
        frame = _read_dataset_with_market_filter_columns(
            self.path(dataset_id_or_alias),
            spec,
            columns,
        )
        filtered = filter_by_market_types(frame, self.allowed_market_types)
        return _project_columns(filtered, columns)

    def date_series_for(
        self,
        dataset_id_or_alias: str,
        columns: list[str] | None,
        frame: pd.DataFrame,
        date_column: str,
    ) -> pd.Series:
        return _date_series(frame[date_column])

    def rows_for_date(
        self,
        dataset_id_or_alias: str,
        columns: list[str] | None,
        frame: pd.DataFrame,
        date_column: str,
        date: pd.Timestamp,
    ) -> pd.DataFrame:
        dates = self.date_series_for(dataset_id_or_alias, columns, frame, date_column)
        return frame[dates == date].copy()

    def at(self, date: str | pd.Timestamp) -> DatedDataBundle:
        return DatedDataBundle(self, _to_timestamp(date))


class DatedDataBundle:
    def __init__(self, bundle: DataBundle, date: pd.Timestamp):
        self.bundle = bundle
        self.date = date.normalize()

    def load(
        self,
        dataset_id_or_alias: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        columns: list[str] | None = None,
        *,
        numeric_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        return self._load_bounded(
            dataset_id_or_alias,
            start=start,
            end=end,
            columns=columns,
            numeric_columns=numeric_columns,
            required_columns=[],
            project=True,
        )

    def _load_bounded(
        self,
        dataset_id_or_alias: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        columns: list[str] | None = None,
        numeric_columns: list[str] | None = None,
        required_columns: list[str] | None = None,
        project: bool = True,
    ) -> pd.DataFrame:
        spec = self.bundle.describe(dataset_id_or_alias)
        required = list(required_columns or [])
        if spec.primary_asof_column is not None:
            required.append(spec.primary_asof_column)
        read_columns = _columns_with_required(columns, required)
        df = self.bundle._load_raw_for_dated_access(
            dataset_id_or_alias,
            columns=read_columns,
        )
        if spec.primary_asof_column is None:
            result = _project_columns(df, columns) if project else df
            return _coerce_numeric_columns(result, numeric_columns) if project else result

        start_date = _to_timestamp(start) if start is not None else None
        end_date = _to_timestamp(end) if end is not None else self.date
        if start_date is not None and start_date > self.date:
            raise FutureDataAccessError(
                f"start date {start_date.date()} is after bound date {self.date.date()}"
            )
        if end_date > self.date:
            raise FutureDataAccessError(
                f"end date {end_date.date()} is after bound date {self.date.date()}"
            )

        if start_date is not None and start_date == end_date:
            filtered = self.bundle.rows_for_date(
                dataset_id_or_alias,
                read_columns,
                df,
                spec.primary_asof_column,
                end_date,
            )
        else:
            dates = self.bundle.date_series_for(
                dataset_id_or_alias,
                read_columns,
                df,
                spec.primary_asof_column,
            )
            mask = dates <= end_date
            if start_date is not None:
                mask &= dates >= start_date
            filtered = df[mask].copy()
        result = _project_columns(filtered, columns) if project else filtered
        return _coerce_numeric_columns(result, numeric_columns) if project else result

    def current(
        self,
        dataset_id_or_alias: str,
        columns: list[str] | None = None,
        *,
        numeric_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        return self.load(
            dataset_id_or_alias,
            start=self.date,
            end=self.date,
            columns=columns,
            numeric_columns=numeric_columns,
        )

    def history(
        self,
        dataset_id_or_alias: str,
        start: str | pd.Timestamp | None = None,
        lookback_days: int | None = None,
        columns: list[str] | None = None,
        *,
        numeric_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        if lookback_days is not None and start is not None:
            raise ValueError("pass either start or lookback_days, not both")
        history_start = start
        if lookback_days is not None:
            if lookback_days < 0:
                raise ValueError("lookback_days cannot be negative")
            history_start = self.date - timedelta(days=lookback_days)
        return self.load(
            dataset_id_or_alias,
            start=history_start,
            end=self.date,
            columns=columns,
            numeric_columns=numeric_columns,
        )

    def latest(
        self,
        dataset_id_or_alias: str,
        by: str | None = None,
        columns: list[str] | None = None,
        *,
        numeric_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        spec = self.bundle.describe(dataset_id_or_alias)
        group_column = by or spec.symbol_column
        if spec.primary_asof_column is None:
            return self.load(
                dataset_id_or_alias,
                columns=columns,
                numeric_columns=numeric_columns,
            )

        required_columns = [group_column] if group_column is not None else []
        df = self._load_bounded(
            dataset_id_or_alias,
            columns=columns,
            required_columns=required_columns,
            project=False,
        )
        if df.empty:
            return _coerce_numeric_columns(_project_columns(df, columns), numeric_columns)

        dates = self.bundle.date_series_for(
            dataset_id_or_alias,
            columns,
            df,
            spec.primary_asof_column,
        )
        working = df.assign(__quantfish_asof=dates).sort_values("__quantfish_asof")
        if group_column is None:
            latest_date = working["__quantfish_asof"].max()
            result = working[working["__quantfish_asof"] == latest_date]
        else:
            result = working.groupby(group_column, as_index=False, sort=False).tail(1)
        projected = _project_columns(result.drop(columns=["__quantfish_asof"]).copy(), columns)
        return _coerce_numeric_columns(projected, numeric_columns)


def _read_dataset(path: Path, spec: DatasetSpec, columns: list[str] | None = None) -> pd.DataFrame:
    if spec.format == "csv":
        return _read_csv_dataset(path, spec, columns=columns)
    if spec.format == "parquet":
        return pd.read_parquet(path, columns=columns)
    raise ValueError(f"unsupported dataset format: {spec.format}")


def _read_dataset_with_market_filter_columns(
    path: Path,
    spec: DatasetSpec,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    if columns is None or market_type_column(columns) is not None:
        return _read_dataset(path, spec, columns=columns)
    for candidate in market_type_candidate_columns():
        read_columns = _columns_with_required(columns, [candidate])
        try:
            return _read_dataset(path, spec, columns=read_columns)
        except (KeyError, ValueError) as exc:
            if not _is_missing_market_filter_column(exc, candidate):
                raise
    return _read_dataset(path, spec, columns=columns)


def _is_missing_market_filter_column(exc: Exception, candidate: str) -> bool:
    message = str(exc).lower()
    return candidate.lower() in message and any(
        token in message
        for token in (
            "not found",
            "no match",
            "missing",
            "usecols",
            "columns expected",
        )
    )


def _read_csv_dataset(
    path: Path, spec: DatasetSpec, columns: list[str] | None = None
) -> pd.DataFrame:
    kwargs = {"encoding": "utf-8-sig"}
    if columns is not None:
        kwargs["usecols"] = columns
    if spec.symbol_column:
        kwargs["dtype"] = {spec.symbol_column: str}
    try:
        return pd.read_csv(path, **kwargs)
    except ParserError:
        return _read_repaired_csmar_csv(path, spec, columns=columns)


def _columns_with_required(
    columns: list[str] | None, required_columns: list[str]
) -> list[str] | None:
    if columns is None:
        return None
    merged = list(columns)
    for column in required_columns:
        if column not in merged:
            merged.append(column)
    return merged


def _project_columns(df: pd.DataFrame, columns: list[str] | None) -> pd.DataFrame:
    if columns is None:
        return df.copy()
    return df.loc[:, columns].copy()


def _coerce_numeric_columns(
    df: pd.DataFrame,
    numeric_columns: list[str] | None,
) -> pd.DataFrame:
    if not numeric_columns:
        return df
    result = df.copy()
    missing = [column for column in numeric_columns if column not in result.columns]
    if missing:
        raise KeyError(f"numeric columns missing from returned data: {missing}")
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def _read_repaired_csmar_csv(
    path: Path, spec: DatasetSpec, columns: list[str] | None = None
) -> pd.DataFrame:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration:
            return pd.DataFrame(columns=columns)

        expected_fields = len(header)
        pending_row: list[str] | None = None
        pending_line_number: int | None = None
        for line_number, row in enumerate(reader, start=2):
            if not row:
                continue
            if pending_row is not None:
                pending_row.extend(row)
                row = pending_row
                line_number = pending_line_number or line_number
                pending_row = None
                pending_line_number = None
            if len(row) < expected_fields:
                pending_row = row
                pending_line_number = line_number
                continue
            rows.append(_repair_csmar_row(path, line_number, header, row))

        if pending_row is not None:
            raise CSMARCSVRepairError(
                f"cannot repair {path} line {pending_line_number}: "
                f"expected {expected_fields} fields, saw {len(pending_row)}"
            )

    df = pd.DataFrame(rows, columns=header)
    if columns is not None:
        df = df.loc[:, columns]
    return df


def _repair_csmar_row(path: Path, line_number: int, header: list[str], row: list[str]) -> list[str]:
    expected_fields = len(header)
    if len(row) == expected_fields:
        return row
    if len(row) < expected_fields:
        raise CSMARCSVRepairError(
            f"cannot repair {path} line {line_number}: "
            f"expected {expected_fields} fields, saw {len(row)}"
        )

    candidates = []
    for repair_index in _repair_column_indexes(header):
        try:
            repaired = _merge_overflow_fields(row, expected_fields, repair_index)
        except CSMARCSVRepairError:
            continue
        candidates.append((_repair_score(header, repaired), -repair_index, repaired))
    if not candidates:
        raise CSMARCSVRepairError(
            f"cannot repair {path} line {line_number}: "
            f"expected {expected_fields} fields, saw {len(row)}"
        )
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _repair_column_indexes(header: list[str]) -> list[int]:
    return [index for index, column in enumerate(header) if column in TEXT_REPAIR_COLUMNS]


def _merge_overflow_fields(row: list[str], expected_fields: int, repair_index: int) -> list[str]:
    tail_field_count = expected_fields - repair_index - 1
    tail_start = len(row) - tail_field_count
    if tail_start <= repair_index:
        raise CSMARCSVRepairError("not enough overflow fields to merge")
    merged_text = ",".join(row[repair_index:tail_start])
    if merged_text.endswith('"'):
        merged_text = merged_text[:-1]
    repaired = [*row[:repair_index], merged_text, *row[tail_start:]]
    if len(repaired) != expected_fields:
        raise CSMARCSVRepairError(
            f"repair produced {len(repaired)} fields, expected {expected_fields}"
        )
    return repaired


def _repair_score(header: list[str], row: list[str]) -> int:
    score = 0
    # Broken CSV rows can have more or fewer fields than the header; the
    # heuristic must tolerate the mismatch instead of raising.
    for column, value in zip(header, row, strict=False):
        if column in TEXT_REPAIR_COLUMNS:
            continue
        text = "" if value is None else str(value)
        stripped = text.strip()
        if column in SHORT_CODE_COLUMNS and not SHORT_CODE_RE.match(stripped):
            score += 200
        if len(text) > 80:
            score += 100
        if len(text) > 20 and any(mark in text for mark in "，。；;:"):
            score += 20
    return score


def _to_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, errors="raise")
    if isinstance(timestamp, pd.DatetimeIndex):
        raise ValueError("expected one date, got many")
    return pd.Timestamp(timestamp).normalize()


def _date_series(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y/%m", "%Y%m"):
        missing = parsed.isna() & values.notna() & (values != "")
        if not missing.any():
            break
        parsed.loc[missing] = pd.to_datetime(
            values.loc[missing], format=date_format, errors="coerce"
        )
    missing = parsed.isna() & values.notna() & (values != "")
    if missing.any():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            parsed.loc[missing] = pd.to_datetime(values.loc[missing], errors="coerce")
    return parsed.dt.normalize()
