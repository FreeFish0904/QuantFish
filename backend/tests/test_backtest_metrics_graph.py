import json
import math

import pandas as pd
import pytest

from quantfish.backtest import (
    BacktestResult,
    build_backtest_graph_data,
    calculate_backtest_metrics,
)
from quantfish.backtest.active_returns import calculate_long_only_active_returns
from quantfish.backtest.metrics import build_yearly_performance_table


def test_metrics_summarize_returns_risk_exposure_and_group_returns() -> None:
    daily = pd.DataFrame(
        [
            {
                "date": "2023-01-03",
                "portfolio_return": 0.10,
                "long_return": 0.06,
                "short_return": 0.04,
                "turnover": 0.4,
                "long_exposure": 0.7,
                "short_exposure": -0.3,
                "gross_exposure": 1.0,
                "position_count": 2,
            },
            {
                "date": "2023-01-04",
                "portfolio_return": -0.05,
                "long_return": -0.03,
                "short_return": -0.02,
                "turnover": 0.2,
                "long_exposure": 0.6,
                "short_exposure": -0.2,
                "gross_exposure": 0.8,
                "position_count": 2,
            },
            {
                "date": "2023-01-05",
                "portfolio_return": 0.02,
                "long_return": 0.02,
                "short_return": 0.0,
                "turnover": 0.1,
                "long_exposure": 0.4,
                "short_exposure": 0.0,
                "gross_exposure": 0.4,
                "position_count": 1,
            },
        ]
    )
    group_returns = pd.DataFrame(
        [
            {"date": "2023-01-03", "group": "G1", "return": 0.01},
            {"date": "2023-01-03", "group": "G2", "return": -0.01},
            {"date": "2023-01-04", "group": "G1", "return": 0.02},
            {"date": "2023-01-04", "group": "G2", "return": 0.03},
        ]
    )
    result = BacktestResult(
        daily=daily.assign(date=lambda df: pd.to_datetime(df["date"])),
        positions=pd.DataFrame(),
        group_returns=group_returns.assign(date=lambda df: pd.to_datetime(df["date"])),
    )

    metrics = calculate_backtest_metrics(result)

    assert metrics.summary["all_return"] == pytest.approx(0.07)
    assert metrics.summary["annual_return"] == pytest.approx(0.07 / 3 * 252)
    assert metrics.summary["max_drawdown"] == pytest.approx(1.0 - 1.05 / 1.10)
    assert metrics.summary["win_rate"] == pytest.approx(2 / 3)
    assert metrics.summary["average_turnover"] == pytest.approx((0.4 + 0.2 + 0.1) / 3)
    assert metrics.summary["long_total_return"] == pytest.approx(0.05)
    assert metrics.summary["short_total_return"] == pytest.approx(0.02)
    assert metrics.summary["annualized_short_profit"] == pytest.approx(0.02 / 3 * 252)
    assert metrics.summary["average_gross_exposure"] == pytest.approx((1.0 + 0.8 + 0.4) / 3)
    assert metrics.summary["average_position_count"] == pytest.approx(5 / 3)
    assert metrics.summary["calmar"] == pytest.approx(
        metrics.summary["annual_return"] / metrics.summary["max_drawdown"]
    )
    assert metrics.summary["fitness"] > 0
    assert metrics.group_returns.set_index("group")["all_return"].to_dict() == {
        "G1": pytest.approx(0.03),
        "G2": pytest.approx(0.02),
    }


def test_metrics_clamp_losing_short_leg_profit_to_zero() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2023-01-03"),
                    "portfolio_return": 0.01,
                    "short_return": -0.03,
                    "turnover": 0.1,
                },
                {
                    "date": pd.Timestamp("2023-01-04"),
                    "portfolio_return": 0.02,
                    "short_return": 0.01,
                    "turnover": 0.1,
                },
            ]
        ),
        group_returns=pd.DataFrame(),
    )

    metrics = calculate_backtest_metrics(result)

    assert metrics.summary["long_total_return"] == pytest.approx(0.0)
    assert metrics.summary["short_total_return"] == pytest.approx(-0.02)
    assert metrics.summary["annualized_short_profit"] == pytest.approx(0.0)


def test_metrics_drawdown_includes_initial_capital_baseline() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": -0.05, "turnover": 0.0},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": -0.02, "turnover": 0.0},
            ]
        ),
        group_returns=pd.DataFrame(),
    )

    metrics = calculate_backtest_metrics(result)

    assert metrics.summary["max_drawdown"] == pytest.approx(0.07)


