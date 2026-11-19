from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from quantfish.backtest.equity import arithmetic_equity, relative_drawdown_from_equity
from quantfish.backtest.metrics import TRADING_DAYS_PER_YEAR

HS300_BENCHMARK_LABEL = "hs300"
MIN_EXCESS_OBSERVATIONS = 20


@dataclass(frozen=True)
class BenchmarkRelativeMetrics:
    """Strategy vs benchmark ("excess return") block reported next to the run.

    All return fields use the *raw portfolio* returns on the days that have a
    benchmark observation, so ``strategy_*``, ``benchmark_*`` and ``excess_*``
    always describe the same window and add up: ``excess = strategy - benchmark``.

    The ``active_*`` block in :mod:`quantfish.backtest.active_returns` is a
    different (beta-adjusted) scoring basis and is deliberately *not* reused
    here. See ``docs/metrics-definitions.md``.
    """

    benchmark: str
    observations: int
    start: str
    end: str
    strategy_total_return: float
    strategy_annual_return: float
    benchmark_total_return: float
    benchmark_annual_return: float
    benchmark_cagr: float | None
    excess_total_return: float
    excess_annual_return: float
    excess_compounded_return: float | None
    excess_cagr: float | None
    excess_max_drawdown: float
    excess_win_rate: float
    excess_volatility: float
    excess_information_ratio: float | None
    excess_beta: float | None

    def summary_fields(self) -> dict[str, float | int]:
        """Flat ``summary.csv`` columns for this block."""

        return {
            "strategy_total_return": self.strategy_total_return,
            "strategy_annual_return": self.strategy_annual_return,
            "benchmark_total_return": self.benchmark_total_return,
            "benchmark_annual_return": self.benchmark_annual_return,
            "benchmark_cagr": self.benchmark_cagr,
            "excess_total_return": self.excess_total_return,
            "excess_annual_return": self.excess_annual_return,
            "excess_compounded_return": self.excess_compounded_return,
            "excess_cagr": self.excess_cagr,
            "excess_max_drawdown": self.excess_max_drawdown,
            "excess_win_rate": self.excess_win_rate,
            "excess_volatility": self.excess_volatility,
            "excess_information_ratio": self.excess_information_ratio,
            "excess_beta": self.excess_beta,
            "excess_observations": self.observations,
        }


def calculate_benchmark_relative_metrics(
    daily: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    return_column: str = "portfolio_return",
    min_observations: int = MIN_EXCESS_OBSERVATIONS,
    benchmark_label: str = HS300_BENCHMARK_LABEL,
) -> BenchmarkRelativeMetrics:
    """Summarize raw portfolio returns against the benchmark on aligned days.

    Raises ``ValueError`` when there is nothing to compare (no benchmark rows,
    no overlap with the strategy dates, or fewer than ``min_observations``
    aligned days). Callers that only *report* these numbers should treat that
    as "not available" instead of failing the whole backtest.
    """

    if min_observations <= 0:
        raise ValueError("min_observations must be positive")

    strategy = daily.copy()
    if strategy.empty:
        raise ValueError("benchmark-relative metrics require daily strategy returns")
    if "date" not in strategy.columns or return_column not in strategy.columns:
        raise ValueError(
            f"benchmark-relative metrics require date and {return_column} columns"
        )
    if benchmark is None or benchmark.empty:
        raise ValueError("benchmark-relative metrics require benchmark observations")
    if "date" not in benchmark.columns or "return" not in benchmark.columns:
        raise ValueError(
            "benchmark-relative metrics require benchmark date and return columns"
        )

    strategy["date"] = pd.to_datetime(strategy["date"]).dt.normalize()
    strategy[return_column] = pd.to_numeric(strategy[return_column], errors="coerce")
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
    aligned = strategy.dropna(subset=[return_column, "benchmark_return"])
    if len(aligned) < min_observations:
        raise ValueError(
            "benchmark-relative metrics require at least "
            f"{min_observations} aligned benchmark observations; got {len(aligned)}"
        )

    strategy_returns = aligned[return_column].astype(float)
    benchmark_returns = aligned["benchmark_return"].astype(float)
    excess_returns = strategy_returns - benchmark_returns
    count = len(aligned)

    strategy_total_return = float(strategy_returns.sum())
    benchmark_total_return = float(benchmark_returns.sum())
    excess_total_return = float(excess_returns.sum())
    excess_volatility = _annualized_volatility(excess_returns)
    excess_annual_return = _annualize_return(excess_total_return, count)

    return BenchmarkRelativeMetrics(
        benchmark=benchmark_label,
        observations=count,
        start=_date(aligned["date"].iloc[0]),
        end=_date(aligned["date"].iloc[-1]),
        strategy_total_return=strategy_total_return,
        strategy_annual_return=_annualize_return(strategy_total_return, count),
        benchmark_total_return=benchmark_total_return,
        benchmark_annual_return=_annualize_return(benchmark_total_return, count),
        benchmark_cagr=_cagr(benchmark_returns),
        excess_total_return=excess_total_return,
        excess_annual_return=excess_annual_return,
        excess_compounded_return=_excess_compounded_return(
            strategy_returns, benchmark_returns
        ),
        excess_cagr=_excess_cagr(strategy_returns, benchmark_returns),
        excess_max_drawdown=_max_drawdown(excess_returns),
        excess_win_rate=float((excess_returns > 0).mean()),
        excess_volatility=excess_volatility,
        excess_information_ratio=(
            _safe_float(excess_annual_return / excess_volatility)
            if excess_volatility > 0
            else None
        ),
        excess_beta=_beta(strategy_returns, benchmark_returns),
    )


