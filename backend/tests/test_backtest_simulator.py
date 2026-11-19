import pandas as pd
import pytest

from quantfish.backtest import BacktestPanel, simulate_backtest


def _panel(rows: list[dict]) -> BacktestPanel:
    return BacktestPanel(pd.DataFrame(rows).assign(date=lambda df: pd.to_datetime(df["date"])))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capital", float("nan")),
        ("limit_threshold", float("inf")),
        ("commission_rate", float("nan")),
        ("slippage_rate", float("inf")),
        ("sell_stamp_duty_rate", float("nan")),
        ("max_leverage", float("inf")),
        ("max_participation_rate", float("nan")),
    ],
)
def test_simulator_rejects_non_finite_numeric_settings(field: str, value: float) -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            }
        ]
    )
    arguments = {"capital": 100.0, "mode": "longonly", field: value}

    with pytest.raises(ValueError, match=f"{field} must be finite"):
        simulate_backtest(panel, pd.DataFrame(), **arguments)


def test_simulator_trades_signal_next_day_applies_liquidity_and_pnl_legs() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 109.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 91.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 126.0,
                "front_vwap": 120.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-04",
                "symbol": "000002",
                "front_close": 88.0,
                "front_vwap": 80.0,
                "dnvaltrd": 0.0,
                "tradable": False,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": -1.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longshort")

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-02")].to_dict() == {
        "000001": 0.0,
        "000002": 0.0,
    }
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == {
        "000001": 0.5,
        "000002": -0.5,
    }
    assert positions.loc[pd.Timestamp("2023-01-04")].to_dict() == {
        "000001": 0.5,
        "000002": -0.5,
    }

    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-03"), "close_to_vwap_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-03"), "vwap_to_close_return"] == pytest.approx(0.09)
    assert daily.loc[pd.Timestamp("2023-01-03"), "long_return"] == pytest.approx(0.045)
    assert daily.loc[pd.Timestamp("2023-01-03"), "short_return"] == pytest.approx(0.045)
    assert daily.loc[pd.Timestamp("2023-01-03"), "long_return"] + daily.loc[
        pd.Timestamp("2023-01-03"), "short_return"
    ] - daily.loc[pd.Timestamp("2023-01-03"), "transaction_cost"] == pytest.approx(
        daily.loc[pd.Timestamp("2023-01-03"), "portfolio_return"]
    )
    assert daily.loc[pd.Timestamp("2023-01-03"), "buy_turnover"] == pytest.approx(0.5)
    assert daily.loc[pd.Timestamp("2023-01-03"), "sell_turnover"] == pytest.approx(0.5)
    assert daily.loc[pd.Timestamp("2023-01-04"), "close_to_vwap_return"] == pytest.approx(
        0.11089827603589075
    )
    assert daily.loc[pd.Timestamp("2023-01-04"), "vwap_to_close_return"] == pytest.approx(-0.025)
    assert daily.loc[pd.Timestamp("2023-01-04"), "long_return"] == pytest.approx(
        0.07545871559633028
    )
    assert daily.loc[pd.Timestamp("2023-01-04"), "short_return"] == pytest.approx(
        0.010439560439560472
    )
    assert daily.loc[pd.Timestamp("2023-01-04"), "portfolio_return"] == pytest.approx(
        0.08589827603589075
    )
    assert daily.loc[pd.Timestamp("2023-01-04"), "long_return"] + daily.loc[
        pd.Timestamp("2023-01-04"), "short_return"
    ] - daily.loc[pd.Timestamp("2023-01-04"), "transaction_cost"] == pytest.approx(
        daily.loc[pd.Timestamp("2023-01-04"), "portfolio_return"]
    )
    assert daily.loc[pd.Timestamp("2023-01-04"), "turnover"] == pytest.approx(0.0)
    assert daily.loc[pd.Timestamp("2023-01-04"), "buy_turnover"] == pytest.approx(0.0)
    assert daily.loc[pd.Timestamp("2023-01-04"), "sell_turnover"] == pytest.approx(0.0)


