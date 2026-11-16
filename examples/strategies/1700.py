"""
short-return_OC_strategy.py — #1: Asymmetric K exponents.
Overbought (dev > 0): reversal → short with K_POS.
Oversold (dev < 0): momentum → short with K_NEG.
Different optimal exponents for each regime.
"""
import pandas as pd
import numpy as np

K_POS = 32   # overbought reversal
K_NEG = 40   # oversold momentum (tune: 16, 24, 32, 40, 48)


def generate_signals(data, date):
    today = data.current(
        "stock.daily_returns",
        columns=["stkcd", "clsprc", "dnvaltrd", "dnshrtrd"],
        numeric_columns=["clsprc", "dnvaltrd", "dnshrtrd"],
    )
    if today is None or len(today) == 0:
        return pd.Series(dtype="float64")

    cls = today["clsprc"].values
    val = today["dnvaltrd"].values
    shr = today["dnshrtrd"].values

    vwap = val / np.where(shr > 0, shr, np.nan)
    dev = (cls - vwap) / np.where(np.abs(vwap) > 1e-8, vwap, np.nan)
    dev = np.where(np.isfinite(dev), dev, 0.0)

    pos = dev > 0
    score = np.where(
        pos,
        -(dev ** K_POS),
        -((-dev) ** K_NEG),
    )

    return pd.Series(score, index=today["stkcd"].values)