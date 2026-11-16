from __future__ import annotations

from dataclasses import dataclass
import math

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
) -> BacktestMetrics:
    daily = result.daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date")
    if return_column not in daily.columns:
        raise ValueError(f"missing return column: {return_column}")
    returns = pd.to_numeric(daily[return_column], errors="coerce").fillna(0.0)

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
        count = int(len(group_rows))
        records.append(
            {
                "group": group,
                "all_return": cumulative,
                "annual_return": _annualize_return(cumulative, count),
                "count": count,
            }
        )
    return pd.DataFrame(records)


def _annualize_return(all_return: float, count: int) -> float:
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
