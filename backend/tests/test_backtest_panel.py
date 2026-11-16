import math

import pandas as pd

from quantfish.backtest import build_backtest_panel, preprocess_signals
import quantfish.backtest.panel as panel_module


def test_panel_prefers_official_backward_factor_for_front_prices() -> None:
    daily_returns = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "Clsprc": 10.0,
                "Adjprcwd": 999.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1100.0,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000002",
                "Clsprc": 5.0,
                "Adjprcwd": 888.0,
                "Dnshrtrd": 0.0,
                "Dnvaltrd": 900.0,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000001",
                "Clsprc": 12.0,
                "Adjprcwd": 777.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 0.0,
            },
        ]
    )
    adj_factor = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "cumulatefwardfactor": 2.0,
                "cumulatebwardfactor": 3.0,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000002",
                "cumulatefwardfactor": 3.0,
                "cumulatebwardfactor": 4.0,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000001",
                "cumulatefwardfactor": 1.5,
                "cumulatebwardfactor": 2.5,
            },
        ]
    )

    panel = build_backtest_panel(daily_returns, adj_factor).rows

    first = panel.loc[
        (panel["date"] == pd.Timestamp("2023-01-03"))
        & (panel["symbol"] == "000001")
    ].iloc[0]
    assert first["raw_vwap"] == 11.0
    assert first["front_close"] == 30.0
    assert first["front_vwap"] == 33.0
    assert first["tradable"] is True

    zero_volume = panel.loc[panel["symbol"] == "000002"].iloc[0]
    assert math.isnan(zero_volume["raw_vwap"])
    assert zero_volume["tradable"] is False

    zero_value = panel.loc[panel["date"] == pd.Timestamp("2023-01-04")].iloc[0]
    assert zero_value["raw_vwap"] == 0.0
    assert zero_value["front_close"] == 30.0
    assert zero_value["front_vwap"] == 0.0
    assert zero_value["tradable"] is False


def test_panel_keeps_trading_status_informational_only() -> None:
    daily_returns = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "Clsprc": 10.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1_000.0,
                "Trdsta": "0",
            },
        ]
    )
    adj_factor = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "cumulatefwardfactor": 1.0,
            },
        ]
    )

    rows = build_backtest_panel(daily_returns, adj_factor).rows

    assert rows.loc[0, "trading_status"] == "0"
    assert rows.loc[0, "tradable"] is True


def test_panel_preserves_market_and_official_price_limit_fields() -> None:
    daily_returns = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "300001",
                "Clsprc": 10.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1_000.0,
                "Markettype": 16,
                "LimitStatus": 1,
                "LimitUp": 10.0,
                "LimitDown": 6.67,
            },
        ]
    )
    adj_factor = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": "300001",
                "cumulatefwardfactor": 2.0,
            },
        ]
    )

    row = build_backtest_panel(daily_returns, adj_factor).rows.iloc[0]

    assert row["market_type"] == 16
    assert row["limit_status"] == 1
    assert row["raw_limit_up"] == 10.0
    assert row["raw_limit_down"] == 6.67
    assert row["front_limit_up"] == 20.0
    assert row["front_limit_down"] == 13.34


def test_panel_asof_fills_forward_factors_and_normalizes_stock_codes() -> None:
    daily_returns = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-03",
                "Symbol": 1,
                "Clsprc": 10.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1000.0,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": 1,
                "Clsprc": 12.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1200.0,
            },
        ]
    )
    adj_factor = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000001",
                "cumulatefwardfactor": 2.0,
            }
        ]
    )

    panel = build_backtest_panel(daily_returns, adj_factor).rows

    assert panel["symbol"].tolist() == ["000001", "000001"]
    assert panel["front_close"].tolist() == [20.0, 24.0]
    assert panel["front_vwap"].tolist() == [20.0, 24.0]


