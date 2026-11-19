from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

LeaderboardMetric = Literal["sharpe", "max_drawdown", "calmar"]
OBJECTIVE_LEADERBOARD_METRICS: tuple[LeaderboardMetric, ...] = (
    "sharpe",
    "max_drawdown",
    "calmar",
)


@dataclass(frozen=True)
class ScoringWeights:
    sharpe_weight: float = 45.0
    sharpe_target: float = 2.0
    annual_return_weight: float = 35.0
    annual_return_target: float = 0.30
    drawdown_weight: float = 15.0
    drawdown_limit: float = 0.30
    turnover_weight: float = 5.0
    turnover_limit: float = 3.0
    short_profit_weight: float = 50.0
    short_profit_target: float = 0.30
    minimum_slice_trading_days: int = 1


@dataclass(frozen=True)
class LeaderboardRow:
    rank: int
    id: str
    team_name: str
    status: str
    stale: bool
    eligible: bool
    submitted_at: str
    summary: dict[str, float]
    score: float
    metric: str
    metric_value: float
    badge: str | None


@dataclass(frozen=True)
class ScoreContribution:
    key: str
    label: str
    metric_value: float
    weight: float
    contribution: float


def rank_leaderboard(
    records: Sequence[Mapping[str, Any]],
    *,
    weights: ScoringWeights,
) -> list[LeaderboardRow]:
    sorted_rows = sorted(
        [_to_leaderboard_row(record, weights) for record in records],
        key=_sort_key,
    )
    return _rank_rows(sorted_rows)


def rank_best_per_team_leaderboard(
    records: Sequence[Mapping[str, Any]],
    *,
    weights: ScoringWeights,
) -> list[LeaderboardRow]:
    candidates = sorted(
        [
            (_team_key(record), _to_leaderboard_row(record, weights))
            for record in records
        ],
        key=lambda item: _sort_key(item[1]),
    )
    best_by_team: dict[str, LeaderboardRow] = {}
    for team_key, row in candidates:
        best_by_team.setdefault(team_key, row)
    return _rank_rows(best_by_team.values())


def rank_objective_leaderboard(
    records: Sequence[Mapping[str, Any]],
    *,
    metric: LeaderboardMetric,
) -> list[LeaderboardRow]:
    sorted_rows = sorted(
        [_to_objective_leaderboard_row(record, metric) for record in records],
        key=lambda row: _objective_sort_key(row, metric),
    )
    return _rank_rows(sorted_rows)


def rank_best_per_team_objective_leaderboard(
    records: Sequence[Mapping[str, Any]],
    *,
    metric: LeaderboardMetric,
) -> list[LeaderboardRow]:
    candidates = sorted(
        [
            (_team_key(record), _to_objective_leaderboard_row(record, metric))
            for record in records
        ],
        key=lambda item: _objective_sort_key(item[1], metric),
    )
    best_by_team: dict[str, LeaderboardRow] = {}
    for team_key, row in candidates:
        best_by_team.setdefault(team_key, row)
    return _rank_rows(best_by_team.values())


def _rank_rows(rows: Sequence[LeaderboardRow]) -> list[LeaderboardRow]:
    return [
        LeaderboardRow(
            rank=index + 1,
            id=row.id,
            team_name=row.team_name,
            status=row.status,
            stale=row.stale,
            eligible=row.eligible,
            submitted_at=row.submitted_at,
            summary=row.summary,
            score=row.score,
            metric=row.metric,
            metric_value=row.metric_value,
            badge=_badge_for_rank(index + 1) if row.eligible else None,
        )
        for index, row in enumerate(rows)
    ]


def _to_leaderboard_row(
    record: Mapping[str, Any], weights: ScoringWeights
) -> LeaderboardRow:
    status = str(record.get("status", "unknown"))
    stale = bool(record.get("stale", False))
    summary = _summary_as_floats(record.get("summary", {}))
    eligible = status == "completed" and not stale and _meets_minimum_days(
        summary,
        weights.minimum_slice_trading_days,
    )
    score = calculate_leaderboard_score(summary, weights)
    return LeaderboardRow(
        rank=0,
        id=str(record["id"]),
        team_name=str(record.get("team_name", "Unknown Team")),
        status=status,
        stale=stale,
        eligible=eligible,
        submitted_at=str(record.get("submitted_at", "")),
        summary=summary,
        score=score,
        metric="score",
        metric_value=score,
        badge=None,
    )


def _to_objective_leaderboard_row(
    record: Mapping[str, Any],
    metric: LeaderboardMetric,
) -> LeaderboardRow:
    status = str(record.get("status", "unknown"))
    stale = bool(record.get("stale", False))
    summary = _summary_as_floats(record.get("summary", {}))
    metric_value = _objective_metric_value(summary, metric)
    eligible = (
        status == "completed"
        and not stale
        and metric_value is not None
        and _meets_minimum_days(summary, 1)
    )
    display_value = metric_value if metric_value is not None else 0.0
    return LeaderboardRow(
        rank=0,
        id=str(record["id"]),
        team_name=str(record.get("team_name", "Unknown Team")),
        status=status,
        stale=stale,
        eligible=eligible,
        submitted_at=str(record.get("submitted_at", "")),
        summary=summary,
        score=display_value,
        metric=metric,
        metric_value=display_value,
        badge=None,
    )


