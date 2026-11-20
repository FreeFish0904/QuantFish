import pytest

from quantfish.leaderboard.ranking import (
    ScoringWeights,
    calculate_leaderboard_score,
    rank_best_per_team_leaderboard,
    rank_best_per_team_objective_leaderboard,
    rank_leaderboard,
    rank_objective_leaderboard,
    score_contributions,
)


def test_rank_leaderboard_prioritizes_eligible_score_then_risk() -> None:
    rows = [
        {
            "id": "slow",
            "team_name": "Slow Capital",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:02:00Z",
            "summary": {"sharpe": 1.2, "total_return": 0.20, "max_drawdown": -0.03},
        },
        {
            "id": "fast",
            "team_name": "Fast Alpha",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:01:00Z",
            "summary": {"sharpe": 1.4, "total_return": 0.16, "max_drawdown": -0.08},
        },
        {
            "id": "stale",
            "team_name": "Old Edge",
            "status": "completed",
            "stale": True,
            "submitted_at": "2026-06-19T09:00:00Z",
            "summary": {"sharpe": 9.0, "total_return": 3.0, "max_drawdown": -0.01},
        },
    ]

    ranked = rank_leaderboard(rows, weights=ScoringWeights())

    assert [row.id for row in ranked] == ["fast", "slow", "stale"]
    assert [row.rank for row in ranked] == [1, 2, 3]
    assert ranked[0].badge == "gold"
    assert ranked[1].badge == "silver"
    assert ranked[2].stale is True
    assert ranked[2].badge is None


def test_rank_leaderboard_uses_drawdown_as_positive_penalty() -> None:
    weights = ScoringWeights(
        sharpe_weight=0.0,
        annual_return_weight=0.0,
        drawdown_weight=1.0,
        turnover_weight=0.0,
        short_profit_weight=0.0,
    )
    rows = [
        {
            "id": "deep",
            "team_name": "Deep Drawdown",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {"max_drawdown": -0.25},
        },
        {
            "id": "shallow",
            "team_name": "Shallow Drawdown",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:01:00Z",
            "summary": {"max_drawdown": -0.05},
        },
    ]

    ranked = rank_leaderboard(rows, weights=weights)

    assert [row.id for row in ranked] == ["shallow", "deep"]
    assert ranked[0].score > ranked[1].score


def test_rank_objective_leaderboard_orders_by_metric_without_weighted_score() -> None:
    rows = [
        {
            "id": "highest-sharpe",
            "team_name": "Sharpe Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {"sharpe": 3.0, "max_drawdown": -0.20, "calmar": 1.5},
        },
        {
            "id": "smallest-drawdown",
            "team_name": "Risk Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:01:00Z",
            "summary": {"sharpe": 1.0, "max_drawdown": -0.02, "calmar": 3.0},
        },
        {
            "id": "highest-calmar",
            "team_name": "Calmar Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:02:00Z",
            "summary": {"sharpe": 2.0, "max_drawdown": -0.08, "calmar": 4.5},
        },
    ]

    assert [row.id for row in rank_objective_leaderboard(rows, metric="sharpe")] == [
        "highest-sharpe",
        "highest-calmar",
        "smallest-drawdown",
    ]
    assert [row.id for row in rank_objective_leaderboard(rows, metric="max_drawdown")] == [
        "smallest-drawdown",
        "highest-calmar",
        "highest-sharpe",
    ]
    calmar_ranked = rank_objective_leaderboard(rows, metric="calmar")

    assert [row.id for row in calmar_ranked] == [
        "highest-calmar",
        "smallest-drawdown",
        "highest-sharpe",
    ]
    assert calmar_ranked[0].score == pytest.approx(4.5)
    assert calmar_ranked[0].metric == "calmar"
    assert calmar_ranked[0].metric_value == pytest.approx(4.5)


def test_rank_objective_leaderboard_excludes_missing_metric_from_medals() -> None:
    rows = [
        {
            "id": "missing-calmar",
            "team_name": "Missing",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {"sharpe": 9.0},
        },
        {
            "id": "has-calmar",
            "team_name": "Present",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:01:00Z",
            "summary": {"calmar": 1.2},
        },
    ]

    ranked = rank_objective_leaderboard(rows, metric="calmar")

    assert [row.id for row in ranked] == ["has-calmar", "missing-calmar"]
    assert ranked[0].eligible is True
    assert ranked[0].badge == "gold"
    assert ranked[1].eligible is False
    assert ranked[1].badge is None