def test_metrics_mark_zero_drawdown_calmar_missing_and_summarize_stale_positions() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2023-01-03"),
                    "portfolio_return": 0.01,
                    "turnover": 0.0,
                    "stale_position_count": 0,
                    "stale_gross_exposure": 0.0,
                },
                {
                    "date": pd.Timestamp("2023-01-04"),
                    "portfolio_return": 0.02,
                    "turnover": 0.0,
                    "stale_position_count": 1,
                    "stale_gross_exposure": 0.35,
                },
                {
                    "date": pd.Timestamp("2023-01-05"),
                    "portfolio_return": 0.03,
                    "turnover": 0.0,
                    "stale_position_count": 2,
                    "stale_gross_exposure": 0.50,
                },
            ]
        ),
        group_returns=pd.DataFrame(),
    )

    metrics = calculate_backtest_metrics(result)

    assert metrics.summary["max_drawdown"] == 0.0
    assert metrics.summary["calmar"] is None
    assert metrics.summary["stale_position_days"] == 2
    assert metrics.summary["max_stale_gross_exposure"] == pytest.approx(0.50)
    assert metrics.summary["average_stale_gross_exposure"] == pytest.approx(0.85 / 3)
    assert metrics.summary["terminal_stale_position_count"] == 2
    assert metrics.summary["terminal_stale_gross_exposure"] == pytest.approx(0.50)


def test_long_only_active_returns_beta_adjust_benchmark_like_portfolio_to_zero() -> None:
    daily = pd.DataFrame(
        [
            {"date": "2023-01-03", "portfolio_return": 0.010},
            {"date": "2023-01-04", "portfolio_return": -0.020},
            {"date": "2023-01-05", "portfolio_return": 0.030},
            {"date": "2023-01-06", "portfolio_return": -0.010},
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"date": "2023-01-03", "return": 0.010},
            {"date": "2023-01-04", "return": -0.020},
            {"date": "2023-01-05", "return": 0.030},
            {"date": "2023-01-06", "return": -0.010},
        ]
    )

    active = calculate_long_only_active_returns(
        daily,
        benchmark,
        min_observations=2,
        risk_free_rate=0.0175,
    )

    assert active.beta == pytest.approx(1.0)
    assert active.daily["benchmark_return"].tolist() == pytest.approx(
        [0.010, -0.020, 0.030, -0.010]
    )
    assert active.daily["risk_free_return"].tolist() == pytest.approx([0.0175 / 252] * 4)
    assert active.daily["active_return"].abs().max() == pytest.approx(0.0)
    assert active.daily["scored_daily_return"].abs().max() == pytest.approx(0.0)
    assert active.tracking_error == pytest.approx(0.0)
    assert active.information_ratio == pytest.approx(0.0)


def test_long_only_active_returns_treat_cash_like_portfolio_as_zero_active_return() -> None:
    annual_risk_free_rate = 0.0175
    daily_risk_free_return = annual_risk_free_rate / 252
    daily = pd.DataFrame(
        [
            {"date": "2023-01-03", "portfolio_return": daily_risk_free_return},
            {"date": "2023-01-04", "portfolio_return": daily_risk_free_return},
            {"date": "2023-01-05", "portfolio_return": daily_risk_free_return},
            {"date": "2023-01-06", "portfolio_return": daily_risk_free_return},
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"date": "2023-01-03", "return": 0.010},
            {"date": "2023-01-04", "return": -0.020},
            {"date": "2023-01-05", "return": 0.030},
            {"date": "2023-01-06", "return": -0.010},
        ]
    )

    active = calculate_long_only_active_returns(
        daily,
        benchmark,
        min_observations=2,
        risk_free_rate=annual_risk_free_rate,
    )

    assert active.beta == pytest.approx(0.0)
    assert active.daily["risk_free_return"].tolist() == pytest.approx([daily_risk_free_return] * 4)
    assert active.daily["active_return"].abs().max() == pytest.approx(0.0)


