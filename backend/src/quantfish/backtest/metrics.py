from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from quantfish.backtest.equity import arithmetic_equity, relative_drawdown_from_equity
from quantfish.backtest.simulator import BacktestResult

TRADING_DAYS_PER_YEAR = 252
PERFORMANCE_TABLE_COLUMNS = [
    "period",
    "long",
    "short",
    "long_count",
    "short_count",
    "sharpe",
    "total_return",
    "annualized_return",
    "turnover",
    "drawdown",
    "fitness",
    "calmar",
]


@dataclass(frozen=True)
class BacktestMetrics:
    summary: dict[str, float | None]
    group_returns: pd.DataFrame


def calculate_backtest_metrics(
    result: BacktestResult,
    *,
    return_column: str = "portfolio_return",
    risk_free_daily_return: float = 0.0,
) -> BacktestMetrics:
    """Summarize one backtest.

    ``all_return``/``annual_return``/``max_drawdown``/``calmar`` keep the
    arithmetic ("simple summed return") convention the scoring config was tuned
    on. The ``compounded_*``, ``cagr``, ``volatility``, ``sortino`` and
    ``t_stat`` fields next to them describe the same run geometrically so the
    report can be read the way external platforms report performance. See
    ``docs/metrics-definitions.md``.
    """

    daily = result.daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date")
    if return_column not in daily.columns:
        raise ValueError(f"missing return column: {return_column}")
    returns = pd.to_numeric(daily[return_column], errors="coerce").fillna(0.0)
    risk_free_daily_return = _finite_float_or_zero(risk_free_daily_return)

    equity = arithmetic_equity(returns)
    all_return = float(returns.sum()) if not returns.empty else 0.0
    annual_return = _annualize_return(all_return, len(returns))
    sharpe = _sharpe(returns)
    drawdown = relative_drawdown_from_equity(equity)
    max_drawdown = abs(float(drawdown.min())) if not drawdown.empty else 0.0
    average_turnover = _mean(daily, "turnover")
    year_returns = _calendar_year_returns(daily, returns)
    long_total_return = _sum(daily, "long_return")
    short_total_return = _sum(daily, "short_return")
    annualized_short_profit = max(_annualize_return(short_total_return, len(returns)), 0.0)

    summary = {
        "all_return": all_return,
        "annual_return": annual_return,
        "average_year_return": _mean_series(year_returns),
        "worst_year_return": float(year_returns.min()) if not year_returns.empty else 0.0,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "average_turnover": average_turnover,
        "long_total_return": long_total_return,
        "short_total_return": short_total_return,
        "annualized_short_profit": annualized_short_profit,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "average_long_exposure": _mean(daily, "long_exposure"),
        "average_short_exposure": _mean(daily, "short_exposure"),
        "average_gross_exposure": _mean(daily, "gross_exposure"),
        "average_net_exposure": _mean(daily, "net_exposure"),
        "average_position_count": _mean(daily, "position_count"),
        "stale_position_days": _positive_count(daily, "stale_position_count"),
        "max_stale_gross_exposure": _max(daily, "stale_gross_exposure"),
        "average_stale_gross_exposure": _mean(daily, "stale_gross_exposure"),
        "terminal_stale_position_count": int(_last(daily, "stale_position_count")),
        "terminal_stale_gross_exposure": _last(daily, "stale_gross_exposure"),
        "calmar": annual_return / max_drawdown if max_drawdown > 0 else None,
        "fitness": _fitness(sharpe, annual_return, average_turnover),
        **_compounded_metrics(returns, risk_free_daily_return),
    }

    return BacktestMetrics(
        summary=summary,
        group_returns=_summarize_group_returns(result.group_returns),
    )