def test_rank_objective_leaderboard_excludes_zero_drawdown_calmar() -> None:
    rows = [
        {
            "id": "smooth",
            "team_name": "Smooth",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {
                "annual_return": 0.20,
                "max_drawdown": 0.0,
                "calmar": None,
            },
        },
        {
            "id": "has-calmar",
            "team_name": "Present",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:01:00Z",
            "summary": {"calmar": 1.2},
        },
    ]

    ranked = rank_objective_leaderboard(rows, metric="calmar")

    assert [row.id for row in ranked] == ["has-calmar", "smooth"]
    assert ranked[0].eligible is True
    assert ranked[1].eligible is False
    assert ranked[1].badge is None


def test_calculate_leaderboard_score_is_sum_of_score_contributions() -> None:
    weights = ScoringWeights(
        sharpe_weight=10.0,
        sharpe_target=2.0,
        annual_return_weight=20.0,
        annual_return_target=0.4,
        drawdown_weight=30.0,
        drawdown_limit=0.2,
        turnover_weight=40.0,
        turnover_limit=1.0,
        short_profit_weight=50.0,
        short_profit_target=0.25,
    )
    summary = {
        "total_return": 0.20,
        "sharpe": 1.50,
        "annual_return": 0.20,
        "max_drawdown": -0.08,
        "average_turnover": 0.40,
        "annualized_short_profit": 0.10,
    }
    ranked = rank_leaderboard(
        [
            {
                "id": "alpha",
                "team_name": "Alpha",
                "status": "completed",
                "stale": False,
                "submitted_at": "2026-06-19T10:00:00Z",
                "summary": summary,
            }
        ],
        weights=weights,
    )
    contributions = score_contributions(summary, weights)

    expected = sum(item.contribution for item in contributions)
    assert calculate_leaderboard_score(summary, weights) == pytest.approx(expected)
    assert ranked[0].score == pytest.approx(expected)
    assert [item.key for item in contributions] == [
        "sharpe",
        "annual_return",
        "drawdown_penalty",
        "turnover_penalty",
        "short_profit_penalty",
    ]


def test_score_contributions_include_normalized_risk_and_short_profit_penalties() -> None:
    weights = ScoringWeights(
        sharpe_weight=0.0,
        annual_return_weight=0.0,
        drawdown_weight=30.0,
        drawdown_limit=0.3,
        turnover_weight=5.0,
        turnover_limit=2.0,
        short_profit_weight=50.0,
        short_profit_target=0.25,
    )

    contributions = {
        item.key: item
        for item in score_contributions(
            {
                "max_drawdown": -0.15,
                "average_turnover": 1.0,
                "annualized_short_profit": 0.10,
            },
            weights,
        )
    }

    assert contributions["drawdown_penalty"].metric_value == pytest.approx(-0.15)
    assert contributions["drawdown_penalty"].weight == pytest.approx(30.0)
    assert contributions["drawdown_penalty"].contribution == pytest.approx(-15.0)
    assert contributions["turnover_penalty"].metric_value == pytest.approx(1.0)
    assert contributions["turnover_penalty"].weight == pytest.approx(5.0)
    assert contributions["turnover_penalty"].contribution == pytest.approx(-2.5)
    assert contributions["short_profit_penalty"].metric_value == pytest.approx(0.10)
    assert contributions["short_profit_penalty"].weight == pytest.approx(50.0)
    assert contributions["short_profit_penalty"].contribution == pytest.approx(-20.0)


def test_short_profit_penalty_ignores_short_exposure_when_short_leg_loses_money() -> None:
    no_short_profit = {
        "sharpe": 1.0,
        "annual_return": 0.12,
        "max_drawdown": 0.10,
        "average_turnover": 0.50,
        "average_short_exposure": 0.0,
        "annualized_short_profit": 0.0,
    }
    short_exposure_only = {**no_short_profit, "average_short_exposure": -0.50}

    assert calculate_leaderboard_score(no_short_profit, ScoringWeights()) == pytest.approx(
        calculate_leaderboard_score(
            short_exposure_only,
            ScoringWeights(),
        )
    )


def test_short_profit_penalty_discourages_profitable_short_books() -> None:
    no_short_profit = {
        "sharpe": 1.0,
        "annual_return": 0.12,
        "max_drawdown": 0.10,
        "average_turnover": 0.50,
        "annualized_short_profit": 0.0,
    }
    profitable_short_book = {**no_short_profit, "annualized_short_profit": 0.15}

    assert calculate_leaderboard_score(
        no_short_profit, ScoringWeights()
    ) - calculate_leaderboard_score(
        profitable_short_book,
        ScoringWeights(),
    ) == pytest.approx(25.0)


