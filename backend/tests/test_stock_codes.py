from __future__ import annotations

import math

import pytest

from quantfish.stock_codes import StockCodeError, normalize_stock_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1, "000001"),
        (1.0, "000001"),
        ("1", "000001"),
        ("000001.0", "000001"),
        ("000001.SZ", "000001"),
        ("600000.XSHG", "600000"),
        ("BJ.430047", "430047"),
        ("bse430047", "430047"),
    ],
)
def test_normalize_stock_code_accepts_supported_source_formats(
    raw: object,
    expected: str,
) -> None:
    assert normalize_stock_code(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [None, math.nan, True, -1, 1_000_000, 1.5, "", "000001.US", "prefix000001"],
)
def test_normalize_stock_code_rejects_invalid_values_without_truncating(
    raw: object,
) -> None:
    with pytest.raises(StockCodeError):
        normalize_stock_code(raw)
