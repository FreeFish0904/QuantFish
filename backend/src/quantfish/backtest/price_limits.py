from __future__ import annotations

from datetime import date, datetime
from typing import Any

import math

import pandas as pd


DEFAULT_PRICE_LIMIT_THRESHOLD = 0.0995
CHINEXT_REFORM_DATE = date(2020, 8, 24)


def fallback_price_limit_threshold(
    market_type: Any,
    trading_date: date | datetime | pd.Timestamp,
    *,
    default: float = DEFAULT_PRICE_LIMIT_THRESHOLD,
) -> float:
    """Return a conservative fallback when daily limit fields are unavailable."""
    try:
        normalized_market_type = int(float(market_type))
    except (TypeError, ValueError, OverflowError):
        return float(default)
    if normalized_market_type == 16:
        normalized_date = pd.Timestamp(trading_date).date()
        return 0.1995 if normalized_date >= CHINEXT_REFORM_DATE else 0.0995
    if normalized_market_type == 32:
        return 0.1995
    if normalized_market_type == 64:
        return 0.2995
    return float(default) if math.isfinite(float(default)) else DEFAULT_PRICE_LIMIT_THRESHOLD
