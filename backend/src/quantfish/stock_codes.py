from __future__ import annotations

import math
from numbers import Integral, Real
import re
from typing import Any


class StockCodeError(ValueError):
    """Raised when a value cannot represent a Chinese A-share/index code."""


_STRING_CODE_PATTERNS = (
    re.compile(r"(\d{1,6})"),
    re.compile(r"(\d{1,6})\.0+"),
    re.compile(r"(\d{1,6})\.(?:SH|SZ|BJ|XSHG|XSHE|BSE)"),
    re.compile(r"(?:SH|SZ|BJ|XSHG|XSHE|BSE)\.?([0-9]{1,6})"),
)


def normalize_stock_code(value: Any) -> str:
    """Return a six-digit code without silently truncating invalid input."""

    if value is None:
        raise StockCodeError("stock code cannot be missing")
    if isinstance(value, bool):
        raise StockCodeError("stock code cannot be a boolean")
    if isinstance(value, Integral):
        return _format_numeric_code(int(value))
    if isinstance(value, Real):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise StockCodeError("stock code must be finite")
        if not numeric.is_integer():
            raise StockCodeError("numeric stock code must be an integer")
        return _format_numeric_code(int(numeric))

    text = str(value).strip().upper()
    if not text or text in {"NAN", "<NA>", "NONE"}:
        raise StockCodeError("stock code cannot be missing")
    for pattern in _STRING_CODE_PATTERNS:
        matched = pattern.fullmatch(text)
        if matched is not None:
            return matched.group(1).zfill(6)
    raise StockCodeError(
        "stock code must be 1-6 digits or a supported exchange-qualified code"
    )


def _format_numeric_code(value: int) -> str:
    if value < 0 or value > 999_999:
        raise StockCodeError("numeric stock code must be between 0 and 999999")
    return str(value).zfill(6)
