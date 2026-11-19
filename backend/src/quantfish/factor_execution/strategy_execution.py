from __future__ import annotations

import importlib.util
import inspect
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pandas as pd

from quantfish.data import DataBundle
from quantfish.market_types import DEFAULT_ALLOWED_MARKET_TYPES
from quantfish.stock_codes import StockCodeError, normalize_stock_code

CANONICAL_PANEL_DATASET = "stock.daily_returns"


class StrategySignalError(ValueError):
    """Raised when a student strategy cannot produce valid factor scores."""


@dataclass(frozen=True)
class StrategyExecutionConfig:
    data_start: str | pd.Timestamp
    scoring_end: str | pd.Timestamp
    canonical_panel: str = CANONICAL_PANEL_DATASET
    allowed_market_types: tuple[int, ...] | None = DEFAULT_ALLOWED_MARKET_TYPES


@dataclass(frozen=True)
class StrategyExecutionResult:
    scores: pd.DataFrame
    diagnostics: dict[str, Any]


class CachedDataBundle(DataBundle):
    """DataBundle variant that caches raw dataset reads across dated views."""

    def __init__(
        self,
        root: Path | str,
        allowed_market_types: Sequence[int] | None = DEFAULT_ALLOWED_MARKET_TYPES,
        max_cache_entries: int = 16,
    ):
        super().__init__(root, allowed_market_types=allowed_market_types)
        self._max_cache_entries = max(1, int(max_cache_entries))
        self._raw_cache: OrderedDict[
            tuple[str, tuple[str, ...] | None], pd.DataFrame
        ] = OrderedDict()
        self._date_cache: OrderedDict[
            tuple[str, tuple[str, ...] | None, str], pd.Series
        ] = OrderedDict()
        self._date_index_cache: OrderedDict[
            tuple[str, tuple[str, ...] | None, str], dict[pd.Timestamp, pd.Index]
        ] = OrderedDict()

    def load_raw(
        self, dataset_id_or_alias: str, columns: list[str] | None = None
    ) -> pd.DataFrame:
        return self._load_raw_for_dated_access(dataset_id_or_alias, columns).copy()

    def _load_raw_for_dated_access(
        self, dataset_id_or_alias: str, columns: list[str] | None = None
    ) -> pd.DataFrame:
        column_key = _column_key(columns)
        cache_key = (dataset_id_or_alias, column_key)
        cached = _lru_get(self._raw_cache, cache_key)
        if cached is None and column_key is not None:
            full = _lru_get(self._raw_cache, (dataset_id_or_alias, None))
            if full is not None:
                cached = full.loc[:, list(column_key)]
        if cached is None:
            cached = super()._load_raw_for_dated_access(
                dataset_id_or_alias,
                list(column_key) if column_key is not None else None,
            )
            _lru_set(
                self._raw_cache,
                cache_key,
                cached,
                max_entries=self._max_cache_entries,
            )
        return cached

    def date_series_for(
        self,
        dataset_id_or_alias: str,
        columns: list[str] | None,
        frame: pd.DataFrame,
        date_column: str,
    ) -> pd.Series:
        column_key = _column_key(columns)
        cache_key = (dataset_id_or_alias, column_key, date_column)
        cached = _lru_get(self._date_cache, cache_key)
        if cached is None:
            cached = super().date_series_for(
                dataset_id_or_alias,
                list(column_key) if column_key is not None else None,
                frame,
                date_column,
            )
            _lru_set(
                self._date_cache,
                cache_key,
                cached,
                max_entries=self._max_cache_entries,
            )
        return cached

    def rows_for_date(
        self,
        dataset_id_or_alias: str,
        columns: list[str] | None,
        frame: pd.DataFrame,
        date_column: str,
        date: pd.Timestamp,
    ) -> pd.DataFrame:
        column_key = _column_key(columns)
        cache_key = (dataset_id_or_alias, column_key, date_column)
        date_index = _lru_get(self._date_index_cache, cache_key)
        if date_index is None:
            dates = self.date_series_for(
                dataset_id_or_alias,
                list(column_key) if column_key is not None else None,
                frame,
                date_column,
            )
            date_index = {
                pd.Timestamp(group_date).normalize(): indexes
                for group_date, indexes in dates.groupby(dates).groups.items()
                if pd.notna(group_date)
            }
            _lru_set(
                self._date_index_cache,
                cache_key,
                date_index,
                max_entries=self._max_cache_entries,
            )
        indexes = date_index.get(pd.Timestamp(date).normalize())
        if indexes is None:
            return frame.iloc[0:0].copy()
        return frame.loc[indexes].copy()