def test_simulator_carries_previous_position_when_limit_hit_blocks_trade() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 111.0,
                "front_vwap": 111.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [{"date": "2023-01-02", "symbol": "000001", "signal": 1.0}]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.set_index(["date", "symbol"])
    assert positions.loc[(pd.Timestamp("2023-01-03"), "000001"), "weight"] == 0.0
    assert result.daily.set_index("date").loc[pd.Timestamp("2023-01-03"), "turnover"] == 0.0


def test_simulator_longshort_uses_legacy_limit_blocking_for_rebalances() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 111.0,
                "front_vwap": 111.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 1,
            },
            {
                "date": "2023-01-04",
                "symbol": "000002",
                "front_close": 89.0,
                "front_vwap": 89.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": -1,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": -1.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 1.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longshort")

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-04")].to_dict() == {
        "000001": 0.5,
        "000002": -0.5,
    }
    day = result.daily.set_index("date").loc[pd.Timestamp("2023-01-04")]
    assert day["buy_turnover"] == pytest.approx(0.0)
    assert day["sell_turnover"] == pytest.approx(0.0)


def test_simulator_blocks_buy_on_limit_up_and_sell_on_limit_down() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 111.0,
                "front_vwap": 111.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 1,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 89.0,
                "front_vwap": 89.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": -1,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longshort")

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == {
        "000001": 0.0,
        "000002": 0.0,
    }
    assert result.daily.set_index("date").loc[pd.Timestamp("2023-01-03"), "turnover"] == 0.0


def test_simulator_retries_blocked_targets_from_actual_positions() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 1,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": -1,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-04",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": -1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=1_000.0,
        mode="longshort",
        max_participation_rate=1.0,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == {
        "000001": 0.0,
        "000002": 0.0,
    }
    assert positions.loc[pd.Timestamp("2023-01-04")].to_dict() == pytest.approx(
        {
            "000001": 0.5,
            "000002": -0.5,
        }
    )


def test_simulator_blocks_trade_when_limit_status_marks_stock_restricted() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 1,
            },
        ]
    )
    signals = pd.DataFrame(
        [{"date": "2023-01-02", "symbol": "000001", "signal": 1.0}]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.set_index(["date", "symbol"])
    assert positions.loc[(pd.Timestamp("2023-01-03"), "000001"), "weight"] == 0.0
    assert result.daily.set_index("date").loc[pd.Timestamp("2023-01-03"), "turnover"] == 0.0


def test_simulator_fallback_uses_chinext_twenty_percent_price_limit() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "300001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "market_type": 16,
            },
            {
                "date": "2023-01-03",
                "symbol": "300001",
                "front_close": 111.0,
                "front_vwap": 105.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "market_type": 16,
            },
        ]
    )
    signals = pd.DataFrame(
        [{"date": "2023-01-02", "symbol": "300001", "signal": 1.0}]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    position = result.positions.set_index(["date", "symbol"]).loc[
        (pd.Timestamp("2023-01-03"), "300001"), "weight"
    ]
    assert position == pytest.approx(1.0)


def test_simulator_blocks_trade_when_execution_vwap_is_missing() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 101.0,
                "front_vwap": None,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [{"date": "2023-01-02", "symbol": "000001", "signal": 1.0}]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.set_index(["date", "symbol"])
    assert positions.loc[(pd.Timestamp("2023-01-03"), "000001"), "weight"] == 0.0
    assert result.daily.set_index("date").loc[pd.Timestamp("2023-01-03"), "turnover"] == 0.0


def test_simulator_marks_held_position_to_close_when_execution_vwap_missing() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 105.0,
                "front_vwap": None,
                "dnvaltrd": 0.0,
                "tradable": False,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 1.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.set_index(["date", "symbol"])
    assert positions.loc[(pd.Timestamp("2023-01-04"), "000001"), "weight"] == 1.0
    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-04"), "turnover"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "vwap_to_close_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "portfolio_return"] == pytest.approx(0.05)