def test_long_only_active_returns_beta_uses_excess_returns() -> None:
    annual_risk_free_rate = 0.0175
    daily_risk_free_return = annual_risk_free_rate / 252
    benchmark_returns = [0.010, -0.020, 0.030, -0.010]
    daily = pd.DataFrame(
        [
            {
                "date": date,
                "portfolio_return": daily_risk_free_return
                + 2 * (benchmark_return - daily_risk_free_return),
            }
            for date, benchmark_return in zip(
                ["2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"],
                benchmark_returns, strict=True,
            )
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"date": date, "return": benchmark_return}
            for date, benchmark_return in zip(
                ["2023-01-03", "2023-01-04", "2023-01-05", "2023-01-06"],
                benchmark_returns, strict=True,
            )
        ]
    )

    active = calculate_long_only_active_returns(
        daily,
        benchmark,
        min_observations=2,
        risk_free_rate=annual_risk_free_rate,
    )

    assert active.beta == pytest.approx(2.0)
    assert active.daily["active_return"].abs().max() == pytest.approx(0.0)


def test_long_only_active_returns_require_aligned_benchmark_observations() -> None:
    daily = pd.DataFrame(
        [
            {"date": "2023-01-03", "portfolio_return": 0.01},
            {"date": "2023-01-04", "portfolio_return": 0.02},
            {"date": "2023-01-05", "portfolio_return": 0.03},
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"date": "2023-01-03", "return": 0.01},
            {"date": "2023-01-05", "return": 0.03},
        ]
    )

    with pytest.raises(ValueError, match="benchmark observations"):
        calculate_long_only_active_returns(daily, benchmark, min_observations=3)


def test_long_only_active_returns_allow_sparse_benchmark_with_enough_overlap() -> None:
    daily = pd.DataFrame(
        [
            {"date": "2023-01-03", "portfolio_return": 0.01},
            {"date": "2023-01-04", "portfolio_return": 0.02},
            {"date": "2023-01-05", "portfolio_return": 0.03},
        ]
    )
    benchmark = pd.DataFrame(
        [
            {"date": "2023-01-03", "return": 0.01},
            {"date": "2023-01-05", "return": 0.03},
        ]
    )

    active = calculate_long_only_active_returns(daily, benchmark, min_observations=2)

    assert active.observation_count == 2
    assert active.daily["date"].tolist() == [
        pd.Timestamp("2023-01-03"),
        pd.Timestamp("2023-01-05"),
    ]
    assert active.daily["benchmark_return"].tolist() == pytest.approx([0.01, 0.03])
    assert active.daily["active_return"].abs().max() == pytest.approx(0.0)


def test_yearly_performance_table_splits_total_and_annualized_returns() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": 0.10, "turnover": 0.4},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": -0.05, "turnover": 0.2},
                {"date": pd.Timestamp("2024-01-03"), "portfolio_return": 0.02, "turnover": 0.1},
            ]
        ),
        positions=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "code": "000001", "weight": 0.6},
                {"date": pd.Timestamp("2023-01-03"), "code": "000002", "weight": -0.4},
                {"date": pd.Timestamp("2023-01-03"), "code": "000003", "weight": 0.0},
                {"date": pd.Timestamp("2023-01-04"), "code": "000001", "weight": 0.5},
                {"date": pd.Timestamp("2023-01-04"), "code": "000002", "weight": -0.2},
                {"date": pd.Timestamp("2023-01-04"), "code": "000003", "weight": -0.1},
                {"date": pd.Timestamp("2024-01-03"), "code": "000001", "weight": 0.7},
                {"date": pd.Timestamp("2024-01-03"), "code": "000002", "weight": -0.3},
                {"date": pd.Timestamp("2024-01-03"), "code": "000003", "weight": 0.1},
            ]
        ),
    )

    table = build_yearly_performance_table(result)
    rows = table.set_index("period").to_dict("index")

    assert list(table["period"]) == ["2023", "2024", "all"]
    assert rows["2023"]["long"] == pytest.approx(0.55)
    assert rows["2023"]["short"] == pytest.approx(-0.35)
    assert rows["2023"]["long_count"] == 1
    assert rows["2023"]["short_count"] == 1
    assert rows["2023"]["total_return"] == pytest.approx(0.05)
    assert rows["2023"]["annualized_return"] == pytest.approx(0.025 * 252)
    assert rows["2023"]["turnover"] == pytest.approx(0.3)
    relative_drawdown = 1.0 - 1.05 / 1.10
    assert rows["2023"]["drawdown"] == pytest.approx(relative_drawdown)
    assert rows["2023"]["sharpe"] == pytest.approx((0.025 / pd.Series([0.10, -0.05]).std()) * (252 ** 0.5))
    assert rows["2023"]["fitness"] == pytest.approx(
        rows["2023"]["sharpe"]
        * ((abs(rows["2023"]["annualized_return"]) / rows["2023"]["turnover"]) ** 0.5)
    )
    assert rows["2023"]["calmar"] == pytest.approx(
        (0.025 * 252) / relative_drawdown
    )

    assert rows["2024"]["long"] == pytest.approx(0.8)
    assert rows["2024"]["short"] == pytest.approx(-0.3)
    assert rows["2024"]["long_count"] == 2
    assert rows["2024"]["short_count"] == 1
    assert rows["2024"]["total_return"] == pytest.approx(0.02)
    assert rows["2024"]["annualized_return"] == pytest.approx(0.02 * 252)
    assert rows["2024"]["drawdown"] == pytest.approx(0.0)
    assert pd.isna(rows["2024"]["sharpe"])
    assert pd.isna(rows["2024"]["fitness"])
    assert pd.isna(rows["2024"]["calmar"])

    assert rows["all"]["long"] == pytest.approx((0.6 + 0.5 + 0.8) / 3)
    assert rows["all"]["short"] == pytest.approx((-0.4 - 0.3 - 0.3) / 3)
    assert rows["all"]["long_count"] == 1
    assert rows["all"]["short_count"] == 1
    assert rows["all"]["total_return"] == pytest.approx(0.10 - 0.05 + 0.02)
    assert rows["all"]["annualized_return"] == pytest.approx((0.10 - 0.05 + 0.02) / 3 * 252)
    assert rows["all"]["drawdown"] == pytest.approx(relative_drawdown)


