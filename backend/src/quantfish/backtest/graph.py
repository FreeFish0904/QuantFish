from __future__ import annotations

import math

import pandas as pd

from quantfish.backtest.equity import arithmetic_equity, relative_drawdown_from_equity
from quantfish.backtest.simulator import BacktestResult


def build_backtest_graph_data(
    result: BacktestResult,
    *,
    capital: float = 1.0,
    benchmark: pd.DataFrame | None = None,
    return_column: str | None = None,
) -> dict[str, list[dict]]:
    daily = result.daily.copy()
    daily["date"] = pd.to_datetime(daily["date"])
    daily = daily.sort_values("date")
    graph_return_column = _graph_return_column(daily, return_column)
    returns = _return_series(daily, graph_return_column)
    equity = arithmetic_equity(returns)
    drawdown = relative_drawdown_from_equity(equity)
    benchmark_records, benchmark_returns = _benchmark_records(daily["date"], benchmark, capital)
    active_returns = (
        pd.to_numeric(daily["active_return"], errors="coerce")
        if "active_return" in daily.columns
        else None
    )
    alpha_records = _alpha_records(
        daily["date"],
        returns,
        benchmark_returns,
        capital,
        active_returns=active_returns,
    )
    excess_records = _excess_records(returns, benchmark_returns, capital)

    return {
        "equity": [
            {"date": _date(date), "equity": _json_float(value)}
            for date, value in zip(daily["date"], equity, strict=True)
        ],
        "equity_cny": [
            {"date": _date(date), "equity_cny": _json_float(value * capital)}
            for date, value in zip(daily["date"], equity, strict=True)
        ],
        "drawdown": [
            {"date": _date(date), "drawdown": _json_float(value)}
            for date, value in zip(daily["date"], drawdown, strict=True)
        ],
        "daily_pnl": _daily_pnl_records(daily, capital, graph_return_column),
        "trade_volume": _trade_volume_records(daily, capital),
        "benchmark": benchmark_records,
        "alpha": alpha_records,
        "excess": excess_records,
        "daily_returns": _series_records(
            daily,
            graph_return_column,
            output_column="daily_return",
        ),
        "turnover": _series_records(daily, "turnover"),
        "exposure": _exposure_records(daily),
        "group_cumulative": _group_cumulative_records(result.group_returns),
    }


def _graph_return_column(rows: pd.DataFrame, requested: str | None) -> str:
    if requested is not None:
        if requested not in rows.columns:
            raise ValueError(f"graph return column is missing: {requested}")
        return requested
    return "portfolio_return"