def build_yearly_performance_table(
    result: BacktestResult,
    *,
    return_column: str = "portfolio_return",
) -> pd.DataFrame:
    daily = result.daily.copy()
    if daily.empty or "date" not in daily.columns:
        return pd.DataFrame(columns=PERFORMANCE_TABLE_COLUMNS)

    daily["date"] = pd.to_datetime(daily["date"]).dt.normalize()
    daily = daily.sort_values("date").reset_index(drop=True)
    daily["portfolio_return"] = pd.to_numeric(
        daily.get(return_column, 0.0),
        errors="coerce",
    ).fillna(0.0)
    daily["turnover"] = pd.to_numeric(daily.get("turnover", 0.0), errors="coerce").fillna(0.0)
    daily["year"] = daily["date"].dt.year

    exposures = _daily_position_exposures(result.positions, daily["date"])
    exposures["year"] = exposures["date"].dt.year

    records = []
    for year, year_daily in daily.groupby("year", sort=True):
        year_exposures = exposures[exposures["year"] == year]
        returns = year_daily["portfolio_return"]
        turnover = float(year_daily["turnover"].mean()) if not year_daily.empty else 0.0
        total_return = float(returns.sum())
        annualized_return = _annualize_return(total_return, len(returns))
        drawdown = _relative_drawdown(returns)
        sharpe = _legacy_sharpe(returns)
        records.append(
            _performance_record(
                period=str(year),
                exposures=year_exposures,
                sharpe=sharpe,
                total_return=total_return,
                annualized_return=annualized_return,
                turnover=turnover,
                drawdown=drawdown,
            )
        )

    all_returns = daily["portfolio_return"]
    all_turnover = float(daily["turnover"].mean()) if not daily.empty else 0.0
    all_total_return = float(all_returns.sum()) if not daily.empty else 0.0
    all_annualized_return = _annualize_return(all_total_return, len(all_returns))
    records.append(
        _performance_record(
            period="all",
            exposures=exposures,
            sharpe=_legacy_sharpe(all_returns),
            total_return=all_total_return,
            annualized_return=all_annualized_return,
            turnover=all_turnover,
            drawdown=_relative_drawdown(all_returns),
        )
    )
    return pd.DataFrame(records, columns=PERFORMANCE_TABLE_COLUMNS)


def _daily_position_exposures(positions: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"date": pd.to_datetime(dates).dt.normalize()}).drop_duplicates()
    if positions.empty or "date" not in positions.columns or "weight" not in positions.columns:
        return frame.assign(long=0.0, short=0.0, long_count=0, short_count=0)

    rows = positions.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()
    rows["weight"] = pd.to_numeric(rows["weight"], errors="coerce").fillna(0.0)
    by_date = rows.groupby("date")["weight"].agg(
        long=lambda values: float(values[values > 0].sum()),
        short=lambda values: float(values[values < 0].sum()),
        long_count=lambda values: int((values > 0).sum()),
        short_count=lambda values: int((values < 0).sum()),
    )
    merged = frame.merge(by_date.reset_index(), on="date", how="left")
    return merged.fillna(
        {
            "long": 0.0,
            "short": 0.0,
            "long_count": 0,
            "short_count": 0,
        }
    )


def _performance_record(
    *,
    period: str,
    exposures: pd.DataFrame,
    sharpe: float | None,
    total_return: float,
    annualized_return: float,
    turnover: float,
    drawdown: float,
) -> dict[str, float | int | str | None]:
    return {
        "period": period,
        "long": _safe_float(_mean(exposures, "long")),
        "short": _safe_float(_mean(exposures, "short")),
        "long_count": _mean_count(exposures, "long_count"),
        "short_count": _mean_count(exposures, "short_count"),
        "sharpe": _safe_float(sharpe),
        "total_return": _safe_float(total_return),
        "annualized_return": _safe_float(annualized_return),
        "turnover": _safe_float(turnover),
        "drawdown": _safe_float(drawdown),
        "fitness": _safe_float(_legacy_fitness(sharpe, annualized_return, turnover)),
        "calmar": _safe_float(_legacy_calmar(annualized_return, drawdown)),
    }


def _legacy_sharpe(returns: pd.Series) -> float | None:
    if len(returns) < 2:
        return None
    std = float(returns.std(ddof=1))
    if std <= 0 or not math.isfinite(std):
        return None
    return float(returns.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))


