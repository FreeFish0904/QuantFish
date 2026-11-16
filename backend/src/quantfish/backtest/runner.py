from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from quantfish.backtest.active_returns import calculate_long_only_active_returns
from quantfish.backtest.benchmark import HS300_DATASET, load_hs300_benchmark
from quantfish.backtest.graph import build_backtest_graph_data
from quantfish.backtest.metrics import (
    TRADING_DAYS_PER_YEAR,
    build_yearly_performance_table,
    calculate_backtest_metrics,
    calculate_sharpe,
)
from quantfish.backtest.industry_neutralization import (
    DEFAULT_INDUSTRY_DATASET,
    disabled_summary,
    industry_column_for,
    neutralize_scores_by_industry,
)
from quantfish.backtest.panel import BacktestPanel
from quantfish.backtest.panel_cache import load_or_build_backtest_panel
from quantfish.backtest.price_limits import fallback_price_limit_threshold
from quantfish.backtest.simulator import BacktestResult, simulate_backtest
from quantfish.data import DataBundle
from quantfish.data.scoring_datasets import (
    ADJ_FACTOR_DATASET,
    COMPANY_INFO_DATASET,
    RETURNS_DATASET,
)
from quantfish.factor_execution import StrategyExecutionConfig, execute_student_strategy
from quantfish.stock_codes import normalize_stock_code
from quantfish.market_types import (
    DEFAULT_ALLOWED_MARKET_TYPES,
    normalize_allowed_market_types,
)

