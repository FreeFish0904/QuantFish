from __future__ import annotations

import pandas as pd


def calculate_raw_vwap(trading_value: pd.Series, trading_volume: pd.Series) -> pd.Series:
    volume = pd.to_numeric(trading_volume, errors="coerce")
    value = pd.to_numeric(trading_value, errors="coerce")
    return value / volume.where(volume > 0)


def apply_front_adjustment(raw_price: pd.Series, forward_factor: pd.Series) -> pd.Series:
    price = pd.to_numeric(raw_price, errors="coerce")
    factor = pd.to_numeric(forward_factor, errors="coerce")
    return price * factor