def _annualize_return(all_return: float, count: int) -> float:
    """Arithmetic annualization kept identical to ``metrics.annual_return``."""

    if count <= 0:
        return 0.0
    return float(all_return * TRADING_DAYS_PER_YEAR / count)


def _compounded_equity(returns: pd.Series) -> pd.Series | None:
    if returns.empty:
        return None
    growth = 1.0 + returns
    if bool((growth <= 0).any()):
        return None
    return growth.cumprod()


def _cagr(returns: pd.Series) -> float | None:
    equity = _compounded_equity(returns)
    if equity is None or equity.empty:
        return None
    ending_value = float(equity.iloc[-1])
    if ending_value <= 0 or not math.isfinite(ending_value):
        return None
    return _safe_float(ending_value ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1.0)


def _excess_compounded_return(
    strategy_returns: pd.Series, benchmark_returns: pd.Series
) -> float | None:
    """``(1 + S) / (1 + B) - 1`` on compounded net values."""

    strategy_equity = _compounded_equity(strategy_returns)
    benchmark_equity = _compounded_equity(benchmark_returns)
    if strategy_equity is None or benchmark_equity is None:
        return None
    if strategy_equity.empty or benchmark_equity.empty:
        return None
    benchmark_ending = float(benchmark_equity.iloc[-1])
    if benchmark_ending <= 0 or not math.isfinite(benchmark_ending):
        return None
    return _safe_float(float(strategy_equity.iloc[-1]) / benchmark_ending - 1.0)


def _excess_cagr(
    strategy_returns: pd.Series, benchmark_returns: pd.Series
) -> float | None:
    relative = _excess_compounded_return(strategy_returns, benchmark_returns)
    if relative is None:
        return None
    growth = 1.0 + relative
    if growth <= 0 or not math.isfinite(growth):
        return None
    return _safe_float(growth ** (TRADING_DAYS_PER_YEAR / len(strategy_returns)) - 1.0)


def _max_drawdown(excess_returns: pd.Series) -> float:
    """Largest peak-to-trough drop of the arithmetic excess equity curve."""

    if excess_returns.empty:
        return 0.0
    drawdown = relative_drawdown_from_equity(arithmetic_equity(excess_returns))
    if drawdown.empty:
        return 0.0
    value = abs(float(drawdown.min()))
    return value if math.isfinite(value) else 0.0


def _annualized_volatility(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if not math.isfinite(std):
        return 0.0
    return float(std * math.sqrt(TRADING_DAYS_PER_YEAR))


def _beta(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float | None:
    """Regression beta of strategy returns on benchmark returns."""

    if len(strategy_returns) < 2:
        return None
    if benchmark_returns.nunique() <= 1:
        # A flat benchmark has no beta; float noise must not turn this into 0.0.
        return None
    variance = float(benchmark_returns.var(ddof=1))
    if variance <= 0 or not math.isfinite(variance):
        return None
    covariance = float(strategy_returns.cov(benchmark_returns))
    if not math.isfinite(covariance):
        return None
    return _safe_float(covariance / variance)


def _safe_float(value: float | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _date(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")
