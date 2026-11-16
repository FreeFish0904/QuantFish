from __future__ import annotations

import math
from typing import Any, Mapping

from quantfish.submissions.models import SubmissionStatus


REQUIRED_ZERO_METRICS: tuple[str, ...] = (
    "total_return",
    "annual_return",
    "sharpe",
    "max_drawdown",
)

OPTIONAL_ZERO_METRICS: tuple[str, ...] = (
    "average_turnover",
    "average_short_exposure",
    "long_total_return",
    "short_total_return",
    "annualized_short_profit",
    "calmar",
    "win_rate",
    "average_year_return",
    "worst_year_return",
    "all_return",
    "fitness",
    "average_long_exposure",
    "average_gross_exposure",
    "average_net_exposure",
    "average_position_count",
)


def is_zero_result_stale(
    submission: Any,
    summary: Mapping[str, Any] | None = None,
) -> bool:
    status = getattr(submission, "status", None)
    status_value = getattr(status, "value", status)
    if status_value != SubmissionStatus.COMPLETED.value:
        return False
    return is_zero_result_summary(summary or _metrics_summary(submission))


def is_zero_result_summary(summary: Mapping[str, Any] | None) -> bool:
    if not isinstance(summary, Mapping):
        return False
    for key in REQUIRED_ZERO_METRICS:
        value = _finite_float(summary.get(key))
        if value is None or value != 0.0:
            return False
    for key in OPTIONAL_ZERO_METRICS:
        if key not in summary or summary.get(key) is None:
            continue
        value = _finite_float(summary.get(key))
        if value is None or value != 0.0:
            return False
    return True


def _metrics_summary(submission: Any) -> Mapping[str, Any] | None:
    metrics = getattr(submission, "metrics", None)
    if metrics is None:
        return None
    to_dict = getattr(metrics, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(metrics, Mapping):
        return metrics
    return None


def _finite_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None
