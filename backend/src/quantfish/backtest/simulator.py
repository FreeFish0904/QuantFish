from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from quantfish.backtest.panel import BacktestPanel, preprocess_signals
from quantfish.backtest.price_limits import fallback_price_limit_threshold


class TerminalStalePositionsError(ValueError):
    def __init__(self, symbols: list[str], gross_exposure: float):
        self.symbols = tuple(symbols)
        self.gross_exposure = float(gross_exposure)
        super().__init__(
            "backtest ended with unpriced positions; "
            f"symbols={symbols}, gross_exposure={gross_exposure:.6f}"
        )

    @property
    def public_message(self) -> str:
        return (
            f"Backtest ended with {len(self.symbols)} unpriced terminal positions "
            f"(gross exposure {self.gross_exposure:.6f})"
        )


@dataclass(frozen=True)
class BacktestResult:
    daily: pd.DataFrame = field(default_factory=pd.DataFrame)
    positions: pd.DataFrame = field(default_factory=pd.DataFrame)
    group_returns: pd.DataFrame = field(default_factory=pd.DataFrame)
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    daily_returns: pd.DataFrame = field(default_factory=pd.DataFrame)
    net_value: pd.DataFrame = field(default_factory=pd.DataFrame)
    turnover: pd.DataFrame = field(default_factory=pd.DataFrame)
    group_daily_returns: pd.DataFrame = field(default_factory=pd.DataFrame)
    performance_by_year: pd.DataFrame = field(default_factory=pd.DataFrame)
    graph_data: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def simulate_backtest(
    panel: BacktestPanel,
    signals: pd.DataFrame,
    *,
    capital: float,
    mode: str,
    limit_threshold: float = 0.0995,
    commission_rate: float = 0.0,
    slippage_rate: float = 0.0,
    sell_stamp_duty_rate: float = 0.0,
    max_leverage: float = 1.0,
    top_k: int | None = None,
    long_only_weighting: str = "rank_equal",
    max_position_weight: float | None = None,
    max_participation_rate: float = 0.10,
    terminal_stale_position_policy: str = "carry",
) -> BacktestResult:
    capital = _finite_number("capital", capital)
    if capital <= 0:
        raise ValueError("capital must be positive")
    limit_threshold = _finite_number("limit_threshold", limit_threshold)
    if limit_threshold <= 0:
        raise ValueError("limit_threshold must be positive")
    commission_rate = _finite_number("commission_rate", commission_rate)
    if commission_rate < 0:
        raise ValueError("commission_rate cannot be negative")
    slippage_rate = _finite_number("slippage_rate", slippage_rate)
    if slippage_rate < 0:
        raise ValueError("slippage_rate cannot be negative")
    sell_stamp_duty_rate = _finite_number(
        "sell_stamp_duty_rate",
        sell_stamp_duty_rate,
    )
    if sell_stamp_duty_rate < 0:
        raise ValueError("sell_stamp_duty_rate cannot be negative")
    max_leverage = _finite_number("max_leverage", max_leverage)
    if max_leverage <= 0:
        raise ValueError("max_leverage must be positive")
    if top_k is not None and (isinstance(top_k, bool) or not isinstance(top_k, int)):
        raise ValueError("top_k must be an integer")
    if max_position_weight is not None:
        max_position_weight = _finite_number(
            "max_position_weight",
            max_position_weight,
        )
        if not (0 < max_position_weight <= 1):
            raise ValueError("max_position_weight must be between 0 and 1")
    max_participation_rate = _finite_number(
        "max_participation_rate",
        max_participation_rate,
    )
    if not (0 < max_participation_rate <= 1):
        raise ValueError("max_participation_rate must be between 0 and 1")
    if mode not in {"longshort", "longonly"}:
        raise ValueError("mode must be 'longshort' or 'longonly'")
    if terminal_stale_position_policy not in {"carry", "reject"}:
        raise ValueError("terminal_stale_position_policy must be 'carry' or 'reject'")

    rows = panel.rows.copy()
    rows["date"] = pd.to_datetime(rows["date"])
    rows["symbol"] = rows["symbol"].astype(str)
    rows = rows.sort_values(["date", "symbol"]).reset_index(drop=True)

    dates = pd.Index(rows["date"]).drop_duplicates().sort_values()
    symbols = pd.Index(sorted(rows["symbol"].unique()))
    targets = _target_weights(
        signals,
        mode,
        list(dates),
        list(symbols),
        top_k,
        max_leverage,
        long_only_weighting,
        max_position_weight,
    )
    close = _pivot(rows, "front_close", dates, symbols).to_numpy(dtype=float)
    vwap = _pivot(rows, "front_vwap", dates, symbols).to_numpy(dtype=float)
    dnvaltrd = _pivot(rows, "dnvaltrd", dates, symbols).to_numpy(dtype=float)
    tradable = _pivot(rows.assign(tradable=rows["tradable"].map(bool)), "tradable", dates, symbols)
    tradable_values = tradable.fillna(False).to_numpy(dtype=bool)
    limit_status_raw = _optional_numeric_matrix(rows, "limit_status", dates, symbols)
    limit_status_known = np.isfinite(limit_status_raw)
    limit_status_values = np.nan_to_num(limit_status_raw, nan=0.0)
    front_limit_up = _optional_numeric_matrix(rows, "front_limit_up", dates, symbols)
    front_limit_down = _optional_numeric_matrix(rows, "front_limit_down", dates, symbols)
    market_types = _optional_numeric_matrix(rows, "market_type", dates, symbols)
    fallback_limit_thresholds = _fallback_limit_thresholds(
        market_types,
        dates,
        default=limit_threshold,
    )

    previous_positions = np.zeros(len(symbols), dtype=float)
    previous_close = np.full(len(symbols), np.nan, dtype=float)
    position_frames = []
    daily_records = []

    for index, date in enumerate(dates):
        desired_positions = targets[index - 1] if index > 0 else np.zeros(len(symbols))
        desired_change = desired_positions - previous_positions
        day_close = close[index]
        day_vwap = vwap[index]
        valid_close = np.isfinite(day_close) & (day_close > 0)
        valid_vwap = np.isfinite(day_vwap) & (day_vwap > 0)
        previous_close_valid = np.isfinite(previous_close) & (previous_close > 0)
        close_return = np.zeros(len(symbols), dtype=float)
        close_return[previous_close_valid & valid_close] = (
            day_close[previous_close_valid & valid_close]
            / previous_close[previous_close_valid & valid_close]
            - 1.0
        )
        source_limit_up = (limit_status_values[index] > 0) | (
            np.isfinite(front_limit_up[index])
            & valid_close
            & (day_close >= front_limit_up[index] - 1e-10)
        )
        source_limit_down = (limit_status_values[index] < 0) | (
            np.isfinite(front_limit_down[index])
            & valid_close
            & (day_close <= front_limit_down[index] + 1e-10)
        )
        fallback_limit_up = (
            previous_close_valid
            & ~limit_status_known[index]
            & ~np.isfinite(front_limit_up[index])
            & (close_return > fallback_limit_thresholds[index])
        )
        fallback_limit_down = (
            previous_close_valid
            & ~limit_status_known[index]
            & ~np.isfinite(front_limit_down[index])
            & (close_return < -fallback_limit_thresholds[index])
        )
        limit_up = source_limit_up | fallback_limit_up
        limit_down = source_limit_down | fallback_limit_down
        if mode == "longshort":
            blocked = (
                ~tradable_values[index]
                | ~(valid_close & valid_vwap)
                | limit_up
                | limit_down
            )
            cap = (
                10.0
                * np.nan_to_num(dnvaltrd[index], nan=0.0, posinf=0.0, neginf=0.0)
                / capital
            )
            executed_change = np.clip(desired_change, -cap, cap)
            executed_change[blocked] = 0.0
            current_positions = previous_positions + executed_change
            current_positions = _rescale_gross_exposure(
                current_positions,
                max_leverage,
            )
        else:
            base_blocked = (
                ~tradable_values[index]
                | ~(valid_close & valid_vwap)
            )
            buy_blocked = base_blocked | limit_up
            sell_blocked = base_blocked | limit_down
            cap = (
                max_participation_rate
                * np.nan_to_num(dnvaltrd[index], nan=0.0, posinf=0.0, neginf=0.0)
                / capital
            )
            executed_change = np.clip(desired_change, -cap, cap)
            executed_change[(desired_change > 0) & buy_blocked] = 0.0
            executed_change[(desired_change < 0) & sell_blocked] = 0.0
            current_positions = _apply_execution_with_gross_limit(
                previous_positions,
                executed_change,
                max_leverage,
            )

        close_to_vwap_terms = np.zeros(len(symbols), dtype=float)
        close_to_vwap_mask = previous_close_valid & valid_vwap & valid_close
        close_to_vwap_terms[close_to_vwap_mask] = previous_positions[
            close_to_vwap_mask
        ] * (day_vwap[close_to_vwap_mask] / previous_close[close_to_vwap_mask] - 1.0)
        missing_vwap_mark_mask = previous_close_valid & valid_close & ~valid_vwap
        close_to_vwap_terms[missing_vwap_mark_mask] = previous_positions[
            missing_vwap_mark_mask
        ] * close_return[missing_vwap_mark_mask]
        vwap_to_close_terms = np.zeros(len(symbols), dtype=float)
        vwap_to_close_mask = valid_vwap & valid_close
        vwap_to_close_terms[vwap_to_close_mask] = current_positions[
            vwap_to_close_mask
        ] * (day_close[vwap_to_close_mask] / day_vwap[vwap_to_close_mask] - 1.0)

        close_to_vwap = float(close_to_vwap_terms.sum())
        vwap_to_close = float(vwap_to_close_terms.sum())
        long_return = float(
            close_to_vwap_terms[previous_positions > 0].sum()
            + vwap_to_close_terms[current_positions > 0].sum()
        )
        short_return = float(
            close_to_vwap_terms[previous_positions < 0].sum()
            + vwap_to_close_terms[current_positions < 0].sum()
        )
        position_change = current_positions - previous_positions
        turnover = float(np.abs(position_change).sum())
        buy_turnover = float(position_change[position_change > 0].sum())
        sell_turnover = float(-position_change[position_change < 0].sum())
        transaction_cost = (
            turnover * (commission_rate + slippage_rate)
            + sell_turnover * sell_stamp_duty_rate
        )
        long_exposure = float(current_positions[current_positions > 0].sum())
        short_exposure = float(current_positions[current_positions < 0].sum())
        gross_exposure = float(np.abs(current_positions).sum())
        position_count = int((np.abs(current_positions) > 1e-12).sum())
        stale_position_mask = (np.abs(current_positions) > 1e-12) & ~valid_close
        stale_position_count = int(stale_position_mask.sum())
        stale_gross_exposure = float(np.abs(current_positions[stale_position_mask]).sum())
        daily_records.append(
            {
                "date": date,
                "close_to_vwap_return": close_to_vwap,
                "vwap_to_close_return": vwap_to_close,
                "long_return": long_return,
                "short_return": short_return,
                "transaction_cost": transaction_cost,
                "portfolio_return": long_return + short_return - transaction_cost,
                "turnover": turnover,
                "buy_turnover": buy_turnover,
                "sell_turnover": sell_turnover,
                "long_exposure": long_exposure,
                "short_exposure": short_exposure,
                "gross_exposure": gross_exposure,
                "net_exposure": long_exposure + short_exposure,
                "position_count": position_count,
                "stale_position_count": stale_position_count,
                "stale_gross_exposure": stale_gross_exposure,
            }
        )
        position_frames.append(
            pd.DataFrame({"date": date, "symbol": symbols, "weight": current_positions})
        )
        previous_close = np.where(valid_close, day_close, previous_close)
        previous_positions = current_positions

    if (
        terminal_stale_position_policy == "reject"
        and daily_records
        and daily_records[-1]["stale_position_count"] > 0
    ):
        terminal_close_valid = np.isfinite(close[-1]) & (close[-1] > 0)
        terminal_stale = (np.abs(previous_positions) > 1e-12) & ~terminal_close_valid
        stale_symbols = [str(symbol) for symbol in symbols[terminal_stale]]
        stale_exposure = float(np.abs(previous_positions[terminal_stale]).sum())
        raise TerminalStalePositionsError(stale_symbols, stale_exposure)

    return BacktestResult(
        daily=pd.DataFrame(daily_records),
        positions=pd.concat(position_frames, ignore_index=True)
        if position_frames
        else pd.DataFrame(columns=["date", "symbol", "weight"]),
    )