def test_simulator_keeps_missing_close_position_stale_without_vwap_mark_pnl() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": None,
                "front_vwap": 110.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 1.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.set_index(["date", "symbol"])
    assert positions.loc[(pd.Timestamp("2023-01-04"), "000001"), "weight"] == 1.0
    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-04"), "turnover"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "close_to_vwap_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "vwap_to_close_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "portfolio_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "stale_position_count"] == 1
    assert daily.loc[pd.Timestamp("2023-01-04"), "stale_gross_exposure"] == pytest.approx(
        1.0
    )


def test_simulator_catches_up_from_last_valid_close_when_stale_price_returns() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": None,
                "front_vwap": None,
                "dnvaltrd": 0.0,
                "tradable": False,
            },
            {
                "date": "2023-01-05",
                "symbol": "000001",
                "front_close": 110.0,
                "front_vwap": 110.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-04", "symbol": "000001", "signal": 1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=100.0,
        mode="longonly",
        commission_rate=0.01,
        terminal_stale_position_policy="carry",
    )

    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-04"), "portfolio_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "stale_position_count"] == 1
    assert daily.loc[pd.Timestamp("2023-01-05"), "portfolio_return"] == pytest.approx(0.10)
    assert daily.loc[pd.Timestamp("2023-01-05"), "stale_position_count"] == 0
    assert daily.loc[pd.Timestamp("2023-01-05"), "turnover"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-05"), "transaction_cost"] == 0.0


def test_simulator_longonly_keeps_participation_clipped_positions_without_relevering() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 101.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 99.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=1_000.0,
        mode="longonly",
        max_participation_rate=0.10,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == pytest.approx(
        {
            "000001": 0.0025,
            "000002": 0.0,
        }
    )
    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-03"), "gross_exposure"] == pytest.approx(0.0025)
    assert daily.loc[pd.Timestamp("2023-01-03"), "portfolio_return"] == pytest.approx(0.000025)


def test_simulator_longshort_uses_legacy_full_gross_rebalance_despite_participation_cap() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 101.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 99.0,
                "front_vwap": 100.0,
                "dnvaltrd": 25.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=1_000.0,
        mode="longshort",
        max_participation_rate=0.10,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == pytest.approx(
        {
            "000001": 0.5,
            "000002": -0.5,
        }
    )
    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-03"), "gross_exposure"] == pytest.approx(1.0)
    assert daily.loc[pd.Timestamp("2023-01-03"), "portfolio_return"] == pytest.approx(0.01)


def test_simulator_longonly_does_not_liquidate_blocked_exit() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 89.0,
                "front_vwap": 89.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": -1,
            },
            {
                "date": "2023-01-04",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
                "limit_status": 0,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 0.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 0.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-04")].to_dict() == pytest.approx(
        {
            "000001": 1.0,
            "000002": 0.0,
        }
    )
    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-04"), "gross_exposure"] == pytest.approx(1.0)