def _summary_as_floats(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        return {}
    values: dict[str, float] = {}
    for key, value in raw.items():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values[str(key)] = number
    return values


def calculate_leaderboard_score(
    summary: Mapping[str, Any],
    weights: ScoringWeights,
) -> float:
    return sum(
        contribution.contribution
        for contribution in score_contributions(summary, weights)
    )


def score_contributions(
    summary: Mapping[str, Any],
    weights: ScoringWeights,
) -> list[ScoreContribution]:
    values = _summary_as_floats(summary)
    sharpe = values.get("sharpe", 0.0)
    annual_return = values.get("annual_return", 0.0)
    max_drawdown = values.get("max_drawdown", 0.0)
    turnover = values.get("average_turnover", 0.0)
    annualized_short_profit = values.get("annualized_short_profit", 0.0)
    contribution_inputs = [
        (
            "sharpe",
            "Sharpe",
            sharpe,
            weights.sharpe_weight,
            weights.sharpe_weight
            * _clamp(_safe_ratio(sharpe, weights.sharpe_target), -1.0, 1.0),
        ),
        (
            "annual_return",
            "Annual return",
            annual_return,
            weights.annual_return_weight,
            weights.annual_return_weight
            * _clamp(
                _safe_ratio(annual_return, weights.annual_return_target),
                -1.0,
                1.0,
            ),
        ),
        (
            "drawdown_penalty",
            "Drawdown penalty",
            max_drawdown,
            weights.drawdown_weight,
            -weights.drawdown_weight
            * _clamp(_safe_ratio(abs(max_drawdown), weights.drawdown_limit), 0.0, 1.0),
        ),
        (
            "turnover_penalty",
            "Turnover penalty",
            turnover,
            weights.turnover_weight,
            -weights.turnover_weight
            * _clamp(_safe_ratio(turnover, weights.turnover_limit), 0.0, 1.0),
        ),
        (
            "short_profit_penalty",
            "Short profit penalty",
            annualized_short_profit,
            weights.short_profit_weight,
            -weights.short_profit_weight
            * _clamp(
                _safe_ratio(annualized_short_profit, weights.short_profit_target),
                0.0,
                1.0,
            ),
        ),
    ]
    return [
        ScoreContribution(
            key=key,
            label=label,
            metric_value=metric_value,
            weight=weight,
            contribution=contribution,
        )
        for key, label, metric_value, weight, contribution in contribution_inputs
    ]


def score_calculation_text(
    summary: Mapping[str, Any],
    weights: ScoringWeights,
) -> str:
    values = _summary_as_floats(summary)
    sharpe = values.get("sharpe", 0.0)
    annual_return = values.get("annual_return", 0.0)
    max_drawdown = values.get("max_drawdown", 0.0)
    average_turnover = values.get("average_turnover", 0.0)
    annualized_short_profit = values.get("annualized_short_profit", 0.0)
    score = calculate_leaderboard_score(values, weights)
    return (
        "Score = "
        f"clamp({_fmt(sharpe)} / {_fmt(weights.sharpe_target)}, -1, 1) "
        f"× {_fmt(weights.sharpe_weight)} "
        f"+ clamp({_fmt(annual_return)} / {_fmt(weights.annual_return_target)}, -1, 1) "
        f"× {_fmt(weights.annual_return_weight)} "
        f"- clamp(abs({_fmt(max_drawdown)}) / {_fmt(weights.drawdown_limit)}, 0, 1) "
        f"× {_fmt(weights.drawdown_weight)} "
        f"- clamp({_fmt(average_turnover)} / {_fmt(weights.turnover_limit)}, 0, 1) "
        f"× {_fmt(weights.turnover_weight)} "
        f"- clamp({_fmt(annualized_short_profit)} / {_fmt(weights.short_profit_target)}, 0, 1) "
        f"× {_fmt(weights.short_profit_weight)} "
        f"= {_fmt(score)}"
    )


def _meets_minimum_days(summary: Mapping[str, float], minimum_days: int) -> bool:
    if "trading_days" not in summary:
        return True
    return summary.get("trading_days", 0.0) >= minimum_days


def _safe_ratio(value: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return value / denominator


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _team_key(record: Mapping[str, Any]) -> str:
    team_id = str(record.get("team_id", "")).strip()
    if team_id:
        return f"id:{team_id}"
    return f"name:{str(record.get('team_name', 'Unknown Team')).strip().casefold()}"


def _sort_key(row: LeaderboardRow) -> tuple[int, float, float, float, str]:
    if not row.eligible:
        return (1, 0.0, 0.0, 0.0, row.submitted_at)
    return (
        0,
        -row.score,
        -row.summary.get("sharpe", 0.0),
        abs(row.summary.get("max_drawdown", 0.0)),
        row.submitted_at,
    )


def _objective_metric_value(
    summary: Mapping[str, float],
    metric: LeaderboardMetric,
) -> float | None:
    if metric == "calmar":
        if "calmar" in summary:
            return summary["calmar"]
        annual_return = summary.get("annual_return")
        max_drawdown = summary.get("max_drawdown")
        if annual_return is None or max_drawdown is None:
            return None
        drawdown = abs(max_drawdown)
        return annual_return / drawdown if drawdown > 0 else None
    return summary.get(metric)


def _objective_sort_key(
    row: LeaderboardRow,
    metric: LeaderboardMetric,
) -> tuple[int, float, float, str]:
    if not row.eligible:
        return (1, 0.0, 0.0, row.submitted_at)
    if metric == "max_drawdown":
        return (
            0,
            abs(row.metric_value),
            -row.summary.get("sharpe", 0.0),
            row.submitted_at,
        )
    return (
        0,
        -row.metric_value,
        abs(row.summary.get("max_drawdown", 0.0)),
        row.submitted_at,
    )


def _badge_for_rank(rank: int) -> str | None:
    return {1: "gold", 2: "silver", 3: "bronze"}.get(rank)


def _fmt(value: float) -> str:
    return f"{value:.3f}"