def test_yearly_performance_table_marks_non_finite_legacy_metrics_missing() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": 0.01, "turnover": 0.0},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": 0.01, "turnover": 0.0},
            ]
        ),
        positions=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "code": "000001", "weight": 1.0},
                {"date": pd.Timestamp("2023-01-04"), "code": "000001", "weight": 1.0},
            ]
        ),
    )

    rows = build_yearly_performance_table(result).set_index("period").to_dict("index")

    assert rows["2023"]["sharpe"] is None
    assert rows["2023"]["fitness"] is None
    assert rows["2023"]["calmar"] is None
    assert rows["all"]["sharpe"] is None
    assert rows["all"]["fitness"] is None
    assert rows["all"]["calmar"] is None


def test_yearly_performance_table_drawdown_includes_zero_return_baseline() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": -0.05, "turnover": 0.0},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": 0.02, "turnover": 0.0},
            ]
        ),
        positions=pd.DataFrame(),
    )

    rows = build_yearly_performance_table(result).set_index("period").to_dict("index")

    assert rows["2023"]["drawdown"] == pytest.approx(0.05)
    assert rows["all"]["drawdown"] == pytest.approx(0.05)


def test_graph_data_is_json_friendly_with_cumulative_group_series() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2023-01-03"),
                    "portfolio_return": 0.10,
                    "turnover": 0.4,
                    "buy_turnover": 0.25,
                    "sell_turnover": 0.15,
                    "long_exposure": 0.7,
                    "short_exposure": -0.3,
                    "gross_exposure": 1.0,
                    "position_count": 2,
                    "stale_position_count": 1,
                    "stale_gross_exposure": 0.10,
                },
                {
                    "date": pd.Timestamp("2023-01-04"),
                    "portfolio_return": -0.05,
                    "turnover": 0.2,
                    "buy_turnover": 0.05,
                    "sell_turnover": 0.15,
                    "long_exposure": 0.6,
                    "short_exposure": -0.2,
                    "gross_exposure": 0.8,
                    "position_count": 2,
                    "stale_position_count": 0,
                    "stale_gross_exposure": 0.0,
                },
            ]
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "group": "G1", "return": 0.01},
                {"date": pd.Timestamp("2023-01-04"), "group": "G1", "return": 0.02},
            ]
        ),
    )

    benchmark = pd.DataFrame(
        [
            {"date": pd.Timestamp("2023-01-03"), "return": 0.01},
            {"date": pd.Timestamp("2023-01-04"), "return": -0.02},
        ]
    )

    graph_data = build_backtest_graph_data(result, capital=1_000_000, benchmark=benchmark)

    json.dumps(graph_data)
    assert graph_data["equity"] == [
        {"date": "2023-01-03", "equity": pytest.approx(1.1)},
        {"date": "2023-01-04", "equity": pytest.approx(1.05)},
    ]
    assert graph_data["equity_cny"] == [
        {"date": "2023-01-03", "equity_cny": pytest.approx(1_100_000)},
        {"date": "2023-01-04", "equity_cny": pytest.approx(1_050_000)},
    ]
    assert graph_data["drawdown"] == [
        {"date": "2023-01-03", "drawdown": pytest.approx(0.0)},
        {"date": "2023-01-04", "drawdown": pytest.approx(1.05 / 1.10 - 1.0)},
    ]
    assert graph_data["daily_pnl"] == [
        {"date": "2023-01-03", "pnl_cny": pytest.approx(100_000), "daily_return": pytest.approx(0.10)},
        {"date": "2023-01-04", "pnl_cny": pytest.approx(-50_000), "daily_return": pytest.approx(-0.05)},
    ]
    assert graph_data["trade_volume"] == [
        {"date": "2023-01-03", "buy_cny": pytest.approx(250_000), "sell_cny": pytest.approx(150_000)},
        {"date": "2023-01-04", "buy_cny": pytest.approx(50_000), "sell_cny": pytest.approx(150_000)},
    ]
    assert graph_data["benchmark"] == [
        {
            "date": "2023-01-03",
            "benchmark_return": pytest.approx(0.01),
            "benchmark_equity": pytest.approx(1.01),
            "benchmark_cny": pytest.approx(1_010_000),
        },
        {
            "date": "2023-01-04",
            "benchmark_return": pytest.approx(-0.02),
            "benchmark_equity": pytest.approx(0.99),
            "benchmark_cny": pytest.approx(990_000),
        },
    ]
    assert graph_data["alpha"] == [
        {
            "date": "2023-01-03",
            "alpha_return": pytest.approx(0.09),
            "alpha_equity": pytest.approx(1.09),
            "alpha_cny": pytest.approx(1_090_000),
        },
        {
            "date": "2023-01-04",
            "alpha_return": pytest.approx(-0.03),
            "alpha_equity": pytest.approx(1.06),
            "alpha_cny": pytest.approx(1_060_000),
        },
    ]
    assert graph_data["exposure"][0]["stale_position_count"] == pytest.approx(1)
    assert graph_data["exposure"][0]["stale_gross_exposure"] == pytest.approx(0.10)
    assert graph_data["exposure"][1]["stale_position_count"] == pytest.approx(0)
    assert graph_data["exposure"][1]["stale_gross_exposure"] == pytest.approx(0.0)
    assert graph_data["group_cumulative"] == [
        {"date": "2023-01-03", "group": "G1", "cumulative_return": pytest.approx(0.01)},
        {"date": "2023-01-04", "group": "G1", "cumulative_return": pytest.approx(0.03)},
    ]