def _relative_drawdown(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    equity = arithmetic_equity(returns)
    drawdown = relative_drawdown_from_equity(equity)
    return abs(float(drawdown.min())) if not drawdown.empty else 0.0


def _legacy_fitness(sharpe: float | None, annual_ret: float, turnover: float) -> float | None:
    if sharpe is None or turnover <= 0:
        return None
    return float(sharpe * math.sqrt(abs(annual_ret) / turnover))


def _legacy_calmar(annual_ret: float, drawdown: float) -> float | None:
    if drawdown <= 0:
        return None
    return float(annual_ret / drawdown)


def _mean_count(rows: pd.DataFrame, column: str) -> int:
    if column not in rows.columns or rows.empty:
        return 0
    return int(pd.to_numeric(rows[column], errors="coerce").fillna(0).mean())


def _safe_float(value: float | None) -> float | None:
    if value is None:
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _summarize_group_returns(group_returns: pd.DataFrame) -> pd.DataFrame:
    if group_returns.empty:
        return pd.DataFrame(columns=["group", "all_return", "annual_return", "count"])

    rows = group_returns.copy()
    rows["return"] = pd.to_numeric(rows["return"], errors="coerce").fillna(0.0)
    records = []
    for group, group_rows in rows.groupby("group", sort=True):
        cumulative = float(group_rows["return"].sum())
        count = len(group_rows)
        records.append(
            {
                "group": group,
                "all_return": cumulative,
                "annual_return": _annualize_return(cumulative, count),
                "count": count,
            }
        )
    return pd.DataFrame(records)


def _compounded_metrics(
    returns: pd.Series, risk_free_daily_return: float
) -> dict[str, float | None]:
    """Geometric-basis metrics reported next to the arithmetic scoring basis."""

    cagr = _cagr(returns)
    compounded_max_drawdown = _compounded_max_drawdown(returns)
    t_stat = _t_stat(returns)
    calmar = None
    if cagr is not None and compounded_max_drawdown and compounded_max_drawdown > 0:
        calmar = cagr / compounded_max_drawdown
    return {
        "compounded_total_return": _compounded_total_return(returns),
        "cagr": cagr,
        "compounded_max_drawdown": compounded_max_drawdown,
        "compounded_calmar": _safe_float(calmar),
        "volatility": _annualized_volatility(returns),
        "sortino": _sortino(returns, risk_free_daily_return),
        "t_stat": t_stat,
        "t_stat_p_value": _normal_two_sided_p(t_stat),
    }


def _compounded_equity(returns: pd.Series) -> pd.Series | None:
    """Compounded net value series, or ``None`` when a day wipes out capital."""

    if returns.empty:
        return pd.Series(dtype=float)
    growth = 1.0 + returns
    if bool((growth <= 0).any()):
        return None
    return growth.cumprod()


def _compounded_total_return(returns: pd.Series) -> float | None:
    equity = _compounded_equity(returns)
    if equity is None:
        return None
    if equity.empty:
        return 0.0
    return _safe_float(float(equity.iloc[-1]) - 1.0)


def _cagr(returns: pd.Series) -> float | None:
    """Compound annual growth rate: ``equity ** (252 / n) - 1``."""

    equity = _compounded_equity(returns)
    if equity is None:
        return None
    count = len(returns)
    if count <= 0:
        return 0.0
    ending_value = float(equity.iloc[-1])
    if ending_value <= 0 or not math.isfinite(ending_value):
        return None
    return _safe_float(ending_value ** (TRADING_DAYS_PER_YEAR / count) - 1.0)


def _compounded_max_drawdown(returns: pd.Series) -> float | None:
    equity = _compounded_equity(returns)
    if equity is None:
        return None
    series = pd.concat(
        [pd.Series([1.0]), equity.reset_index(drop=True)], ignore_index=True
    )
    return abs(float(relative_drawdown_from_equity(series).min()))


def _annualized_volatility(returns: pd.Series) -> float | None:
    if len(returns) < 2:
        return None
    std = float(returns.std(ddof=1))
    if not math.isfinite(std):
        return None
    return _safe_float(math.sqrt(TRADING_DAYS_PER_YEAR) * std)


def _sortino(returns: pd.Series, risk_free_daily_return: float) -> float | None:
    """Annualized Sortino ratio using the daily risk-free rate as the MAR.

    Downside deviation is the root mean square of the negative excess returns
    over *all* observations (a zero-return day is not a downside day but it does
    dilute the deviation). A strategy with no downside observation has no
    finite Sortino, so ``None`` is reported instead of an infinite ratio.
    """

    if len(returns) < 2:
        return None
    excess = returns - risk_free_daily_return
    downside = excess.clip(upper=0.0)
    downside_deviation = math.sqrt(float((downside**2).mean()))
    if downside_deviation <= 0 or not math.isfinite(downside_deviation):
        return None
    ratio = math.sqrt(TRADING_DAYS_PER_YEAR) * float(excess.mean()) / downside_deviation
    return _safe_float(ratio)


def _t_stat(returns: pd.Series) -> float | None:
    """Student t-statistic of the mean daily return (unadjusted for autocorrelation)."""

    if len(returns) < 2:
        return None
    std = float(returns.std(ddof=1))
    if std <= 0 or not math.isfinite(std):
        return None
    return _safe_float(float(returns.mean()) / std * math.sqrt(len(returns)))


def _normal_two_sided_p(statistic: float | None) -> float | None:
    """Two-sided p-value via the normal approximation (``erfc`` of |t| / sqrt 2)."""

    if statistic is None:
        return None
    return _safe_float(math.erfc(abs(statistic) / math.sqrt(2.0)))


def _finite_float_or_zero(value: float | None) -> float:
    if value is None:
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _annualize_return(all_return: float, count: int) -> float:
    """Arithmetic annualization (``return * 252 / n``) kept for scoring parity."""

    if count <= 0:
        return 0.0
    return float(all_return * TRADING_DAYS_PER_YEAR / count)


def _sharpe(returns: pd.Series) -> float:
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0 or not math.isfinite(std):
        return 0.0
    return float(math.sqrt(TRADING_DAYS_PER_YEAR) * returns.mean() / std)


def calculate_sharpe(returns: pd.Series) -> float:
    cleaned = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    return _sharpe(cleaned)


def _mean(rows: pd.DataFrame, column: str) -> float:
    if column not in rows.columns or rows.empty:
        return 0.0
    return float(pd.to_numeric(rows[column], errors="coerce").fillna(0.0).mean())


def _max(rows: pd.DataFrame, column: str) -> float:
    if column not in rows.columns or rows.empty:
        return 0.0
    values = pd.to_numeric(rows[column], errors="coerce").fillna(0.0)
    return float(values.max()) if not values.empty else 0.0


def _last(rows: pd.DataFrame, column: str) -> float:
    if column not in rows.columns or rows.empty:
        return 0.0
    values = pd.to_numeric(rows[column], errors="coerce").fillna(0.0)
    return float(values.iloc[-1]) if not values.empty else 0.0


def _positive_count(rows: pd.DataFrame, column: str) -> int:
    if column not in rows.columns or rows.empty:
        return 0
    values = pd.to_numeric(rows[column], errors="coerce").fillna(0.0)
    return int((values > 0).sum())


def _sum(rows: pd.DataFrame, column: str) -> float:
    if column not in rows.columns or rows.empty:
        return 0.0
    return float(pd.to_numeric(rows[column], errors="coerce").fillna(0.0).sum())


def _mean_series(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    return float(pd.to_numeric(values, errors="coerce").fillna(0.0).mean())


def _calendar_year_returns(daily: pd.DataFrame, returns: pd.Series) -> pd.Series:
    if daily.empty:
        return pd.Series(dtype=float)
    years = pd.to_datetime(daily["date"]).dt.year
    frame = pd.DataFrame({"year": years, "portfolio_return": returns})
    return frame.groupby("year", sort=True)["portfolio_return"].apply(lambda values: float(values.sum()))


def _fitness(sharpe: float, annual_return: float, average_turnover: float) -> float:
    denominator = max(average_turnover, 0.125)
    return float(sharpe * math.sqrt(abs(annual_return) / denominator))