def _column_key(columns: list[str] | None) -> tuple[str, ...] | None:
    if columns is None:
        return None
    return tuple(dict.fromkeys(str(column) for column in columns))


def _lru_get(
    cache: OrderedDict[tuple[Any, ...], Any],
    key: tuple[Any, ...],
) -> Any | None:
    if key not in cache:
        return None
    cache.move_to_end(key)
    return cache[key]


def _lru_set(
    cache: OrderedDict[tuple[Any, ...], Any],
    key: tuple[Any, ...],
    value: Any,
    *,
    max_entries: int,
) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_entries:
        cache.popitem(last=False)


class StudentDataView:
    """Restricted date-aware data surface passed into student strategies."""

    __slots__ = ("__dated_bundle", "date")

    def __init__(self, dated_bundle: Any):
        self.__dated_bundle = dated_bundle
        self.date = dated_bundle.date

    def list_datasets(self) -> list[str]:
        return self.__dated_bundle.bundle.list_datasets()

    def describe(self, dataset_id_or_alias: str) -> Any:
        return self.__dated_bundle.bundle.describe(dataset_id_or_alias)

    def load(
        self,
        dataset_id_or_alias: str,
        start: str | pd.Timestamp | None = None,
        end: str | pd.Timestamp | None = None,
        columns: list[str] | None = None,
        *,
        numeric_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        return self.__dated_bundle.load(
            dataset_id_or_alias,
            start=start,
            end=end,
            columns=columns,
            numeric_columns=numeric_columns,
        )

    def current(
        self,
        dataset_id_or_alias: str,
        columns: list[str] | None = None,
        *,
        numeric_columns: list[str] | None = None,
    ) -> pd.DataFrame:
        return self.__dated_bundle.current(
            dataset_id_or_alias,
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
        return self.__dated_bundle.history(
            dataset_id_or_alias,
            start=start,
            lookback_days=lookback_days,
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
        return self.__dated_bundle.latest(
            dataset_id_or_alias,
            by=by,
            columns=columns,
            numeric_columns=numeric_columns,
        )


def execute_student_strategy(
    strategy_path: Path | str,
    data_root: Path | str,
    config: StrategyExecutionConfig,
) -> StrategyExecutionResult:
    strategy = _load_strategy_module(Path(strategy_path))
    generate_signals = getattr(strategy, "generate_signals", None)
    if not callable(generate_signals):
        raise StrategySignalError("student strategy must define callable generate_signals")

    bundle = CachedDataBundle(
        data_root,
        allowed_market_types=config.allowed_market_types,
    )
    trading_dates = _trading_dates(bundle, config)
    call_generate_signals = _compile_generate_signals_call(generate_signals)
    frames = []
    for trading_date in trading_dates:
        dated_bundle = bundle.at(trading_date)
        student_data = StudentDataView(dated_bundle)
        raw_signals = call_generate_signals(student_data, trading_date)
        frames.append(_normalize_signals(raw_signals, trading_date))

    scores = pd.concat(frames, ignore_index=True) if frames else _empty_scores()
    return StrategyExecutionResult(
        scores=scores,
        diagnostics={
            "strategy_path": Path(strategy_path).as_posix(),
            "data_root": Path(data_root).as_posix(),
            "canonical_panel": config.canonical_panel,
            "allowed_market_types": _allowed_market_type_list(config.allowed_market_types),
            "trading_dates": [date.date().isoformat() for date in trading_dates],
            "signal_rows": len(scores),
        },
    )


def _allowed_market_type_list(
    allowed_market_types: Sequence[int] | None,
) -> list[int] | None:
    if allowed_market_types is None:
        return None
    return [int(value) for value in allowed_market_types]


def _compile_generate_signals_call(
    generate_signals: Callable[..., Any],
) -> Callable[[Any, pd.Timestamp], Any]:
    signature = inspect.signature(generate_signals)
    accepts_varargs = any(
        parameter.kind == inspect.Parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    )
    positional_parameters = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if accepts_varargs or len(positional_parameters) >= 2:
        return lambda dated_bundle, trading_date: generate_signals(
            dated_bundle,
            trading_date,
        )
    return lambda dated_bundle, trading_date: generate_signals(dated_bundle)


def _load_strategy_module(strategy_path: Path) -> ModuleType:
    if not strategy_path.exists():
        raise StrategySignalError(f"strategy file does not exist: {strategy_path}")
    module_name = f"quantfish_student_strategy_{abs(hash(strategy_path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, strategy_path)
    if spec is None or spec.loader is None:
        raise StrategySignalError(f"cannot import strategy file: {strategy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _trading_dates(
    bundle: DataBundle, config: StrategyExecutionConfig
) -> list[pd.Timestamp]:
    spec = bundle.describe(config.canonical_panel)
    if spec.primary_asof_column is None:
        raise StrategySignalError(
            f"canonical panel {config.canonical_panel} has no trading date column"
        )
    panel = bundle.load_raw(config.canonical_panel, columns=[spec.primary_asof_column])
    dates = pd.to_datetime(panel[spec.primary_asof_column], errors="raise").dt.normalize()
    data_start = pd.Timestamp(config.data_start).normalize()
    scoring_end = pd.Timestamp(config.scoring_end).normalize()
    if data_start > scoring_end:
        raise StrategySignalError("data_start cannot be after scoring_end")
    mask = (dates >= data_start) & (dates <= scoring_end)
    return sorted(pd.Series(dates[mask].unique()).dropna().tolist())


def _normalize_signals(raw_signals: Any, trading_date: pd.Timestamp) -> pd.DataFrame:
    signals = _signals_to_frame(raw_signals)
    if signals.empty:
        return _empty_scores()
    if "code" not in signals.columns or "score" not in signals.columns:
        raise StrategySignalError("signals must include code and score columns")

    score = pd.to_numeric(signals["score"], errors="coerce")
    invalid_scores = score.isna() & signals["score"].notna().to_numpy()
    if invalid_scores.any():
        raise StrategySignalError("signal scores must be numeric")
    score = score.replace([float("inf"), -float("inf")], float("nan"))
    normalized = pd.DataFrame(
        {
            "date": pd.Timestamp(trading_date).normalize(),
            "code": signals["code"].map(_normalize_code),
            "score": score,
        }
    )
    duplicated = normalized["code"].duplicated(keep=False)
    if duplicated.any():
        duplicate_codes = sorted(normalized.loc[duplicated, "code"].unique())
        raise StrategySignalError(f"duplicate signal codes: {duplicate_codes}")
    return normalized.sort_values("code", kind="stable").reset_index(drop=True)


def _signals_to_frame(raw_signals: Any) -> pd.DataFrame:
    if isinstance(raw_signals, pd.Series):
        return pd.DataFrame({"code": raw_signals.index, "score": raw_signals.values})
    if isinstance(raw_signals, pd.DataFrame):
        if {"code", "score"}.issubset(raw_signals.columns):
            return raw_signals.loc[:, ["code", "score"]].copy()
        if len(raw_signals.columns) == 1:
            column = raw_signals.columns[0]
            return pd.DataFrame({"code": raw_signals.index, "score": raw_signals[column]})
    raise StrategySignalError(
        "generate_signals must return a pandas Series or DataFrame of scores"
    )


def _normalize_code(value: Any) -> str:
    try:
        return normalize_stock_code(value)
    except StockCodeError as exc:
        raise StrategySignalError(f"invalid signal code: {exc}") from exc


def _empty_scores() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "code": pd.Series(dtype="object"),
            "score": pd.Series(dtype="float64"),
        }
    )