def test_graph_uses_raw_equity_and_precomputed_active_alpha_when_present() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2023-01-03"),
                    "portfolio_return": 0.10,
                    "active_return": 0.015,
                    "scored_daily_return": 0.015,
                },
                {
                    "date": pd.Timestamp("2023-01-04"),
                    "portfolio_return": -0.05,
                    "active_return": -0.020,
                    "scored_daily_return": -0.020,
                },
            ]
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(),
    )
    benchmark = pd.DataFrame(
        [
            {"date": pd.Timestamp("2023-01-03"), "return": 0.08},
            {"date": pd.Timestamp("2023-01-04"), "return": -0.01},
        ]
    )

    graph_data = build_backtest_graph_data(result, capital=1_000_000, benchmark=benchmark)

    assert graph_data["equity"] == [
        {"date": "2023-01-03", "equity": pytest.approx(1.10)},
        {"date": "2023-01-04", "equity": pytest.approx(1.05)},
    ]
    assert graph_data["drawdown"] == [
        {"date": "2023-01-03", "drawdown": pytest.approx(0.0)},
        {"date": "2023-01-04", "drawdown": pytest.approx(1.05 / 1.10 - 1.0)},
    ]
    assert graph_data["daily_pnl"] == [
        {
            "date": "2023-01-03",
            "pnl_cny": pytest.approx(100_000),
            "daily_return": pytest.approx(0.10),
        },
        {
            "date": "2023-01-04",
            "pnl_cny": pytest.approx(-50_000),
            "daily_return": pytest.approx(-0.05),
        },
    ]
    assert graph_data["daily_returns"] == [
        {"date": "2023-01-03", "daily_return": pytest.approx(0.10)},
        {"date": "2023-01-04", "daily_return": pytest.approx(-0.05)},
    ]
    assert graph_data["alpha"] == [
        {
            "date": "2023-01-03",
            "alpha_return": pytest.approx(0.015),
            "alpha_equity": pytest.approx(1.015),
            "alpha_cny": pytest.approx(1_015_000),
        },
        {
            "date": "2023-01-04",
            "alpha_return": pytest.approx(-0.020),
            "alpha_equity": pytest.approx(0.995),
            "alpha_cny": pytest.approx(995_000),
        },
    ]