def test_simulator_longonly_does_not_rescale_blocked_holdings_to_fund_new_names() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": symbol,
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 600.0,
                "tradable": True,
                "limit_status": 0,
            }
            for symbol in ["000001", "000002", "000003", "000004"]
        ]
        + [
            {
                "date": "2023-01-03",
                "symbol": symbol,
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 600.0,
                "tradable": True,
                "limit_status": 0,
            }
            for symbol in ["000001", "000002", "000003", "000004"]
        ]
        + [
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 89.0,
                "front_vwap": 89.0,
                "dnvaltrd": 600.0,
                "tradable": True,
                "limit_status": -1,
            },
            {
                "date": "2023-01-04",
                "symbol": "000002",
                "front_close": 111.0,
                "front_vwap": 111.0,
                "dnvaltrd": 600.0,
                "tradable": True,
                "limit_status": 1,
            },
            {
                "date": "2023-01-04",
                "symbol": "000003",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 100.0,
                "tradable": True,
                "limit_status": 0,
            },
            {
                "date": "2023-01-04",
                "symbol": "000004",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 100.0,
                "tradable": True,
                "limit_status": 0,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": -1.0},
            {"date": "2023-01-02", "symbol": "000003", "signal": 0.0},
            {"date": "2023-01-02", "symbol": "000004", "signal": 0.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 0.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 0.0},
            {"date": "2023-01-03", "symbol": "000003", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000004", "signal": -1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=600.0,
        mode="longonly",
        max_participation_rate=1.0,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == pytest.approx(
        {
            "000001": 1.0,
            "000002": 0.0,
            "000003": 0.0,
            "000004": 0.0,
        }
    )
    assert positions.loc[pd.Timestamp("2023-01-04")].to_dict() == pytest.approx(
        {
            "000001": 1.0,
            "000002": 0.0,
            "000003": 0.0,
            "000004": 0.0,
        }
    )
    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-04"), "turnover"] == pytest.approx(0.0)


def test_simulator_enforces_max_position_weight_after_target_and_execution() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": symbol,
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            }
            for symbol in ["000001", "000002", "000003"]
        ]
        + [
            {
                "date": "2023-01-03",
                "symbol": symbol,
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            }
            for symbol in ["000001", "000002", "000003"]
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 3.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": 2.0},
            {"date": "2023-01-02", "symbol": "000003", "signal": 1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=100.0,
        mode="longonly",
        long_only_weighting="rank_equal",
        top_k=2,
        max_position_weight=0.30,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == pytest.approx(
        {
            "000001": 0.30,
            "000002": 0.30,
            "000003": 0.0,
        }
    )


def test_simulator_redistributes_long_only_weight_after_position_cap() -> None:
    panel = _panel(
        [
            {
                "date": date,
                "symbol": symbol,
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            }
            for date in ["2023-01-02", "2023-01-03"]
            for symbol in ["000001", "000002", "000003"]
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 8.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000003", "signal": 1.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=100.0,
        mode="longonly",
        long_only_weighting="score_proportional",
        max_position_weight=0.50,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03")].to_dict() == pytest.approx(
        {"000001": 0.50, "000002": 0.25, "000003": 0.25}
    )
    assert positions.loc[pd.Timestamp("2023-01-03")].sum() == pytest.approx(1.0)


def test_simulator_carries_position_when_symbol_missing_from_sparse_panel() -> None:
    panel = _panel(
        [
            {
                "date": "2023-01-02",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-02",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-03",
                "symbol": "000002",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
            {
                "date": "2023-01-04",
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            },
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000002", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000002", "signal": 1.0},
        ]
    )

    result = simulate_backtest(panel, signals, capital=100.0, mode="longonly")

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03"), "000002"] == 1.0
    assert positions.loc[pd.Timestamp("2023-01-04"), "000002"] == 1.0

    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-04"), "turnover"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-04"), "portfolio_return"] == 0.0
    assert daily.loc[pd.Timestamp("2023-01-03"), "stale_position_count"] == 0
    assert daily.loc[pd.Timestamp("2023-01-03"), "stale_gross_exposure"] == pytest.approx(0.0)
    assert daily.loc[pd.Timestamp("2023-01-04"), "stale_position_count"] == 1
    assert daily.loc[pd.Timestamp("2023-01-04"), "stale_gross_exposure"] == pytest.approx(1.0)

    with pytest.raises(ValueError, match="ended with unpriced positions"):
        simulate_backtest(
            panel,
            signals,
            capital=100.0,
            mode="longonly",
            terminal_stale_position_policy="reject",
        )


def test_simulator_applies_sell_stamp_duty_only_to_sells() -> None:
    panel = _panel(
        [
            {
                "date": date,
                "symbol": "000001",
                "front_close": 100.0,
                "front_vwap": 100.0,
                "dnvaltrd": 1_000.0,
                "tradable": True,
            }
            for date in ["2023-01-02", "2023-01-03", "2023-01-04"]
        ]
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-03", "symbol": "000001", "signal": 0.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=100.0,
        mode="longonly",
        commission_rate=0.001,
        slippage_rate=0.002,
        sell_stamp_duty_rate=0.0005,
    )

    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-03"), "transaction_cost"] == pytest.approx(
        0.003
    )
    assert daily.loc[pd.Timestamp("2023-01-04"), "transaction_cost"] == pytest.approx(
        0.0035
    )
