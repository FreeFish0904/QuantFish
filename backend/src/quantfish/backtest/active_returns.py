from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from quantfish.backtest.metrics import TRADING_DAYS_PER_YEAR


@dataclass(frozen=True)
class LongOnlyActiveReturns:
    daily: pd.DataFrame
    beta: float
    observation_count: int
    tracking_error: float
    information_ratio: float


def calculate_long_only_active_returns(
    daily: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    min_observations: int,
    risk_free_rate: float = 0.0,
) -> LongOnlyActiveReturns:
    if min_observations <= 0:
        raise ValueError("min_observations must be positive")
    annual_risk_free_rate = float(risk_free_rate)
    if not math.isfinite(annual_risk_free_rate):
        raise ValueError("risk_free_rate must be finite")
    daily_risk_free_return = annual_risk_free_rate / TRADING_DAYS_PER_YEAR

    strategy = daily.copy()
    if strategy.empty:
        raise ValueError("long-only scoring requires daily strategy returns")
    if "date" not in strategy.columns or "portfolio_return" not in strategy.columns:
        raise ValueError("long-only scoring requires date and portfolio_return columns")
    if benchmark is None or benchmark.empty:
        raise ValueError("long-only scoring requires benchmark observations")
    if "date" not in benchmark.columns or "return" not in benchmark.columns:
        raise ValueError("long-only scoring requires benchmark date and return columns")

    strategy["date"] = pd.to_datetime(strategy["date"]).dt.normalize()
    strategy["portfolio_return"] = pd.to_numeric(
        strategy["portfolio_return"],
        errors="coerce",
    )
    strategy = strategy.sort_values("date").reset_index(drop=True)

    benchmark_rows = benchmark.copy()
    benchmark_rows["date"] = pd.to_datetime(benchmark_rows["date"]).dt.normalize()
    benchmark_rows["return"] = pd.to_numeric(benchmark_rows["return"], errors="coerce")
    benchmark_by_date = (
        benchmark_rows.dropna(subset=["date", "return"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .set_index("date")["return"]
    )

    strategy["benchmark_return"] = strategy["date"].map(benchmark_by_date)
    aligned = strategy.dropna(subset=["portfolio_return", "benchmark_return"]).copy()
    if len(aligned) < min_observations:
        raise ValueError(
            "long-only scoring requires at least "
            f"{min_observations} aligned benchmark observations; got {len(aligned)}"
        )

    strategy_returns = aligned["portfolio_return"].astype(float)
    benchmark_returns = aligned["benchmark_return"].astype(float)
    strategy_excess_returns = strategy_returns - daily_risk_free_return
    benchmark_excess_returns = benchmark_returns - daily_risk_free_return
    benchmark_variance = float(benchmark_excess_returns.var(ddof=1))
    if benchmark_variance <= 0 or not math.isfinite(benchmark_variance):
        raise ValueError("long-only scoring requires non-zero benchmark return variance")

    beta = float(strategy_excess_returns.cov(benchmark_excess_returns) / benchmark_variance)
    if not math.isfinite(beta):
        raise ValueError("long-only scoring produced a non-finite beta")

    active_return = strategy_excess_returns - beta * benchmark_excess_returns
    active_return = active_return.mask(active_return.abs() < 1e-15, 0.0)
    scored = aligned.copy()
    scored["risk_free_return"] = daily_risk_free_return
    scored["active_return"] = active_return.to_numpy(dtype=float)
    scored["scored_daily_return"] = scored["active_return"]

    daily_std = float(active_return.std(ddof=1)) if len(active_return) >= 2 else 0.0
    tracking_error = (
        float(daily_std * math.sqrt(TRADING_DAYS_PER_YEAR))
        if daily_std > 0 and math.isfinite(daily_std)
        else 0.0
    )
    annual_active_return = float(active_return.mean() * TRADING_DAYS_PER_YEAR)
    information_ratio = (
        float(annual_active_return / tracking_error)
        if tracking_error > 0
        else 0.0
    )

    return LongOnlyActiveReturns(
        daily=scored.reset_index(drop=True),
        beta=beta,
        observation_count=len(aligned),
        tracking_error=tracking_error,
        information_ratio=information_ratio,
    )