def _target_weights(
    signals: pd.DataFrame,
    mode: str,
    dates: list[pd.Timestamp],
    symbols: list[str],
    top_k: int | None,
    max_leverage: float,
    long_only_weighting: str,
    max_position_weight: float | None,
) -> np.ndarray:
    weights = preprocess_signals(
        signals,
        mode=mode,
        top_k=top_k,
        long_only_weighting=long_only_weighting,
    )
    weights["weight"] = weights["weight"] * max_leverage
    if mode == "longonly" and max_position_weight is not None:
        for _, index in weights.groupby("date", sort=False).groups.items():
            weights.loc[index, "weight"] = _allocate_long_only_with_cap(
                weights.loc[index, "weight"].to_numpy(dtype=float),
                max_position_weight,
                max_leverage,
            )
    weights["date"] = pd.to_datetime(weights["date"])
    return (
        weights.pivot_table(index="date", columns="symbol", values="weight", aggfunc="last")
        .reindex(index=dates, columns=symbols)
        .fillna(0.0)
        .to_numpy(dtype=float)
    )


def _pivot(
    rows: pd.DataFrame,
    value_column: str,
    dates: pd.Index,
    symbols: pd.Index,
) -> pd.DataFrame:
    return (
        rows.pivot_table(
            index="date",
            columns="symbol",
            values=value_column,
            aggfunc="last",
        )
        .reindex(index=dates, columns=symbols)
    )


