from __future__ import annotations

from typing import Any

from quantfish.leaderboard.ranking import ScoringWeights


def score_sort_expression(weights: ScoringWeights) -> tuple[str, list[Any]]:
    """Return a SQLite expression matching calculate_leaderboard_score for sorting."""
    values: list[Any] = []

    def metric(name: str) -> str:
        return f"COALESCE(CAST(json_extract(metrics_json, '$.{name}') AS REAL), 0.0)"

    def ratio(expression: str, denominator: float) -> str:
        if denominator == 0:
            return "0.0"
        values.append(float(denominator))
        return f"({expression} / ?)"

    def weighted_clamp(
        *,
        expression: str,
        weight: float,
        denominator: float,
        lower: float,
        upper: float,
        sign: str = "+",
    ) -> str:
        values.append(float(weight))
        ratio_expression = ratio(expression, denominator)
        operator = "-" if sign == "-" else "+"
        return f"{operator} (? * MIN({upper}, MAX({lower}, {ratio_expression})))"

    score_sql = " ".join(
        [
            weighted_clamp(
                expression=metric("sharpe"),
                weight=weights.sharpe_weight,
                denominator=weights.sharpe_target,
                lower=-1.0,
                upper=1.0,
            ).lstrip("+ "),
            weighted_clamp(
                expression=metric("annual_return"),
                weight=weights.annual_return_weight,
                denominator=weights.annual_return_target,
                lower=-1.0,
                upper=1.0,
            ),
            weighted_clamp(
                expression=f"ABS({metric('max_drawdown')})",
                weight=weights.drawdown_weight,
                denominator=weights.drawdown_limit,
                lower=0.0,
                upper=1.0,
                sign="-",
            ),
            weighted_clamp(
                expression=metric("average_turnover"),
                weight=weights.turnover_weight,
                denominator=weights.turnover_limit,
                lower=0.0,
                upper=1.0,
                sign="-",
            ),
            weighted_clamp(
                expression=metric("annualized_short_profit"),
                weight=weights.short_profit_weight,
                denominator=weights.short_profit_target,
                lower=0.0,
                upper=1.0,
                sign="-",
            ),
        ]
    )
    return f"CASE WHEN metrics_json IS NULL THEN NULL ELSE ({score_sql}) END", values
