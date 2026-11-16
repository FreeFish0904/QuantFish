from quantfish.submissions.models import (
    ScoreFingerprints,
    Submission,
    SubmissionMetrics,
    SubmissionStatus,
)
from quantfish.submissions.result_staleness import is_zero_result_stale


def test_completed_zero_performance_metrics_with_trading_days_is_stale() -> None:
    submission = _submission(
        status=SubmissionStatus.COMPLETED,
        metrics=SubmissionMetrics(
            total_return=0.0,
            annual_return=0.0,
            average_year_return=0.0,
            worst_year_return=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            average_turnover=0.0,
            average_short_exposure=0.0,
            short_total_return=0.0,
            annualized_short_profit=0.0,
            calmar=0.0,
            win_rate=0.0,
            trading_days=3159,
        ),
    )

    assert is_zero_result_stale(submission) is True


def test_nonzero_performance_or_activity_metric_is_not_zero_result_stale() -> None:
    submission = _submission(
        status=SubmissionStatus.COMPLETED,
        metrics=SubmissionMetrics(
            total_return=0.0,
            annual_return=0.0,
            average_year_return=0.0,
            worst_year_return=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            average_turnover=0.25,
            average_short_exposure=0.0,
            short_total_return=0.0,
            annualized_short_profit=0.0,
            calmar=0.0,
            win_rate=0.0,
            trading_days=3159,
        ),
    )

    assert is_zero_result_stale(submission) is False


def test_missing_required_zero_metric_is_not_zero_result_stale() -> None:
    submission = _submission(
        status=SubmissionStatus.COMPLETED,
        metrics=SubmissionMetrics(
            total_return=0.0,
            annual_return=0.0,
            sharpe=0.0,
            max_drawdown=None,
            average_turnover=0.0,
            trading_days=3159,
        ),
    )

    assert is_zero_result_stale(submission) is False


def test_non_completed_submission_is_not_zero_result_stale() -> None:
    submission = _submission(
        status=SubmissionStatus.FAILED,
        metrics=SubmissionMetrics(
            total_return=0.0,
            annual_return=0.0,
            sharpe=0.0,
            max_drawdown=0.0,
            average_turnover=0.0,
            trading_days=3159,
        ),
    )

    assert is_zero_result_stale(submission) is False


def _submission(
    *,
    status: SubmissionStatus,
    metrics: SubmissionMetrics | None,
) -> Submission:
    return Submission(
        submission_id="sub-zero",
        team_id="team-zero",
        status=status,
        strategy_path="/tmp/strategy.py",
        report_dir="/tmp/report",
        fingerprints=ScoreFingerprints(
            config_sha256="config",
            hidden_catalog_sha256="catalog",
            strategy_sha256="strategy",
            engine_version="engine",
        ),
        original_filename="strategy.py",
        metrics=metrics,
    )