def _optional_numeric_matrix(
    rows: pd.DataFrame,
    column: str,
    dates: pd.Index,
    symbols: pd.Index,
) -> np.ndarray:
    source = rows[column] if column in rows.columns else np.nan
    numeric_rows = rows.assign(**{column: source})
    matrix = _pivot(numeric_rows, column, dates, symbols)
    return matrix.apply(lambda values: pd.to_numeric(values, errors="coerce")).to_numpy(
        dtype=float
    )


def _finite_number(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _fallback_limit_thresholds(
    market_types: np.ndarray,
    dates: pd.Index,
    *,
    default: float,
) -> np.ndarray:
    thresholds = np.empty_like(market_types, dtype=float)
    for date_index, trading_date in enumerate(dates):
        thresholds[date_index] = [
            fallback_price_limit_threshold(
                market_type,
                pd.Timestamp(trading_date),
                default=default,
            )
            for market_type in market_types[date_index]
        ]
    return thresholds


def _allocate_long_only_with_cap(
    values: np.ndarray,
    max_position_weight: float,
    max_leverage: float,
) -> np.ndarray:
    base = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
    base = np.clip(base, 0.0, None)
    selected = base > 1e-12
    if not selected.any():
        return np.zeros_like(base)

    target_gross = min(float(base.sum()), float(selected.sum()) * max_position_weight)
    if target_gross <= 1e-12:
        return np.zeros_like(base)
    target_gross = min(target_gross, max_leverage)

    selected_base = base[selected]
    lower = 0.0
    upper = max(1.0, target_gross / float(selected_base.min()))
    while float(np.minimum(max_position_weight, upper * selected_base).sum()) < target_gross:
        upper *= 2.0
    for _ in range(80):
        scale = (lower + upper) / 2.0
        allocated = float(np.minimum(max_position_weight, scale * selected_base).sum())
        if allocated < target_gross:
            lower = scale
        else:
            upper = scale

    result = np.zeros_like(base)
    result[selected] = np.minimum(max_position_weight, upper * selected_base)
    return result


def _rescale_gross_exposure(positions: np.ndarray, max_leverage: float) -> np.ndarray:
    gross = float(np.abs(positions).sum())
    if gross <= 1e-12:
        return positions
    return positions * (max_leverage / gross)


def _apply_execution_with_gross_limit(
    previous_positions: np.ndarray,
    executed_change: np.ndarray,
    max_leverage: float,
) -> np.ndarray:
    reducing_change = np.zeros_like(executed_change)
    opposite_direction = (
        (np.abs(previous_positions) > 1e-12)
        & (np.sign(previous_positions) != np.sign(executed_change))
        & (np.abs(executed_change) > 1e-12)
    )
    reducing_change[opposite_direction] = (
        np.sign(executed_change[opposite_direction])
        * np.minimum(
            np.abs(executed_change[opposite_direction]),
            np.abs(previous_positions[opposite_direction]),
        )
    )
    exposure_increasing_change = executed_change - reducing_change
    base_positions = previous_positions + reducing_change
    candidate_positions = base_positions + exposure_increasing_change
    candidate_gross = float(np.abs(candidate_positions).sum())
    if candidate_gross <= max_leverage + 1e-12:
        return candidate_positions

    remaining_capacity = max_leverage - float(np.abs(base_positions).sum())
    if remaining_capacity <= 1e-12:
        return base_positions

    increasing_gross = float(np.abs(exposure_increasing_change).sum())
    if increasing_gross <= 1e-12:
        return base_positions
    scale = min(1.0, remaining_capacity / increasing_gross)
    return base_positions + exposure_increasing_change * scale