def _return_series(rows: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(rows[column], errors="coerce").fillna(0.0)


def _series_records(
    rows: pd.DataFrame,
    column: str,
    *,
    output_column: str | None = None,
) -> list[dict]:
    if column not in rows.columns:
        return []
    record_column = output_column or column
    return [
        {"date": _date(row["date"]), record_column: _json_float(row[column])}
        for _, row in rows.iterrows()
    ]


def _daily_pnl_records(rows: pd.DataFrame, capital: float, return_column: str) -> list[dict]:
    returns = _return_series(rows, return_column)
    return [
        {
            "date": _date(date),
            "pnl_cny": _json_float(daily_return * capital),
            "daily_return": _json_float(daily_return),
        }
        for date, daily_return in zip(rows["date"], returns, strict=True)
    ]


def _trade_volume_records(rows: pd.DataFrame, capital: float) -> list[dict]:
    buy = _numeric_column(rows, "buy_turnover")
    sell = _numeric_column(rows, "sell_turnover")
    return [
        {
            "date": _date(date),
            "buy_cny": _json_float(buy_turnover * capital),
            "sell_cny": _json_float(sell_turnover * capital),
        }
        for date, buy_turnover, sell_turnover in zip(rows["date"], buy, sell, strict=True)
    ]


def _benchmark_records(
    dates: pd.Series,
    benchmark: pd.DataFrame | None,
    capital: float,
) -> tuple[list[dict], pd.DataFrame]:
    aligned = _aligned_benchmark_returns(dates, benchmark)
    if aligned.empty:
        return [], pd.DataFrame(columns=["strategy_index", "date", "return"])
    equity = arithmetic_equity(aligned["return"])
    records = [
        {
            "date": _date(date),
            "benchmark_return": _json_float(daily_return),
            "benchmark_equity": _json_float(value),
            "benchmark_cny": _json_float(value * capital),
        }
        for date, daily_return, value in zip(
            aligned["date"], aligned["return"], equity, strict=True
        )
    ]
    return records, aligned


def _alpha_records(
    dates: pd.Series,
    strategy_returns: pd.Series,
    benchmark_returns: pd.DataFrame,
    capital: float,
    *,
    active_returns: pd.Series | None = None,
) -> list[dict]:
    if benchmark_returns.empty:
        return []
    strategy = (
        active_returns.reset_index(drop=True)
        if active_returns is not None
        else strategy_returns.reset_index(drop=True)
    )
    aligned_strategy = strategy.iloc[benchmark_returns["strategy_index"].to_numpy()].reset_index(
        drop=True
    )
    if active_returns is not None:
        excess = aligned_strategy.fillna(0.0)
    else:
        excess = aligned_strategy - benchmark_returns["return"].reset_index(drop=True)
    equity = arithmetic_equity(excess)
    return [
        {
            "date": _date(date),
            "alpha_return": _json_float(daily_return),
            "alpha_equity": _json_float(value),
            "alpha_cny": _json_float(value * capital),
        }
        for date, daily_return, value in zip(benchmark_returns["date"], excess, equity, strict=True)
    ]


def _excess_records(
    strategy_returns: pd.Series,
    benchmark_returns: pd.DataFrame,
    capital: float,
) -> list[dict]:
    """Plain ``strategy - benchmark`` curve; never beta-adjusted.

    ``alpha`` keeps its historical beta-adjusted meaning for the equity chart,
    while ``excess`` is the simple difference used by the excess-return table.
    """

    if benchmark_returns.empty:
        return []
    aligned_strategy = (
        strategy_returns.reset_index(drop=True)
        .iloc[benchmark_returns["strategy_index"].to_numpy()]
        .reset_index(drop=True)
    )
    excess = aligned_strategy.fillna(0.0) - benchmark_returns["return"].reset_index(drop=True)
    equity = arithmetic_equity(excess)
    return [
        {
            "date": _date(date),
            "excess_return": _json_float(daily_return),
            "excess_equity": _json_float(value),
            "excess_cny": _json_float(value * capital),
        }
        for date, daily_return, value in zip(benchmark_returns["date"], excess, equity, strict=True)
    ]


def _aligned_benchmark_returns(
    dates: pd.Series,
    benchmark: pd.DataFrame | None,
) -> pd.DataFrame:
    if benchmark is None or benchmark.empty:
        return pd.DataFrame(columns=["strategy_index", "date", "return"])
    rows = benchmark.copy()
    if "date" not in rows.columns or "return" not in rows.columns:
        return pd.DataFrame(columns=["strategy_index", "date", "return"])
    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()
    rows["return"] = pd.to_numeric(rows["return"], errors="coerce")
    rows = rows.dropna(subset=["date", "return"]).sort_values("date")
    by_date = rows.drop_duplicates("date", keep="last").set_index("date")["return"]
    requested = pd.DataFrame(
        {
            "strategy_index": range(len(dates)),
            "date": pd.Series(pd.to_datetime(dates)).dt.normalize(),
        }
    )
    aligned = requested.assign(return_=requested["date"].map(by_date))
    aligned = aligned.dropna(subset=["return_"])
    if aligned.empty:
        return pd.DataFrame(columns=["strategy_index", "date", "return"])
    return (
        aligned.rename(columns={"return_": "return"})
        .loc[:, ["strategy_index", "date", "return"]]
        .reset_index(drop=True)
    )


def _numeric_column(rows: pd.DataFrame, column: str) -> pd.Series:
    if column not in rows.columns:
        return pd.Series([0.0] * len(rows), index=rows.index, dtype=float)
    return pd.to_numeric(rows[column], errors="coerce").fillna(0.0)


def _exposure_records(rows: pd.DataFrame) -> list[dict]:
    columns = [
        "long_exposure",
        "short_exposure",
        "gross_exposure",
        "net_exposure",
        "position_count",
        "stale_position_count",
        "stale_gross_exposure",
    ]
    records = []
    for _, row in rows.iterrows():
        record = {"date": _date(row["date"])}
        for column in columns:
            if column in rows.columns:
                record[column] = _json_float(row[column])
        records.append(record)
    return records


def _group_cumulative_records(group_returns: pd.DataFrame) -> list[dict]:
    if group_returns.empty:
        return []
    rows = group_returns.copy()
    rows["date"] = pd.to_datetime(rows["date"])
    rows["return"] = pd.to_numeric(rows["return"], errors="coerce").fillna(0.0)
    rows = rows.sort_values(["group", "date"])
    records = []
    for group, group_rows in rows.groupby("group", sort=True):
        cumulative = group_rows["return"].cumsum()
        for date, value in zip(group_rows["date"], cumulative, strict=True):
            records.append(
                {
                    "date": _date(date),
                    "group": group,
                    "cumulative_return": _json_float(value),
                }
            )
    return records


def _date(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _json_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