def test_normalized_score_terms_are_clamped_and_legacy_short_metric_defaults_to_zero() -> None:
    score = calculate_leaderboard_score(
        {
            "sharpe": 99.0,
            "annual_return": 99.0,
            "max_drawdown": 99.0,
            "average_turnover": 99.0,
        },
        ScoringWeights(),
    )

    assert score == pytest.approx(45.0 + 35.0 - 15.0 - 5.0)


def test_rank_leaderboard_sends_failed_and_running_rows_to_bottom() -> None:
    rows = [
        {
            "id": "failed",
            "team_name": "Failed",
            "status": "failed",
            "stale": False,
            "submitted_at": "2026-06-19T09:00:00Z",
            "summary": {"sharpe": 99.0},
        },
        {
            "id": "running",
            "team_name": "Running",
            "status": "running",
            "stale": False,
            "submitted_at": "2026-06-19T09:00:01Z",
            "summary": {"sharpe": 88.0},
        },
        {
            "id": "winner",
            "team_name": "Winner",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T09:02:00Z",
            "summary": {"sharpe": 0.1},
        },
    ]

    ranked = rank_leaderboard(rows, weights=ScoringWeights())

    assert [row.id for row in ranked] == ["winner", "failed", "running"]
    assert ranked[0].eligible is True
    assert ranked[1].eligible is False
    assert ranked[2].eligible is False
    assert ranked[1].badge is None
    assert ranked[2].badge is None


def test_rank_best_per_team_leaderboard_keeps_best_scored_submission() -> None:
    rows = [
        {
            "id": "alpha-old",
            "team_id": "team-alpha",
            "team_name": "Alpha Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T09:00:00Z",
            "summary": {"sharpe": 1.0, "total_return": 0.10, "max_drawdown": -0.04},
        },
        {
            "id": "alpha-best",
            "team_id": "team-alpha",
            "team_name": "Alpha Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {"sharpe": 2.0, "total_return": 0.20, "max_drawdown": -0.05},
        },
        {
            "id": "beta-best",
            "team_id": "team-beta",
            "team_name": "Beta Fund",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T09:30:00Z",
            "summary": {"sharpe": 1.5, "total_return": 0.16, "max_drawdown": -0.03},
        },
    ]

    ranked = rank_best_per_team_leaderboard(rows, weights=ScoringWeights())

    assert [row.id for row in ranked] == ["alpha-best", "beta-best"]
    assert [row.rank for row in ranked] == [1, 2]
    assert [row.badge for row in ranked] == ["gold", "silver"]


def test_rank_best_per_team_objective_leaderboard_picks_best_for_each_metric() -> None:
    rows = [
        {
            "id": "alpha-sharpe",
            "team_id": "team-alpha",
            "team_name": "Alpha Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T09:00:00Z",
            "summary": {"sharpe": 4.0, "max_drawdown": -0.20, "calmar": 1.0},
        },
        {
            "id": "alpha-risk",
            "team_id": "team-alpha",
            "team_name": "Alpha Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {"sharpe": 2.0, "max_drawdown": -0.03, "calmar": 5.0},
        },
        {
            "id": "beta-risk",
            "team_id": "team-beta",
            "team_name": "Beta Desk",
            "status": "completed",
            "stale": False,
            "submitted_at": "2026-06-19T11:00:00Z",
            "summary": {"sharpe": 3.0, "max_drawdown": -0.02, "calmar": 2.0},
        },
    ]

    assert [row.id for row in rank_best_per_team_objective_leaderboard(rows, metric="sharpe")] == [
        "alpha-sharpe",
        "beta-risk",
    ]
    assert [
        row.id for row in rank_best_per_team_objective_leaderboard(rows, metric="max_drawdown")
    ] == ["beta-risk", "alpha-risk"]
    assert [row.id for row in rank_best_per_team_objective_leaderboard(rows, metric="calmar")] == [
        "alpha-risk",
        "beta-risk",
    ]


def test_rank_best_per_team_leaderboard_falls_back_to_team_name() -> None:
    rows = [
        {
            "id": "first",
            "team_name": "Unnamed Team",
            "status": "running",
            "stale": False,
            "submitted_at": "2026-06-19T09:00:00Z",
            "summary": {},
        },
        {
            "id": "second",
            "team_name": "Unnamed Team",
            "status": "failed",
            "stale": False,
            "submitted_at": "2026-06-19T10:00:00Z",
            "summary": {},
        },
        {
            "id": "other",
            "team_name": "Other Team",
            "status": "failed",
            "stale": False,
            "submitted_at": "2026-06-19T11:00:00Z",
            "summary": {},
        },
    ]

    ranked = rank_best_per_team_leaderboard(rows, weights=ScoringWeights())

    assert [row.id for row in ranked] == ["first", "other"]
    assert [row.rank for row in ranked] == [1, 2]
    assert ranked[0].badge is None
