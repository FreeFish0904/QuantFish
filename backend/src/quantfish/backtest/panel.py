from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from quantfish.backtest.price_adjustment import (
    apply_front_adjustment,
    calculate_raw_vwap,
)
from quantfish.stock_codes import normalize_stock_code


@dataclass(frozen=True)
class BacktestPanel:
    rows: pd.DataFrame


def build_backtest_panel(
    daily_returns: pd.DataFrame,
    adj_factor: pd.DataFrame,
) -> BacktestPanel:
    daily = daily_returns.copy()
    factors = adj_factor.copy()

    daily_date = _find_column(daily, ["date", "TradingDate", "Trddt"])
    daily_symbol = _find_column(daily, ["symbol", "Symbol", "Stkcd"])
    close = _find_column(daily, ["front_close", "close", "Clsprc", "clsprc"])
    shares = _find_column(daily, ["dnshrtrd", "Dnshrtrd", "volume"])
    value = _find_column(daily, ["dnvaltrd", "Dnvaltrd", "amount"])

    factor_date = _find_column(factors, ["date", "TradingDate", "Trddt"])
    factor_symbol = _find_column(factors, ["symbol", "Symbol", "Stkcd"])
    factor_column = _find_column(
        factors,
        [
            "cumulatebwardfactor",
            "CumulateBwardFactor",
            "Cumulatebwardfactor",
            "cumulatefwardfactor",
            "CumulateFwardFactor",
            "Cumulatefwardfactor",
        ],
    )

    daily = daily.rename(
        columns={
            daily_date: "date",
            daily_symbol: "symbol",
            close: "raw_close",
            shares: "dnshrtrd",
            value: "dnvaltrd",
        }
    )
    daily["trading_status"] = _optional_source_column(
        daily,
        "trading_status",
    ).to_numpy()
    daily["limit_status"] = _optional_source_column(daily, "limit_status").to_numpy()
    daily["market_type"] = _optional_source_column(daily, "market_type").to_numpy()
    daily["raw_limit_up"] = _optional_source_column(daily, "limit_up").to_numpy()
    daily["raw_limit_down"] = _optional_source_column(daily, "limit_down").to_numpy()
    factors = factors.loc[:, [factor_date, factor_symbol, factor_column]].rename(
        columns={
            factor_date: "date",
            factor_symbol: "symbol",
            factor_column: "cumulatefwardfactor",
        }
    )

    daily["date"] = pd.to_datetime(daily["date"])
    factors["date"] = pd.to_datetime(factors["date"])
    daily["symbol"] = daily["symbol"].map(normalize_stock_code)
    factors["symbol"] = factors["symbol"].map(normalize_stock_code)

    rows = _join_factors_asof(daily, factors)
    rows["raw_close"] = pd.to_numeric(rows["raw_close"], errors="coerce")
    rows["dnshrtrd"] = pd.to_numeric(rows["dnshrtrd"], errors="coerce")
    rows["dnvaltrd"] = pd.to_numeric(rows["dnvaltrd"], errors="coerce")
    rows["market_type"] = pd.to_numeric(rows["market_type"], errors="coerce")
    rows["raw_limit_up"] = pd.to_numeric(rows["raw_limit_up"], errors="coerce")
    rows["raw_limit_down"] = pd.to_numeric(rows["raw_limit_down"], errors="coerce")
    rows["cumulatefwardfactor"] = pd.to_numeric(rows["cumulatefwardfactor"], errors="coerce")

    shares_positive = rows["dnshrtrd"] > 0
    valid_liquidity = shares_positive & (rows["dnvaltrd"] > 0)
    rows["raw_vwap"] = calculate_raw_vwap(rows["dnvaltrd"], rows["dnshrtrd"])
    rows["front_close"] = apply_front_adjustment(rows["raw_close"], rows["cumulatefwardfactor"])
    rows["front_vwap"] = apply_front_adjustment(rows["raw_vwap"], rows["cumulatefwardfactor"])
    rows["front_limit_up"] = apply_front_adjustment(
        rows["raw_limit_up"], rows["cumulatefwardfactor"]
    )
    rows["front_limit_down"] = apply_front_adjustment(
        rows["raw_limit_down"], rows["cumulatefwardfactor"]
    )
    rows["tradable"] = valid_liquidity.map(bool).astype(object)

    ordered_columns = [
        "date",
        "symbol",
        "raw_close",
        "raw_vwap",
        "dnvaltrd",
        "dnshrtrd",
        "trading_status",
        "limit_status",
        "market_type",
        "raw_limit_up",
        "raw_limit_down",
        "front_close",
        "front_vwap",
        "front_limit_up",
        "front_limit_down",
        "cumulatefwardfactor",
        "tradable",
    ]
    return BacktestPanel(
        rows.loc[:, ordered_columns].sort_values(["date", "symbol"]).reset_index(drop=True)
    )


