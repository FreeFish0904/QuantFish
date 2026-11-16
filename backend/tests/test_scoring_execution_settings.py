import pandas as pd
import pytest

from quantfish.backtest import BacktestPanel, simulate_backtest
from quantfish.backtest.metrics import calculate_backtest_metrics
from quantfish.leaderboard.ranking import ScoringWeights, rank_leaderboard
from quantfish.submissions.models import SubmissionMetrics


def test_scoring_weights_use_year_metrics_turnover_penalty_and_minimum_days() -> None:
    weights = ScoringWeights(
        sharpe_weight=2.0,
        sharpe_target=1.0,
        annual_return_weight=1.0,
        annual_return_target=0.5,
        drawdown_weight=3.0,
        drawdown_limit=0.3,
        turnover_weight=10.0,
        turnover_limit=1.0,
        short_profit_weight=20.0,
        short_profit_target=0.2,
        minimum_slice_trading_days=120,
    )
    rows = [
        {
            "id": "eligible",
            "team_name": "Eligible",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {
                "total_return": 0.4,
                "annual_return": 0.4,
                "sharpe": 1.2,
                "max_drawdown": 0.1,
                "average_turnover": 0.25,
                "average_short_exposure": -0.2,
                "annualized_short_profit": 0.04,
                "trading_days": 252,
            },
        },
        {
            "id": "too-short",
            "team_name": "Too Short",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:01:00Z",
            "summary": {
                "total_return": 9.0,
                "sharpe": 9.0,
                "trading_days": 20,
            },
        },
    ]

    ranked = rank_leaderboard(rows, weights=weights)

    assert ranked[0].id == "eligible"
    assert ranked[0].eligible is True
    assert ranked[0].score == pytest.approx(
        2.0 + 0.8 - 1.0 - 2.5 - 4.0
    )
    assert ranked[1].id == "too-short"
    assert ranked[1].eligible is False
    assert ranked[1].badge is None


def test_execution_settings_apply_top_k_leverage_and_transaction_costs() -> None:
    panel = BacktestPanel(
        pd.DataFrame(
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
                    "front_close": 110.0,
                    "front_vwap": 100.0,
                    "dnvaltrd": 1_000.0,
                    "tradable": True,
                },
                {
                    "date": "2023-01-03",
                    "symbol": "000002",
                    "front_close": 120.0,
                    "front_vwap": 100.0,
                    "dnvaltrd": 1_000.0,
                    "tradable": True,
                },
            ]
        ).assign(date=lambda df: pd.to_datetime(df["date"]))
    )
    signals = pd.DataFrame(
        [
            {"date": "2023-01-02", "symbol": "000001", "signal": 1.0},
            {"date": "2023-01-02", "symbol": "000002", "signal": 2.0},
        ]
    )

    result = simulate_backtest(
        panel,
        signals,
        capital=100.0,
        mode="longonly",
        top_k=1,
        max_leverage=1.5,
        max_participation_rate=1.0,
        commission_rate=0.01,
        slippage_rate=0.02,
        limit_threshold=1.0,
    )

    positions = result.positions.pivot(index="date", columns="symbol", values="weight")
    assert positions.loc[pd.Timestamp("2023-01-03"), "000001"] == 0.0
    assert positions.loc[pd.Timestamp("2023-01-03"), "000002"] == pytest.approx(1.5)

    daily = result.daily.set_index("date")
    assert daily.loc[pd.Timestamp("2023-01-03"), "turnover"] == pytest.approx(1.5)
    assert daily.loc[pd.Timestamp("2023-01-03"), "transaction_cost"] == pytest.approx(0.045)
    assert daily.loc[pd.Timestamp("2023-01-03"), "portfolio_return"] == pytest.approx(
        1.5 * 0.20 - 0.045
    )


def test_metrics_include_average_and_worst_calendar_year_returns() -> None:
    result = calculate_backtest_metrics(
        result=type(
            "BacktestResultLike",
            (),
            {
                "daily": pd.DataFrame(
                    [
                        {"date": "2023-01-03", "portfolio_return": 0.10, "turnover": 0.1},
                        {"date": "2023-01-04", "portfolio_return": 0.10, "turnover": 0.1},
                        {"date": "2024-01-03", "portfolio_return": -0.20, "turnover": 0.1},
                    ]
                ),
                "group_returns": pd.DataFrame(),
            },
        )()
    )

    assert result.summary["average_year_return"] == pytest.approx(((0.10 + 0.10) + -0.20) / 2)
    assert result.summary["worst_year_return"] == pytest.approx(-0.2)


def test_submission_metrics_reads_new_scoring_fields_from_summary() -> None:
    metrics = SubmissionMetrics.from_summary(
        {
            "average_year_return": 0.12,
            "worst_year_return": -0.08,
            "average_short_exposure": -0.35,
            "long_total_return": 0.18,
            "short_total_return": 0.08,
            "annualized_short_profit": 0.10,
            "stale_position_days": 2,
            "max_stale_gross_exposure": 0.40,
            "average_stale_gross_exposure": 0.10,
            "trading_days": 200,
        }
    )

    assert metrics.average_year_return == 0.12
    assert metrics.worst_year_return == -0.08
    assert metrics.average_short_exposure == -0.35
    assert metrics.long_total_return == 0.18
    assert metrics.short_total_return == 0.08
    assert metrics.annualized_short_profit == 0.10
    assert metrics.stale_position_days == 2
    assert metrics.max_stale_gross_exposure == 0.40
    assert metrics.average_stale_gross_exposure == 0.10
    assert metrics.trading_days == 200
