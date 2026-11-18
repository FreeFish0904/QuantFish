import math

import pandas as pd
import pytest

from quantfish.backtest.excess import (
    MIN_EXCESS_OBSERVATIONS,
    calculate_benchmark_relative_metrics,
)

STRATEGY = [0.03, -0.02, 0.05, -0.05, 0.01]
BENCHMARK = [0.01, -0.01, 0.02, -0.02, 0.00]


def _daily(returns: list[float], start: str = "2023-01-03") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(returns), freq="D"),
            "portfolio_return": returns,
        }
    )


def _benchmark(returns: list[float], start: str = "2023-01-03") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range(start, periods=len(returns), freq="D"),
            "return": returns,
        }
    )


def test_benchmark_relative_metrics_match_hand_calculated_sample() -> None:
    metrics = calculate_benchmark_relative_metrics(
        _daily(STRATEGY), _benchmark(BENCHMARK), min_observations=5
    )

    excess = [s - b for s, b in zip(STRATEGY, BENCHMARK, strict=True)]
    excess_variance = sum((value - 0.004) ** 2 for value in excess) / 4
    excess_volatility = math.sqrt(excess_variance) * math.sqrt(252)
    benchmark_growth = 1.01 * 0.99 * 1.02 * 0.98 * 1.00
    strategy_growth = 1.03 * 0.98 * 1.05 * 0.95 * 1.01
    relative = strategy_growth / benchmark_growth - 1.0

    assert metrics.observations == 5
    assert metrics.start == "2023-01-03"
    assert metrics.end == "2023-01-07"
    assert metrics.strategy_total_return == pytest.approx(0.02)
    assert metrics.strategy_annual_return == pytest.approx(0.02 * 252 / 5)
    assert metrics.benchmark_total_return == pytest.approx(0.0)
    assert metrics.benchmark_annual_return == pytest.approx(0.0)
    assert metrics.benchmark_cagr == pytest.approx(benchmark_growth ** (252 / 5) - 1.0)
    assert metrics.excess_total_return == pytest.approx(0.02)
    assert metrics.excess_total_return + metrics.benchmark_total_return == pytest.approx(
        metrics.strategy_total_return
    )
    assert metrics.excess_annual_return == pytest.approx(0.02 * 252 / 5)
    assert metrics.excess_compounded_return == pytest.approx(relative)
    assert metrics.excess_cagr == pytest.approx((1.0 + relative) ** (252 / 5) - 1.0)
    assert metrics.excess_max_drawdown == pytest.approx(1.0 - 1.01 / 1.04)
    assert metrics.excess_win_rate == pytest.approx(3 / 5)
    assert metrics.excess_volatility == pytest.approx(excess_volatility)
    assert metrics.excess_information_ratio == pytest.approx(
        (0.02 * 252 / 5) / excess_volatility
    )
    assert metrics.excess_beta == pytest.approx(2.5)

    fields = metrics.summary_fields()
    assert fields["excess_observations"] == 5
    assert fields["excess_total_return"] == pytest.approx(0.02)
    assert fields["strategy_annual_return"] == pytest.approx(0.02 * 252 / 5)
    assert set(fields) == {
        "strategy_total_return",
        "strategy_annual_return",
        "benchmark_total_return",
        "benchmark_annual_return",
        "benchmark_cagr",
        "excess_total_return",
        "excess_annual_return",
        "excess_compounded_return",
        "excess_cagr",
        "excess_max_drawdown",
        "excess_win_rate",
        "excess_volatility",
        "excess_information_ratio",
        "excess_beta",
        "excess_observations",
    }


def test_benchmark_relative_metrics_require_benchmark_observations() -> None:
    with pytest.raises(ValueError, match="require benchmark observations"):
        calculate_benchmark_relative_metrics(
            _daily(STRATEGY), pd.DataFrame(columns=["date", "return"])
        )


def test_benchmark_relative_metrics_require_module_columns() -> None:
    with pytest.raises(ValueError, match="date and portfolio_return"):
        calculate_benchmark_relative_metrics(
            pd.DataFrame([{"date": "2023-01-03"}]), _benchmark(BENCHMARK)
        )
    with pytest.raises(ValueError, match="benchmark date and return"):
        calculate_benchmark_relative_metrics(
            _daily(STRATEGY), pd.DataFrame([{"date": "2023-01-03"}])
        )


def test_benchmark_relative_metrics_require_minimum_aligned_observations() -> None:
    with pytest.raises(ValueError, match=f"at least {MIN_EXCESS_OBSERVATIONS}"):
        calculate_benchmark_relative_metrics(_daily(STRATEGY), _benchmark(BENCHMARK))


def test_benchmark_relative_metrics_reject_non_positive_min_observations() -> None:
    with pytest.raises(ValueError, match="min_observations must be positive"):
        calculate_benchmark_relative_metrics(
            _daily(STRATEGY), _benchmark(BENCHMARK), min_observations=0
        )


def test_benchmark_relative_metrics_use_only_overlapping_dates() -> None:
    daily = _daily([0.01] * 30)
    benchmark = _benchmark([0.0] * 20, start="2023-01-13")

    metrics = calculate_benchmark_relative_metrics(daily, benchmark)

    assert metrics.observations == 20
    assert metrics.start == "2023-01-13"
    assert metrics.end == "2023-02-01"
    assert metrics.excess_total_return == pytest.approx(0.2)
    assert metrics.benchmark_total_return == pytest.approx(0.0)
    assert metrics.excess_win_rate == pytest.approx(1.0)


def test_benchmark_relative_metrics_degrade_when_benchmark_has_no_variance() -> None:
    metrics = calculate_benchmark_relative_metrics(
        _daily([0.01, -0.01] * 10), _benchmark([0.001] * 20)
    )

    assert metrics.observations == 20
    assert metrics.excess_beta is None
    assert metrics.excess_volatility > 0
    assert metrics.excess_information_ratio is not None
    assert metrics.benchmark_cagr == pytest.approx(1.001**252 - 1.0)


def test_benchmark_relative_metrics_drop_days_without_benchmark_return() -> None:
    benchmark = _benchmark(BENCHMARK)
    benchmark.loc[len(benchmark)] = {"date": pd.Timestamp("2023-01-20"), "return": None}

    metrics = calculate_benchmark_relative_metrics(
        _daily(STRATEGY), benchmark, min_observations=5
    )

    assert metrics.observations == 5
    assert metrics.excess_beta == pytest.approx(2.5)