def preprocess_signals(
    signals: pd.DataFrame,
    mode: str,
    *,
    signal_column: str = "signal",
    top_k: int | None = None,
    long_only_weighting: str = "score_proportional",
) -> pd.DataFrame:
    if mode not in {"longshort", "longonly"}:
        raise ValueError("mode must be 'longshort' or 'longonly'")
    if top_k is not None and top_k <= 0:
        raise ValueError("top_k must be positive")
    if long_only_weighting not in {"rank_equal", "score_proportional"}:
        raise ValueError("long_only_weighting must be 'rank_equal' or 'score_proportional'")

    date = _find_column(signals, ["date", "TradingDate", "trading_date"])
    symbol = _find_column(signals, ["code", "symbol", "Symbol", "Stkcd"])
    if signal_column not in signals.columns:
        signal_column = _find_column(signals, ["signal", "factor", "score", "weight"])

    rows = signals.rename(columns={date: "date", symbol: "symbol", signal_column: "signal"}).copy()
    rows["date"] = pd.to_datetime(rows["date"])
    rows["symbol"] = rows["symbol"].map(normalize_stock_code)
    rows["signal"] = pd.to_numeric(rows["signal"], errors="coerce")
    rows["weight"] = 0.0

    for _, index in rows.groupby("date", sort=False).groups.items():
        values = rows.loc[index, "signal"].astype(float)
        valid = values.where(values.map(math.isfinite), other=float("nan"))
        if top_k is not None:
            keep_index = _top_k_index(valid, mode, top_k)
            valid = valid.where(valid.index.isin(keep_index), other=float("nan"))
        if mode == "longshort":
            centered = valid - valid.mean(skipna=True)
            gross = centered.abs().sum(skipna=True)
            weights = centered / gross if gross > 0 else centered * 0.0
        elif long_only_weighting == "rank_equal":
            selected = valid[valid > 0].dropna()
            weights = valid * 0.0
            if not selected.empty:
                weights.loc[selected.index] = 1.0 / len(selected)
        else:
            clipped = valid.clip(lower=0.0)
            total = clipped.sum(skipna=True)
            weights = clipped / total if total > 0 else clipped * 0.0
        rows.loc[index, "weight"] = weights.fillna(0.0)

    return rows.loc[:, ["date", "symbol", "weight"]]


def _top_k_index(values: pd.Series, mode: str, top_k: int) -> set[Any]:
    valid = values.dropna()
    if valid.empty:
        return set()
    if mode == "longonly":
        return set(valid.nlargest(top_k, keep="first").index)
    return set(valid.nlargest(top_k, keep="first").index) | set(
        valid.nsmallest(top_k, keep="first").index
    )


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    folded = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    raise KeyError(f"missing required column; tried {', '.join(candidates)}")


def _join_factors_asof(daily: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    factor_columns = ["date", "symbol", "cumulatefwardfactor"]
    daily_sorted = daily.sort_values(["date", "symbol"]).reset_index(drop=True)
    if daily_sorted.empty:
        return daily.assign(cumulatefwardfactor=pd.Series(dtype="float64"))
    factor_subset = (
        factors.loc[:, factor_columns]
        .sort_values(
            ["date", "symbol"],
        )
        .reset_index(drop=True)
    )
    if factor_subset.empty:
        merged = daily_sorted.copy()
        merged["cumulatefwardfactor"] = float("nan")
        return merged
    return pd.merge_asof(
        daily_sorted,
        factor_subset,
        on="date",
        by="symbol",
        direction="backward",
    )


def _optional_source_column(df: pd.DataFrame, normalized_name: str) -> pd.Series:
    candidates = {
        "trading_status": ["trading_status", "TradingStatus", "Trdsta", "TrdStatus"],
        "limit_status": [
            "limit_status",
            "limitstatus",
            "LimitStatus",
            "Limitstatus",
            "涨跌停状态",
        ],
        "market_type": ["market_type", "markettype", "MarketType", "Markettype"],
        "limit_up": ["limit_up", "limitup", "LimitUp", "Limitup", "涨停价"],
        "limit_down": [
            "limit_down",
            "limitdown",
            "LimitDown",
            "Limitdown",
            "跌停价",
        ],
    }[normalized_name]
    for candidate in candidates:
        if candidate in df.columns:
            return df[candidate]
    folded = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return df[folded[candidate.lower()]]
    return pd.Series([None] * len(df), index=df.index, dtype="object")
