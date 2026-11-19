from __future__ import annotations

import math
from typing import Any

import pandas as pd

from quantfish.data import DataBundle
from quantfish.data.scoring_datasets import HS300_DATASET
from quantfish.stock_codes import normalize_stock_code

LEGACY_HS300_DATASET = "TRD_Index"


def load_hs300_benchmark(
    bundle: DataBundle,
    scoring_start: pd.Timestamp,
    scoring_end: pd.Timestamp,
) -> pd.DataFrame:
    candidates = [
        _load_hs300_benchmark_candidate(
            bundle,
            HS300_DATASET,
            code_columns=["indexcd", "Indexcd"],
            date_columns=["idxtrd01", "Trddt", "date", "tradingdate"],
            return_columns=["idxtrd08", "Retindex", "return"],
            close_columns=["idxtrd05", "Clsindex", "close"],
            scoring_start=scoring_start,
            scoring_end=scoring_end,
        ),
        _load_hs300_benchmark_candidate(
            bundle,
            LEGACY_HS300_DATASET,
            code_columns=["Indexcd", "indexcd"],
            date_columns=["Trddt", "idxtrd01", "date", "tradingdate"],
            return_columns=["Retindex", "idxtrd08", "return"],
            close_columns=["Clsindex", "idxtrd05", "close"],
            scoring_start=scoring_start,
            scoring_end=scoring_end,
        ),
    ]
    return max(candidates, key=len)


def build_hs300_benchmark_records(
    benchmark: pd.DataFrame,
    *,
    capital: float,
) -> list[dict[str, Any]]:
    if benchmark.empty:
        return []
    rows = benchmark.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()
    returns = pd.to_numeric(rows["return"], errors="coerce").fillna(0.0)
    equity = 1.0 + returns.cumsum()
    return [
        {
            "date": _date(date),
            "benchmark_return": _json_float(daily_return),
            "benchmark_equity": _json_float(value),
            "benchmark_cny": _json_float(value * capital),
        }
        for date, daily_return, value in zip(rows["date"], returns, equity, strict=True)
    ]


def _load_hs300_benchmark_candidate(
    bundle: DataBundle,
    dataset_id: str,
    *,
    code_columns: list[str],
    date_columns: list[str],
    return_columns: list[str],
    close_columns: list[str],
    scoring_start: pd.Timestamp,
    scoring_end: pd.Timestamp,
) -> pd.DataFrame:
    try:
        rows = bundle.load_raw(dataset_id)
    except KeyError:
        return pd.DataFrame(columns=["date", "return"])
    code_column = _optional_column(rows, code_columns)
    date_column = _optional_column(rows, date_columns)
    return_column = _optional_column(rows, return_columns)
    close_column = _optional_column(rows, close_columns)
    if code_column is None or date_column is None:
        return pd.DataFrame(columns=["date", "return"])

    benchmark = rows.copy()
    benchmark["date"] = pd.to_datetime(benchmark[date_column]).dt.normalize()
    benchmark = benchmark[
        benchmark[code_column].map(normalize_stock_code) == "000300"
    ]
    benchmark = benchmark[
        (benchmark["date"] >= scoring_start) & (benchmark["date"] <= scoring_end)
    ].sort_values("date")
    if benchmark.empty:
        return pd.DataFrame(columns=["date", "return"])

    if return_column is not None:
        returns = pd.to_numeric(benchmark[return_column], errors="coerce")
        max_abs_return = returns.abs().max(skipna=True)
        if pd.notna(max_abs_return) and max_abs_return > 1:
            returns = returns / 100.0
    elif close_column is not None:
        close = pd.to_numeric(benchmark[close_column], errors="coerce")
        returns = close.pct_change().fillna(0.0)
    else:
        return pd.DataFrame(columns=["date", "return"])

    return benchmark.assign(return_=returns).loc[:, ["date", "return_"]].rename(
        columns={"return_": "return"}
    )


def _optional_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    folded = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    return None


def _date(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _json_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