def run_student_backtest(
    strategy_path: Path | str, data_root: Path | str, config: Any
) -> BacktestResult:
    backtest_config = _config_section(config, "backtest")
    platform_execution = _config_section(config, "execution")
    allowed_market_types = _allowed_market_types(platform_execution)
    _validate_backtest_config(backtest_config)
    data_start = pd.Timestamp(
        _config_value(
            backtest_config,
            "data_start",
            _config_value(backtest_config, "scoring_start"),
        )
    ).normalize()
    scoring_start = pd.Timestamp(
        _config_value(backtest_config, "scoring_start", data_start)
    ).normalize()
    scoring_end = pd.Timestamp(_config_value(backtest_config, "scoring_end")).normalize()
    execution_config = StrategyExecutionConfig(
        data_start=data_start,
        scoring_end=scoring_end,
        canonical_panel=_config_value(backtest_config, "canonical_panel", RETURNS_DATASET),
        allowed_market_types=allowed_market_types,
    )
    bundle = DataBundle(data_root, allowed_market_types=allowed_market_types)
    industry_neutralization_enabled = bool(
        _config_value(backtest_config, "industry_neutralization", False)
    )
    _validate_industry_neutralization_source(bundle, industry_neutralization_enabled)
    execution = execute_student_strategy(strategy_path, data_root, execution_config)

    panel, panel_cache_status = _load_backtest_panel(
        bundle,
        data_start,
        scoring_end,
    )
    scores = _filter_scores_to_panel(execution.scores, panel)
    # Keep the historical fallback for callers that pass a partial plain dict.
    # PlatformConfig and config/platform.yaml now explicitly default to long-only.
    mode = "longonly" if _config_value(platform_execution, "long_only", False) else "longshort"
    universe_summary: dict[str, Any] | None = None
    if mode == "longonly":
        scores, universe_summary = _filter_investable_universe(
            bundle,
            panel,
            scores,
            min_listing_days=int(
                _config_value(platform_execution, "min_listing_days", 60)
            ),
        )
    scores_for_backtest, industry_summary = _maybe_neutralize_scores(
        bundle,
        scores,
        industry_neutralization_enabled,
    )
    capital = float(_config_value(backtest_config, "capital", 1_000_000))
    if mode == "longonly":
        simulation_top_k = int(
            _config_value(platform_execution, "long_only_target_count", 50)
        )
    else:
        simulation_top_k = _config_value(platform_execution, "top_k", None)
    simulated = simulate_backtest(
        panel,
        scores_for_backtest.rename(columns={"code": "symbol", "score": "signal"}),
        capital=capital,
        mode=mode,
        commission_rate=float(_config_value(platform_execution, "commission_rate", 0.0)),
        slippage_rate=float(_config_value(platform_execution, "slippage_rate", 0.0)),
        sell_stamp_duty_rate=float(
            _config_value(platform_execution, "sell_stamp_duty_rate", 0.0)
        ),
        max_leverage=float(_config_value(platform_execution, "max_leverage", 1.0)),
        top_k=simulation_top_k,
        long_only_weighting=str(
            _config_value(platform_execution, "long_only_weighting", "rank_equal")
        ),
        max_position_weight=(
            float(_config_value(platform_execution, "max_position_weight", 0.05))
            if mode == "longonly"
            else None
        ),
        max_participation_rate=(
            float(_config_value(platform_execution, "max_participation_rate", 0.10))
            if mode == "longonly"
            else 1.0
        ),
        terminal_stale_position_policy=str(
            _config_value(
                platform_execution,
                "terminal_stale_position_policy",
                "reject",
            )
        ),
    )
    group_returns = _calculate_group_returns(
        panel,
        scores_for_backtest,
        int(_config_value(backtest_config, "group_count", 5)),
    )
    scoring_result = _scoring_result(simulated, group_returns, scoring_start, scoring_end)
    benchmark = load_hs300_benchmark(bundle, scoring_start, scoring_end)
    risk_free_rate = float(
        _config_value(backtest_config, "long_only_risk_free_rate", 0.0175)
    )
    risk_free_daily_return = risk_free_rate / TRADING_DAYS_PER_YEAR
    raw_metrics = calculate_backtest_metrics(
        scoring_result,
        risk_free_daily_return=risk_free_daily_return,
    )
    metrics = raw_metrics
    scoring_return_column = "portfolio_return"
    active_scoring_summary: dict[str, Any] = {}
    long_only_benchmark_name: str | None = None
    long_only_scoring_basis: str | None = None
    if mode == "longonly":
        long_only_benchmark_name = str(
            _config_value(backtest_config, "long_only_benchmark", "hs300")
        )
        if long_only_benchmark_name not in {"hs300", "none"}:
            raise ValueError(
                f"unsupported long_only_benchmark: {long_only_benchmark_name}"
            )
        if long_only_benchmark_name == "hs300":
            active = calculate_long_only_active_returns(
                scoring_result.daily,
                benchmark,
                min_observations=int(
                    _config_value(
                        backtest_config,
                        "long_only_min_beta_observations",
                        20,
                    )
                ),
                risk_free_rate=risk_free_rate,
            )
            raw_excess_returns = (
                pd.to_numeric(scoring_result.daily["portfolio_return"], errors="coerce")
                .fillna(0.0)
                .sub(risk_free_daily_return)
            )
            scoring_result = BacktestResult(
                daily=active.daily,
                positions=scoring_result.positions,
                group_returns=scoring_result.group_returns,
            )
            scoring_return_column = "scored_daily_return"
            metrics = calculate_backtest_metrics(
                scoring_result,
                return_column=scoring_return_column,
                risk_free_daily_return=risk_free_daily_return,
            )
            long_only_scoring_basis = "beta_adjusted_active_return"
            active_scoring_summary = {
                "beta": active.beta,
                "tracking_error": active.tracking_error,
                "information_ratio": active.information_ratio,
                "active_observations": active.observation_count,
                "risk_free_rate": risk_free_rate,
                "risk_free_daily_return": risk_free_daily_return,
                "active_total_return": metrics.summary["all_return"],
                "active_annual_return": metrics.summary["annual_return"],
                "active_max_drawdown": metrics.summary["max_drawdown"],
                "active_calmar": metrics.summary["calmar"],
                "raw_total_return": raw_metrics.summary["all_return"],
                "raw_sharpe": calculate_sharpe(raw_excess_returns),
                "raw_max_drawdown": raw_metrics.summary["max_drawdown"],
                "raw_calmar": raw_metrics.summary["calmar"],
            }
        else:
            long_only_scoring_basis = "portfolio_return"
            active_scoring_summary = {
                "raw_total_return": raw_metrics.summary["all_return"],
                "raw_sharpe": raw_metrics.summary["sharpe"],
                "raw_max_drawdown": raw_metrics.summary["max_drawdown"],
                "raw_calmar": raw_metrics.summary["calmar"],
            }
    else:
        active_scoring_summary = {
            "raw_total_return": raw_metrics.summary["all_return"],
            "raw_sharpe": raw_metrics.summary["sharpe"],
            "raw_max_drawdown": raw_metrics.summary["max_drawdown"],
            "raw_calmar": raw_metrics.summary["calmar"],
        }

    daily_returns = _public_daily_returns(
        scoring_result.daily,
        return_column=scoring_return_column,
    )
    net_value = daily_returns.assign(
        net_value=lambda df: 1.0 + df["daily_return"].cumsum()
    ).loc[:, ["date", "net_value"]]
    turnover = scoring_result.daily.loc[:, ["date", "turnover"]].copy()
    group_daily_returns = scoring_result.group_returns.rename(
        columns={"return": "daily_return"}
    )
    performance_by_year = build_yearly_performance_table(
        scoring_result,
        return_column=scoring_return_column,
    )
    summary = _summary_frame(metrics, daily_returns)
    for key, value in active_scoring_summary.items():
        summary.loc[0, key] = value
    graph_data = build_backtest_graph_data(
        scoring_result,
        capital=capital,
        benchmark=benchmark,
    )
    diagnostics = {
        **execution.diagnostics,
        "capital": _config_value(backtest_config, "capital", None),
        "group_count": int(_config_value(backtest_config, "group_count", 5)),
        "execution_mode": mode,
        "commission_rate": _config_value(platform_execution, "commission_rate", 0.0),
        "slippage_rate": _config_value(platform_execution, "slippage_rate", 0.0),
        "sell_stamp_duty_rate": _config_value(
            platform_execution,
            "sell_stamp_duty_rate",
            0.0,
        ),
        "max_leverage": _config_value(platform_execution, "max_leverage", 1.0),
        "top_k": simulation_top_k,
        "long_only_weighting": _config_value(
            platform_execution,
            "long_only_weighting",
            "rank_equal",
        ),
        "long_only_target_count": _config_value(
            platform_execution,
            "long_only_target_count",
            50,
        ),
        "max_position_weight": _config_value(
            platform_execution,
            "max_position_weight",
            0.05,
        ),
        "max_participation_rate": _config_value(
            platform_execution,
            "max_participation_rate",
            0.10,
        ),
        "min_listing_days": _config_value(platform_execution, "min_listing_days", 60),
        "terminal_stale_position_policy": _config_value(
            platform_execution,
            "terminal_stale_position_policy",
            "reject",
        ),
        "allowed_market_types": _allowed_market_type_list(allowed_market_types),
        "panel_cache": panel_cache_status,
        "stale_positions": _stale_position_diagnostics(metrics.summary),
        "industry_neutralization": industry_summary.to_dict(),
        "investable_universe": universe_summary,
        "long_only_universe": universe_summary if mode == "longonly" else None,
        "long_only_scoring": (
            {
                "benchmark": long_only_benchmark_name,
                "benchmark_available": not benchmark.empty,
                "scoring_basis": long_only_scoring_basis,
                **(
                    {
                        "min_beta_observations": _config_value(
                            backtest_config,
                            "long_only_min_beta_observations",
                            20,
                        )
                    }
                    if long_only_benchmark_name == "hs300"
                    else {}
                ),
                **{
                    key: active_scoring_summary[key]
                    for key in [
                        "beta",
                        "tracking_error",
                        "information_ratio",
                        "active_observations",
                        "risk_free_rate",
                        "risk_free_daily_return",
                    ]
                    if key in active_scoring_summary
                },
            }
            if mode == "longonly"
            else None
        ),
        "price_policy": "front_adjusted",
        "data_start": data_start.date().isoformat(),
        "scoring_start": scoring_start.date().isoformat(),
        "scoring_end": scoring_end.date().isoformat(),
        "scoring_dates": [
            pd.Timestamp(date).date().isoformat()
            for date in scoring_result.daily["date"].tolist()
        ],
        "price_inputs": {
            "daily_returns": RETURNS_DATASET,
            "adj_factor": ADJ_FACTOR_DATASET,
            "benchmark": HS300_DATASET,
            "execution_price": "front_vwap",
            "mark_price": "front_close",
        },
    }
    return BacktestResult(
        daily=scoring_result.daily,
        group_returns=scoring_result.group_returns,
        summary=summary,
        daily_returns=daily_returns,
        net_value=net_value,
        positions=scoring_result.positions,
        turnover=turnover,
        group_daily_returns=group_daily_returns,
        performance_by_year=performance_by_year,
        graph_data=graph_data,
        diagnostics=diagnostics,
    )