def test_graph_drawdown_includes_initial_capital_baseline() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": -0.05},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": 0.02},
            ]
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(),
    )

    graph_data = build_backtest_graph_data(result)

    assert graph_data["drawdown"] == [
        {"date": "2023-01-03", "drawdown": pytest.approx(-0.05)},
        {"date": "2023-01-04", "drawdown": pytest.approx(-0.03)},
    ]


def test_graph_data_omits_benchmark_and_alpha_when_index_data_is_missing() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2023-01-03"),
                    "portfolio_return": 0.10,
                    "turnover": 0.4,
                    "buy_turnover": 0.25,
                    "sell_turnover": 0.15,
                },
            ]
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(),
    )

    graph_data = build_backtest_graph_data(result, capital=1_000_000)

    assert graph_data["benchmark"] == []
    assert graph_data["alpha"] == []
    assert graph_data["daily_pnl"] == [
        {"date": "2023-01-03", "pnl_cny": pytest.approx(100_000), "daily_return": pytest.approx(0.10)}
    ]


def test_graph_data_keeps_available_benchmark_dates_when_one_day_is_missing() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": 0.03, "turnover": 0.1},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": -0.02, "turnover": 0.2},
                {"date": pd.Timestamp("2023-01-05"), "portfolio_return": 0.01, "turnover": 0.1},
            ]
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(),
    )
    benchmark = pd.DataFrame(
        [
            {"date": pd.Timestamp("2023-01-03"), "return": 0.01},
            {"date": pd.Timestamp("2023-01-05"), "return": -0.02},
        ]
    )

    graph_data = build_backtest_graph_data(result, capital=1_000_000, benchmark=benchmark)

    assert graph_data["benchmark"] == [
        {
            "date": "2023-01-03",
            "benchmark_return": pytest.approx(0.01),
            "benchmark_equity": pytest.approx(1.01),
            "benchmark_cny": pytest.approx(1_010_000),
        },
        {
            "date": "2023-01-05",
            "benchmark_return": pytest.approx(-0.02),
            "benchmark_equity": pytest.approx(0.99),
            "benchmark_cny": pytest.approx(990_000),
        },
    ]
    assert graph_data["alpha"] == [
        {
            "date": "2023-01-03",
            "alpha_return": pytest.approx(0.02),
            "alpha_equity": pytest.approx(1.02),
            "alpha_cny": pytest.approx(1_020_000),
        },
        {
            "date": "2023-01-05",
            "alpha_return": pytest.approx(0.03),
            "alpha_equity": pytest.approx(1.05),
            "alpha_cny": pytest.approx(1_050_000),
        },
    ]


