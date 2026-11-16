from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd


MARKET_TYPE_LABELS: dict[int, str] = {
    1: "上证A股市场(不包含科创板)",
    2: "上证B股市场",
    4: "深证A股市场(不包含创业板)",
    8: "深证B股市场",
    16: "创业板",
    32: "科创板",
    64: "北证A股市场",
}
VALID_MARKET_TYPES = frozenset(MARKET_TYPE_LABELS)
A_SHARE_MARKET_TYPES = (1, 4, 16, 32, 64)
DEFAULT_ALLOWED_MARKET_TYPES = A_SHARE_MARKET_TYPES

_MARKET_TYPE_COLUMN_KEYS = ("markettype", "market_type")


def normalize_allowed_market_types(value: Any) -> tuple[int, ...]:
    if value is None:
        return DEFAULT_ALLOWED_MARKET_TYPES
    if isinstance(value, str):
        raw_items: Iterable[Any] = [item.strip() for item in value.split(",")]
    elif isinstance(value, int) and not isinstance(value, bool):
        raw_items = [value]
    else:
        raw_items = value

    allowed: list[int] = []
    seen: set[int] = set()
    for item in raw_items:
        market_type = _coerce_market_type(item)
        if market_type in seen:
            continue
        if market_type not in VALID_MARKET_TYPES:
            raise ValueError(f"unsupported market type: {market_type}")
        allowed.append(market_type)
        seen.add(market_type)
    if not allowed:
        raise ValueError("allowed_market_types cannot be empty")
    return tuple(allowed)


def market_type_column(columns: Iterable[Any]) -> str | None:
    folded = {str(column).lower(): str(column) for column in columns}
    for key in _MARKET_TYPE_COLUMN_KEYS:
        if key in folded:
            return folded[key]
    return None


def filter_by_market_types(
    frame: pd.DataFrame,
    allowed_market_types: tuple[int, ...] | list[int] | None,
) -> pd.DataFrame:
    if allowed_market_types is None:
        return frame
    column = market_type_column(frame.columns)
    if column is None:
        return frame
    allowed = set(normalize_allowed_market_types(allowed_market_types))
    values = pd.to_numeric(frame[column], errors="coerce")
    return frame[values.isin(allowed)].copy()


def market_type_candidate_columns() -> tuple[str, ...]:
    return ("markettype", "Markettype", "MarketType", "market_type")


def _coerce_market_type(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"market type must be an integer tag, got {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"market type must be an integer tag, got {value!r}")
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("market type cannot be blank")
        return int(stripped)
    raise ValueError(f"market type must be an integer tag, got {value!r}")