def test_panel_asof_uses_grouped_merge_once_and_preserves_missing_factors(
    monkeypatch,
) -> None:
    daily_returns = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000002",
                "Clsprc": 20.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 2000.0,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000001",
                "Clsprc": 10.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1000.0,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000001",
                "Clsprc": 12.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 1200.0,
            },
            {
                "TradingDate": "2023-01-04",
                "Symbol": "000003",
                "Clsprc": 30.0,
                "Dnshrtrd": 100.0,
                "Dnvaltrd": 3000.0,
            },
        ]
    )
    adj_factor = pd.DataFrame(
        [
            {
                "TradingDate": "2023-01-02",
                "Symbol": "000001",
                "cumulatefwardfactor": 2.0,
            },
            {
                "TradingDate": "2023-01-03",
                "Symbol": "000002",
                "cumulatefwardfactor": 3.0,
            },
        ]
    )
    original_merge_asof = panel_module.pd.merge_asof
    calls = {"count": 0}

    def counting_merge_asof(*args, **kwargs):
        calls["count"] += 1
        return original_merge_asof(*args, **kwargs)

    monkeypatch.setattr(panel_module.pd, "merge_asof", counting_merge_asof)

    panel = build_backtest_panel(daily_returns, adj_factor).rows

    assert calls["count"] == 1
    assert panel[["date", "symbol"]].to_dict("records") == [
        {"date": pd.Timestamp("2023-01-03"), "symbol": "000001"},
        {"date": pd.Timestamp("2023-01-04"), "symbol": "000001"},
        {"date": pd.Timestamp("2023-01-04"), "symbol": "000002"},
        {"date": pd.Timestamp("2023-01-04"), "symbol": "000003"},
    ]
    by_symbol = panel.set_index("symbol")
    assert by_symbol.loc["000001", "front_close"].tolist() == [20.0, 24.0]
    assert by_symbol.loc["000002", "front_close"] == 60.0
    assert pd.isna(by_symbol.loc["000003", "cumulatefwardfactor"])


def test_preprocess_signals_normalizes_longshort_and_longonly_by_date() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2023-01-03", "symbol": "000001", "signal": 2.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000003", "signal": None},
            {"date": "2023-01-04", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-04", "symbol": "000002", "signal": 1.0},
        ]
    )

    longshort = preprocess_signals(signals, mode="longshort")
    assert longshort.pivot(index="date", columns="symbol", values="weight").loc[
        pd.Timestamp("2023-01-03")
    ].to_dict() == {
        "000001": 0.5,
        "000002": -0.5,
        "000003": 0.0,
    }
    assert longshort.loc[longshort["date"] == pd.Timestamp("2023-01-04"), "weight"].sum() == 0

    longonly = preprocess_signals(
        pd.DataFrame(
            [
                {"date": "2023-01-03", "symbol": "000001", "signal": 2.0},
                {"date": "2023-01-03", "symbol": "000002", "signal": -1.0},
                {"date": "2023-01-03", "symbol": "000003", "signal": 0.0},
            ]
        ),
        mode="longonly",
    )

    assert longonly[["symbol", "weight"]].to_dict("records") == [
        {"symbol": "000001", "weight": 1.0},
        {"symbol": "000002", "weight": 0.0},
        {"symbol": "000003", "weight": 0.0},
    ]


def test_preprocess_signals_rank_equal_longonly_ignores_non_positive_scores() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2023-01-03", "symbol": "000001", "signal": -2.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 0.0},
            {"date": "2023-01-03", "symbol": "000003", "signal": 4.0},
            {"date": "2023-01-03", "symbol": "000004", "signal": None},
        ]
    )

    weights = preprocess_signals(
        signals,
        mode="longonly",
        top_k=2,
        long_only_weighting="rank_equal",
    )

    assert weights[["symbol", "weight"]].to_dict("records") == [
        {"symbol": "000001", "weight": 0.0},
        {"symbol": "000002", "weight": 0.0},
        {"symbol": "000003", "weight": 1.0},
        {"symbol": "000004", "weight": 0.0},
    ]


def test_preprocess_signals_top_k_is_strict_for_ties() -> None:
    signals = pd.DataFrame(
        [
            {"date": "2023-01-03", "symbol": "000001", "signal": 3.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 3.0},
            {"date": "2023-01-03", "symbol": "000003", "signal": 1.0},
            {"date": "2023-01-04", "symbol": "000010", "signal": 2.0},
            {"date": "2023-01-04", "symbol": "000011", "signal": 2.0},
            {"date": "2023-01-04", "symbol": "000012", "signal": -1.0},
            {"date": "2023-01-04", "symbol": "000013", "signal": -1.0},
        ]
    )

    longonly = preprocess_signals(
        signals.loc[signals["date"] == "2023-01-03"],
        mode="longonly",
        top_k=1,
        long_only_weighting="rank_equal",
    )
    assert longonly[["symbol", "weight"]].to_dict("records") == [
        {"symbol": "000001", "weight": 1.0},
        {"symbol": "000002", "weight": 0.0},
        {"symbol": "000003", "weight": 0.0},
    ]

    longshort = preprocess_signals(
        signals.loc[signals["date"] == "2023-01-04"],
        mode="longshort",
        top_k=1,
    )
    assert longshort[["symbol", "weight"]].to_dict("records") == [
        {"symbol": "000010", "weight": 0.5},
        {"symbol": "000011", "weight": 0.0},
        {"symbol": "000012", "weight": -0.5},
        {"symbol": "000013", "weight": 0.0},
    ]