def _config_value(config: Any, name: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def _config_section(config: Any, name: str) -> Any:
    if isinstance(config, dict):
        return config.get(name, config)
    return getattr(config, name, config)


def _allowed_market_types(config: Any) -> tuple[int, ...]:
    value = _config_value(
        config,
        "allowed_market_types",
        DEFAULT_ALLOWED_MARKET_TYPES,
    )
    return normalize_allowed_market_types(value)


def _allowed_market_type_list(value: tuple[int, ...]) -> list[int]:
    return list(value)


def _validate_backtest_config(config: Any) -> None:
    if _config_value(config, "price_policy", "front_adjusted") != "front_adjusted":
        raise ValueError("only front_adjusted price_policy is supported")
    if _config_value(config, "execution_price", "vwap") != "vwap":
        raise ValueError("only vwap execution_price is supported")
    if _config_value(config, "mark_price", "close") != "close":
        raise ValueError("only close mark_price is supported")


def _load_backtest_panel(
    bundle: DataBundle,
    data_start: pd.Timestamp,
    scoring_end: pd.Timestamp,
) -> tuple[BacktestPanel, str]:
    panel_result = load_or_build_backtest_panel(
        bundle,
        RETURNS_DATASET,
        ADJ_FACTOR_DATASET,
    )
    panel = panel_result.panel.rows.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    filtered = panel[(panel["date"] >= data_start) & (panel["date"] <= scoring_end)]
    return BacktestPanel(filtered.reset_index(drop=True)), panel_result.status


def _maybe_neutralize_scores(
    bundle: DataBundle,
    scores: pd.DataFrame,
    enabled: bool,
) -> tuple[pd.DataFrame, Any]:
    if not enabled:
        return scores, disabled_summary(signal_rows=len(scores))
    industry_rows = bundle.load_raw(DEFAULT_INDUSTRY_DATASET)
    return neutralize_scores_by_industry(scores, industry_rows)


def _validate_industry_neutralization_source(bundle: DataBundle, enabled: bool) -> None:
    if not enabled:
        return
    try:
        industry_rows = bundle.load_raw(DEFAULT_INDUSTRY_DATASET)
        industry_column_for(industry_rows)
    except Exception as exc:
        raise ValueError(
            "industry_neutralization is enabled but "
            f"{DEFAULT_INDUSTRY_DATASET} is unavailable or lacks a supported "
            "industry column"
        ) from exc


def _filter_scores_to_panel(scores: pd.DataFrame, panel: BacktestPanel) -> pd.DataFrame:
    if scores.empty:
        return scores
    allowed_codes = set(panel.rows["symbol"].astype(str).unique())
    filtered = scores[scores["code"].astype(str).isin(allowed_codes)].copy()
    return filtered.reset_index(drop=True)


def _filter_investable_universe(
    bundle: DataBundle,
    panel: BacktestPanel,
    scores: pd.DataFrame,
    *,
    min_listing_days: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    summary: dict[str, Any] = {
        "enabled": True,
        "selection_information_date": "signal_date",
        "initial_rows": int(len(scores)),
        "min_listing_days": int(min_listing_days),
        "company_info_dataset": COMPANY_INFO_DATASET,
        "company_info_available": False,
        "listing_date_rows": 0,
        "non_tradable_rows": 0,
        "recent_listing_rows": 0,
        "missing_listing_date_rows": 0,
        "missing_signal_date_rows": 0,
        "final_rows": int(len(scores)),
        "st_filter": {
            "enforced": False,
            "reason": "no point-in-time ST/delist field found in release data",
        },
    }
    if scores.empty:
        summary["final_rows"] = 0
        return scores, summary

    rows = panel.rows.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()
    rows["symbol"] = rows["symbol"].map(normalize_stock_code)
    tradable = (
        rows["tradable"]
        if "tradable" in rows.columns
        else pd.Series(False, index=rows.index)
    )
    front_vwap = (
        rows["front_vwap"]
        if "front_vwap" in rows.columns
        else pd.Series(0.0, index=rows.index)
    )
    front_close = (
        rows["front_close"]
        if "front_close" in rows.columns
        else pd.Series(0.0, index=rows.index)
    )
    dnvaltrd = (
        rows["dnvaltrd"]
        if "dnvaltrd" in rows.columns
        else pd.Series(0.0, index=rows.index)
    )
    valid_universe = (
        tradable.fillna(False).astype(bool)
        & (pd.to_numeric(front_vwap, errors="coerce") > 0)
        & (pd.to_numeric(front_close, errors="coerce") > 0)
        & (pd.to_numeric(dnvaltrd, errors="coerce") > 0)
    )
    panel_keys = rows.loc[:, ["date", "symbol"]].drop_duplicates()
    valid_keys = rows.loc[valid_universe, ["date", "symbol"]].drop_duplicates()

    keyed_scores = scores.copy()
    keyed_scores["_order"] = range(len(keyed_scores))
    keyed_scores["date"] = pd.to_datetime(keyed_scores["date"]).dt.normalize()
    keyed_scores["code"] = keyed_scores["code"].map(normalize_stock_code)
    merged = keyed_scores.merge(
        panel_keys.rename(columns={"symbol": "code"}).assign(_panel_row=True),
        on=["date", "code"],
        how="left",
    ).merge(
        valid_keys.rename(columns={"symbol": "code"}).assign(_investable=True),
        on=["date", "code"],
        how="left",
    )
    row_investable = merged["_investable"].fillna(False).astype(bool).to_numpy()
    has_panel_row = merged["_panel_row"].fillna(False).astype(bool).to_numpy()
    summary["missing_signal_date_rows"] = int((~has_panel_row).sum())
    summary["non_tradable_rows"] = int((has_panel_row & ~row_investable).sum())
    filtered = merged.loc[row_investable, keyed_scores.columns].copy()

    listing_dates, listing_summary = _load_listing_dates(bundle)
    summary.update(listing_summary)
    if min_listing_days > 0 and (listing_dates is None or listing_dates.empty):
        availability = (
            "lacks a supported symbol/listing-date column or valid rows"
            if listing_summary["company_info_available"]
            else "is unavailable"
        )
        raise ValueError(
            f"min_listing_days={min_listing_days} requires "
            f"{COMPANY_INFO_DATASET}, but the dataset {availability}"
        )

    if min_listing_days > 0 and not filtered.empty:
        assert listing_dates is not None
        filtered["_listdt"] = filtered["code"].map(listing_dates)
        missing_listing = filtered["_listdt"].isna()
        age_days = (filtered["date"] - filtered["_listdt"]).dt.days
        recent_listing = filtered["_listdt"].notna() & (age_days < min_listing_days)
        summary["missing_listing_date_rows"] = int(missing_listing.sum())
        summary["recent_listing_rows"] = int(recent_listing.sum())
        filtered = filtered.loc[~missing_listing & ~recent_listing].drop(
            columns=["_listdt"]
        )

    filtered = filtered.sort_values("_order").drop(columns=["_order"])
    summary["final_rows"] = int(len(filtered))
    return filtered.reset_index(drop=True), summary


def _load_listing_dates(bundle: DataBundle) -> tuple[pd.Series | None, dict[str, Any]]:
    summary = {
        "company_info_dataset": COMPANY_INFO_DATASET,
        "company_info_available": False,
        "listing_date_rows": 0,
    }
    try:
        company_info = bundle.load_raw(COMPANY_INFO_DATASET)
    except KeyError:
        return None, summary
    symbol_column = _optional_column(
        company_info,
        ["symbol", "Symbol", "stkcd", "Stkcd", "code"],
    )
    listdt_column = _optional_column(
        company_info,
        ["listdt", "Listdt", "LISTDT", "list_date", "ListDate"],
    )
    if symbol_column is None or listdt_column is None:
        summary["company_info_available"] = True
        return None, summary

    rows = company_info.loc[:, [symbol_column, listdt_column]].copy()
    rows["code"] = rows[symbol_column].map(normalize_stock_code)
    rows["listdt"] = pd.to_datetime(rows[listdt_column], errors="coerce").dt.normalize()
    listing_dates = rows.dropna(subset=["code", "listdt"]).groupby("code")["listdt"].min()
    summary["company_info_available"] = True
    summary["listing_date_rows"] = int(len(listing_dates))
    return listing_dates, summary


def _optional_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    folded = {column.lower(): column for column in df.columns}
    for candidate in candidates:
        if candidate.lower() in folded:
            return folded[candidate.lower()]
    return None


def _calculate_group_returns(
    panel: BacktestPanel, scores: pd.DataFrame, group_count: int
) -> pd.DataFrame:
    if scores.empty or group_count <= 0:
        return pd.DataFrame(columns=["date", "group", "return"])
    rows = panel.rows.copy()
    rows["date"] = pd.to_datetime(rows["date"]).dt.normalize()
    rows["symbol"] = rows["symbol"].map(normalize_stock_code)
    dates = pd.Index(rows["date"]).drop_duplicates().sort_values()
    if len(dates) < 2:
        return pd.DataFrame(columns=["date", "group", "return"])
    next_dates = pd.DataFrame(
        {"source_date": dates[:-1], "trade_date": dates[1:]}
    )
    ranked = scores.dropna(subset=["score"]).copy()
    if ranked.empty:
        return pd.DataFrame(columns=["date", "group", "return"])
    ranked["date"] = pd.to_datetime(ranked["date"]).dt.normalize()
    ranked["code"] = ranked["code"].map(normalize_stock_code)
    grouped_scores = []
    for source_date, frame in ranked.groupby("date", sort=True):
        ordered = frame.sort_values("score", kind="stable").reset_index(drop=True)
        group_count_for_date = min(group_count, len(ordered))
        ordered["group"] = [
            f"group_{int(position * group_count_for_date / len(ordered)) + 1}"
            for position in range(len(ordered))
        ]
        grouped_scores.append(ordered.loc[:, ["date", "code", "group"]])
    if not grouped_scores:
        return pd.DataFrame(columns=["date", "group", "return"])
    signal_groups = pd.concat(grouped_scores, ignore_index=True).merge(
        next_dates,
        left_on="date",
        right_on="source_date",
        how="inner",
    )
    if signal_groups.empty:
        return pd.DataFrame(columns=["date", "group", "return"])

    if "tradable" not in rows.columns:
        rows["tradable"] = False
    for optional_column in (
        "limit_status",
        "front_limit_up",
        "front_limit_down",
        "market_type",
    ):
        if optional_column not in rows.columns:
            rows[optional_column] = float("nan")
    day_returns = rows.loc[
        :,
        [
            "date",
            "symbol",
            "front_vwap",
            "front_close",
            "tradable",
            "limit_status",
            "front_limit_up",
            "front_limit_down",
            "market_type",
        ],
    ].copy()
    day_returns["front_vwap"] = pd.to_numeric(
        day_returns["front_vwap"], errors="coerce"
    )
    day_returns["front_close"] = pd.to_numeric(
        day_returns["front_close"], errors="coerce"
    )
    day_returns["tradable"] = day_returns["tradable"].fillna(False).astype(bool)
    for numeric_column in (
        "limit_status",
        "front_limit_up",
        "front_limit_down",
        "market_type",
    ):
        day_returns[numeric_column] = pd.to_numeric(
            day_returns[numeric_column], errors="coerce"
        )
    day_returns = day_returns.sort_values(["symbol", "date"]).reset_index(drop=True)
    valid_close_history = day_returns["front_close"].where(day_returns["front_close"] > 0)
    previous_close = valid_close_history.groupby(day_returns["symbol"]).ffill()
    day_returns["previous_close"] = previous_close.groupby(day_returns["symbol"]).shift(1)
    valid_close = day_returns["front_close"] > 0
    valid_vwap = day_returns["front_vwap"] > 0
    previous_close_valid = day_returns["previous_close"] > 0
    close_return = pd.Series(0.0, index=day_returns.index)
    close_return.loc[previous_close_valid & valid_close] = (
        day_returns.loc[previous_close_valid & valid_close, "front_close"]
        / day_returns.loc[previous_close_valid & valid_close, "previous_close"]
        - 1.0
    )
    fallback_threshold = pd.Series(
        [
            fallback_price_limit_threshold(market_type, trading_date)
            for market_type, trading_date in zip(
                day_returns["market_type"],
                day_returns["date"],
            )
        ],
        index=day_returns.index,
        dtype=float,
    )
    source_limit = (day_returns["limit_status"].fillna(0.0) != 0) | (
        day_returns["front_limit_up"].notna()
        & valid_close
        & (day_returns["front_close"] >= day_returns["front_limit_up"] - 1e-10)
    ) | (
        day_returns["front_limit_down"].notna()
        & valid_close
        & (day_returns["front_close"] <= day_returns["front_limit_down"] + 1e-10)
    )
    fallback_limit_up = (
        previous_close_valid
        & day_returns["limit_status"].isna()
        & day_returns["front_limit_up"].isna()
        & (close_return > fallback_threshold)
    )
    fallback_limit_down = (
        previous_close_valid
        & day_returns["limit_status"].isna()
        & day_returns["front_limit_down"].isna()
        & (close_return < -fallback_threshold)
    )
    limit_blocked = source_limit | fallback_limit_up | fallback_limit_down
    executable = (
        valid_close
        & valid_vwap
        & day_returns["tradable"]
        & ~limit_blocked
    )
    day_returns = day_returns.loc[executable].copy()
    day_returns["return"] = (
        day_returns["front_close"] / day_returns["front_vwap"]
        - 1.0
    )

    merged = signal_groups.merge(
        day_returns.loc[:, ["date", "symbol", "return"]],
        left_on=["trade_date", "code"],
        right_on=["date", "symbol"],
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame(columns=["date", "group", "return"])
    return (
        merged.rename(columns={"trade_date": "date"})
        .groupby(["date", "group"], as_index=False)["return"]
        .mean()
        .loc[:, ["date", "group", "return"]]
    )


def _scoring_result(
    simulated: BacktestResult,
    group_returns: pd.DataFrame,
    scoring_start: pd.Timestamp,
    scoring_end: pd.Timestamp,
) -> BacktestResult:
    daily = simulated.daily.copy()
    positions = simulated.positions.copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.normalize()
    positions["date"] = pd.to_datetime(positions["date"]).dt.normalize()
    daily = daily[(daily["date"] >= scoring_start) & (daily["date"] <= scoring_end)]
    positions = positions[
        (positions["date"] >= scoring_start) & (positions["date"] <= scoring_end)
    ]
    public_positions = positions.rename(columns={"symbol": "code"})
    if not group_returns.empty:
        group_returns = group_returns.copy()
        group_returns["date"] = pd.to_datetime(group_returns["date"]).dt.normalize()
        group_returns = group_returns[
            (group_returns["date"] >= scoring_start)
            & (group_returns["date"] <= scoring_end)
        ]
    return BacktestResult(
        daily=daily.reset_index(drop=True),
        positions=public_positions.reset_index(drop=True),
        group_returns=group_returns.reset_index(drop=True),
    )


def _summary_frame(metrics: Any, daily_returns: pd.DataFrame) -> pd.DataFrame:
    summary = dict(metrics.summary)
    summary["total_return"] = summary.get("all_return", 0.0)
    summary["trading_days"] = int(len(daily_returns))
    return pd.DataFrame([summary])


def _public_daily_returns(daily: pd.DataFrame, *, return_column: str) -> pd.DataFrame:
    if return_column not in daily.columns:
        raise ValueError(f"daily return column is missing: {return_column}")
    rows = daily.loc[:, ["date"]].copy()
    rows["daily_return"] = daily[return_column]
    for column in [
        "portfolio_return",
        "long_return",
        "short_return",
        "benchmark_return",
        "risk_free_return",
        "active_return",
        "scored_daily_return",
    ]:
        if column not in daily.columns:
            continue
        if column == "portfolio_return" and return_column == "portfolio_return":
            continue
        rows[column] = daily[column]
    return rows


def _stale_position_diagnostics(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "stale_position_days": summary.get("stale_position_days", 0),
        "max_stale_gross_exposure": summary.get("max_stale_gross_exposure", 0.0),
        "average_stale_gross_exposure": summary.get("average_stale_gross_exposure", 0.0),
        "terminal_stale_position_count": summary.get(
            "terminal_stale_position_count",
            0,
        ),
        "terminal_stale_gross_exposure": summary.get(
            "terminal_stale_gross_exposure",
            0.0,
        ),
    }