def test_graph_data_limits_benchmark_and_alpha_to_strategy_dates() -> None:
    result = BacktestResult(
        daily=pd.DataFrame(
            [
                {"date": pd.Timestamp("2023-01-03"), "portfolio_return": 0.03, "turnover": 0.1},
                {"date": pd.Timestamp("2023-01-04"), "portfolio_return": -0.02, "turnover": 0.2},
            ]
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(),
    )
    benchmark = pd.DataFrame(
        [
            {"date": pd.Timestamp("2023-01-02"), "return": 0.04},
            {"date": pd.Timestamp("2023-01-03"), "return": 0.01},
            {"date": pd.Timestamp("2023-01-04"), "return": -0.02},
            {"date": pd.Timestamp("2023-01-05"), "return": 0.03},
        ]
    )

    graph_data = build_backtest_graph_data(result, capital=1_000_000, benchmark=benchmark)

    strategy_dates = [point["date"] for point in graph_data["equity"]]
    assert strategy_dates == ["2023-01-03", "2023-01-04"]
    assert [point["date"] for point in graph_data["benchmark"]] == strategy_dates
    assert [point["date"] for point in graph_data["alpha"]] == strategy_dates


def _daily_returns_result(returns: list[float]) -> BacktestResult:
    return BacktestResult(
        daily=pd.DataFrame(
            {
                "date": pd.bdate_range("2023-01-03", periods=len(returns)),
                "portfolio_return": returns,
            }
        ),
        positions=pd.DataFrame(),
        group_returns=pd.DataFrame(),
    )


def test_metrics_report_geometric_basis_alongside_arithmetic_basis() -> None:
    returns = [0.10, -0.05, 0.02]
    metrics = calculate_backtest_metrics(_daily_returns_result(returns))
    summary = metrics.summary
    series = pd.Series(returns)
    growth = float((1.0 + series).prod())

    assert summary["all_return"] == pytest.approx(0.07)
    assert summary["annual_return"] == pytest.approx(0.07 / 3 * 252)
    assert summary["compounded_total_return"] == pytest.approx(growth - 1.0)
    assert summary["cagr"] == pytest.approx(growth ** (252 / 3) - 1.0)
    assert summary["compounded_max_drawdown"] == pytest.approx(
        1.0 - (1.10 * 0.95) / 1.10
    )
    assert summary["compounded_calmar"] == pytest.approx(
        summary["cagr"] / summary["compounded_max_drawdown"]
    )
    assert summary["volatility"] == pytest.approx(float(series.std(ddof=1)) * math.sqrt(252))
    assert summary["t_stat"] == pytest.approx(
        float(series.mean() / series.std(ddof=1) * math.sqrt(3))
    )
    assert summary["t_stat_p_value"] == pytest.approx(
        math.erfc(abs(summary["t_stat"]) / math.sqrt(2.0))
    )


def test_metrics_sortino_uses_the_risk_free_rate_as_mar() -> None:
    returns = [0.01, -0.02, 0.03, 0.0]
    risk_free_daily_return = 0.0175 / 252

    summary = calculate_backtest_metrics(
        _daily_returns_result(returns),
        risk_free_daily_return=risk_free_daily_return,
    ).summary
    excess = pd.Series(returns) - risk_free_daily_return
    downside_deviation = math.sqrt(float((excess.clip(upper=0.0) ** 2).mean()))

    assert summary["sortino"] == pytest.approx(
        math.sqrt(252) * float(excess.mean()) / downside_deviation
    )


def test_metrics_compounded_drawdown_differs_from_arithmetic_for_volatile_path() -> None:
    summary = calculate_backtest_metrics(_daily_returns_result([0.5, -0.4])).summary

    assert summary["all_return"] == pytest.approx(0.1)
    assert summary["max_drawdown"] == pytest.approx(1.0 - 1.1 / 1.5)
    assert summary["compounded_max_drawdown"] == pytest.approx(1.0 - 0.9 / 1.5)
    assert summary["compounded_max_drawdown"] > summary["max_drawdown"]


def test_metrics_mark_undefined_statistics_missing_instead_of_infinite() -> None:
    flat = calculate_backtest_metrics(_daily_returns_result([0.0, 0.0, 0.0])).summary
    assert flat["cagr"] == pytest.approx(0.0)
    assert flat["compounded_total_return"] == pytest.approx(0.0)
    assert flat["volatility"] == pytest.approx(0.0)
    assert flat["sortino"] is None
    assert flat["t_stat"] is None
    assert flat["t_stat_p_value"] is None

    wiped_out = calculate_backtest_metrics(_daily_returns_result([0.05, -1.0])).summary
    assert wiped_out["all_return"] == pytest.approx(-0.95)
    assert wiped_out["cagr"] is None
    assert wiped_out["compounded_total_return"] is None
    assert wiped_out["compounded_max_drawdown"] is None
    assert wiped_out["compounded_calmar"] is None

    single_day = calculate_backtest_metrics(_daily_returns_result([0.01])).summary
    assert single_day["cagr"] == pytest.approx(1.01**252 - 1.0)
    assert single_day["volatility"] is None
    assert single_day["sortino"] is None
    assert single_day["t_stat"] is None

